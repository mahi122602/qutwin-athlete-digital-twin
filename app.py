import streamlit as st

from datetime import datetime, timedelta

from ui.theme import apply_theme
from authentication.session import init_session, logout_user

from views.athlete_home import (
    athlete_feature_gallery,
    _render_athlete_top_navigation,
)

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

def athlete_notifications_page():
    """
    Dedicated Athlete Notifications page.

    Shows:
    - pending coach connection requests
    - Accept / Reject controls
    - notifications from the last 14 days
    - unread/read state
    """

    athlete_id = str(
        st.session_state.user_id
    )

    st.title("Notifications")

    st.caption(
        "Connection requests, request updates, "
        "risk alerts, coach recommendations and "
        "other important updates from the last 14 days."
    )

    # ========================================================
    # LOAD NOTIFICATIONS
    # ========================================================

    try:

        notifications = get_notifications(
            "Athlete",
            athlete_id,
            limit=100,
        )

        incoming_requests = (
            get_incoming_connection_requests(
                "Athlete",
                athlete_id,
            )
        )

        unread_count = (
            get_unread_notification_count(
                "Athlete",
                athlete_id,
            )
        )

    except Exception as exc:

        st.error(
            f"Notifications could not be loaded: {exc}"
        )

        return

    # ========================================================
    # PAGE SUMMARY
    # ========================================================

    summary_col_1, summary_col_2 = (
        st.columns(2)
    )

    with summary_col_1:

        st.metric(
            "Unread Notifications",
            unread_count,
        )

    with summary_col_2:

        st.metric(
            "Pending Coach Requests",
            len(incoming_requests),
        )

    if unread_count > 0:

        if st.button(
            "Mark all notifications as read",
            key="notification_page_mark_all_read",
        ):

            try:

                mark_all_notifications_read(
                    "Athlete",
                    athlete_id,
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    f"Notifications could not be updated: {exc}"
                )

    st.divider()

    # ========================================================
    # CONNECTION REQUESTS
    # ========================================================

    st.subheader(
        "Coach Connection Requests"
    )

    if not incoming_requests:

        st.info(
            "You do not currently have any "
            "pending coach connection requests."
        )

    else:

        for request in incoming_requests:

            request_id = (
                request["request_id"]
            )

            coach_id = (
                request["sender_id"]
            )

            coach_name = (
                request.get("sender_name")
                or "Coach"
            )

            message = (
                request.get("message")
                or "No message provided."
            )

            created_at = (
                request.get("created_at")
            )

            with st.container(
                border=True
            ):

                title_col, badge_col = (
                    st.columns(
                        [4, 1]
                    )
                )

                with title_col:

                    st.markdown(
                        f"### 🤝 {coach_name}"
                    )

                    st.caption(
                        f"Coach ID: {coach_id}"
                    )

                with badge_col:

                    st.warning(
                        "Pending"
                    )

                st.write(message)

                if created_at:

                    try:

                        st.caption(
                            "Received: "
                            f"{created_at:%d %b %Y, %H:%M}"
                        )

                    except Exception:

                        st.caption(
                            f"Received: {created_at}"
                        )

                accept_col, reject_col = (
                    st.columns(2)
                )

                with accept_col:

                    if st.button(
                        "Accept",
                        key=(
                            f"notification_accept_"
                            f"{request_id}"
                        ),
                        type="primary",
                        use_container_width=True,
                    ):

                        try:

                            respond_to_connection_request(
                                request_id=request_id,
                                responder_role="Athlete",
                                responder_id=athlete_id,
                                decision="Accepted",
                            )

                            # Mark original request
                            # notification as read.
                            for notification in notifications:

                                if (
                                    notification.get(
                                        "request_id"
                                    )
                                    == request_id
                                    and
                                    notification.get(
                                        "notification_type"
                                    )
                                    == "Connection Request"
                                ):

                                    mark_notification_read(
                                        notification[
                                            "notification_id"
                                        ],
                                        "Athlete",
                                        athlete_id,
                                    )

                            st.success(
                                f"You are now connected "
                                f"with Coach {coach_id}."
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Request could not be accepted: {exc}"
                            )

                with reject_col:

                    if st.button(
                        "Reject",
                        key=(
                            f"notification_reject_"
                            f"{request_id}"
                        ),
                        use_container_width=True,
                    ):

                        try:

                            respond_to_connection_request(
                                request_id=request_id,
                                responder_role="Athlete",
                                responder_id=athlete_id,
                                decision="Rejected",
                            )

                            for notification in notifications:

                                if (
                                    notification.get(
                                        "request_id"
                                    )
                                    == request_id
                                    and
                                    notification.get(
                                        "notification_type"
                                    )
                                    == "Connection Request"
                                ):

                                    mark_notification_read(
                                        notification[
                                            "notification_id"
                                        ],
                                        "Athlete",
                                        athlete_id,
                                    )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Request could not be rejected: {exc}"
                            )

    # ========================================================
    # LAST 14 DAYS
    # ========================================================

    st.divider()

    st.subheader(
        "Last 14 Days"
    )

    cutoff = (
        datetime.now()
        - timedelta(days=14)
    )

    recent_notifications = []

    for notification in notifications:

        created_at = (
            notification.get(
                "created_at"
            )
        )

        if created_at is None:

            recent_notifications.append(
                notification
            )

            continue

        try:

            if created_at >= cutoff:

                recent_notifications.append(
                    notification
                )

        except TypeError:

            recent_notifications.append(
                notification
            )

    if not recent_notifications:

        st.info(
            "No notifications were received "
            "during the last 14 days."
        )

        return

    # ========================================================
    # NOTIFICATION CARDS
    # ========================================================

    for notification in recent_notifications:

        notification_id = (
            notification[
                "notification_id"
            ]
        )

        notification_type = (
            notification.get(
                "notification_type",
                "Notification",
            )
        )

        notification_message = (
            notification.get(
                "message"
            )
            or "Notification update."
        )

        is_read = bool(
            notification.get(
                "is_read",
                False,
            )
        )

        created_at = (
            notification.get(
                "created_at"
            )
        )

        icon = _notification_icon(
            notification_type
        )

        destination = (
            _notification_destination(
                notification_type
            )
        )

        with st.container(
            border=True
        ):

            title_col, status_col = (
                st.columns(
                    [4, 1]
                )
            )

            with title_col:

                st.markdown(
                    f"### {icon} "
                    f"{notification_type}"
                )

            with status_col:

                if is_read:

                    st.caption(
                        "Read"
                    )

                else:

                    st.info(
                        "New"
                    )

            st.write(
                notification_message
            )

            if created_at:

                try:

                    st.caption(
                        f"{created_at:%d %b %Y, %H:%M}"
                    )

                except Exception:

                    st.caption(
                        str(created_at)
                    )

            action_col_1, action_col_2 = (
                st.columns(
                    [1, 1]
                )
            )

            # -----------------------------------------------
            # MARK READ
            # -----------------------------------------------

            with action_col_1:

                if not is_read:

                    if st.button(
                        "Mark as read",
                        key=(
                            f"mark_notification_"
                            f"{notification_id}"
                        ),
                        use_container_width=True,
                    ):

                        try:

                            mark_notification_read(
                                notification_id,
                                "Athlete",
                                athlete_id,
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Notification could not "
                                f"be updated: {exc}"
                            )

            # -----------------------------------------------
            # OPEN RELATED PAGE
            # -----------------------------------------------

            with action_col_2:

                if destination:

                    if st.button(
                        "Open related page →",
                        key=(
                            f"open_notification_"
                            f"{notification_id}"
                        ),
                        use_container_width=True,
                    ):

                        if not is_read:

                            try:

                                mark_notification_read(
                                    notification_id,
                                    "Athlete",
                                    athlete_id,
                                )

                            except Exception:

                                pass

                        st.session_state.current_page = (
                            destination
                        )

                        st.rerun()


# ============================================================
# ATHLETE SETTINGS PAGE
# ============================================================

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

        "Digital Twin Timeline":
            athlete_timeline,

        "Visualisations / Graphs":
            athlete_visualisations,

        "What-if Simulation":
            athlete_simulation,

        "Forecasting":
            athlete_forecasting,

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

        "Assign Athlete to Coach",

        "Assigned Athletes",

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

        "Assign Athlete to Coach":
            assign_athlete,

        "Assigned Athletes":
            assigned_athletes,

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

    elif (
        st.session_state.role
        == "Coach"
    ):

        show_coach_sidebar()

        coach_navigation()

        st.sidebar.divider()

        if st.sidebar.button(
            "Logout",
            use_container_width=True,
        ):

            perform_logout()

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