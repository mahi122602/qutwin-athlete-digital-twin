import base64
import html

import pandas as pd
import streamlit as st

from authentication.session import logout_user
from database.connection_request_repository import (
    get_notifications,
    get_unread_notification_count,
    mark_all_notifications_read,
    mark_notification_read,
)
from database.coach_repository import (
    get_assigned_athletes,
    get_coach_athlete_risk_dashboard,
)
from database.recommendation_repository import save_coach_recommendation
from database.twin_repository import get_athlete_twin_history
from dashboards.visualization import show_athlete_timeline
from digital_twin.forecasting_engine import (
    forecast_metric,
    generate_forecast_summary,
)
from views.model_evaluation_page import model_evaluation_dashboard
from views.request_pages import coach_requests_page


# ============================================================
# COACH NAVIGATION
# ============================================================

COACH_NAV_ITEMS = [
    {
        "label": "Dashboard",
        "page": "Digital Twin Dashboard",
        "key": "dashboard",
    },
    {
        "label": "Athletes",
        "page": "Assigned Athletes",
        "key": "athletes",
    },
    {
        "label": "Intelligence",
        "page": "Coach Intelligence Dashboard",
        "key": "intelligence",
    },
    {
        "label": "Twin Summary",
        "page": "Selected Athlete Twin Summary",
        "key": "summary",
    },
    {
        "label": "History",
        "page": "Digital Twin History",
        "key": "history",
    },
    {
        "label": "Timeline",
        "page": "Digital Twin Timeline",
        "key": "timeline",
    },
    {
        "label": "Visualisation",
        "page": "Visualisations / Graphs",
        "key": "visualisation",
    },
    {
        "label": "Requests",
        "page": "Requests",
        "key": "requests",
    },
    {
        "label": "Notifications",
        "page": "Notifications",
        "key": "notifications",
    },
    {
        "label": "Model Eval",
        "page": "Model Evaluation",
        "key": "model_eval",
    },
]

COACH_NAV_ITEMS_PER_PAGE = 3


def open_coach_page(page_name):
    """Navigate without browser URL changes."""

    st.session_state.current_page = page_name

    for index, item in enumerate(COACH_NAV_ITEMS):
        if item["page"] == page_name:
            st.session_state.coach_nav_carousel_start = (
                index // COACH_NAV_ITEMS_PER_PAGE
            ) * COACH_NAV_ITEMS_PER_PAGE
            break

    st.rerun()


def _initialise_coach_nav_carousel():
    if "coach_nav_carousel_start" not in st.session_state:
        st.session_state.coach_nav_carousel_start = 0

    if "coach_nav_slide_direction" not in st.session_state:
        st.session_state.coach_nav_slide_direction = "none"

    if "coach_nav_animation_nonce" not in st.session_state:
        st.session_state.coach_nav_animation_nonce = 0


def _coach_carousel_max_start():
    if not COACH_NAV_ITEMS:
        return 0

    return (
        (len(COACH_NAV_ITEMS) - 1)
        // COACH_NAV_ITEMS_PER_PAGE
    ) * COACH_NAV_ITEMS_PER_PAGE


def _move_coach_nav_carousel(direction):
    _initialise_coach_nav_carousel()

    current = int(
        st.session_state.coach_nav_carousel_start
    )

    if direction == "left":
        new_start = max(
            0,
            current - COACH_NAV_ITEMS_PER_PAGE,
        )
    elif direction == "right":
        new_start = min(
            _coach_carousel_max_start(),
            current + COACH_NAV_ITEMS_PER_PAGE,
        )
    else:
        return

    if new_start == current:
        return

    st.session_state.coach_nav_carousel_start = new_start
    st.session_state.coach_nav_slide_direction = direction
    st.session_state.coach_nav_animation_nonce += 1
    st.rerun()


def _logout_coach():
    logout_user()
    st.session_state.auth_page = "Login"
    st.session_state.current_page = "Athlete Home"
    st.rerun()


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coach_display_name():
    for key in (
        "coach_name",
        "name",
        "display_name",
    ):
        value = st.session_state.get(key)
        if value:
            return str(value)

    return str(
        st.session_state.get(
            "user_id",
            "Coach",
        )
    )


def _photo_to_data_uri(profile_photo):
    if profile_photo is None:
        return None

    if isinstance(profile_photo, memoryview):
        profile_photo = profile_photo.tobytes()
    elif isinstance(profile_photo, bytearray):
        profile_photo = bytes(profile_photo)

    if not isinstance(profile_photo, bytes):
        return None

    if not profile_photo:
        return None

    if profile_photo.startswith(b"\x89PNG"):
        mime_type = "image/png"
    elif profile_photo.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif profile_photo.startswith((b"GIF87a", b"GIF89a")):
        mime_type = "image/gif"
    elif (
        profile_photo.startswith(b"RIFF")
        and b"WEBP" in profile_photo[:16]
    ):
        mime_type = "image/webp"
    else:
        mime_type = "image/png"

    encoded = base64.b64encode(
        profile_photo
    ).decode("ascii")

    return (
        f"data:{mime_type};"
        f"base64,{encoded}"
    )


def _normalise_injury_level(value):
    text = str(value).strip().lower()

    if text in {
        "high",
        "high risk",
        "elevated",
    }:
        return "High"

    if text in {
        "medium",
        "medium risk",
        "moderate",
        "moderate risk",
    }:
        return "Medium"

    if text in {
        "low",
        "low risk",
    }:
        return "Low"

    numeric = _safe_float(value)

    if numeric is not None:
        if numeric >= 70:
            return "High"
        if numeric >= 40:
            return "Medium"
        if numeric >= 0:
            return "Low"

    return "Unknown"


def _fatigue_level(value):
    fatigue = _safe_float(value)

    if fatigue is None:
        return "Unknown"

    if fatigue >= 70:
        return "High"

    if fatigue >= 45:
        return "Medium"

    return "Low"


def _overall_risk(fatigue_level, injury_level):
    if (
        fatigue_level == "High"
        or injury_level == "High"
    ):
        return "High"

    if (
        fatigue_level == "Medium"
        or injury_level == "Medium"
        or fatigue_level == "Unknown"
        or injury_level == "Unknown"
    ):
        return "Medium"

    return "Low"


