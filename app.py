import streamlit as st
from utils.performance import begin_run
begin_run()

from datetime import datetime, timedelta

from ui.theme import apply_theme
from authentication.session import init_session, logout_user

def athlete_feature_gallery(*args, **kwargs):
    from views.athlete_home import athlete_feature_gallery as page
    return page(*args, **kwargs)

def _render_athlete_top_navigation(*args, **kwargs):
    from views.athlete_home import _render_athlete_top_navigation as page
    return page(*args, **kwargs)


def athlete_forecasting(*args, **kwargs):
    from views.forecasting_page import athlete_forecasting as page
    return page(*args, **kwargs)

def model_evaluation_dashboard(*args, **kwargs):
    from views.model_evaluation_page import model_evaluation_dashboard as page
    return page(*args, **kwargs)



def login_page(*args, **kwargs):
    from views.auth_pages import login_page as page
    return page(*args, **kwargs)

def signup_page(*args, **kwargs):
    from views.auth_pages import signup_page as page
    return page(*args, **kwargs)

def forgot_password_page(*args, **kwargs):
    from views.auth_pages import forgot_password_page as page
    return page(*args, **kwargs)


def athlete_profile(*args, **kwargs):
    from views.athlete_pages import athlete_profile as page
    return page(*args, **kwargs)

def athlete_dashboard(*args, **kwargs):
    from views.athlete_pages import athlete_dashboard as page
    return page(*args, **kwargs)

def upload_garmin_data(*args, **kwargs):
    from views.athlete_pages import upload_garmin_data as page
    return page(*args, **kwargs)

def athlete_predictions(*args, **kwargs):
    from views.athlete_pages import athlete_predictions as page
    return page(*args, **kwargs)

def athlete_history(*args, **kwargs):
    from views.athlete_pages import athlete_history as page
    return page(*args, **kwargs)

def athlete_visualisations(*args, **kwargs):
    from views.athlete_pages import athlete_visualisations as page
    return page(*args, **kwargs)

def athlete_simulation(*args, **kwargs):
    from views.athlete_pages import athlete_simulation as page
    return page(*args, **kwargs)


def coach_dashboard(*args, **kwargs):
    from views.coach_pages import coach_dashboard as page
    return page(*args, **kwargs)

def assigned_athletes(*args, **kwargs):
    from views.coach_pages import assigned_athletes as page
    return page(*args, **kwargs)

def coach_intelligence_dashboard(*args, **kwargs):
    from views.coach_pages import coach_intelligence_dashboard as page
    return page(*args, **kwargs)

def selected_athlete_twin_summary(*args, **kwargs):
    from views.coach_pages import selected_athlete_twin_summary as page
    return page(*args, **kwargs)

def coach_history(*args, **kwargs):
    from views.coach_pages import coach_history as page
    return page(*args, **kwargs)

def coach_timeline(*args, **kwargs):
    from views.coach_pages import coach_timeline as page
    return page(*args, **kwargs)

def coach_visualisations(*args, **kwargs):
    from views.coach_pages import coach_visualisations as page
    return page(*args, **kwargs)

def coach_portal(*args, **kwargs):
    from views.coach_pages import coach_portal as page
    return page(*args, **kwargs)


from database.athlete_repository import (
    get_athlete_profile,
)

from database.connection_request_repository import (
    get_notifications,
    get_unread_notification_count,
    get_incoming_connection_requests,
    respond_to_connection_request,
    mark_notification_read,
    mark_all_notifications_read,
)

def athlete_requests_page(*args, **kwargs):
    from views.request_pages import athlete_requests_page as page
    return page(*args, **kwargs)

def coach_requests_page(*args, **kwargs):
    from views.request_pages import coach_requests_page as page
    return page(*args, **kwargs)


# ============================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Athlete Digital Twin",
    page_icon="assests/logo.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# INITIALISE SESSION
# ============================================================

init_session()


# ============================================================
# SESSION DEFAULTS
# ============================================================

if "auth_page" not in st.session_state:
    st.session_state.auth_page = "Login"

if "current_page" not in st.session_state:
    st.session_state.current_page = "Athlete Home"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

if "user_id" not in st.session_state:
    st.session_state.user_id = None


# ============================================================
# APPLY THEME AFTER AUTHENTICATION
# ============================================================

if st.session_state.logged_in:
    apply_theme()


# ============================================================
# SIDEBAR VISIBILITY
# ============================================================

