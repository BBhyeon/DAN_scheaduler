import streamlit as st
st.set_page_config(page_title="DAC_manager_v12", layout="wide")


import pandas as pd
from pandas import ExcelWriter
from datetime import datetime, timedelta
import os
import json
import re
from PIL import Image
from streamlit_sortables import sort_items
import gspread
from oauth2client.service_account import ServiceAccountCredentials



# ——— Google Sheets settings ———
SHEET_ID = st.secrets.get("SHEET_ID")
if not SHEET_ID:
    st.error("Missing SHEET_ID in Streamlit secrets. Please add your Google Sheet ID.")
    st.stop()

try:
    GSPREAD_CRED = st.secrets["GSPREAD_CRED"]
except KeyError:
    st.error("Missing GSPREAD_CRED in Streamlit secrets. Please add your service account JSON under that key.")
    st.stop()

# Authenticate to Google Sheets
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(GSPREAD_CRED, scope)
gc    = gspread.authorize(creds)
try:
    sh = gc.open_by_key(SHEET_ID)
except Exception as e:
    st.error(f"Failed to open Google Sheet (check permissions & API): {e}")
    st.stop()
ws_info   = sh.worksheet("info")
ws_counts = sh.worksheet("cell_counts")

# Select the account worksheet by its gid from secrets
GID_ACCOUNTS = int(st.secrets["GID_ACCOUNTS"])
ws_accounts = next(ws for ws in sh.worksheets() if ws.id == GID_ACCOUNTS)

@st.cache_data(ttl=300)
def load_accounts():
    records = ws_accounts.get_all_records()
    df = pd.DataFrame(records)
    # Ensure username and password columns exist
    required = ["username", "password"]
    for col in required:
        if col not in df.columns:
            df[col] = ""
    return df[required]


# Initialize session state flags if not present
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "show_create" not in st.session_state:
    st.session_state["show_create"] = False

## ---------------------- CREDENTIALS from Secrets ----------------------
# (Removed static credentials; now using Google Sheet for accounts)

## ---------------------- TOP-BAR LOGIN & ACCOUNT CREATION ----------------------

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
                else:
                    accounts_df = load_accounts()
                    # verify username exists
                    if username not in accounts_df["username"].astype(str).tolist():
                        st.error("Invalid username or password.")
                    else:
                        stored_pw = accounts_df.set_index("username").at[username, "password"]
                        if password != str(stored_pw):
                            st.error("Invalid username or password.")
                        else:
                            st.session_state["logged_in"] = True
                            st.session_state["username"]  = username
                            os.makedirs(os.path.join("batches", username), exist_ok=True)
        else:
            cols[3].markdown("")

    # Fifth column: Create Account button only when not logged in
    with cols[4]:
        if not st.session_state.get("logged_in", False):
            if st.button("New Account"):
                st.session_state["show_create"] = True
        else:
            if st.button("Logout"):
                # Clear login state and URL param
                for key in ["logged_in", "username", "view", "show_create"]:
                    st.session_state.pop(key, None)

# If not logged in and show_create is True, display create-account form in main area
if not st.session_state.get("logged_in", False) and st.session_state.get("show_create", False):
    st.subheader("Create New Account")
    new_user = st.text_input("New Username", key="main_new_user")
    new_pass = st.text_input("New Password", type="password", key="main_new_pass")
    if st.button("Save Account", key="main_save_account"):
        accounts_df = load_accounts()
        if not new_user or not new_pass:
            st.error("Please enter both username and password.")
        elif new_user in accounts_df["username"].astype(str).tolist():
            st.error("Username already exists.")
        else:
            ws_accounts.append_row([new_user, new_pass])
            load_accounts.clear()
            st.success(f"Account '{new_user}' created. Please login.")
            st.session_state["show_create"] = False
    st.stop()

# If not logged in, stop rendering the rest
if not st.session_state.get("logged_in", False):
    st.stop()