def _format_number(value, suffix="", decimals=1):
    number = _safe_float(value)

    if number is None:
        return "N/A"

    return f"{number:.{decimals}f}{suffix}"


# ============================================================
# DATA
# ============================================================

def _get_risk_df():
    risk_rows = get_coach_athlete_risk_dashboard(
        st.session_state.user_id
    )

    if not risk_rows:
        return pd.DataFrame()

    risk_df = pd.DataFrame(
        {
            "Athlete ID": [r[0] for r in risk_rows],
            "Name": [r[1] for r in risk_rows],
            "Fatigue Score": [r[2] for r in risk_rows],
            "Injury Risk": [r[3] for r in risk_rows],
            "Readiness Score": [r[4] for r in risk_rows],
            "Twin Score": [r[5] for r in risk_rows],
            "Athlete State": [r[6] for r in risk_rows],
            "Recommendation": [r[7] for r in risk_rows],
            "Last Updated": [r[8] for r in risk_rows],
        }
    )

    for column in (
        "Fatigue Score",
        "Readiness Score",
        "Twin Score",
    ):
        risk_df[column] = pd.to_numeric(
            risk_df[column],
            errors="coerce",
        )

    risk_df["Fatigue Level"] = risk_df[
        "Fatigue Score"
    ].apply(_fatigue_level)

    risk_df["Injury Level"] = risk_df[
        "Injury Risk"
    ].apply(_normalise_injury_level)

    risk_df["Overall Risk"] = risk_df.apply(
        lambda row: _overall_risk(
            row["Fatigue Level"],
            row["Injury Level"],
        ),
        axis=1,
    )

    risk_order = {
        "High": 1,
        "Medium": 2,
        "Low": 3,
    }

    risk_df["_risk_rank"] = (
        risk_df["Overall Risk"]
        .map(risk_order)
        .fillna(4)
    )

    risk_df = risk_df.sort_values(
        by=[
            "_risk_rank",
            "Fatigue Score",
        ],
        ascending=[
            True,
            False,
        ],
        na_position="last",
    )

    return risk_df.drop(
        columns=["_risk_rank"]
    )


def _risk_counts(risk_df):
    if risk_df is None or risk_df.empty:
        return {
            "High": 0,
            "Medium": 0,
            "Low": 0,
        }

    return {
        "High": int(
            (
                risk_df["Overall Risk"]
                == "High"
            ).sum()
        ),
        "Medium": int(
            (
                risk_df["Overall Risk"]
                == "Medium"
            ).sum()
        ),
        "Low": int(
            (
                risk_df["Overall Risk"]
                == "Low"
            ).sum()
        ),
    }


def _notification_badge_count():
    coach_id = str(
        st.session_state.user_id
    )

    try:
        risk_df = _get_risk_df()
        high_count = _risk_counts(
            risk_df
        )["High"]
    except Exception:
        high_count = 0

    try:
        unread_count = int(
            get_unread_notification_count(
                "Coach",
                coach_id,
            )
            or 0
        )
    except Exception:
        unread_count = 0

    return high_count + unread_count


# ============================================================
# COACH TOP NAVIGATION
# ============================================================

def _render_coach_nav_carousel():
    _initialise_coach_nav_carousel()

    start = int(
        st.session_state.coach_nav_carousel_start
    )

    direction = st.session_state.get(
        "coach_nav_slide_direction",
        "none",
    )

    nonce = int(
        st.session_state.get(
            "coach_nav_animation_nonce",
            0,
        )
    )

    visible_items = COACH_NAV_ITEMS[
        start:
        start + COACH_NAV_ITEMS_PER_PAGE
    ]

    padded_items = visible_items + [None] * (
        COACH_NAV_ITEMS_PER_PAGE
        - len(visible_items)
    )

    with st.container(
        key="coach_nav_carousel"
    ):
        (
            left_arrow_col,
            centre_col,
            right_arrow_col,
        ) = st.columns(
            [
                0.34,
                3.0,
                0.34,
            ],
            gap="small",
            vertical_alignment="center",
        )

        with left_arrow_col:
            if st.button(
                "‹",
                key="coach_nav_left",
                help="Previous navigation options",
                disabled=(start <= 0),
                use_container_width=True,
            ):
                _move_coach_nav_carousel(
                    "left"
                )

        with centre_col:
            track_key = (
                f"coach_nav_track_"
                f"{direction}_"
                f"{nonce}"
            )

            with st.container(
                key=track_key
            ):
                nav_cols = st.columns(
                    3,
                    gap="small",
                    vertical_alignment="center",
                )

                for nav_col, item in zip(
                    nav_cols,
                    padded_items,
                ):
                    with nav_col:
                        if item is None:
                            st.empty()
                            continue

                        if st.button(
                            item["label"],
                            key=(
                                "coach_top_nav_"
                                f"{item['key']}"
                            ),
                            help=(
                                "Open "
                                f"{item['label']}"
                            ),
                            use_container_width=True,
                        ):
                            open_coach_page(
                                item["page"]
                            )

        with right_arrow_col:
            if st.button(
                "›",
                key="coach_nav_right",
                help="More navigation options",
                disabled=(
                    start
                    >= _coach_carousel_max_start()
                ),
                use_container_width=True,
            ):
                _move_coach_nav_carousel(
                    "right"
                )


