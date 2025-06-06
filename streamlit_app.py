import streamlit as st
import pandas as pd
from pandas import ExcelWriter
from datetime import datetime, timedelta
import os
import json
import re
from PIL import Image
from streamlit_sortables import sort_items

import io, base64
from github import Github

# Initialize GitHub client using Secret token
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo("BBhyeon/DAN_scheaduler")

def commit_batch_to_github(username, batch_id, local_path):
    repo_path = f"batches/{username}/batch_{batch_id}.xlsx"
    with open(local_path, "rb") as f:
        data_bytes = f.read()
    data_b64 = base64.b64encode(data_bytes).decode()
    try:
        existing = repo.get_contents(repo_path, ref="main")
        repo.update_file(
            path=repo_path,
            message=f"Update batch {batch_id} for {username}",
            content=data_b64,
            sha=existing.sha,
            branch="main"
        )
    except:
        repo.create_file(
            path=repo_path,
            message=f"Add batch {batch_id} for {username}",
            content=data_b64,
            branch="main"
        )

def fetch_user_batches(username):
    prefix = f"batches/{username}/"
    out = []
    try:
        contents = repo.get_contents(prefix, ref="main")
        for file in contents:
            if file.name.endswith(".xlsx"):
                data_bytes = base64.b64decode(file.content)
                out.append((file.name, io.BytesIO(data_bytes)))
    except:
        pass
    return out

st.set_page_config(page_title="DAC_manager_v11", layout="wide")

# Initialize session state flags if not present
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "show_create" not in st.session_state:
    st.session_state["show_create"] = False

# ---------------------- CREDENTIALS FILE ----------------------
CRED_FILE = "credentials.json"
if os.path.exists(CRED_FILE):
    with open(CRED_FILE, "r") as f:
        credentials = json.load(f)
else:
    credentials = {}
    with open(CRED_FILE, "w") as f:
        json.dump(credentials, f)

# ---------------------- TOP-BAR LOGIN & ACCOUNT CREATION ----------------------
# Credentials file path
CRED_FILE = "credentials.json"

# Restore login from URL params if present
params = st.query_params
if "user" in params and params["user"]:
    param_user = params["user"][0]
    try:
        with open(CRED_FILE, "r") as f:
            all_creds = json.load(f)
    except:
        all_creds = {}
    if param_user in all_creds:
        st.session_state["logged_in"] = True
        st.session_state["username"] = param_user
        USER_BATCH_DIR = os.path.join("batches", param_user)
        os.makedirs(USER_BATCH_DIR, exist_ok=True)

# Load or initialize credentials
if os.path.exists(CRED_FILE):
    with open(CRED_FILE, "r") as f:
        credentials = json.load(f)
else:
    credentials = {}
    with open(CRED_FILE, "w") as f:
        json.dump(credentials, f)

top_bar = st.container()
with top_bar:
    cols = st.columns([2, 2, 2, 2, 1])
    # First column: Welcome message or app title
    if not st.session_state.get("logged_in", False):
        cols[0].markdown("### DAC Manager")
    else:
        cols[0].markdown(f"### Welcome, {st.session_state['username']}!")

    # Second and third columns: Hide entirely when logged in
    with cols[1]:
        if not st.session_state.get("logged_in", False):
            username = st.text_input("", key="top_login_user", placeholder="Username", label_visibility="collapsed")
    with cols[2]:
        if not st.session_state.get("logged_in", False):
            password = st.text_input("", type="password", key="top_login_pass", placeholder="Password", label_visibility="collapsed")

    # Fourth column: Login button only (no logout here)
    with cols[3]:
        if not st.session_state.get("logged_in", False):
            if st.button("Login"):
                if not username or not password:
                    st.warning("Please enter both username and password.")
                elif username not in credentials or credentials[username] != password:
                    st.error("Invalid username or password.")
                else:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    USER_BATCH_DIR = os.path.join("batches", username)
                    os.makedirs(USER_BATCH_DIR, exist_ok=True)
                    try:
                        st.experimental_set_query_params(user=username)
                    except Exception:
                        pass
        else:
            cols[3].markdown("")

    # Fifth column: Create Account button only when not logged in
    with cols[4]:
        if not st.session_state.get("logged_in", False):
            if st.button("New Account"):
                st.session_state["show_create"] = True
        else:
            if st.button("Logout"):
                for key in ["logged_in", "username", "view", "show_create"]:
                    if key in st.session_state:
                        del st.session_state[key]
                try:
                    st.experimental_set_query_params()
                except Exception:
                    pass

