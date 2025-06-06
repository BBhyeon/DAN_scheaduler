import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="DAC_manager_v9", layout="wide")

# ---------------------- CONSTANTS ----------------------
BATCH_DIR = "batches"
os.makedirs(BATCH_DIR, exist_ok=True)
PROTOCOL_FILE = "DAP_protocol_extended.xlsx"

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
    If "batches.csv" exists, load everything from it; otherwise fall back to per-batch CSV files.
    Returns a DataFrame containing at least:
      ['batch_id','start_date','end_date','cell','note','initial_plate_count','replaced_plate_count']
    """
    BATCHES_CSV = "batches.csv"
    if os.path.exists(BATCHES_CSV):
        df = pd.read_csv(BATCHES_CSV, dtype=str)
        required = {'batch_id','cell','start_date','initial_plate_count','replaced_plate_count'}
        if not required.issubset(df.columns):
            st.error("batches.csv must include columns: batch_id, cell, start_date, initial_plate_count, replaced_plate_count")
            return pd.DataFrame(columns=['batch_id','start_date','end_date'])
        df['end_date_raw'] = df.get('end_date', "")
        def compute_end(row):
            try:
                sd = pd.to_datetime(row['start_date'], format='%Y.%m.%d', errors='coerce')
            except:
                return pd.NaT
            if not row['end_date_raw']:
                return (sd + timedelta(days=21)).date()
            else:
                ed = pd.to_datetime(row['end_date_raw'], errors='coerce')
                if pd.isna(ed):
                    return (sd + timedelta(days=21)).date()
                return ed.date()
        df['end_date'] = df.apply(compute_end, axis=1)
        df.drop(columns=['end_date_raw'], inplace=True)
        df['start_date'] = pd.to_datetime(df['start_date'], format='%Y.%m.%d', errors='coerce').dt.date
        df['end_date']   = pd.to_datetime(df['end_date'], errors='coerce').dt.date
        return df[['batch_id','start_date','end_date','cell','note','initial_plate_count','replaced_plate_count']]
    else:
        frames = []
        for fn in os.listdir(BATCH_DIR):
            if fn.endswith(".csv") and fn.startswith("batch_"):
                try:
                    d = pd.read_csv(os.path.join(BATCH_DIR, fn), dtype=str)
                    if {'batch_id','start_date','end_date'}.issubset(d.columns):
                        frames.append(d.iloc[:1])
                except:
                    continue
        if frames:
            df_all = pd.concat(frames, ignore_index=True)
            df_all['start_date'] = pd.to_datetime(df_all['start_date'], errors='coerce').dt.date
            df_all['end_date']   = pd.to_datetime(df_all['end_date'], errors='coerce').dt.date
            return df_all
        return pd.DataFrame(columns=['batch_id','start_date','end_date'], dtype=str)

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

# ---------------------- MAIN LAYOUT ----------------------

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
    counts_file = os.path.join(BATCH_DIR, f"batch_{new_bid}_cell_counts.csv")
    if os.path.exists(counts_file):
        cell_df = pd.read_csv(counts_file, index_col=0)
    else:
        cell_df = pd.DataFrame(index=cell_index, columns=cols)
    edited_cell_df = st.data_editor(cell_df, use_container_width=True)

    if st.button("Save New Batch"):
        BATCHES_CSV = "batches.csv"
        if os.path.exists(BATCHES_CSV):
            df = pd.read_csv(BATCHES_CSV, dtype=str)
        else:
            df = pd.DataFrame(columns=[
                "batch_id","cell","start_date","end_date","note","day15","day21","banking"
            ])
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
        df = df[df['batch_id'] != str(new_bid)]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(BATCHES_CSV, index=False)
        # Save cell counts
        edited_cell_df.to_csv(counts_file)
        st.success(f"Batch {new_bid} added.")

elif st.session_state['mode'] == 'edit':
    bid = st.session_state['edit_id']
    st.subheader(f"Batch Information #{bid}")
    BATCHES_CSV = "batches.csv"
    if os.path.exists(BATCHES_CSV):
        df_all = pd.read_csv(BATCHES_CSV, dtype=str)
        rec = df_all[df_all['batch_id'] == str(bid)]
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
            counts_file = os.path.join(BATCH_DIR, f"batch_{bid}_cell_counts.csv")
            if os.path.exists(counts_file):
                cell_df = pd.read_csv(counts_file, index_col=0)
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
                df_all = df_all[df_all['batch_id'] != str(bid)]
                df_all = pd.concat([df_all, pd.DataFrame([new_row])], ignore_index=True)
                df_all.to_csv(BATCHES_CSV, index=False)
                # Save cell counts for edit mode
                edited_cell_df.to_csv(counts_file)
                st.success(f"Batch {bid} updated.")
        else:
            st.error(f"Batch {bid} not found in batches.csv.")
    else:
        st.error("batches.csv not found. Cannot load batch.")