def _render_coach_top_navigation():
    coach_name = _coach_display_name()
    coach_id = str(
        st.session_state.user_id
    )

    initials = "".join(
        part[0].upper()
        for part in coach_name.split()
        if part
    )[:2]

    if not initials:
        initials = "C"

    profile_photo = (
        st.session_state.get(
            "profile_photo"
        )
    )

    photo_uri = _photo_to_data_uri(
        profile_photo
    )

    if photo_uri:
        avatar_background = f"""
            background-image: url('{photo_uri}');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
        """
        avatar_text_colour = "transparent"
    else:
        avatar_background = """
            background:
                linear-gradient(
                    135deg,
                    #2563eb,
                    #06b6d4
                );
        """
        avatar_text_colour = "white"

    alert_count = (
        _notification_badge_count()
    )

    st.markdown(
        f"""
<style>

/* =========================================================
   HIDE STREAMLIT CHROME + SIDEBAR
========================================================= */

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
section[data-testid="stSidebar"],
button[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {{
    display: none !important;
}}

.main .block-container,
.stMainBlockContainer,
[data-testid="stAppViewBlockContainer"] {{
    padding-top: 0 !important;
}}


/* =========================================================
   GLOBAL WIDTH SAFETY
========================================================= */

html,
body,
[data-testid="stAppViewContainer"],
.stApp,
.main,
.main .block-container {{
    width: 100% !important;
    max-width: 100vw !important;
    overflow-x: clip !important;
    box-sizing: border-box !important;
}}

*,
*::before,
*::after {{
    box-sizing: border-box !important;
}}


/* =========================================================
   COACH STICKY TOP SHELL
========================================================= */

.st-key-coach_top_nav_shell {{
    position: sticky !important;
    top: 0 !important;
    z-index: 99999 !important;

    width: 100% !important;
    max-width: 100% !important;

    margin: 0 0 18px 0 !important;
    padding: 12px 18px !important;

    border: 1px solid rgba(56, 189, 248, 0.15) !important;
    border-top: none !important;
    border-radius: 0 0 18px 18px !important;

    background: rgba(2, 12, 27, 0.97) !important;

    backdrop-filter: blur(18px) !important;
    -webkit-backdrop-filter: blur(18px) !important;

    box-shadow:
        0 10px 28px rgba(0, 0, 0, 0.24)
        !important;

    overflow: visible !important;
}}


/* =========================================================
   HEADER ROW
========================================================= */

.st-key-coach_header_row
[data-testid="stHorizontalBlock"] {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 12px !important;
    width: 100% !important;
}}

.st-key-coach_header_row
[data-testid="column"] {{
    min-width: 0 !important;
    padding: 0 !important;
}}

.st-key-coach_header_row
[data-testid="column"]:nth-child(1) {{
    flex: 0 0 68px !important;
    width: 68px !important;
}}

.st-key-coach_header_row
[data-testid="column"]:nth-child(2) {{
    flex: 1 1 auto !important;
    width: auto !important;
}}

.st-key-coach_header_row
[data-testid="column"]:nth-child(3) {{
    flex: 0 0 84px !important;
    width: 84px !important;
}}

.st-key-coach_header_row
[data-testid="column"]:nth-child(4) {{
    flex: 0 0 64px !important;
    width: 64px !important;
}}


/* =========================================================
   COACH AVATAR
========================================================= */

.st-key-coach_avatar_circle button {{
    width: 62px !important;
    height: 62px !important;
    min-width: 62px !important;
    min-height: 62px !important;

    padding: 0 !important;

    border-radius: 50% !important;
    border: 3px solid #22d3ee !important;

    {avatar_background}

    color: {avatar_text_colour} !important;

    font-size: 17px !important;
    font-weight: 850 !important;

    box-shadow:
        0 0 0 4px rgba(34, 211, 238, 0.10)
        !important;

    transition:
        transform 0.16s ease,
        border-color 0.16s ease,
        box-shadow 0.16s ease;
}}

.st-key-coach_avatar_circle button:hover {{
    transform: scale(1.05);
    border-color: #67e8f9 !important;
    box-shadow:
        0 0 0 5px rgba(34, 211, 238, 0.18)
        !important;
}}

.st-key-coach_avatar_circle button p {{
    color: {avatar_text_colour} !important;
}}


/* =========================================================
   HEADER BUTTONS
========================================================= */

.st-key-coach_header_notifications button,
.st-key-coach_header_logout button {{
    width: 100% !important;
    height: 46px !important;
    min-height: 46px !important;

    padding: 5px !important;

    border-radius: 12px !important;
    border: 1px solid rgba(148, 163, 184, 0.25) !important;

    background: rgba(15, 23, 42, 0.78) !important;
    color: #e2e8f0 !important;

    box-shadow: none !important;
}}

.st-key-coach_header_notifications button:hover,
.st-key-coach_header_logout button:hover {{
    border-color: rgba(34, 211, 238, 0.60) !important;
    background: rgba(8, 47, 73, 0.78) !important;
}}


/* =========================================================
   CAROUSEL
========================================================= */

.st-key-coach_nav_carousel {{
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
}}

.st-key-coach_nav_carousel
[data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important;
}}

.st-key-coach_nav_carousel
[data-testid="column"] {{
    min-width: 0 !important;
}}

[class*="st-key-coach_nav_track_"] {{
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
    will-change:
        transform,
        opacity,
        clip-path;
}}

[class*="st-key-coach_nav_track_"]
[data-testid="stHorizontalBlock"] {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 10px !important;
    width: 100% !important;
}}

[class*="st-key-coach_nav_track_"]
[data-testid="column"] {{
    flex: 1 1 0 !important;
    width: 0 !important;
    min-width: 0 !important;
    padding: 0 !important;
}}


/* LEFT pressed -> group physically moves left */
[class*="st-key-coach_nav_track_left_"] {{
    animation:
        coachSlideDoorLeft
        420ms
        cubic-bezier(0.22, 1, 0.36, 1)
        both;
}}

/* RIGHT pressed -> group physically moves right */
[class*="st-key-coach_nav_track_right_"] {{
    animation:
        coachSlideDoorRight
        420ms
        cubic-bezier(0.22, 1, 0.36, 1)
        both;
}}

@keyframes coachSlideDoorLeft {{
    0% {{
        opacity: 0;
        transform: translateX(18%);
        clip-path:
            inset(
                0 0 0 72%
                round 12px
            );
    }}

    55% {{
        opacity: 0.92;
        clip-path:
            inset(
                0 0 0 10%
                round 12px
            );
    }}

    100% {{
        opacity: 1;
        transform: translateX(0);
        clip-path:
            inset(
                0 0 0 0
                round 12px
            );
    }}
}}

@keyframes coachSlideDoorRight {{
    0% {{
        opacity: 0;
        transform: translateX(-18%);
        clip-path:
            inset(
                0 72% 0 0
                round 12px
            );
    }}

    55% {{
        opacity: 0.92;
        clip-path:
            inset(
                0 10% 0 0
                round 12px
            );
    }}

    100% {{
        opacity: 1;
        transform: translateX(0);
        clip-path:
            inset(
                0 0 0 0
                round 12px
            );
    }}
}}


/* =========================================================
   COACH NAV BUTTONS
========================================================= */

.st-key-coach_top_nav_dashboard button,
.st-key-coach_top_nav_athletes button,
.st-key-coach_top_nav_intelligence button,
.st-key-coach_top_nav_summary button,
.st-key-coach_top_nav_history button,
.st-key-coach_top_nav_timeline button,
.st-key-coach_top_nav_visualisation button,
.st-key-coach_top_nav_requests button,
.st-key-coach_top_nav_notifications button,
.st-key-coach_top_nav_model_eval button {{
    width: 100% !important;
    min-width: 0 !important;

    height: 60px !important;
    min-height: 60px !important;

    padding: 8px 10px !important;

    border-radius: 12px !important;
    border: 1px solid #1f3954 !important;

    background: #0c1728 !important;
    color: #d8e3ef !important;

    box-shadow: none !important;

    font-size: 14px !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;

    white-space: normal !important;
    word-break: normal !important;
    overflow-wrap: normal !important;

    text-align: center !important;

    transition:
        background 0.16s ease,
        border-color 0.16s ease,
        transform 0.16s ease;
}}

.st-key-coach_top_nav_dashboard button:hover,
.st-key-coach_top_nav_athletes button:hover,
.st-key-coach_top_nav_intelligence button:hover,
.st-key-coach_top_nav_summary button:hover,
.st-key-coach_top_nav_history button:hover,
.st-key-coach_top_nav_timeline button:hover,
.st-key-coach_top_nav_visualisation button:hover,
.st-key-coach_top_nav_requests button:hover,
.st-key-coach_top_nav_notifications button:hover,
.st-key-coach_top_nav_model_eval button:hover {{
    background: #10233a !important;
    color: #ffffff !important;
    border-color: #2a5778 !important;
    transform: translateY(-1px);
}}


/* =========================================================
   ARROWS
========================================================= */

.st-key-coach_nav_left button,
.st-key-coach_nav_right button {{
    width: 100% !important;
    min-width: 0 !important;

    height: 60px !important;
    min-height: 60px !important;

    padding: 0 !important;

    border-radius: 12px !important;
    border: 1px solid #1f3954 !important;

    background: #0c1728 !important;
    color: #e2e8f0 !important;

    box-shadow: none !important;

    font-size: 30px !important;
    font-weight: 500 !important;
    line-height: 1 !important;
}}

.st-key-coach_nav_left button:hover:not(:disabled),
.st-key-coach_nav_right button:hover:not(:disabled) {{
    background: #12324c !important;
    color: #ffffff !important;
    border-color: #38bdf8 !important;
}}

.st-key-coach_nav_left button:disabled,
.st-key-coach_nav_right button:disabled {{
    opacity: 0.28 !important;
    cursor: default !important;
}}


/* =========================================================
   COACH CONTENT STYLING
========================================================= */

.qutwin-coach-page-heading {{
    margin: 8px 0 22px 0;
}}

.qutwin-coach-eyebrow {{
    color: #38bdf8;
    font-size: 11px;
    font-weight: 850;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}}

.qutwin-coach-title {{
    color: #f8fafc;
    margin-top: 5px;
    font-size: 30px;
    font-weight: 850;
    letter-spacing: -0.4px;
}}

.qutwin-coach-subtitle {{
    color: #94a3b8;
    margin-top: 6px;
    font-size: 13px;
    line-height: 1.5;
}}

.qutwin-risk-card {{
    padding: 16px 18px;
    border-radius: 14px;
    margin: 8px 0;
    background:
        linear-gradient(
            145deg,
            rgba(8,47,73,0.30),
            rgba(2,12,27,0.78)
        );
    border:
        1px solid
        rgba(56,189,248,0.16);
}}

.qutwin-risk-card.high {{
    border-color:
        rgba(248,113,113,0.44);
}}

.qutwin-risk-card.medium {{
    border-color:
        rgba(251,191,36,0.42);
}}

.qutwin-risk-card.low {{
    border-color:
        rgba(74,222,128,0.36);
}}

.qutwin-risk-name {{
    color: #f8fafc;
    font-size: 16px;
    font-weight: 800;
}}

.qutwin-risk-line {{
    color: #cbd5e1;
    font-size: 12px;
    margin-top: 7px;
}}

.qutwin-risk-meta {{
    color: #64748b;
    font-size: 10.5px;
    margin-top: 8px;
}}


/* =========================================================
   MOBILE / SMALL TABLET
========================================================= */

@media (max-width: 700px) {{

    .main .block-container {{
        padding:
            0 8px 18px 8px
            !important;
    }}

    .st-key-coach_top_nav_shell {{
        padding: 8px !important;
        margin-bottom: 12px !important;
        border-radius:
            0 0 14px 14px
            !important;
    }}

    .st-key-coach_header_row
    [data-testid="stHorizontalBlock"] {{
        gap: 7px !important;
    }}

    .st-key-coach_header_row
    [data-testid="column"]:nth-child(1) {{
        flex: 0 0 50px !important;
        width: 50px !important;
    }}

    .st-key-coach_header_row
    [data-testid="column"]:nth-child(2) {{
        flex: 1 1 auto !important;
    }}

    .st-key-coach_header_row
    [data-testid="column"]:nth-child(3) {{
        flex: 0 0 48px !important;
        width: 48px !important;
    }}

    .st-key-coach_header_row
    [data-testid="column"]:nth-child(4) {{
        flex: 0 0 44px !important;
        width: 44px !important;
    }}

    .st-key-coach_avatar_circle button {{
        width: 46px !important;
        height: 46px !important;
        min-width: 46px !important;
        min-height: 46px !important;
        border-width: 2px !important;
        font-size: 13px !important;
    }}

    .qutwin-coach-brand-title {{
        font-size: 20px !important;
    }}

    .qutwin-coach-brand-subtitle {{
        font-size: 9px !important;
    }}

    .st-key-coach_header_notifications button,
    .st-key-coach_header_logout button {{
        height: 42px !important;
        min-height: 42px !important;
        font-size: 12px !important;
    }}

    .st-key-coach_nav_carousel
    [data-testid="stHorizontalBlock"] {{
        gap: 5px !important;
    }}

    [class*="st-key-coach_nav_track_"]
    [data-testid="stHorizontalBlock"] {{
        gap: 5px !important;
    }}

    .st-key-coach_top_nav_dashboard button,
    .st-key-coach_top_nav_athletes button,
    .st-key-coach_top_nav_intelligence button,
    .st-key-coach_top_nav_summary button,
    .st-key-coach_top_nav_history button,
    .st-key-coach_top_nav_timeline button,
    .st-key-coach_top_nav_visualisation button,
    .st-key-coach_top_nav_requests button,
    .st-key-coach_top_nav_notifications button,
    .st-key-coach_top_nav_model_eval button {{
        height: 50px !important;
        min-height: 50px !important;

        padding: 5px 3px !important;

        border-radius: 9px !important;

        font-size: 10.5px !important;
        line-height: 1.1 !important;
    }}

    .st-key-coach_nav_left button,
    .st-key-coach_nav_right button {{
        height: 50px !important;
        min-height: 50px !important;
        border-radius: 9px !important;
        font-size: 22px !important;
    }}

    .qutwin-coach-title {{
        font-size: 26px !important;
    }}
}}


/* =========================================================
   LARGE DISPLAY / TV
========================================================= */

@media (min-width: 1800px) {{

    .main .block-container {{
        max-width: 1900px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding-left: 36px !important;
        padding-right: 36px !important;
    }}

    .st-key-coach_top_nav_dashboard button,
    .st-key-coach_top_nav_athletes button,
    .st-key-coach_top_nav_intelligence button,
    .st-key-coach_top_nav_summary button,
    .st-key-coach_top_nav_history button,
    .st-key-coach_top_nav_timeline button,
    .st-key-coach_top_nav_visualisation button,
    .st-key-coach_top_nav_requests button,
    .st-key-coach_top_nav_notifications button,
    .st-key-coach_top_nav_model_eval button {{
        height: 70px !important;
        min-height: 70px !important;
        font-size: 16px !important;
    }}

    .st-key-coach_nav_left button,
    .st-key-coach_nav_right button {{
        height: 70px !important;
        min-height: 70px !important;
        font-size: 34px !important;
    }}
}}


/* =========================================================
   ACCESSIBILITY
========================================================= */

@media (prefers-reduced-motion: reduce) {{
    [class*="st-key-coach_nav_track_"] {{
        animation: none !important;
    }}
}}

</style>
""",
        unsafe_allow_html=True,
    )

    with st.container(
        key="coach_top_nav_shell"
    ):
        with st.container(
            key="coach_header_row"
        ):
            (
                avatar_col,
                brand_col,
                bell_col,
                logout_col,
            ) = st.columns(
                [
                    0.65,
                    7.8,
                    0.9,
                    0.75,
                ],
                vertical_alignment="center",
            )

            with avatar_col:
                if st.button(
                    initials,
                    key="coach_avatar_circle",
                    help=(
                        f"Open {coach_name}'s "
                        "coach dashboard"
                    ),
                ):
                    open_coach_page(
                        "Digital Twin Dashboard"
                    )

            with brand_col:
                st.html(
                    f"""
<div class="qutwin-coach-brand">
    <div
        class="qutwin-coach-brand-title"
        style="
            color:#f8fafc;
            font-size:27px;
            font-weight:850;
            line-height:1;
            letter-spacing:-0.4px;
        "
    >
        QUTwin
    </div>

    <div
        class="qutwin-coach-brand-subtitle"
        style="
            color:#94a3b8;
            font-size:11px;
            margin-top:6px;
        "
    >
        Coach Digital Twin ·
        {html.escape(coach_id)}
    </div>
</div>
"""
                )

            with bell_col:
                bell_label = (
                    f"🔔 {alert_count}"
                    if alert_count > 0
                    else "🔔"
                )

                if st.button(
                    bell_label,
                    key=(
                        "coach_header_"
                        "notifications"
                    ),
                    help=(
                        "Athlete risk and "
                        "request notifications"
                    ),
                    use_container_width=True,
                ):
                    open_coach_page(
                        "Notifications"
                    )

            with logout_col:
                if st.button(
                    "⎋",
                    key="coach_header_logout",
                    help="Logout",
                    use_container_width=True,
                ):
                    _logout_coach()

        st.html(
            """
<div style="
    height:1px;
    background:rgba(148,163,184,0.18);
    margin:10px 0;
"></div>
"""
        )

        _render_coach_nav_carousel()