# If not logged in and show_create is True, display create-account form in main area
if not st.session_state.get("logged_in", False) and st.session_state.get("show_create", False):
    st.subheader("Create New Account")
    new_user = st.text_input("New Username", key="main_new_user")
    new_pass = st.text_input("New Password", type="password", key="main_new_pass")
    if st.button("Save Account", key="main_save_account"):
        if not new_user or not new_pass:
            st.error("Please enter both username and password.")
        elif new_user in credentials:
            st.error("Username already exists.")
        else:
            credentials[new_user] = new_pass
            with open(CRED_FILE, "w") as f:
                json.dump(credentials, f)
            os.makedirs(os.path.join("batches", new_user), exist_ok=True)
            st.success(f"Account '{new_user}' created! Please log in.")
            st.session_state["show_create"] = False
    st.stop()

# If not logged in, stop rendering the rest
if not st.session_state.get("logged_in", False):
    st.stop()

# We use GitHub as the backend for batch storage — no local folder needed
username = st.session_state["username"]
BATCH_DIR = f"batches/{username}"  # logical path in GitHub repo
PROTOCOL_FILE = "DAP_protocol_extended.xlsx"

# ---------------------- TOP-BAR NAVIGATION ----------------------
nav_bar = st.container()
with nav_bar:
    tab1, tab2, tab3, tab4 = st.columns([1, 1, 1, 1])
    with tab1:
        if st.button("Calendar"):
            st.session_state["view"] = "Calendar"
    with tab2:
        if st.button("Tasks"):
            st.session_state["view"] = "Tasks"
    with tab3:
        if st.button("Batch Manager"):
            st.session_state["view"] = "Batch Manager"
    with tab4:
        if st.button("Image Viewer"):
            st.session_state["view"] = "Image Viewer"

# ---------------------- CONFIG ----------------------

# ---------------------- HELPERS ----------------------
def batch_file(bid):
    return os.path.join(BATCH_DIR, f"batch_{bid}.csv")

def save_batch(row):
    """
    Save a single batch’s row (dict with keys: batch_id, start_date, end_date, etc.) to its CSV.
    """
    r = dict(row)
    r['start_date'] = str(r.get('start_date', ''))
    r['end_date'] = str(r.get('end_date', ''))
    pd.DataFrame([r]).to_csv(batch_file(r['batch_id']), index=False)


def load_batches():
    """
    Fetches all batch_<id>.xlsx files for the logged-in user from GitHub.
    Returns a DataFrame with summary info from each file’s “info” sheet.
    """
    batches_list = []
    for fname, bio in fetch_user_batches(username):
        try:
            df_info = pd.read_excel(bio, sheet_name="info", dtype=str)
            if df_info.empty:
                continue
            info_row = df_info.iloc[0].to_dict()
            sd = pd.to_datetime(info_row.get("start_date",""), format="%Y.%m.%d", errors="coerce").date()
            ed_raw = info_row.get("end_date","")
            if ed_raw:
                ed = pd.to_datetime(ed_raw, format="%Y.%m.%d", errors="coerce").date()
            else:
                ed = sd + timedelta(days=21) if sd else None
            row = {
                "batch_id": info_row.get("batch_id",""),
                "start_date": sd,
                "end_date": ed,
                "cell": info_row.get("cell",""),
                "note": info_row.get("note",""),
                "day15": info_row.get("day15",""),
                "day21": info_row.get("day21",""),
                "banking": info_row.get("banking","")
            }
            batches_list.append(row)
        except:
            continue
    if batches_list:
        df_all = pd.DataFrame(batches_list)
        return df_all[["batch_id","start_date","end_date","cell","note","day15","day21","banking"]]
    else:
        return pd.DataFrame(
            columns=["batch_id","start_date","end_date","cell","note","day15","day21","banking"],
            dtype=str
        )

