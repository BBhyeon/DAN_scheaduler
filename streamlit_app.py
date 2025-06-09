import streamlit as st
import pandas as pd
from pandas import ExcelWriter
from datetime import datetime, timedelta
import os
import json
import re
from PIL import Image
from streamlit_sortables import sort_items

# Google Sheets client
import gspread
from oauth2client.client import GoogleCredentials
import re

st.set_page_config(page_title="DAC_manager_v11", layout="wide")

# ---------------------- SHEETS SETUP (public URL) ----------------------
# Use a publicly-shared Google Sheet:
SHARE_URL = "https://docs.google.com/spreadsheets/d/1Mptw9CCbi0fWRANxyRm1p-WeQRoGQAWkx3yGhlV9HSU/edit?usp=sharing"
# Extract the sheet ID from the sharing URL
match = re.search(r"/d/([a-zA-Z0-9-_]+)", SHARE_URL)
if not match:
    st.error(f"Could not parse sheet ID from URL: {SHARE_URL}")
    st.stop()
SHEET_ID = match.group(1)

# Authorize using application default credentials (sheet must be "anyone with link can edit")
gc = gspread.authorize(GoogleCredentials.get_application_default())

# Open the 'info' and 'cell_counts' worksheets
sheet_info   = gc.open_by_key(SHEET_ID).worksheet("info")
sheet_counts = gc.open_by_key(SHEET_ID).worksheet("cell_counts")

# ---------------------- HELPERS ----------------------
@st.cache_data(ttl=300)
def load_batches_from_sheets(username):
    df = pd.DataFrame(sheet_info.get_all_records())
    df = df[df["username"] == username]
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
    df["end_date"]   = pd.to_datetime(df["end_date"], errors="coerce").dt.date
    return df

def save_batch_to_sheets(username, batch_id, info_row: dict, counts_df: pd.DataFrame):
    # --- Info sheet update ---
    all_info = pd.DataFrame(sheet_info.get_all_records())
    mask = ~((all_info["username"]==username)&(all_info["batch_id"]==batch_id))
    df_keep = all_info[mask].append(
        {"username":username,"batch_id":batch_id,**info_row},
        ignore_index=True
    )
    sheet_info.clear()
    sheet_info.update([df_keep.columns.tolist()] + df_keep.values.tolist())

    # --- CellCounts sheet update ---
    flat = counts_df.reset_index().melt(
        id_vars="index", var_name="time", value_name="value"
    ).rename(columns={"index":"phase"})
    flat["username"] = username
    flat["batch_id"] = batch_id

    all_counts = pd.DataFrame(sheet_counts.get_all_records())
    mask_c = ~((all_counts["username"]==username)&(all_counts["batch_id"]==batch_id))
    dfc_keep = all_counts[mask_c].append(flat, ignore_index=True)

    sheet_counts.clear()
    sheet_counts.update([dfc_keep.columns.tolist()] + dfc_keep.values.tolist())

# ---------------------- AUTH ----------------------
CRED_FILE = "credentials.json"
if not os.path.exists(CRED_FILE):
    with open(CRED_FILE, "w") as f:
        json.dump({}, f)
with open(CRED_FILE, "r") as f:
    credentials = json.load(f)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "show_create" not in st.session_state:
    st.session_state["show_create"] = False

# Restore from URL params
params = st.query_params
if "user" in params and params["user"]:
    user_param = params["user"][0]
    if user_param in credentials:
        st.session_state["logged_in"] = True
        st.session_state["username"]  = user_param

# Top-bar login / logout / new account
top = st.container()
with top:
    cols = st.columns([2,2,2,2,1])
    if not st.session_state["logged_in"]:
        cols[0].markdown("### DAC Manager")
        with cols[1]:
            username = st.text_input("", placeholder="Username", label_visibility="collapsed")
        with cols[2]:
            password = st.text_input("", type="password", placeholder="Password", label_visibility="collapsed")
        with cols[3]:
            if st.button("Login"):
                if not username or not password:
                    st.warning("Enter both username and password.")
                elif username not in credentials or credentials[username]!=password:
                    st.error("Invalid credentials.")
                else:
                    st.session_state["logged_in"] = True
                    st.session_state["username"]  = username
                    try:
                        st.experimental_set_query_params(user=username)
                    except:
                        pass
        with cols[4]:
            if st.button("New Account"):
                st.session_state["show_create"] = True
    else:
        cols[0].markdown(f"### Welcome, {st.session_state['username']}!")
        cols[3].button("Logout", on_click=lambda: st.session_state.clear(), key="logout")

if not st.session_state["logged_in"] and st.session_state["show_create"]:
    st.subheader("Create New Account")
    new_u = st.text_input("New Username", key="u2")
    new_p = st.text_input("New Password", type="password", key="p2")
    if st.button("Save Account"):
        if not new_u or not new_p:
            st.error("Enter both fields.")
        elif new_u in credentials:
            st.error("Username exists.")
        else:
            credentials[new_u] = new_p
            with open(CRED_FILE,"w") as f:
                json.dump(credentials,f)
            st.success(f"Account '{new_u}' created. Please login.")
            st.session_state["show_create"] = False
    st.stop()

if not st.session_state["logged_in"]:
    st.stop()

username = st.session_state["username"]
today = datetime.today().date()

# Navigation bar
nav = st.container()
with nav:
    t1,t2,t3,t4 = st.columns([1,1,1,1])
    if t1.button("Calendar"):     st.session_state["view"]="Calendar"
    if t2.button("Tasks"):        st.session_state["view"]="Tasks"
    if t3.button("Batch Manager"):st.session_state["view"]="Batch Manager"
    if t4.button("Image Viewer"): st.session_state["view"]="Image Viewer"