# ============================================================
# PAGE COMPONENTS
# ============================================================

def _render_page_heading(
    title,
    subtitle,
    eyebrow="COACH DIGITAL TWIN",
):
    st.html(
        f"""
<div class="qutwin-coach-page-heading">
    <div class="qutwin-coach-eyebrow">
        {html.escape(eyebrow)}
    </div>
    <div class="qutwin-coach-title">
        {html.escape(title)}
    </div>
    <div class="qutwin-coach-subtitle">
        {html.escape(subtitle)}
    </div>
</div>
"""
    )


def _render_risk_athlete_card(
    number,
    row,
    level,
):
    name = (
        row.get("Name")
        or row.get("Athlete ID")
        or "Unknown Athlete"
    )

    athlete_id = row.get(
        "Athlete ID",
        "Unknown",
    )

    fatigue_score = _safe_float(
        row.get("Fatigue Score")
    )

    fatigue_level = row.get(
        "Fatigue Level",
        "Unknown",
    )

    injury_level = row.get(
        "Injury Level",
        _normalise_injury_level(
            row.get(
                "Injury Risk",
                "Unknown",
            )
        ),
    )

    readiness = _safe_float(
        row.get("Readiness Score")
    )

    last_updated = row.get(
        "Last Updated"
    )

    fatigue_display = (
        f"{fatigue_level} "
        f"({fatigue_score:.1f})"
        if fatigue_score is not None
        else fatigue_level
    )

    readiness_display = (
        f"{readiness:.1f}%"
        if readiness is not None
        else "N/A"
    )

    class_name = (
        "high"
        if level == "High"
        else (
            "medium"
            if level == "Medium"
            else "low"
        )
    )

    st.html(
        f"""
<div class="qutwin-risk-card {class_name}">
    <div class="qutwin-risk-name">
        {number}) {html.escape(str(name))}
    </div>

    <div class="qutwin-risk-line">
        <strong>Risk level:</strong>
        {html.escape(level)}
    </div>

    <div class="qutwin-risk-line">
        <strong>Fatigue:</strong>
        {html.escape(fatigue_display)}
    </div>

    <div class="qutwin-risk-line">
        <strong>Injury:</strong>
        {html.escape(str(injury_level))}
    </div>

    <div class="qutwin-risk-line">
        <strong>Readiness:</strong>
        {html.escape(readiness_display)}
    </div>

    <div class="qutwin-risk-meta">
        Athlete ID:
        {html.escape(str(athlete_id))}
        {
            " · Last updated: "
            + html.escape(str(last_updated))
            if last_updated
            else ""
        }
    </div>
</div>
"""
    )