def make_calendar(df: pd.DataFrame, today: datetime.date, length: int = 22) -> pd.DataFrame:
    """
    Build a “heatmap” calendar DataFrame for each batch (rows) over the next `length` days starting today.
    Columns are a MultiIndex [(year, month_abbr, 'weekday dd'), …].
    Each cell’s value = day-index since start_date (0,1,2,…), or NaN if out of window.
    """
    dates = [today + timedelta(days=i) for i in range(length)]
    cols = pd.MultiIndex.from_tuples(
        [(str(d.year), d.strftime('%b'), d.strftime('%a %d')) for d in dates],
        names=['Year','Month','Day']
    )
    df_sorted = df.sort_values('batch_id').reset_index(drop=True)
    cal = pd.DataFrame(index=df_sorted.batch_id.astype(str), columns=cols)

    for _, row in df_sorted.iterrows():
        try:
            start = pd.to_datetime(row.start_date).date()
            end   = pd.to_datetime(row.end_date).date()
        except:
            continue
        if pd.isna(row.end_date):
            end = start + timedelta(days=length)
        current = start
        day_index = 0
        while current <= end:
            if current in dates:
                key = (str(current.year), current.strftime('%b'), current.strftime('%a %d'))
                cal.loc[str(row.batch_id), key] = day_index
            current += timedelta(days=1)
            day_index += 1

    return cal

def style_calendar(df: pd.DataFrame, today: datetime.date, **kwargs):
    """
    Style rules:
      • Red border on the first column (today’s date).
      • Yellow shading on media/change days: {1,2,4,6,8,9,10,12,14,16,18,20}.
      • Blue shading on days 15 and 21.
    """
    yellow_days = {1,2,4,6,8,9,10,12,14,16,18,20}
    blue_days   = {15,21}
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    first_key = df.columns[0]

    for row in df.index:
        for col in df.columns:
            val = df.loc[row, col]
            if pd.isna(val) or val == "":
                continue
            try:
                day_idx = int(float(val))
            except:
                day_idx = None
            if day_idx in yellow_days:
                styles.loc[row, col] = "background-color: #fff3b0"
            elif day_idx in blue_days:
                styles.loc[row, col] = "background-color: #add8e6"
    if first_key in df.columns:
        for row in df.index:
            existing_style = styles.at[row, first_key]
            if existing_style:
                styles.at[row, first_key] = existing_style + "; border: 3px solid red;"
            else:
                styles.at[row, first_key] = "border: 3px solid red;"
    return styles

# Set initial view if not present
if 'view' not in st.session_state:
    st.session_state['view'] = 'Calendar'

# Load batches and filter to those still within Day ≤ 21
batches = load_batches()
today = datetime.today().date()
if not batches.empty:
    full_cal = make_calendar(batches, today)
    valid_ids = []
    today_key = (str(today.year), today.strftime('%b'), today.strftime('%a %d'))
    for bid in full_cal.index:
        val = full_cal.loc[bid, today_key]
        if pd.notna(val) and int(val) <= 21:
            valid_ids.append(str(bid))
    batches = batches[batches['batch_id'].astype(str).isin(valid_ids)].reset_index(drop=True)

# ---------------------- Differentiation Calendar ----------------------
if st.session_state['view'] == 'Calendar':
    st.subheader("📆 Differentiation Calendar")
    if batches.empty:
        st.info("No ongoing batches to display.")
    else:
        cal = make_calendar(batches, today)
        styled = cal.style.apply(style_calendar, today=today, axis=None)
        st.dataframe(styled, use_container_width=True, hide_index=False)
        # Display scheme image below calendar
        st.image("scheme.png", use_container_width=True)