def hide_sidebar():
    """
    Hide Streamlit sidebar.

    Used for:
    - Login
    - Signup
    - Forgot Password
    - All Athlete pages
    """

    st.markdown(
        """
        <style>

        section[data-testid="stSidebar"] {
            display: none !important;
        }

        button[data-testid="stSidebarCollapseButton"] {
            display: none !important;
        }

        [data-testid="collapsedControl"] {
            display: none !important;
        }

        .main .block-container {
            max-width: 100% !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def show_coach_sidebar():
    """
    Display coach information inside the sidebar.
    """

    if st.session_state.get("profile_photo"):

        st.sidebar.image(
            st.session_state.profile_photo,
            width=90,
        )

    st.sidebar.title(
        "Coach Digital Twin"
    )

    st.sidebar.write(
        f"Role: **{st.session_state.role}**"
    )

    st.sidebar.write(
        f"User: **{st.session_state.user_id}**"
    )

    st.sidebar.divider()


# ============================================================
# LOGOUT
# ============================================================

def perform_logout():
    """
    Reset navigation before logout_user() performs its rerun.
    """

    st.session_state.auth_page = "Login"

    st.session_state.current_page = (
        "Athlete Home"
    )

    logout_user()


# ============================================================
# ATHLETE HEADER DATA
# ============================================================

def render_athlete_global_navigation():
    """
    Render the same Athlete header/nav on Athlete feature pages.

    Athlete Home already renders this inside athlete_home.py,
    so this helper is used only on the other pages.
    """

    athlete_id = str(
        st.session_state.user_id
    )

    try:
        profile = get_athlete_profile(
            athlete_id
        )
    except Exception:
        profile = None

    try:
        unread_count = (
            get_unread_notification_count(
                "Athlete",
                athlete_id,
            )
        )
    except Exception:
        unread_count = 0

    _render_athlete_top_navigation(
        profile,
        unread_count,
    )


# ============================================================
# ATHLETE PAGE CONTROLS
# ============================================================

def show_athlete_page_controls():
    """
    Small controls below the main Athlete navigation.

    Home:
        no Back button

    Feature pages:
        Back to Home

    Logout remains available on every non-home Athlete page.
    """

    current_page = (
        st.session_state.get(
            "current_page",
            "Athlete Home",
        )
    )

    home_col, space_col, logout_col = (
        st.columns(
            [1.4, 7.2, 1.4]
        )
    )

    with home_col:

        if current_page != "Athlete Home":

            if st.button(
                "← Back to Home",
                key=(
                    f"athlete_home_"
                    f"{current_page}"
                ),
                use_container_width=True,
            ):
                st.session_state.current_page = (
                    "Athlete Home"
                )

                st.rerun()

    with logout_col:

        if st.button(
            "Logout",
            key=(
                f"athlete_logout_"
                f"{current_page}"
            ),
            use_container_width=True,
        ):
            perform_logout()


# ============================================================
# NOTIFICATION HELPERS
# ============================================================

def _notification_icon(
    notification_type,
):

    if notification_type == "Request Accepted":
        return "✅"

    if notification_type == "Request Rejected":
        return "❌"

    if notification_type == "Connection Request":
        return "🤝"

    if notification_type == "Risk Alert":
        return "⚠️"

    if notification_type == "Coach Recommendation":
        return "💬"

    return "🔔"


def _notification_destination(
    notification_type,
):
    """
    Return the appropriate Athlete page for a notification.

    Risk alerts:
        Digital Twin Dashboard

    Coach recommendations:
        Prediction page

    Request status:
        Profile for now.
    """

    if notification_type == "Risk Alert":
        return "Digital Twin Dashboard"

    if notification_type == "Coach Recommendation":
        return (
            "Predictions & Coach Recommendations"
        )

    if notification_type in {
        "Request Accepted",
        "Request Rejected",
    }:
        return "Profile"

    return None


# ============================================================
# ATHLETE NOTIFICATIONS PAGE
# ============================================================

def athlete_notifications_page(*args, **kwargs):
    from views.athlete.notifications import athlete_notifications_page as page
    return page(*args, **kwargs)



# ============================================================
# ATHLETE SETTINGS PAGE
# ============================================================

def athlete_settings_page(*args, **kwargs):
    from views.athlete.settings import athlete_settings_page as page
    return page(*args, **kwargs)



# ============================================================
# ATHLETE NAVIGATION
# ============================================================

def athlete_navigation():
    """
    Central Athlete router.

    Athlete Home:
        athlete_home.py renders the header/nav itself.

    Other Athlete pages:
        app.py renders the same global header/nav before
        rendering the selected page.
    """

    hide_sidebar()

    athlete_pages = {

        "Athlete Home":
            athlete_feature_gallery,

        "Profile":
            athlete_profile,

        "Digital Twin Dashboard":
            athlete_dashboard,

        "Upload Garmin Data":
            upload_garmin_data,

        "Predictions & Coach Recommendations":
            athlete_predictions,

        "Digital Twin History":
            athlete_history,

        "Visualisations / Graphs":
            athlete_visualisations,

        "What-if Simulation":
            athlete_simulation,

        "Forecasting":
            athlete_forecasting,

        "Requests":
            athlete_requests_page,

        "Model Evaluation":
            model_evaluation_dashboard,

        # NEW
        "Notifications":
            athlete_notifications_page,

        # NEW
        "Settings":
            athlete_settings_page,
    }

    current_page = (
        st.session_state.get(
            "current_page",
            "Athlete Home",
        )
    )

    # ========================================================
    # INVALID ROUTE SAFETY
    # ========================================================

    if current_page not in athlete_pages:

        st.session_state.current_page = (
            "Athlete Home"
        )

        current_page = (
            "Athlete Home"
        )

    # ========================================================
    # ATHLETE HOME
    # ========================================================

    if current_page == "Athlete Home":

        athlete_feature_gallery()

        return

    # ========================================================
    # ALL OTHER ATHLETE PAGES
    # ========================================================

    render_athlete_global_navigation()

    with st.container(key="athlete_page_content"):
        show_athlete_page_controls()

        selected_page_function = (
            athlete_pages[
                current_page
            ]
        )

        selected_page_function()


# ============================================================
# COACH SIDEBAR NAVIGATION
# ============================================================

def coach_navigation():
    """
    Coach navigation continues to use the sidebar.
    """

    coach_menu = [

        "Digital Twin Dashboard",

        "Assigned Athletes",

        "Requests",

        "Coach Intelligence Dashboard",

        "Selected Athlete Twin Summary",

        "Digital Twin History",

        "Digital Twin Timeline",

        "Visualisations / Graphs",

        "Model Evaluation",
    ]

    current_page = (
        st.session_state.get(
            "current_page",
            "Digital Twin Dashboard",
        )
    )

    if current_page not in coach_menu:

        st.session_state.current_page = (
            "Digital Twin Dashboard"
        )

        current_page = (
            "Digital Twin Dashboard"
        )

    selected_page = (
        st.sidebar.radio(
            "Coach Navigation",
            coach_menu,
            index=coach_menu.index(
                current_page
            ),
        )
    )

    st.session_state.current_page = (
        selected_page
    )

    coach_pages = {

        "Digital Twin Dashboard":
            coach_dashboard,

        "Assigned Athletes":
            assigned_athletes,

        "Requests": 
            coach_requests_page,

        "Coach Intelligence Dashboard":
            coach_intelligence_dashboard,

        "Selected Athlete Twin Summary":
            selected_athlete_twin_summary,

        "Digital Twin History":
            coach_history,

        "Digital Twin Timeline":
            coach_timeline,

        "Visualisations / Graphs":
            coach_visualisations,

        "Model Evaluation":
            model_evaluation_dashboard,
    }

    selected_page_function = (
        coach_pages[
            selected_page
        ]
    )

    selected_page_function()


# ============================================================
# AUTHENTICATION ROUTING
# ============================================================

if not st.session_state.logged_in:

    hide_sidebar()

    if (
        st.session_state.auth_page
        == "Signup"
    ):

        signup_page()

    elif (
        st.session_state.auth_page
        == "Forgot Password"
    ):

        forgot_password_page()

    else:

        login_page()


# ============================================================
# LOGGED-IN ROUTING
# ============================================================

else:

    # ========================================================
    # ATHLETE
    # ========================================================

    if (
        st.session_state.role
        == "Athlete"
    ):

        athlete_navigation()

    # ========================================================
    # COACH
    # ========================================================

    elif st.session_state.role == "Coach":
        hide_sidebar()
        coach_portal()

    # ========================================================
    # INVALID ROLE
    # ========================================================

    else:

        st.error(
            "The account role could not be identified. "
            "Please log in again."
        )

        if st.button(
            "Return to Login"
        ):

            perform_logout()