import streamlit as st
from views.athlete.account_helpers import perform_logout

def athlete_settings_page():
    """
    Basic Athlete account/settings screen.
    """

    athlete_id = str(
        st.session_state.user_id
    )

    st.title(
        "Settings"
    )

    st.caption(
        "Manage your account and Athlete Dashboard preferences."
    )

    account_tab, notifications_tab, privacy_tab = (
        st.tabs(
            [
                "Account",
                "Notifications",
                "Privacy & Security",
            ]
        )
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    with account_tab:

        st.subheader(
            "Account"
        )

        st.write(
            f"**Athlete ID:** {athlete_id}"
        )

        st.write(
            "**Role:** Athlete"
        )

        st.caption(
            "Profile information can be edited "
            "from your Athlete Profile page."
        )

        if st.button(
            "Open Profile",
            key="settings_open_profile",
            type="primary",
        ):

            st.session_state.current_page = (
                "Profile"
            )

            st.rerun()

    # ========================================================
    # NOTIFICATION SETTINGS
    # ========================================================

    with notifications_tab:

        st.subheader(
            "Notification Preferences"
        )

        st.caption(
            "These preferences currently apply "
            "to this Streamlit session."
        )

        st.toggle(
            "Connection request notifications",
            value=True,
            key="setting_connection_notifications",
        )

        st.toggle(
            "Coach recommendation notifications",
            value=True,
            key="setting_coach_notifications",
        )

        st.toggle(
            "Injury risk alerts",
            value=True,
            key="setting_risk_notifications",
        )

        st.toggle(
            "Digital Twin status updates",
            value=True,
            key="setting_twin_notifications",
        )

    # ========================================================
    # PRIVACY / SECURITY
    # ========================================================

    with privacy_tab:

        st.subheader(
            "Privacy & Security"
        )

        st.write(
            "Your Athlete account is authenticated "
            "before access to your Digital Twin data."
        )

        st.caption(
            "Use Logout whenever you finish using "
            "QUTwin on a shared device."
        )

        st.divider()

        if st.button(
            "Logout",
            key="settings_logout",
            type="primary",
        ):

            perform_logout()
