import streamlit as st

def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "role" not in st.session_state:
        st.session_state.role = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = None

def login_user(role, user_id):
    st.session_state.logged_in = True
    st.session_state.role = role
    st.session_state.user_id = user_id

def logout_user():
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_id = None
    st.rerun()