# ---------------------- Today's Batch Tasks ----------------------
if st.session_state['view'] == 'Tasks':
    st.subheader("📌 Batch Tasks")
    selected_date = st.date_input("Select Date", value=today, key='task_date')
    if batches.empty:
        st.info("No ongoing batches.")
    else:
        try:
            df_proto = pd.read_excel(PROTOCOL_FILE, engine="openpyxl")
            df_proto["percentage"] = pd.to_numeric(df_proto["percentage"], errors="coerce")
            mask_pct = df_proto["percentage"].isna()

            def parse_conc(val):
                if isinstance(val, str):
                    v = val.strip().lower().replace("μ","u")
                    if "nm" in v:
                        return float(v.replace("nm","")) * 1e-3
                    if "um" in v:
                        return float(v.replace("um",""))
                    if "mm" in v:
                        return float(v.replace("mm","")) * 1e3
                    if "ng/ml" in v:
                        return float(v.replace("ng/ml","")) * 1e-3
                    if "ug/ml" in v:
                        return float(v.replace("ug/ml",""))
                    if "x" in v:
                        return float(v.replace("x",""))
                try:
                    return float(val)
                except:
                    return None

            for idx in df_proto[mask_pct].index:
                row = df_proto.loc[idx]
                w = parse_conc(row["working_conc"])
                s = parse_conc(row["stock_conc"])
                if (w is not None) and s:
                    df_proto.at[idx, "percentage"] = (w / s) * 100

            df_proto["day"] = df_proto["day"].astype(int)
            mdap_protocol = {}
            for day_val in sorted(df_proto["day"].dropna().unique()):
                subset = df_proto[df_proto["day"] == day_val]
                day_entries = []
                for task_name in subset["task"].unique():
                    task_subset = subset[subset["task"] == task_name]
                    if "Media Change" in task_name or "Plate coating" in task_name:
                        comp_list = []
                        for _, r in task_subset.iterrows():
                            comp_list.append({
                                "component":    r["component"],
                                "percentage":   r.get("percentage", ""),
                                "stock_conc":   r.get("stock_conc", ""),
                                "working_conc": r.get("working_conc", ""),
                            })
                        day_entries.append({"task": task_name, "composition": comp_list})
                    else:
                        day_entries.append({"task": task_name})
                mdap_protocol[day_val] = day_entries
        except FileNotFoundError:
            st.warning(f"Protocol file '{PROTOCOL_FILE}' not found.")
            mdap_protocol = {}

        cal2 = make_calendar(batches, selected_date)
        ongoing = []
        selected_key = (str(selected_date.year), selected_date.strftime('%b'), selected_date.strftime('%a %d'))
        for bid in cal2.index:
            try:
                day_idx = cal2.loc[bid, selected_key]
            except KeyError:
                day_idx = None
            if pd.notna(day_idx):
                ongoing.append((bid, int(day_idx)))

        if ongoing and mdap_protocol:
            task_cols = st.columns(len(ongoing))
            for i, (bid, day) in enumerate(ongoing):
                with task_cols[i]:
                    st.markdown(f"### 🧪 Batch {bid} (D{day})")
                    # Determine and display stage based on day index
                    if 0 <= day <= 5:
                        st.markdown("**Stage:** FP induction")
                    elif 6 <= day <= 11:
                        st.markdown("**Stage:** NP induction")
                    elif 12 <= day <= 21:
                        st.markdown("**Stage:** mDAN induction")
                    else:
                        st.markdown("**Stage:** Unknown")
                    day_entries = mdap_protocol.get(day, [])
                    if not day_entries:
                        st.info("No task for this day.")
                    for idx, entry in enumerate(day_entries):
                        task_txt = entry.get("task", "No task")
                        st.markdown(f"**Task {idx+1}:** {task_txt}")
                        if entry.get("composition"):
                            default_vol = 15.0 if day <= 14 else 40.0
                            total_vol = st.number_input(
                                f"Total Volume (mL) for Task {idx+1}", 
                                min_value=1.0, value=default_vol, step=1.0, 
                                key=f"vol_{bid}_{idx}"
                            )
                            comp_entries = entry.get("composition", [])
                            display_rows = []
                            for item in comp_entries:
                                name = item["component"]
                                pct  = item.get("percentage", None)
                                stock= item.get("stock_conc", "")
                                work = item.get("working_conc", "")
                                vol_str = ""
                                if pct not in ("", None) and not pd.isna(pct):
                                    vol_ml = total_vol * float(pct) / 100
                                    if vol_ml < 1:
                                        ul = int(round(vol_ml * 1000))
                                        vol_str = f"{ul} µL"
                                    else:
                                        vol_str = f"{round(vol_ml, 2)} mL"
                                elif stock and work:
                                    stock_val = parse_conc(stock)
                                    work_val  = parse_conc(work)
                                    if stock_val and work_val:
                                        ul_calc = (work_val * total_vol * 1000) / stock_val
                                        if ul_calc < 1000:
                                            vol_str = f"{int(round(ul_calc))} µL"
                                        else:
                                            vol_str = f"{round(ul_calc/1000, 2)} mL"
                                display_rows.append({"Component": name, "Volume": vol_str})
                            st.table(pd.DataFrame(display_rows))
        else:
            st.info("No ongoing batches with tasks for today.")

