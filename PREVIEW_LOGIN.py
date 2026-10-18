"""Run from the project root: streamlit run PREVIEW_LOGIN.py"""
import streamlit as st
st.set_page_config(page_title='QUTwin · Login review',layout='wide',initial_sidebar_state='collapsed')
from authentication.session import init_session
init_session()
if st.session_state.logged_in:
    st.success('Signed in successfully as '+str(st.session_state.role)+'.')
    st.write('User ID:',st.session_state.user_id)
    st.write('Stop this preview and run `streamlit run app.py` to open the dashboard.')
    if st.button('Sign out'):
        st.session_state.clear();st.rerun()
else:
    from ui.auth_studio.page import render_auth
    render_auth()