# ============================================================
# DASHBOARD
# ============================================================

def coach_dashboard():
    _render_page_heading(
        "Coach Digital Twin Dashboard",
        (
            "Team-level fatigue, injury risk, "
            "readiness and athlete priorities."
        ),
    )

    try:
        risk_df = _get_risk_df()
    except Exception as exc:
        st.error(
            "Coach risk data could not be loaded."
        )
        st.exception(exc)
        return

    try:
        athletes = get_assigned_athletes(
            st.session_state.user_id
        )
    except Exception:
        athletes = []

    assigned_count = (
        len(athletes)
        if athletes
        else 0
    )

    counts = _risk_counts(
        risk_df
    )

    avg_readiness = (
        risk_df["Readiness Score"].mean()
        if not risk_df.empty
        else None
    )

    avg_fatigue = (
        risk_df["Fatigue Score"].mean()
        if not risk_df.empty
        else None
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Assigned Athletes",
        assigned_count,
    )

    c2.metric(
        "High Risk",
        counts["High"],
    )

    c3.metric(
        "Monitor",
        counts["Medium"],
    )

    c4.metric(
        "Low Risk",
        counts["Low"],
    )

    c5, c6 = st.columns(2)

    c5.metric(
        "Average Fatigue",
        (
            f"{avg_fatigue:.1f}"
            if pd.notna(avg_fatigue)
            else "N/A"
        ),
    )

    c6.metric(
        "Average Readiness",
        (
            f"{avg_readiness:.1f}%"
            if pd.notna(avg_readiness)
            else "N/A"
        ),
    )

    if risk_df.empty:
        st.info(
            "No athlete Digital Twin data "
            "is available yet."
        )
        return

    st.subheader(
        "Priority Athlete Alerts"
    )

    high_df = risk_df[
        risk_df["Overall Risk"]
        == "High"
    ]

    medium_df = risk_df[
        risk_df["Overall Risk"]
        == "Medium"
    ]

    if not high_df.empty:
        top = high_df.iloc[0]

        st.error(
            (
                f"Immediate review: "
                f"{top['Name']} "
                f"({top['Athlete ID']}) — "
                f"fatigue "
                f"{_format_number(top['Fatigue Score'])}, "
                f"injury "
                f"{top['Injury Level']}, "
                f"readiness "
                f"{_format_number(top['Readiness Score'], '%')}."
            )
        )

        if st.button(
            "Open all athlete alerts",
            key="coach_dashboard_open_alerts",
        ):
            open_coach_page(
                "Notifications"
            )

    elif not medium_df.empty:
        top = medium_df.iloc[0]

        st.warning(
            (
                f"Monitor closely: "
                f"{top['Name']} "
                f"({top['Athlete ID']}) — "
                f"fatigue "
                f"{_format_number(top['Fatigue Score'])}, "
                f"injury "
                f"{top['Injury Level']}."
            )
        )

    else:
        st.success(
            "All athletes with current data "
            "are in the low-risk group."
        )