# Default view
if "view" not in st.session_state:
    st.session_state["view"]="Calendar"

# ---------------------- Calendar View ----------------------
def make_calendar(df, today, length=22):
    dates = [today+timedelta(days=i) for i in range(length)]
    cols = pd.MultiIndex.from_tuples(
        [(d.year, d.strftime("%b"), d.strftime("%a %d")) for d in dates],
        names=["Year","Month","Day"]
    )
    cal = pd.DataFrame(index=df.batch_id.astype(str), columns=cols)
    for _,r in df.iterrows():
        sd,ed = r.start_date, r.end_date or (r.start_date+timedelta(days=length))
        idx = sd
        di = 0
        while idx<=ed:
            if idx in dates:
                key=(idx.year, idx.strftime("%b"), idx.strftime("%a %d"))
                cal.loc[str(r.batch_id),key]=di
            idx+=timedelta(days=1); di+=1
    return cal

def style_cal(df, today):
    yellow={1,2,4,6,8,9,10,12,14,16,18,20}; blue={15,21}
    styles=pd.DataFrame("",index=df.index,columns=df.columns)
    first=df.columns[0]
    for r in df.index:
        for c in df.columns:
            v=df.loc[r,c]
            if pd.isna(v): continue
            d=int(float(v))
            if d in yellow: styles.at[r,c]="background-color:#fff3b0"
            if d in blue:   styles.at[r,c]="background-color:#add8e6"
    for r in df.index:
        styles.at[r,first]+=("; border:3px solid red")
    return styles

if st.session_state["view"]=="Calendar":
    dfb = load_batches_from_sheets(username)
    st.subheader("📆 Differentiation Calendar")
    if dfb.empty:
        st.info("No ongoing batches.")
    else:
        cal = make_calendar(dfb,today)
        st.dataframe(cal.style.apply(style_cal,today=today), use_container_width=True)

# ---------------------- Tasks View ----------------------
if st.session_state["view"]=="Tasks":
    dfb = load_batches_from_sheets(username)
    st.subheader("📌 Batch Tasks")
    sel_date=st.date_input("Select Date",value=today)
    if dfb.empty:
        st.info("No ongoing batches.")
    else:
        # load protocol and show tasks per batch...
        st.write("Tasks implementation here")  # 생략

# ---------------------- Batch Manager ----------------------
if st.session_state["view"]=="Batch Manager":
    st.subheader("📋 Batch Manager")
    dfb = load_batches_from_sheets(username)

    mode = st.radio("Mode",["Add","Edit"], horizontal=True)
    if mode=="Add":
        new_id = st.number_input("Batch ID",min_value=1,value=1)
        c = st.text_input("Cell Type")
        s = st.date_input("Start Date",value=today)
        e = st.date_input("End Date",value=today+timedelta(days=21))
        n = st.text_area("Note")
        # cell counts editor
        cols = ["A","B","C"]+[str(i) for i in range(1,16)]
        idx  = ["Day 15","Day 21","Banking"]
        dfc  = pd.DataFrame(index=idx,columns=cols)
        edited = st.data_editor(dfc,use_container_width=True)
        if st.button("Save New Batch"):
            info = {
                "cell":c, "start_date":s.strftime("%Y.%m.%d"),
                "end_date":e.strftime("%Y.%m.%d"), "note":n,
                "day15":"", "day21":"", "banking":""
            }
            save_batch_to_sheets(username,new_id,info,edited)
            st.success(f"Batch {new_id} saved.")
    else:
        bid = st.number_input("Batch ID to Load",min_value=1,value=1)
        rec = dfb[dfb.batch_id==bid]
        if rec.empty:
            st.error("Not found.")
        else:
            r = rec.iloc[0]
            c = st.text_input("Cell Type", value=r.cell)
            s = st.date_input("Start Date",value=r.start_date)
            e = st.date_input("End Date",value=r.end_date or today+timedelta(days=21))
            n = st.text_area("Note", value=r.note)
            cols = ["A","B","C"]+[str(i) for i in range(1,16)]
            dfc = pd.DataFrame(index=["Day 15","Day 21","Banking"],columns=cols)
            dfc = dfc  # placeholder; 실제 로딩 로직은 sheet_counts에서 불러온 후 설정하세요
            edited = st.data_editor(dfc,use_container_width=True)
            if st.button("Update Batch"):
                info = {
                    "cell":c, "start_date":s.strftime("%Y.%m.%d"),
                    "end_date":e.strftime("%Y.%m.%d"), "note":n,
                    "day15":"", "day21":"", "banking":""
                }
                save_batch_to_sheets(username,bid,info,edited)
                st.success(f"Batch {bid} updated.")

# ---------------------- Image Viewer ----------------------
if st.session_state["view"]=="Image Viewer":
    st.subheader("🖼️ Image Viewer")
    uploaded = st.file_uploader("Upload images", type=["jpg","png"], accept_multiple_files=True)
    if not uploaded:
        st.info("Please upload.")
    else:
        groups={}
        for f in uploaded:
            m = re.search(r"DIF(\d+)_D(\d+)_",f.name)
            bid = m.group(1) if m else "Unknown"
            day = m.group(2) if m else "Unknown"
            groups.setdefault((bid,day),[]).append(f)
        for (bid,day),files in groups.items():
            st.markdown(f"**Batch {bid} - Day {day}**")
            cols = st.columns(4)
            for i,f in enumerate(files):
                img = Image.open(f)
                cols[i%4].image(img,use_container_width=True)