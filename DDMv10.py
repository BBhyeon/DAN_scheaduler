import streamlit as st
import json
import os

st.set_page_config(page_title="DDM v10")

# Credentials file path
CRED_FILE = "credentials.json"

# Restore login from URL params if present
params = st.experimental_get_query_params()
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

# ---------------------- TOP-BAR LOGIN & ACCOUNT CREATION ----------------------

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
    # First column: App title or welcome
    if not st.session_state.get("logged_in", False):
        cols[0].markdown("### DAC Manager")
    else:
        cols[0].markdown(f"### Welcome, {st.session_state['username']}")

    # Second column: Username input (only if not logged in)
    with cols[1]:
        if not st.session_state.get("logged_in", False):
            username = st.text_input("", key="top_login_user", placeholder="Username", label_visibility="collapsed")
        else:
            cols[1].markdown("")

    # Third column: Password input (only if not logged in)
    with cols[2]:
        if not st.session_state.get("logged_in", False):
            password = st.text_input("", type="password", key="top_login_pass", placeholder="Password", label_visibility="collapsed")
        else:
            cols[2].markdown("")

    # Fourth column: Login or Logout button
    with cols[3]:
        if not st.session_state.get("logged_in", False):
            if st.button("Login"):
                if not username or not password:
                    st.warning("아이디와 비밀번호를 모두 입력하세요.")
                elif username not in credentials or credentials[username] != password:
                    st.error("잘못된 아이디 또는 비밀번호입니다.")
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
            if st.button("Logout"):
                for key in ["logged_in", "username", "view"]:
                    if key in st.session_state:
                        del st.session_state[key]
                try:
                    st.experimental_set_query_params()
                except Exception:
                    pass

    # Fifth column: Account creation expander (only if not logged in)
    with cols[4]:
        if not st.session_state.get("logged_in", False):
            if st.button("Create Account"):
                with st.expander("Create Account"):
                    new_user = st.text_input("New Username", key="new_user")
                    new_pass = st.text_input("New Password", type="password", key="new_pass")
                    if st.button("Save Account", key="save_account"):
                        if not new_user or not new_pass:
                            st.error("아이디와 비밀번호를 모두 입력하세요.")
                        elif new_user in credentials:
                            st.error("이미 존재하는 아이디입니다.")
                        else:
                            credentials[new_user] = new_pass
                            with open(CRED_FILE, "w") as f:
                                json.dump(credentials, f)
                            os.makedirs(os.path.join("batches", new_user), exist_ok=True)
                            st.success(f"계정 '{new_user}' 생성 완료! 로그인해주세요.")
                            try:
                                st.experimental_set_query_params()
                            except Exception:
                                pass

# If not logged in, stop rendering the rest
if not st.session_state.get("logged_in", False):
    st.stop()

# Set up user-specific batch directory
username = st.session_state["username"]
USER_BATCH_DIR = os.path.join("batches", username)
BATCH_DIR = USER_BATCH_DIR
os.makedirs(BATCH_DIR, exist_ok=True)
PROTOCOL_FILE = "DAP_protocol_extended.xlsx"
BATCHES_CSV = os.path.join(BATCH_DIR, "batches.csv")

# ---------------------- TOP-BAR NAVIGATION ----------------------
nav_bar = st.container()
with nav_bar:
    tab1, tab2, tab3 = st.columns([1, 1, 1])
    with tab1:
        if st.button("Calendar"):
            st.session_state["view"] = "Calendar"
    with tab2:
        if st.button("Tasks"):
            st.session_state["view"] = "Tasks"
    with tab3:
        if st.button("Batch Manager"):
            st.session_state["view"] = "Batch Manager"

# ... rest of the code ...

                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                USER_BATCH_DIR = os.path.join("batches", username)
                os.makedirs(USER_BATCH_DIR, exist_ok=True)
                # Persist login via URL param
                st.experimental_set_query_params(user=username)

                for key in ["logged_in", "username", "view"]:
                    if key in st.session_state:
                        del st.session_state[key]
                # Clear URL params on logout
                st.experimental_set_query_params()