# ============================================================
# LEGACY ASSIGNMENT ENTRY
# ============================================================

def assign_athlete():
    """
    Kept only so older app.py imports do not fail.

    Direct assignment is intentionally not used anymore.
    Connection consent is managed through Requests.
    """

    _render_page_heading(
        "Athlete Connections",
        (
            "Direct assignment has been replaced "
            "with two-way connection requests."
        ),
    )

    st.info(
        "Use the Requests page to connect "
        "with an athlete."
    )

    if st.button(
        "Open Requests",
        key="legacy_assign_open_requests",
        type="primary",
    ):
        open_coach_page(
            "Requests"
        )


# ============================================================
# ASSIGNED ATHLETES
# ============================================================

def assigned_athletes():
    _render_page_heading(
        "Assigned Athletes",
        (
            "Athletes who have an active "
            "coach-athlete connection."
        ),
    )

    athletes = get_assigned_athletes(
        st.session_state.user_id
    )

    if not athletes:
        st.info(
            "No athletes are assigned yet."
        )
        return

    assigned_df = pd.DataFrame(
        {
            "Athlete ID": [
                a[0]
                for a in athletes
            ],
            "Name": [
                a[1]
                for a in athletes
            ],
            "Age": [
                a[2]
                for a in athletes
            ],
            "Height": [
                a[3]
                for a in athletes
            ],
            "Weight": [
                a[4]
                for a in athletes
            ],
            "Previous Injury": [
                a[5]
                for a in athletes
            ],
        }
    )

    st.dataframe(
        assigned_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# COACH INTELLIGENCE
# ============================================================

def coach_intelligence_dashboard():
    _render_page_heading(
        "Coach Intelligence Dashboard",
        (
            "Combined fatigue and injury-risk "
            "ranking across assigned athletes."
        ),
    )

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info(
            "No risk data is available yet. "
            "Athletes need to upload data first."
        )
        return

    counts = _risk_counts(
        risk_df
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "High Risk",
        counts["High"],
    )

    c2.metric(
        "Monitor",
        counts["Medium"],
    )

    c3.metric(
        "Low Risk",
        counts["Low"],
    )

    st.subheader(
        "Athlete Risk Ranking"
    )

    st.caption(
        (
            "Overall risk combines fatigue "
            "and injury risk. High is shown first."
        )
    )

    display_columns = [
        "Athlete ID",
        "Name",
        "Fatigue Score",
        "Fatigue Level",
        "Injury Level",
        "Overall Risk",
        "Readiness Score",
        "Twin Score",
        "Recommendation",
        "Last Updated",
    ]

    st.dataframe(
        risk_df[display_columns],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# SELECTED ATHLETE SUMMARY
# ============================================================

def selected_athlete_twin_summary():
    _render_page_heading(
        "Selected Athlete Twin Summary",
        (
            "Review the latest state, approve "
            "recommendations and inspect forecast trends."
        ),
    )

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info(
            "No athlete Digital Twin data "
            "is available yet."
        )
        return

    options = risk_df[
        "Athlete ID"
    ].tolist()

    selected_athlete = st.selectbox(
        "Select Athlete",
        options,
        key="coach_summary_athlete",
    )

    selected_row = risk_df[
        risk_df["Athlete ID"]
        == selected_athlete
    ].iloc[0]

    athlete_name = (
        selected_row.get("Name")
        or selected_athlete
    )

    st.subheader(
        f"Current State · {athlete_name}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Fatigue",
        _format_number(
            selected_row[
                "Fatigue Score"
            ]
        ),
    )

    c2.metric(
        "Injury Risk",
        selected_row[
            "Injury Level"
        ],
    )

    c3.metric(
        "Readiness",
        _format_number(
            selected_row[
                "Readiness Score"
            ],
            "%",
        ),
    )

    c4.metric(
        "Twin Score",
        _format_number(
            selected_row[
                "Twin Score"
            ],
        ),
    )

    st.success(
        "AI Recommendation"
    )

    recommendation = (
        selected_row.get(
            "Recommendation"
        )
        or "No recommendation available."
    )

    st.info(
        recommendation
    )

    st.divider()

    st.subheader(
        "Coach Review & Approval"
    )

    coach_note = st.text_area(
        "Edit or write coach recommendation",
        value=str(
            recommendation
        ),
        height=140,
        key="coach_summary_note",
    )

    approval_status = st.radio(
        "Approval Decision",
        [
            "Approved",
            "Rejected",
        ],
        horizontal=True,
        key="coach_summary_approval",
    )

    if st.button(
        "Save Coach Decision",
        key="coach_save_decision",
        type="primary",
    ):
        if not coach_note.strip():
            st.warning(
                "Please write a recommendation "
                "before saving."
            )
        else:
            save_coach_recommendation(
                coach_id=(
                    st.session_state.user_id
                ),
                athlete_id=selected_athlete,
                ai_recommendation=str(
                    recommendation
                ),
                coach_comment=coach_note,
                approval_status=(
                    approval_status
                ),
            )

            if approval_status == "Approved":
                st.success(
                    "Recommendation approved "
                    "and saved."
                )
            else:
                st.warning(
                    "Recommendation rejected "
                    "and saved."
                )

    st.divider()

    st.subheader(
        "7-Day Digital Twin Forecast"
    )

    history_df = (
        get_athlete_twin_history(
            selected_athlete
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):
        st.info(
            "Not enough Digital Twin history "
            "is available for forecasting."
        )
        return

    fatigue_forecast = forecast_metric(
        history_df,
        "fatigue_score",
        days=7,
    )

    readiness_forecast = forecast_metric(
        history_df,
        "readiness_score",
        days=7,
    )

    if (
        fatigue_forecast is not None
        and not fatigue_forecast.empty
    ):
        st.write(
            "Predicted Fatigue Trend"
        )

        st.line_chart(
            fatigue_forecast.set_index(
                "forecast_date"
            )["forecast_value"]
        )

    if (
        readiness_forecast is not None
        and not readiness_forecast.empty
    ):
        st.write(
            "Predicted Readiness Trend"
        )

        st.line_chart(
            readiness_forecast.set_index(
                "forecast_date"
            )["forecast_value"]
        )

    st.success(
        "Forecast Summary"
    )

    st.info(
        generate_forecast_summary(
            fatigue_forecast,
            readiness_forecast,
        )
    )


# ============================================================
# HISTORY
# ============================================================

def coach_history():
    _render_page_heading(
        "Digital Twin History",
        (
            "Inspect historical Digital Twin "
            "states for an assigned athlete."
        ),
    )

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info(
            "No athlete data is available."
        )
        return

    selected_athlete = st.selectbox(
        "Select Athlete",
        risk_df[
            "Athlete ID"
        ].tolist(),
        key="coach_history_athlete",
    )

    history_df = (
        get_athlete_twin_history(
            selected_athlete
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):
        st.info(
            "No Digital Twin history is "
            "available for this athlete."
        )
        return

    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# TIMELINE
# ============================================================

def coach_timeline():
    _render_page_heading(
        "Digital Twin Timeline",
        (
            "Review state changes for an "
            "assigned athlete over time."
        ),
    )

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info(
            "No athlete data is available."
        )
        return

    selected_athlete = st.selectbox(
        "Select Athlete",
        risk_df[
            "Athlete ID"
        ].tolist(),
        key="coach_timeline_athlete",
    )

    history_df = (
        get_athlete_twin_history(
            selected_athlete
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):
        st.info(
            "No timeline is available "
            "for this athlete."
        )
        return

    show_athlete_timeline(
        history_df
    )


# ============================================================
# VISUALISATIONS
# ============================================================

def coach_visualisations():
    _render_page_heading(
        "Visualisations / Graphs",
        (
            "Compare team fatigue, readiness "
            "and Digital Twin scores."
        ),
    )

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info(
            "No coach analytics "
            "are available yet."
        )
        return

    st.subheader(
        "Team Fatigue Overview"
    )

    st.bar_chart(
        risk_df.set_index(
            "Athlete ID"
        )["Fatigue Score"]
    )

    st.subheader(
        "Team Readiness Overview"
    )

    st.bar_chart(
        risk_df.set_index(
            "Athlete ID"
        )["Readiness Score"]
    )

    st.subheader(
        "Twin Score Overview"
    )

    st.bar_chart(
        risk_df.set_index(
            "Athlete ID"
        )["Twin Score"]
    )


# ============================================================
# COACH NOTIFICATIONS
# ============================================================

def coach_notifications():
    _render_page_heading(
        "Coach Notifications",
        (
            "Current fatigue and injury-risk "
            "alerts for assigned athletes, plus "
            "connection request updates."
        ),
        eyebrow="COACH ALERT CENTRE",
    )

    coach_id = str(
        st.session_state.user_id
    )

    try:
        risk_df = _get_risk_df()
    except Exception as exc:
        st.error(
            "Athlete risk information "
            "could not be loaded."
        )
        st.exception(exc)
        risk_df = pd.DataFrame()

    try:
        notifications = get_notifications(
            "Coach",
            coach_id,
            limit=100,
        )

        unread_count = int(
            get_unread_notification_count(
                "Coach",
                coach_id,
            )
            or 0
        )

    except Exception as exc:
        notifications = []
        unread_count = 0

        st.warning(
            "Request notifications could "
            "not be loaded."
        )
        st.exception(exc)

    if risk_df.empty:
        high_df = pd.DataFrame()
        medium_df = pd.DataFrame()
        low_df = pd.DataFrame()
    else:
        high_df = risk_df[
            risk_df["Overall Risk"]
            == "High"
        ]

        medium_df = risk_df[
            risk_df["Overall Risk"]
            == "Medium"
        ]

        low_df = risk_df[
            risk_df["Overall Risk"]
            == "Low"
        ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "High Risk",
        len(high_df),
    )

    c2.metric(
        "Monitor",
        len(medium_df),
    )

    c3.metric(
        "Low Risk",
        len(low_df),
    )

    c4.metric(
        "Unread Requests",
        unread_count,
    )

    st.divider()

    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

    st.subheader(
        "🔴 High Risk Athletes"
    )

    st.caption(
        (
            "An athlete appears here when "
            "fatigue OR injury risk is High."
        )
    )

    if high_df.empty:
        st.success(
            "No assigned athletes are "
            "currently high risk."
        )
    else:
        for number, (_, row) in enumerate(
            high_df.iterrows(),
            start=1,
        ):
            _render_risk_athlete_card(
                number,
                row,
                "High",
            )

    # --------------------------------------------------------
    # MEDIUM
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🟠 Athletes to Monitor"
    )

    if medium_df.empty:
        st.info(
            "No assigned athletes currently "
            "need medium-level monitoring."
        )
    else:
        for number, (_, row) in enumerate(
            medium_df.iterrows(),
            start=1,
        ):
            _render_risk_athlete_card(
                number,
                row,
                "Medium",
            )

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🟢 Low Risk Athletes"
    )

    st.caption(
        (
            "Low-risk athletes have both "
            "fatigue and injury risk in "
            "the low range."
        )
    )

    if low_df.empty:
        st.info(
            "No assigned athletes are "
            "currently in the low-risk group."
        )
    else:
        for number, (_, row) in enumerate(
            low_df.iterrows(),
            start=1,
        ):
            _render_risk_athlete_card(
                number,
                row,
                "Low",
            )

    # --------------------------------------------------------
    # REQUEST NOTIFICATIONS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🔔 Request Notifications"
    )

    if (
        unread_count > 0
        and notifications
    ):
        if st.button(
            "Mark all as read",
            key=(
                "coach_mark_all_"
                "notifications_read"
            ),
        ):
            try:
                mark_all_notifications_read(
                    "Coach",
                    coach_id,
                )
                st.rerun()
            except Exception as exc:
                st.error(
                    "Notifications could "
                    "not be updated."
                )
                st.exception(exc)

    if not notifications:
        st.info(
            "No request notifications "
            "are available."
        )
        return

    for notification in notifications:
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

        message = notification.get(
            "message",
            "",
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
                    "**"
                    + html.escape(
                        str(
                            notification_type
                        )
                    )
                    + "**"
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
                str(message)
            )

            if created_at:
                st.caption(
                    str(created_at)
                )

            if not is_read:
                if st.button(
                    "Mark as read",
                    key=(
                        "coach_notification_"
                        f"read_{notification_id}"
                    ),
                ):
                    try:
                        mark_notification_read(
                            notification_id,
                            "Coach",
                            coach_id,
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(
                            "Notification "
                            "could not be updated."
                        )
                        st.exception(exc)


# ============================================================
# COACH PORTAL ROUTER
# ============================================================

def coach_portal():
    """
    Complete coach-side UI.

    app.py should call this function for logged-in coaches.
    It renders the sticky top navigation first, then the selected
    coach page. No sidebar navigation is required.
    """

    valid_pages = {
        item["page"]
        for item in COACH_NAV_ITEMS
    }

    current_page = st.session_state.get(
        "current_page",
        "Digital Twin Dashboard",
    )

    if current_page not in valid_pages:
        st.session_state.current_page = (
            "Digital Twin Dashboard"
        )
        current_page = (
            "Digital Twin Dashboard"
        )

    _render_coach_top_navigation()

    coach_pages = {
        "Digital Twin Dashboard": (
            coach_dashboard
        ),
        "Assigned Athletes": (
            assigned_athletes
        ),
        "Coach Intelligence Dashboard": (
            coach_intelligence_dashboard
        ),
        "Selected Athlete Twin Summary": (
            selected_athlete_twin_summary
        ),
        "Digital Twin History": (
            coach_history
        ),
        "Digital Twin Timeline": (
            coach_timeline
        ),
        "Visualisations / Graphs": (
            coach_visualisations
        ),
        "Requests": (
            coach_requests_page
        ),
        "Notifications": (
            coach_notifications
        ),
        "Model Evaluation": (
            model_evaluation_dashboard
        ),
    }

    selected_page_function = (
        coach_pages[current_page]
    )

    selected_page_function()