# ---------------------- Batch Manager ----------------------
if st.session_state['view'] == 'Batch Manager':
    st.subheader("📋 Batch Manager")

    if 'mode' not in st.session_state or st.session_state['mode'] == 'none':
        st.session_state['mode'] = 'add'
    if 'edit_id' not in st.session_state:
        st.session_state['edit_id'] = None

    col_add, col_load, col_button = st.columns([1, 3, 1])
    with col_add:
        if st.button("Add new batch"):
            st.session_state['mode'] = 'add'
            st.session_state['edit_id'] = None
    with col_load:
        load_bid = st.number_input("Batch ID to Load", min_value=1, step=1, key='load_bid')
    with col_button:
        if st.button("Load"):
            st.session_state['mode'] = 'edit'
            st.session_state['edit_id'] = int(load_bid)

    if st.session_state['mode'] == 'add':
        st.subheader("Batch Information")
        try:
            max_id = int(batches['batch_id'].astype(int).max())
            default_id = max_id + 1
        except:
            default_id = 1
        new_bid   = st.number_input("Batch ID",      min_value=1, step=1, value=default_id, key='new_bid')
        new_cell  = st.text_input("Cell Type",      key='new_cell')
        new_sdate = st.date_input("Start Date", value=today, key='new_sdate')
        default_edate = today + timedelta(days=21)
        new_edate = st.date_input("End Date (opt)", value=default_edate, key='new_edate')
        new_note   = st.text_area("Note",           key='new_note')
        new_day15  = st.text_input("Day 15 Info",   key='new_day15')
        new_day21  = st.text_input("Day 21 Info",   key='new_day21')
        new_banking= st.text_input("Banking Info",  key='new_banking')

        # --- Cell Count Table Editor ---
        cols = ["A", "B", "C"] + [str(i) for i in range(1, 16)]
        cell_index = ["Day 15", "Day 21", "Banking"]
        counts_file = os.path.join(BATCH_DIR, f"batch_{new_bid}.xlsx")
        if os.path.exists(counts_file):
            try:
                cell_df = pd.read_excel(counts_file, sheet_name="cell_counts", index_col=0)
            except:
                cell_df = pd.DataFrame(index=cell_index, columns=cols)
        else:
            cell_df = pd.DataFrame(index=cell_index, columns=cols)
        edited_cell_df = st.data_editor(cell_df, use_container_width=True)

        if st.button("Save New Batch"):
            row = {
                "batch_id": str(new_bid),
                "cell": new_cell,
                "start_date": new_sdate.strftime("%Y.%m.%d"),
                "end_date": new_edate.strftime("%Y.%m.%d") if new_edate else "",
                "note": new_note,
                "day15": new_day15,
                "day21": new_day21,
                "banking": new_banking
            }
            # Save summary and cell counts into Excel
            with ExcelWriter(counts_file) as writer:
                pd.DataFrame([row]).to_excel(writer, sheet_name="info", index=False)
                edited_cell_df.to_excel(writer, sheet_name="cell_counts")
            # Persist new batch file to GitHub
            commit_batch_to_github(username, new_bid, counts_file)
            st.success(f"Batch {new_bid} added.")

    elif st.session_state['mode'] == 'edit':
        bid = st.session_state['edit_id']
        st.subheader(f"Batch Information #{bid}")
        # Load batch info directly from the batch_<id>.xlsx 'info' sheet
        counts_file = os.path.join(BATCH_DIR, f"batch_{bid}.xlsx")
        if os.path.exists(counts_file):
            df_info = pd.read_excel(counts_file, sheet_name="info", dtype=str)
            rec = df_info.iloc[0:1]
        else:
            rec = pd.DataFrame()
        if not rec.empty:
            rec = rec.iloc[0]
            edit_cell = st.text_input("Cell Type", value=rec.get('cell',''), key='edit_cell')
            sdt = pd.to_datetime(rec.get('start_date'), format="%Y.%m.%d", errors='coerce')
            # Parse end_date if present; otherwise treat as NaT
            if rec.get('end_date', ""):
                edt_parsed = pd.to_datetime(rec.get('end_date'), format="%Y.%m.%d", errors='coerce')
            else:
                edt_parsed = pd.NaT
            # Default to start_date + 21 days if parsed end is NaT
            if pd.isna(edt_parsed) and not pd.isna(sdt):
                default_edate = (sdt + timedelta(days=21)).date()
            elif pd.isna(edt_parsed):
                default_edate = today + timedelta(days=21)
            else:
                default_edate = edt_parsed.date()

            edit_sdate = st.date_input(
                "Start Date",
                value=sdt.date() if not pd.isna(sdt) else today,
                key='edit_sdate'
            )
            edit_edate = st.date_input(
                "End Date",
                value=default_edate,
                key='edit_edate'
            )
            edit_note   = st.text_area("Note", value=rec.get('note',''), key='edit_note')
            edit_day15  = st.text_input("Day 15 Info", value=rec.get('day15',''), key='edit_day15')
            edit_day21  = st.text_input("Day 21 Info", value=rec.get('day21',''), key='edit_day21')
            edit_banking= st.text_input("Banking Info", value=rec.get('banking',''), key='edit_banking')

            # --- Cell Count Table Editor ---
            st.subheader("Cell count information")
            cols = ["A", "B", "C"] + [str(i) for i in range(1, 16)]
            cell_index = ["Day 15", "Day 21", "Banking"]
            counts_file = os.path.join(BATCH_DIR, f"batch_{bid}.xlsx")
            if os.path.exists(counts_file):
                try:
                    cell_df = pd.read_excel(counts_file, sheet_name="cell_counts", index_col=0)
                except:
                    cell_df = pd.DataFrame(index=cell_index, columns=cols)
            else:
                cell_df = pd.DataFrame(index=cell_index, columns=cols)
            edited_cell_df = st.data_editor(cell_df, use_container_width=True)

            if st.button("Update Batch Information"):
                new_row = {
                    "batch_id": str(bid),
                    "cell": edit_cell,
                    "start_date": edit_sdate.strftime("%Y.%m.%d"),
                    "end_date": edit_edate.strftime("%Y.%m.%d") if edit_edate else "",
                    "note": edit_note,
                    "day15": edit_day15,
                    "day21": edit_day21,
                    "banking": edit_banking
                }
                # Save updated summary and cell counts into the same Excel file
                with ExcelWriter(counts_file) as writer:
                    pd.DataFrame([new_row]).to_excel(writer, sheet_name="info", index=False)
                    edited_cell_df.to_excel(writer, sheet_name="cell_counts")
                # Persist updated batch file to GitHub
                commit_batch_to_github(username, bid, counts_file)
                st.success(f"Batch {bid} updated.")
        else:
            st.error(f"Batch {bid} not found.")