# Set up user-specific batch directory
username = st.session_state["username"]
USER_BATCH_DIR = os.path.join("batches", username)
BATCH_DIR = USER_BATCH_DIR
os.makedirs(BATCH_DIR, exist_ok=True)
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
# def batch_file(bid):
#     return os.path.join(BATCH_DIR, f"batch_{bid}.csv")

# def save_batch(row):
#     """
#     Save a single batch’s row (dict with keys: batch_id, start_date, end_date, etc.) to its CSV.
#     """
#     r = dict(row)
#     r['start_date'] = str(r.get('start_date', ''))
#     r['end_date'] = str(r.get('end_date', ''))
#     pd.DataFrame([r]).to_csv(batch_file(r['batch_id']), index=False)

def load_batches():
    """Load all user batches from the 'info' sheet in Google Sheets."""
    all_records = ws_info.get_all_records()
    df = pd.DataFrame(all_records)
    # filter to this user only
    df = df[df["username"] == username].copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "batch_id",
            "start_date",
            "end_date",
            "cell",
            "note",
            "initial_plate_count",
            "replaced_plate_count"
        ])
    # parse dates
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
    df["end_date"]   = pd.to_datetime(df["end_date"], errors="coerce").dt.date
    return df[[
        "batch_id",
        "start_date",
        "end_date",
        "cell",
        "note",
        "initial_plate_count",
        "replaced_plate_count"
    ]]

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
        new_initial_plate_count = st.text_input("Initial Plate Count", key='new_initial_plate_count')
        new_replaced_plate_count = st.text_input("Replaced Plate Count", key='new_replaced_plate_count')

        # --- Cell Count Table Editor ---
        cols = ["A", "B", "C"] + [str(i) for i in range(1, 16)]
        cell_index = ["Day 15", "Day 21", "Banking"]
        # No local file: always create new empty DataFrame for new batch
        cell_df = pd.DataFrame(index=cell_index, columns=cols)
        edited_cell_df = st.data_editor(cell_df, use_container_width=True)

        if st.button("Save New Batch"):
            # Append to info sheet
            info_row = [
                username,
                int(new_bid),
                new_cell,
                new_sdate.strftime("%Y.%m.%d"),
                new_note,
                new_initial_plate_count,
                new_replaced_plate_count,
                new_edate.strftime("%Y.%m.%d")
            ]
            ws_info.append_row(info_row)

            # Append each cell_count row
            for day in edited_cell_df.index:
                row = [username, int(new_bid), day] + edited_cell_df.loc[day].fillna("").tolist()
                ws_counts.append_row(row)

                st.success(f"Batch {new_bid} created and saved to Google Sheets.")
                # page refresh removed

    elif st.session_state['mode'] == 'edit':
        bid = st.session_state['edit_id']
        st.subheader(f"Batch Information #{bid}")
        # Load batch info from Google Sheet
        all_info = ws_info.get_all_records()
        info_df = pd.DataFrame(all_info)
        rec = info_df[(info_df["username"] == username) & (info_df["batch_id"].astype(str) == str(bid))]
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
            edit_initial_plate_count = st.text_input("Initial Plate Count", value=rec.get('initial_plate_count',''), key='edit_initial_plate_count')
            edit_replaced_plate_count = st.text_input("Replaced Plate Count", value=rec.get('replaced_plate_count',''), key='edit_replaced_plate_count')

            # --- Cell Count Table Editor ---
            st.subheader("Cell count information")
            cols = ["A", "B", "C"] + [str(i) for i in range(1, 16)]
            cell_index = ["Day 15", "Day 21", "Banking"]
            # Load cell counts from Google Sheet
            all_counts = ws_counts.get_all_records()
            counts_df = pd.DataFrame(all_counts)
            batch_counts = counts_df[
                (counts_df["username"] == username) & (counts_df["batch_id"].astype(str) == str(bid))
            ]
            cell_df = pd.DataFrame(index=cell_index, columns=cols)
            for _, row in batch_counts.iterrows():
                # third column holds the phase (e.g. "Day 15", "Day 21", "Banking")
                phase = row.iloc[2]
                vals = [row.get(c, "") for c in cols]
                if phase in cell_index:
                    cell_df.loc[phase] = vals
            edited_cell_df = st.data_editor(cell_df, use_container_width=True)

            if st.button("Update Batch Information"):
                # Delete old info rows matching this batch (simple full-sheet rewrite recommended)
                all_info = ws_info.get_all_records()
                df_info = pd.DataFrame(all_info)
                keep = df_info[~((df_info["username"]==username) & (df_info["batch_id"]==bid))]
                ws_info.clear()
                ws_info.update([keep.columns.values.tolist()] + keep.values.tolist())

                updated_row = [
                    username, bid,
                    edit_cell,
                    edit_sdate.strftime("%Y.%m.%d"),
                    edit_note,
                    edit_initial_plate_count,
                    edit_replaced_plate_count,
                    edit_edate.strftime("%Y.%m.%d")
                ]
                ws_info.append_row(updated_row)

                # Clear and rewrite cell_counts for this batch
                all_counts = ws_counts.get_all_records()
                df_counts = pd.DataFrame(all_counts)
                keep_c = df_counts[~((df_counts["username"]==username)&(df_counts["batch_id"]==bid))]
                ws_counts.clear()
                ws_counts.update([keep_c.columns.values.tolist()] + keep_c.values.tolist())
                for day in edited_cell_df.index:
                    row = [username, bid, day] + edited_cell_df.loc[day].fillna("").tolist()
                    ws_counts.append_row(row)
                st.session_state["update_ack"] = bid
        # If no record loaded, show error
        if rec.empty:
            st.error(f"Batch {bid} not found.")
        else:
            # Show update confirmation if just updated
            if st.session_state.get("update_ack") == bid:
                st.success(f"Batch {bid} updated in Google Sheets.")
                del st.session_state["update_ack"]





