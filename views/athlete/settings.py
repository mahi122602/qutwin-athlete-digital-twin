import streamlit as st
from ui.studio_shell import chapter
from views.athlete.account_helpers import perform_logout

def athlete_settings_page():
    st.title('Make it yours')
    chapter('PREFERENCES / YOUR SPACE','Choose your studio appearance and manage your account. Your activity stays saved when you log out.')
    with st.container(border=True):
        st.subheader('Appearance')
        st.caption('Choose Dawn or Dusk on your dashboard. Your choice follows you through every athlete page in this session.')
    with st.container(border=True):
        st.subheader('Profile preferences')
        from database.forecasting_repository import get_forecasting_profile,set_athlete_gender,ensure_forecasting_schema
        try:
            ensure_forecasting_schema();profile=get_forecasting_profile(str(st.session_state.user_id))
            options=['Prefer not to say','Female','Male','Non-binary']
            current=profile.get('gender');choice=st.selectbox('Gender (optional)',options,index=options.index(current) if current in options else 0)
            st.caption('Female profiles can opt into private period tracking on Forecasting. General forecasts are available without it.')
            if st.button('Save profile preference'):set_athlete_gender(str(st.session_state.user_id),choice);st.success('Preference saved.')
        except Exception:st.info('Profile preferences are temporarily unavailable.')
    left,right=st.columns(2)
    if left.button('Open my profile',use_container_width=True):st.session_state.current_page='Profile';st.rerun()
    if right.button('Log out',use_container_width=True):perform_logout()
    st.caption('Account deletion is available in My profile, with password verification and a permanent-deletion confirmation.')