# ---------------------- Image Viewer ----------------------
if st.session_state['view'] == 'Image Viewer':
    # The following code is adapted from BIOv1.py, excluding its own set_page_config(...) call

    # Step 1: Upload image files
    uploaded_files = st.file_uploader(
        "Drag and drop image files here (JPEG/PNG), or click to browse",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    if uploaded_files:
        image_files = uploaded_files
        batch_pattern = re.compile(r"^DIF(\d+)_", re.IGNORECASE)
    else:
        st.info("Please upload image files to proceed.")
        st.stop()

    # Step 2: Group images by Batch ID, then by “DAY” prefix
    batch_pattern = re.compile(r"^DIF(\d+)_", re.IGNORECASE)
    day_pattern   = re.compile(r"_D(\d+)_", re.IGNORECASE)
    batch_groups  = {}

    # Build batch_groups: {batch_id: [UploadedFile, ...], ...}
    for uploaded_file in image_files:
        fname = uploaded_file.name
        m = batch_pattern.search(fname)
        if m:
            bid = m.group(1)
        else:
            bid = "Unknown"
        batch_groups.setdefault(bid, []).append(uploaded_file)


    # Step 3: For each batch, show batch info from Excel, then group by day and display images
    sorted_groups = {}
    for bid, files_in_batch in sorted(batch_groups.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        # Load and display batch info from Excel
        counts_file = os.path.join(BATCH_DIR, f"batch_{bid}.xlsx")
        if os.path.exists(counts_file):
            df_info = pd.read_excel(counts_file, sheet_name="info", dtype=str)
            if not df_info.empty:
                info = df_info.iloc[0].to_dict()
                st.subheader(f"Batch {bid} Information")
                st.write(f"**Cell Type:** {info.get('cell', '')}")
                st.write(f"**Start Date:** {info.get('start_date', '')}")
                st.write(f"**End Date:** {info.get('end_date', '')}")
                st.write(f"**Note:** {info.get('note', '')}")
                st.write(f"**Day 15 Info:** {info.get('day15', '')}")
                st.write(f"**Day 21 Info:** {info.get('day21', '')}")
                st.write(f"**Banking Info:** {info.get('banking', '')}")
                # Display cell_counts sheet
                try:
                    df_counts = pd.read_excel(counts_file, sheet_name="cell_counts", index_col=0)
                    st.subheader("Cell Counts")
                    st.dataframe(df_counts, use_container_width=True)
                except:
                    st.info("No cell counts data available.")
        else:
            st.subheader(f"Batch {bid} (Info not found)")
        # Group this batch's files by day
        day_groups = {}
        for f in files_in_batch:
            fname = f.name
            m = day_pattern.search(fname)
            if m:
                day = m.group(1)
            else:
                day = "Unknown"
            day_groups.setdefault(day, []).append(f)
        # Display each day group
        for day, files in sorted(day_groups.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            st.markdown(f"**Day {day}**")
            # Show images in rows of four for this day
            for i in range(0, len(files), 4):
                chunk = files[i:i+4]
                cols4 = st.columns(4)
                for idx, fobj in enumerate(chunk):
                    try:
                        img_disp = Image.open(fobj)
                        cols4[idx].image(img_disp, caption=fobj.name, use_container_width=True)
                    except:
                        cols4[idx].empty()
                # Fill remaining columns if fewer than 4
                for idx in range(len(chunk), 4):
                    cols4[idx].empty()