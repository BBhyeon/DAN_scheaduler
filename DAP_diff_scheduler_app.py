import streamlit as st
import pandas as pd
from datetime import datetime

# Page configuration and CSS wrapper
st.set_page_config(layout="wide")
st.markdown(
    """
    <style>
    .centered-content {
        max-width: 1100px;
        margin: auto;
        padding: 1rem;
    }
    </style>
    <div class="centered-content">
    """,
    unsafe_allow_html=True,
)

# Load mDAP protocol from Excel
protocol_df = pd.read_excel("DAP_protocol_extended.xlsx", engine="openpyxl")
# Only coerce percentage to numeric; keep stock_conc and working_conc as original strings
protocol_df["percentage"] = pd.to_numeric(protocol_df["percentage"], errors="coerce")
mask = protocol_df["percentage"].isna()

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

for idx in protocol_df[mask].index:
    row = protocol_df.loc[idx]
    w = parse_conc(row["working_conc"])
    s = parse_conc(row["stock_conc"])
    if w is not None and s:
        protocol_df.at[idx, "percentage"] = (w / s) * 100

protocol_df["day"] = protocol_df["day"].astype(int)

mdap_protocol = {}
for day in sorted(protocol_df["day"].dropna().unique()):
    subset = protocol_df[protocol_df["day"] == day]
    task = subset.iloc[0]["task"]
    if "Media Change" in task:
        composition = []
        for _, r in subset.iterrows():
            composition.append({
                "component": r["component"],
                "percentage": r.get("percentage", ""),
                "stock_conc": r.get("stock_conc", ""),
                "working_conc": r.get("working_conc", ""),
            })
        mdap_protocol[day] = {"task": task, "composition": composition}
    else:
        mdap_protocol[day] = {"task": task}

# Load batch data
batch_file = "batches.csv"
try:
    batches_df = pd.read_csv(batch_file, parse_dates=["start_date"])
except FileNotFoundError:
    batches_df = pd.DataFrame(columns=["batch_id","cell","start_date","note"])

# After reading batches_df
if "initial_plate_count" not in batches_df.columns:
    batches_df["initial_plate_count"] = 1
if "replaced_plate_count" not in batches_df.columns:
    batches_df["replaced_plate_count"] = 0

if "selected_batch" not in st.session_state:
    st.session_state.selected_batch = None

today = datetime.now().date()

# Three-column layout: [2,1,1]
col1, col2, col3 = st.columns([2,1,1])

# Column 1: Existing Batches
with col1:
    st.subheader("📋 Existing Batches")
    display_data = []
    for i, row in batches_df.iterrows():
        day_count = int((today - row["start_date"].date()).days)
        task = mdap_protocol.get(day_count, {}).get("task","No task")
        display_data.append({
            "Batch ID": row["batch_id"],
            "Cell": row["cell"],
            "Start Date": row["start_date"].date(),
            "Day Count": day_count,
            "Initial plate #": row["initial_plate_count"],
            "Replated plate #": row["replaced_plate_count"],
            "Today's Task": task
        })
    batch_df_display = pd.DataFrame(display_data)
    st.dataframe(batch_df_display, use_container_width=True)
    # After creating batch_df_display
    if batch_df_display.empty:
        st.info("No batches available. Switching to Add New Batch.")
        st.session_state.selected_batch = None
    else:
        batch_options = ["➕ Add New Batch"] + list(batch_df_display["Batch ID"])
        selected_option = st.selectbox("Select a Batch ID to view/edit:", batch_options)
        if selected_option == "➕ Add New Batch":
            st.session_state.selected_batch = None
        else:
            st.session_state.selected_batch = batches_df[batches_df["batch_id"] == selected_option].index[0]

# Column 2: Batch Information Form
with col2:
    st.subheader("📝 Batch Information")
    if st.session_state.selected_batch is not None:
        sel = batches_df.loc[st.session_state.selected_batch]
        batch_id = sel["batch_id"]
        cell = sel["cell"]
        start_date = sel["start_date"].date()
        initial_plate_count = sel.get("initial_plate_count", 1)
        replaced_plate_count = sel.get("replaced_plate_count", 0)
        note = sel.get("note","")
    else:
        batch_id = ""
        cell = ""
        start_date = today
        initial_plate_count = 1
        replaced_plate_count = 0
        note = ""
    with st.form("batch_form"):
        batch_id = st.text_input("Batch ID", value=batch_id)
        cell = st.text_input("Cell", value=cell)
        start_date = st.date_input("Start Date", value=start_date)
        initial_plate_count = st.number_input("Initial plate #", value=initial_plate_count, min_value=1)
        replaced_plate_count = st.number_input("Replated plate #", value=replaced_plate_count, min_value=0)
        note = st.text_area("Note", value=note)
        submitted = st.form_submit_button("Save Batch")
        if submitted:
            new_entry = {
                "batch_id": batch_id,
                "cell": cell,
                "start_date": pd.to_datetime(start_date),
                "note": note,
                "initial_plate_count": initial_plate_count,
                "replaced_plate_count": replaced_plate_count
            }
            if st.session_state.selected_batch is not None:
                for k,v in new_entry.items():
                    batches_df.at[st.session_state.selected_batch, k] = v
                st.success("✅ Batch updated!")
            else:
                batches_df = pd.concat([batches_df, pd.DataFrame([new_entry])], ignore_index=True)
                st.success("✅ New batch added!")
            batches_df.to_csv(batch_file, index=False)
            st.rerun()

# Column 3: Media Composition
with col3:
    st.subheader("🧪 Media Composition")
    if st.session_state.selected_batch is not None:
        sel = batches_df.loc[st.session_state.selected_batch]
        day_count = int((today - sel["start_date"].date()).days)
        protocol = mdap_protocol.get(day_count, {})
        st.markdown(f"**Day Count:** {day_count}")
        st.markdown(f"**Task:** {protocol.get('task','No task')}")
        if protocol.get("composition"):
            if day_count >= 15:
                suggested_vol = (sel["replaced_plate_count"] + 1) * 4.0
            else:
                suggested_vol = (sel["initial_plate_count"] + 1) * 4.0
            st.markdown(f"**Suggested total media volume:** {suggested_vol} mL")
            total_vol = st.number_input("Total Media Volume (mL)", value=suggested_vol, min_value=1.0, step=1.0)
            comp_rows = []
            for item in protocol["composition"]:
                name = item["component"]
                pct = item["percentage"]
                stock = item["stock_conc"]
                work = item["working_conc"]
                # Determine volume with appropriate unit
                vol = ""
                if pct not in ("", None) and not pd.isna(pct):
                    val_ml = total_vol * float(pct) / 100
                    if val_ml < 1:
                        # µL volumes as integer
                        ul_val = int(round(val_ml * 1000))
                        vol = f"{ul_val} µL"
                    else:
                        vol = f"{round(val_ml, 2)} mL"
                elif stock and work:
                    try:
                        stock_val = parse_conc(stock)
                        work_val = parse_conc(work)
                        ul_val = (work_val * total_vol * 1000) / stock_val
                        if ul_val < 1000:
                            ul_int = int(round(ul_val))
                            vol = f"{ul_int} µL"
                        else:
                            vol = f"{round(ul_val / 1000, 2)} mL"
                    except:
                        vol = ""
                comp_rows.append({"Component": name, "Volume": vol})
            comp_df = pd.DataFrame(comp_rows)
            st.dataframe(comp_df, use_container_width=True)
        else:
            st.info("No media composition defined for today.")
    else:
        st.info("Select a batch to view media.")

# Close the CSS wrapper
st.markdown("</div>", unsafe_allow_html=True)