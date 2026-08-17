import streamlit as st

from ui.theme import apply_theme
from authentication.session import init_session, logout_user

from views.athlete_home import athlete_feature_gallery
from views.forecasting_page import athlete_forecasting
from views.model_evaluation_page import model_evaluation_dashboard

from views.auth_pages import (
    login_page,
    signup_page,
    forgot_password_page,
)

from views.athlete_pages import (
    athlete_profile,
    athlete_dashboard,
    upload_garmin_data,
    athlete_predictions,
    athlete_history,
    athlete_timeline,
    athlete_visualisations,
    athlete_simulation,
)

from views.coach_pages import (
    coach_dashboard,
    assign_athlete,
    assigned_athletes,
    coach_intelligence_dashboard,
    selected_athlete_twin_summary,
    coach_history,
    coach_timeline,
    coach_visualisations,
)


# ---------------------------------------------------------
# STREAMLIT PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Athlete Digital Twin",
    page_icon="assests/logo.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------
# INITIALISE SESSION
# ---------------------------------------------------------
init_session()


# ---------------------------------------------------------
# SESSION DEFAULTS
# ---------------------------------------------------------
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


# Apply the dashboard theme only after authentication.
# The login, signup, and password-reset pages use their own isolated styling.
if st.session_state.logged_in:
    apply_theme()


# ---------------------------------------------------------
# SIDEBAR VISIBILITY
# ---------------------------------------------------------
def hide_sidebar():
    """
    Hide the Streamlit sidebar.

    Used on:
    - Login
    - Signup
    - Forgot password
    - All athlete pages
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
    Display the coach profile information inside the sidebar.
    """
    if st.session_state.get("profile_photo"):
        st.sidebar.image(
            st.session_state.profile_photo,
            width=90,
        )

    st.sidebar.title("Coach Digital Twin")

    st.sidebar.write(
        f"Role: **{st.session_state.role}**"
    )

    st.sidebar.write(
        f"User: **{st.session_state.user_id}**"
    )

    st.sidebar.divider()


# ---------------------------------------------------------
# LOGOUT HANDLER
# ---------------------------------------------------------
def perform_logout():
    """
    Log the user out and reset navigation.
    """
    logout_user()

    st.session_state.auth_page = "Login"
    st.session_state.current_page = "Athlete Home"

    st.rerun()


# ---------------------------------------------------------
# ATHLETE TOP NAVIGATION
# ---------------------------------------------------------
def show_athlete_page_controls():
    """
    Show Home and Logout controls on athlete feature pages.

    The feature gallery itself only shows Logout because it is
    already the athlete home page.
    """
    current_page = st.session_state.get(
        "current_page",
        "Athlete Home",
    )

    home_col, space_col, logout_col = st.columns(
        [1.2, 7, 1.2]
    )

    with home_col:
        if current_page != "Athlete Home":
            if st.button(
                "Back to Home",
                key=f"athlete_home_{current_page}",
                use_container_width=True,
            ):
                st.session_state.current_page = "Athlete Home"
                st.rerun()

    with logout_col:
        if st.button(
            "Logout",
            key=f"athlete_logout_{current_page}",
            use_container_width=True,
        ):
            perform_logout()


# ---------------------------------------------------------
# ATHLETE CARD-BASED NAVIGATION
# ---------------------------------------------------------
def athlete_navigation():
    """
    Athlete navigation without a sidebar.

    The Athlete Home page displays all feature cards.
    Clicking a feature card changes current_page and opens
    the corresponding detailed feature page.
    """
    hide_sidebar()

    athlete_pages = {
        "Athlete Home": athlete_feature_gallery,
        "Profile": athlete_profile,
        "Digital Twin Dashboard": athlete_dashboard,
        "Upload Garmin Data": upload_garmin_data,
        "Predictions & Coach Recommendations": athlete_predictions,
        "Digital Twin History": athlete_history,
        "Digital Twin Timeline": athlete_timeline,
        "Visualisations / Graphs": athlete_visualisations,
        "What-if Simulation": athlete_simulation,
        "Forecasting": athlete_forecasting,
        "Model Evaluation": model_evaluation_dashboard,
    }

    current_page = st.session_state.get(
        "current_page",
        "Athlete Home",
    )

    # Reset invalid pages safely.
    if current_page not in athlete_pages:
        st.session_state.current_page = "Athlete Home"
        current_page = "Athlete Home"

    show_athlete_page_controls()

    selected_page_function = athlete_pages[current_page]
    selected_page_function()


# ---------------------------------------------------------
# COACH SIDEBAR NAVIGATION
# ---------------------------------------------------------
def coach_navigation():
    """
    Coach navigation continues to use the sidebar.
    """
    coach_menu = [
        "Digital Twin Dashboard",
        "Assign Athlete to Coach",
        "Assigned Athletes",
        "Coach Intelligence Dashboard",
        "Selected Athlete Twin Summary",
        "Digital Twin History",
        "Digital Twin Timeline",
        "Visualisations / Graphs",
        "Model Evaluation",
    ]

    current_page = st.session_state.get(
        "current_page",
        "Digital Twin Dashboard",
    )

    if current_page not in coach_menu:
        st.session_state.current_page = "Digital Twin Dashboard"
        current_page = "Digital Twin Dashboard"

    selected_page = st.sidebar.radio(
        "Coach Navigation",
        coach_menu,
        index=coach_menu.index(current_page),
    )

    st.session_state.current_page = selected_page

    coach_pages = {
        "Digital Twin Dashboard": coach_dashboard,
        "Assign Athlete to Coach": assign_athlete,
        "Assigned Athletes": assigned_athletes,
        "Coach Intelligence Dashboard": coach_intelligence_dashboard,
        "Selected Athlete Twin Summary": selected_athlete_twin_summary,
        "Digital Twin History": coach_history,
        "Digital Twin Timeline": coach_timeline,
        "Visualisations / Graphs": coach_visualisations,
        "Model Evaluation": model_evaluation_dashboard,
    }

    selected_page_function = coach_pages[selected_page]
    selected_page_function()


# ---------------------------------------------------------
# AUTHENTICATION ROUTING
# ---------------------------------------------------------
if not st.session_state.logged_in:
    hide_sidebar()

    if st.session_state.auth_page == "Signup":
        signup_page()

    elif st.session_state.auth_page == "Forgot Password":
        forgot_password_page()

    else:
        login_page()


# ---------------------------------------------------------
# LOGGED-IN ROUTING
# ---------------------------------------------------------
else:
    if st.session_state.role == "Athlete":
        athlete_navigation()
        
    elif st.session_state.role == "Coach":
        # Coach continues using sidebar navigation.
        show_coach_sidebar()
        coach_navigation()

        st.sidebar.divider()

        if st.sidebar.button(
            "Logout",
            use_container_width=True,
        ):
            perform_logout()

    else:
        st.error(
            "The account role could not be identified. "
            "Please log in again."
        )

        if st.button("Return to Login"):
            perform_logout()