# ---------------------- Image Viewer ----------------------
if st.session_state['view'] == 'Image Viewer':
    st.subheader("🛠️ Image Viewer Setup")

    # First row: Batch ID, Filename Prefix, Show Filenames
    r1c1, r1c2, r1c3 = st.columns([1,1,1])
    with r1c1:
        batch_id_to_view = st.number_input("Batch ID", min_value=1, step=1, key="img_setup_bid")
    with r1c2:
        day_prefix = st.text_input("Filename prefix", "D", max_chars=3, key="img_setup_prefix")
    with r1c3:
        show_filenames = st.selectbox("Show filenames", ["Yes", "No"], index=0, key="img_setup_showfn")

    # Second row: Images per row, per day, per dish
    r2c1, r2c2, r2c3 = st.columns([1,1,1])
    with r2c1:
        images_per_row = st.number_input("Images/row", 1, 6, 4, key="img_setup_cols")
    with r2c2:
        images_per_day = st.number_input("Images/day", 1, 100, 100, key="img_setup_maxday")
    with r2c3:
        images_per_dish = st.number_input("Images/dish", 1, 10, 4, key="img_setup_perdish")

    # Third row: Upload images and Run button
    r3c1, r3c2 = st.columns([3,1])
    with r3c1:
        uploaded = st.file_uploader(
            "Upload images (JPEG/PNG)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="img_setup_upload"
        )
    with r3c2:
        run = st.button("Run")

    if run:
        if not uploaded:
            st.warning("No images uploaded.")
            st.stop()

        # 1) Batch info
        if batch_id_to_view:
            df_info = pd.DataFrame(ws_info.get_all_records())
            df_info["username"] = df_info["username"].astype(str).str.strip()
            df_info["batch_id"] = pd.to_numeric(df_info["batch_id"], errors="coerce")
            rec = df_info[
                (df_info["username"]==username) &
                (df_info["batch_id"]==batch_id_to_view)
            ]
            if rec.empty:
                st.error(f"Batch {batch_id_to_view} not found.")
            else:
                rec = rec.iloc[0]
                st.markdown(f"**Batch {batch_id_to_view} Information**")
                st.write(f"• Cell Type: {rec['cell']}")
                st.write(f"• Start Date: {rec['start_date']}")
                st.write(f"• End Date: {rec['end_date']}")
                st.write(f"• Note: {rec['note']}")
                st.write(f"• Initial Count: {rec['initial_plate_count']}")
                st.write(f"• Replaced Count: {rec['replaced_plate_count']}")
                st.markdown("---")

                # Cell counts
                df_counts = pd.DataFrame(ws_counts.get_all_records())
                df_counts["username"] = df_counts["username"].astype(str).str.strip()
                df_counts["batch_id"] = pd.to_numeric(df_counts["batch_id"], errors="coerce")
                batch_counts = df_counts[
                    (df_counts["username"]==username) &
                    (df_counts["batch_id"]==batch_id_to_view)
                ]
                if not batch_counts.empty:
                    st.subheader("Cell Counts")
                    # rename 3rd col to 'phase'
                    if "phase" not in batch_counts and len(batch_counts.columns)>2:
                        batch_counts = batch_counts.rename(
                            columns={batch_counts.columns[2]:"phase"}
                        )
                    # build pivot
                    pivot = batch_counts.set_index("phase").drop(
                        ["username","batch_id"], axis=1, errors="ignore"
                    )
                    # ensure the three rows
                    for ph in ["Day 15","Day 21","Banking"]:
                        if ph not in pivot.index:
                            pivot.loc[ph] = [""]*pivot.shape[1]
                    pivot = pivot.loc[["Day 15","Day 21","Banking"]]
                    # drop empty columns
                    pivot = pivot.replace("", pd.NA).dropna(axis=1, how="all")
                    st.table(pivot)
                else:
                    st.info("No cell counts available for this batch.")

        # 2) Images grouping
        from collections import defaultdict
        day_pat  = re.compile(rf"_{re.escape(day_prefix)}(\d+)_", re.IGNORECASE)
        dish_pat = re.compile(r"#([^_]+)", re.IGNORECASE)
        groups   = defaultdict(list)
        for f in uploaded:
            m = day_pat.search(f.name)
            day = m.group(1) if m else "Unknown"
            groups[day].append(f)

        # sort days
        def day_key(it): 
            x,_=it
            return int(x) if x.isdigit() else float('inf')
        for day, files in sorted(groups.items(), key=day_key):
            st.markdown(f"### Day {day}")
            # check dish IDs
            dish_ids = [dish_pat.search(f.name).group(1) for f in files if dish_pat.search(f.name)]
            if dish_ids:
                # group by dish
                from collections import defaultdict
                dg=defaultdict(list)
                for f in files:
                    m2=dish_pat.search(f.name)
                    di = m2.group(1) if m2 else "Unknown"
                    dg[di].append(f)
                for di,flist in sorted(dg.items()):
                    st.markdown(f"#### Dish {di}")
                    flist = sorted(flist, key=lambda x: x.name)
                    sub = flist[:images_per_dish]
                    for i in range(0,len(sub),images_per_row):
                        chunk = sub[i:i+images_per_row]
                        cols = st.columns(images_per_row)
                        for idx,fobj in enumerate(chunk):
                            img = Image.open(fobj)
                            cols[idx].image(img, use_container_width=True)
                            if show_filenames=="Yes":
                                cols[idx].caption(fobj.name)
                        for idx in range(len(chunk), images_per_row):
                            cols[idx].empty()
            else:
                # no dishes, show by day only
                flist = sorted(files, key=lambda x: x.name)[:images_per_day]
                for i in range(0,len(flist),images_per_row):
                    chunk = flist[i:i+images_per_row]
                    cols = st.columns(images_per_row)
                    for idx,fobj in enumerate(chunk):
                        img = Image.open(fobj)
                        cols[idx].image(img, use_container_width=True)
                        if show_filenames=="Yes":
                            cols[idx].caption(fobj.name)
                    for idx in range(len(chunk), images_per_row):
                        cols[idx].empty()
    else:
        st.info("Configure settings above and click Run to view batch info and images.")