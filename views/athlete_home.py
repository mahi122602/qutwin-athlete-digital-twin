import base64
import html

import pandas as pd
import streamlit as st

from database.athlete_repository import get_athlete_profile
from database.twin_repository import get_athlete_twin_history
from database.connection_request_repository import (
    get_unread_notification_count,
)


# ============================================================
# BASIC ATHLETE NAVIGATION
# ============================================================

def open_athlete_page(page_name):
    """
    Navigate using Streamlit session state.

    This prevents browser-level URL navigation and keeps
    the authenticated Streamlit session alive.
    """
    st.session_state.current_page = page_name
    st.rerun()


# ============================================================
# ATHLETE NAVIGATION CAROUSEL
# ============================================================

ATHLETE_NAV_ITEMS = [
    {
        "label": "Dashboard",
        "page": "Digital Twin Dashboard",
        "key": "dashboard",
    },
    {
        "label": "Upload Data",
        "page": "Upload Garmin Data",
        "key": "upload",
    },
    {
        "label": "Prediction",
        "page": "Predictions & Coach Recommendations",
        "key": "prediction",
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
        "label": "What-if",
        "page": "What-if Simulation",
        "key": "simulation",
    },
    {
        "label": "Forecasting",
        "page": "Forecasting",
        "key": "forecasting",
    },
    {
        "label": "Requests",
        "page": "Requests",
        "key": "requests",
    },
]

NAV_ITEMS_PER_PAGE = 3


def _initialise_athlete_nav_carousel():
    """Initialise carousel state once per Streamlit session."""

    if "athlete_nav_carousel_start" not in st.session_state:
        st.session_state.athlete_nav_carousel_start = 0

    if "athlete_nav_slide_direction" not in st.session_state:
        st.session_state.athlete_nav_slide_direction = "none"

    if "athlete_nav_animation_nonce" not in st.session_state:
        st.session_state.athlete_nav_animation_nonce = 0


def _carousel_max_start():
    """Return the last valid 3-item carousel page start."""

    if not ATHLETE_NAV_ITEMS:
        return 0

    return (
        (len(ATHLETE_NAV_ITEMS) - 1)
        // NAV_ITEMS_PER_PAGE
    ) * NAV_ITEMS_PER_PAGE


def _move_athlete_nav_carousel(direction):
    """
    Move one complete carousel page and remember the direction.

    The direction is used by CSS after rerun to create the
    sliding-door transition.
    """

    _initialise_athlete_nav_carousel()

    current = int(
        st.session_state.athlete_nav_carousel_start
    )

    if direction == "left":
        new_start = max(
            0,
            current - NAV_ITEMS_PER_PAGE,
        )

    elif direction == "right":
        new_start = min(
            _carousel_max_start(),
            current + NAV_ITEMS_PER_PAGE,
        )

    else:
        return

    if new_start == current:
        return

    st.session_state.athlete_nav_carousel_start = new_start
    st.session_state.athlete_nav_slide_direction = direction
    st.session_state.athlete_nav_animation_nonce += 1
    st.rerun()


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_float(
    value,
    default=0.0,
):
    try:
        if pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _photo_to_data_uri(
    profile_photo,
):
    """
    Convert profile-photo bytes stored in PostgreSQL into a
    base64 data URI for the clickable avatar.
    """

    if profile_photo is None:
        return None

    if isinstance(
        profile_photo,
        memoryview,
    ):
        profile_photo = profile_photo.tobytes()

    elif isinstance(
        profile_photo,
        bytearray,
    ):
        profile_photo = bytes(profile_photo)

    if not isinstance(
        profile_photo,
        bytes,
    ):
        return None

    if not profile_photo:
        return None

    if profile_photo.startswith(
        b"\x89PNG"
    ):
        mime_type = "image/png"

    elif profile_photo.startswith(
        b"\xff\xd8\xff"
    ):
        mime_type = "image/jpeg"

    elif profile_photo.startswith(
        (
            b"GIF87a",
            b"GIF89a",
        )
    ):
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


# ============================================================
# ATHLETE NAVIGATION CAROUSEL RENDERER
# ============================================================

def _render_athlete_nav_carousel():
    """
    Render the same 3-item arrow carousel on every device.

    The arrows remain fixed while only the three centre items
    animate. Pressing left makes the new nav group slide left
    into place; pressing right makes it slide right into place.
    """

    _initialise_athlete_nav_carousel()

    start = int(
        st.session_state.athlete_nav_carousel_start
    )

    direction = st.session_state.get(
        "athlete_nav_slide_direction",
        "none",
    )

    nonce = int(
        st.session_state.get(
            "athlete_nav_animation_nonce",
            0,
        )
    )

    visible_items = ATHLETE_NAV_ITEMS[
        start:
        start + NAV_ITEMS_PER_PAGE
    ]

    padded_items = visible_items + [None] * (
        NAV_ITEMS_PER_PAGE - len(visible_items)
    )

    with st.container(
        key="athlete_nav_carousel"
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

        # ----------------------------------------------------
        # LEFT ARROW
        # ----------------------------------------------------

        with left_arrow_col:
            if st.button(
                "‹",
                key="athlete_nav_left",
                help="Previous navigation options",
                disabled=(start <= 0),
                use_container_width=True,
            ):
                _move_athlete_nav_carousel(
                    "left"
                )

        # ----------------------------------------------------
        # SLIDING CENTRE TRACK
        # ----------------------------------------------------

        with centre_col:

            track_key = (
                f"athlete_nav_track_"
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
                                f"top_nav_"
                                f"{item['key']}"
                            ),
                            help=(
                                f"Open "
                                f"{item['label']}"
                            ),
                            use_container_width=True,
                        ):
                            open_athlete_page(
                                item["page"]
                            )

        # ----------------------------------------------------
        # RIGHT ARROW
        # ----------------------------------------------------

        with right_arrow_col:
            if st.button(
                "›",
                key="athlete_nav_right",
                help="More navigation options",
                disabled=(
                    start
                    >= _carousel_max_start()
                ),
                use_container_width=True,
            ):
                _move_athlete_nav_carousel(
                    "right"
                )


# ============================================================
# MAIN ATHLETE HEADER + TOP NAVIGATION
# ============================================================

def _render_athlete_top_navigation(
    profile,
    unread_count=0,
):
    """
    Render the sticky Athlete header and carousel navigation.

    The header remains at the top while scrolling. It uses normal
    document flow, so it does not cover the dashboard underneath.
    """

    athlete_name = (
        profile.get("name")
        if (
            profile
            and profile.get("name")
        )
        else str(
            st.session_state.user_id
        )
    )

    profile_photo = (
        profile.get("profile_photo")
        if profile
        else None
    )

    photo_uri = _photo_to_data_uri(
        profile_photo
    )

    initials = "".join(
        part[0].upper()
        for part
        in str(athlete_name).split()
        if part
    )[:2]

    if not initials:
        initials = "A"

    # ========================================================
    # AVATAR APPEARANCE
    # ========================================================

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

    # ========================================================
    # RESPONSIVE + CAROUSEL CSS
    # ========================================================

    st.markdown(
        f"""
<style>

/* =========================================================
   REMOVE STREAMLIT TOP GAP / TOOLBAR
========================================================= */

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {{
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

img {{
    max-width: 100% !important;
}}


/* =========================================================
   STICKY TOP SHELL

   Sticky, NOT fixed. This keeps the navbar at the top while
   also reserving the correct space in normal page flow.
========================================================= */

.st-key-athlete_top_nav_shell {{
    position: sticky !important;
    top: 0 !important;
    z-index: 99999 !important;

    width: 100% !important;
    max-width: 100% !important;

    margin: 0 0 18px 0 !important;
    padding: 12px 18px 12px 18px !important;

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

.st-key-athlete_header_row
[data-testid="stHorizontalBlock"] {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 12px !important;
    width: 100% !important;
}}

.st-key-athlete_header_row
[data-testid="column"] {{
    min-width: 0 !important;
    padding: 0 !important;
}}

.st-key-athlete_header_row
[data-testid="column"]:nth-child(1) {{
    flex: 0 0 68px !important;
    width: 68px !important;
}}

.st-key-athlete_header_row
[data-testid="column"]:nth-child(2) {{
    flex: 1 1 auto !important;
    width: auto !important;
}}

.st-key-athlete_header_row
[data-testid="column"]:nth-child(3) {{
    flex: 0 0 84px !important;
    width: 84px !important;
}}

.st-key-athlete_header_row
[data-testid="column"]:nth-child(4) {{
    flex: 0 0 64px !important;
    width: 64px !important;
}}


/* =========================================================
   CLICKABLE ATHLETE AVATAR
========================================================= */

.st-key-athlete_avatar_circle button {{
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

.st-key-athlete_avatar_circle button:hover {{
    transform: scale(1.05);
    border-color: #67e8f9 !important;

    box-shadow:
        0 0 0 5px rgba(34, 211, 238, 0.18)
        !important;
}}

.st-key-athlete_avatar_circle button p {{
    color: {avatar_text_colour} !important;
}}


/* =========================================================
   HEADER BELL + SETTINGS
========================================================= */

.st-key-athlete_header_notifications button,
.st-key-athlete_header_settings button {{
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

.st-key-athlete_header_notifications button:hover,
.st-key-athlete_header_settings button:hover {{
    border-color: rgba(34, 211, 238, 0.60) !important;
    background: rgba(8, 47, 73, 0.78) !important;
}}


/* =========================================================
   CAROUSEL OUTER ROW
========================================================= */

.st-key-athlete_nav_carousel {{
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
}}

.st-key-athlete_nav_carousel
[data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important;
}}

.st-key-athlete_nav_carousel
[data-testid="column"] {{
    min-width: 0 !important;
}}


/* =========================================================
   SLIDING CENTRE TRACK

   A unique Streamlit key is generated every arrow click.
   That makes the animation restart after each rerun.
========================================================= */

[class*="st-key-athlete_nav_track_"] {{
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
    will-change: transform, opacity, clip-path;
}}

[class*="st-key-athlete_nav_track_"]
[data-testid="stHorizontalBlock"] {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 10px !important;
    width: 100% !important;
}}

[class*="st-key-athlete_nav_track_"]
[data-testid="column"] {{
    flex: 1 1 0 !important;
    width: 0 !important;
    min-width: 0 !important;
    padding: 0 !important;
}}

/* Left arrow pressed: new panel moves toward the left. */
[class*="st-key-athlete_nav_track_left_"] {{
    animation:
        qutwinSlideDoorLeft
        420ms
        cubic-bezier(0.22, 1, 0.36, 1)
        both;
}}

/* Right arrow pressed: new panel moves toward the right. */
[class*="st-key-athlete_nav_track_right_"] {{
    animation:
        qutwinSlideDoorRight
        420ms
        cubic-bezier(0.22, 1, 0.36, 1)
        both;
}}

@keyframes qutwinSlideDoorLeft {{
    0% {{
        opacity: 0;
        transform: translateX(18%);
        clip-path: inset(0 0 0 72% round 12px);
    }}

    55% {{
        opacity: 0.92;
        clip-path: inset(0 0 0 10% round 12px);
    }}

    100% {{
        opacity: 1;
        transform: translateX(0);
        clip-path: inset(0 0 0 0 round 12px);
    }}
}}

@keyframes qutwinSlideDoorRight {{
    0% {{
        opacity: 0;
        transform: translateX(-18%);
        clip-path: inset(0 72% 0 0 round 12px);
    }}

    55% {{
        opacity: 0.92;
        clip-path: inset(0 10% 0 0 round 12px);
    }}

    100% {{
        opacity: 1;
        transform: translateX(0);
        clip-path: inset(0 0 0 0 round 12px);
    }}
}}


/* =========================================================
   NAVIGATION BUTTONS
========================================================= */

.st-key-top_nav_dashboard button,
.st-key-top_nav_upload button,
.st-key-top_nav_prediction button,
.st-key-top_nav_history button,
.st-key-top_nav_timeline button,
.st-key-top_nav_visualisation button,
.st-key-top_nav_simulation button,
.st-key-top_nav_forecasting button,
.st-key-top_nav_requests button {{
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

.st-key-top_nav_dashboard button:hover,
.st-key-top_nav_upload button:hover,
.st-key-top_nav_prediction button:hover,
.st-key-top_nav_history button:hover,
.st-key-top_nav_timeline button:hover,
.st-key-top_nav_visualisation button:hover,
.st-key-top_nav_simulation button:hover,
.st-key-top_nav_forecasting button:hover,
.st-key-top_nav_requests button:hover {{
    background: #10233a !important;
    color: #ffffff !important;
    border-color: #2a5778 !important;
    transform: translateY(-1px);
}}


/* =========================================================
   ARROWS
========================================================= */

.st-key-athlete_nav_left button,
.st-key-athlete_nav_right button {{
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

.st-key-athlete_nav_left button:hover:not(:disabled),
.st-key-athlete_nav_right button:hover:not(:disabled) {{
    background: #12324c !important;
    color: #ffffff !important;
    border-color: #38bdf8 !important;
}}

.st-key-athlete_nav_left button:disabled,
.st-key-athlete_nav_right button:disabled {{
    opacity: 0.28 !important;
    cursor: default !important;
}}


/* =========================================================
   AI DETAIL BUTTONS
========================================================= */

.st-key-dashboard_injury_prediction_details button,
.st-key-dashboard_fatigue_prediction_details button,
.st-key-dashboard_recovery_prediction_details button {{
    margin-top: -2px;
    min-height: 40px !important;
    border-radius: 0 0 12px 12px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
}}


/* =========================================================
   MOBILE / SMALL TABLET
========================================================= */

@media (max-width: 700px) {{

    .main .block-container {{
        padding: 0 8px 18px 8px !important;
    }}

    .st-key-athlete_top_nav_shell {{
        padding: 8px !important;
        margin-bottom: 12px !important;
        border-radius: 0 0 14px 14px !important;
    }}

    .st-key-athlete_header_row
    [data-testid="stHorizontalBlock"] {{
        gap: 7px !important;
    }}

    .st-key-athlete_header_row
    [data-testid="column"]:nth-child(1) {{
        flex: 0 0 50px !important;
        width: 50px !important;
    }}

    .st-key-athlete_header_row
    [data-testid="column"]:nth-child(2) {{
        flex: 1 1 auto !important;
    }}

    .st-key-athlete_header_row
    [data-testid="column"]:nth-child(3) {{
        flex: 0 0 48px !important;
        width: 48px !important;
    }}

    .st-key-athlete_header_row
    [data-testid="column"]:nth-child(4) {{
        flex: 0 0 44px !important;
        width: 44px !important;
    }}

    .st-key-athlete_avatar_circle button {{
        width: 46px !important;
        height: 46px !important;
        min-width: 46px !important;
        min-height: 46px !important;
        border-width: 2px !important;
        font-size: 13px !important;
    }}

    .qutwin-athlete-brand .qutwin-brand-title {{
        font-size: 20px !important;
    }}

    .qutwin-athlete-brand .qutwin-brand-subtitle {{
        font-size: 9px !important;
    }}

    .st-key-athlete_header_notifications button,
    .st-key-athlete_header_settings button {{
        height: 42px !important;
        min-height: 42px !important;
        font-size: 12px !important;
    }}

    .st-key-athlete_nav_carousel
    [data-testid="stHorizontalBlock"] {{
        gap: 5px !important;
    }}

    [class*="st-key-athlete_nav_track_"]
    [data-testid="stHorizontalBlock"] {{
        gap: 5px !important;
    }}

    .st-key-top_nav_dashboard button,
    .st-key-top_nav_upload button,
    .st-key-top_nav_prediction button,
    .st-key-top_nav_history button,
    .st-key-top_nav_timeline button,
    .st-key-top_nav_visualisation button,
    .st-key-top_nav_simulation button,
    .st-key-top_nav_forecasting button,
    .st-key-top_nav_requests button {{
        height: 50px !important;
        min-height: 50px !important;
        padding: 5px 3px !important;
        border-radius: 9px !important;
        font-size: 10.5px !important;
        line-height: 1.1 !important;
    }}

    .st-key-athlete_nav_left button,
    .st-key-athlete_nav_right button {{
        height: 50px !important;
        min-height: 50px !important;
        border-radius: 9px !important;
        font-size: 22px !important;
    }}

    h1 {{
        font-size: 27px !important;
        line-height: 1.15 !important;
    }}

    h2 {{
        font-size: 22px !important;
    }}

    h3 {{
        font-size: 18px !important;
    }}

    input,
    textarea,
    select {{
        max-width: 100% !important;
    }}

    .js-plotly-plot,
    .plot-container,
    .plotly,
    .svg-container {{
        width: 100% !important;
        max-width: 100% !important;
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

    .st-key-top_nav_dashboard button,
    .st-key-top_nav_upload button,
    .st-key-top_nav_prediction button,
    .st-key-top_nav_history button,
    .st-key-top_nav_timeline button,
    .st-key-top_nav_visualisation button,
    .st-key-top_nav_simulation button,
    .st-key-top_nav_forecasting button,
    .st-key-top_nav_requests button {{
        height: 70px !important;
        min-height: 70px !important;
        font-size: 16px !important;
    }}

    .st-key-athlete_nav_left button,
    .st-key-athlete_nav_right button {{
        height: 70px !important;
        min-height: 70px !important;
        font-size: 34px !important;
    }}
}}


/* =========================================================
   ACCESSIBILITY: REDUCED MOTION
========================================================= */

@media (prefers-reduced-motion: reduce) {{
    [class*="st-key-athlete_nav_track_"] {{
        animation: none !important;
    }}
}}

</style>
""",
        unsafe_allow_html=True,
    )

    # ========================================================
    # STICKY HEADER CONTAINER
    # ========================================================

    with st.container(
        key="athlete_top_nav_shell",
    ):

        # ====================================================
        # HEADER ROW
        # ====================================================

        with st.container(
            key="athlete_header_row"
        ):

            (
                avatar_col,
                brand_col,
                bell_col,
                settings_col,
            ) = st.columns(
                [
                    0.65,
                    7.8,
                    0.9,
                    0.75,
                ],
                vertical_alignment="center",
            )

            # ------------------------------------------------
            # AVATAR
            # ------------------------------------------------

            with avatar_col:

                if st.button(
                    initials,
                    key="athlete_avatar_circle",
                    help=(
                        f"Open "
                        f"{athlete_name}'s "
                        f"profile"
                    ),
                ):
                    open_athlete_page(
                        "Profile"
                    )

            # ------------------------------------------------
            # BRAND
            # ------------------------------------------------

            with brand_col:

                st.html(
                    """
<div class="qutwin-athlete-brand">
    <div
        class="qutwin-brand-title"
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
        class="qutwin-brand-subtitle"
        style="
            color:#94a3b8;
            font-size:11px;
            margin-top:6px;
        "
    >
        Athlete Digital Twin
    </div>
</div>
"""
                )

            # ------------------------------------------------
            # NOTIFICATIONS
            # ------------------------------------------------

            with bell_col:

                bell_label = (
                    f"🔔 {unread_count}"
                    if unread_count > 0
                    else "🔔"
                )

                if st.button(
                    bell_label,
                    key=(
                        "athlete_header_"
                        "notifications"
                    ),
                    help="Notifications",
                    use_container_width=True,
                ):
                    open_athlete_page(
                        "Notifications"
                    )

            # ------------------------------------------------
            # SETTINGS
            # ------------------------------------------------

            with settings_col:

                if st.button(
                    "⚙️",
                    key=(
                        "athlete_header_"
                        "settings"
                    ),
                    help="Settings",
                    use_container_width=True,
                ):
                    open_athlete_page(
                        "Settings"
                    )

        # ====================================================
        # DIVIDER
        # ====================================================

        st.html(
            """
<div style="
    height:1px;
    background:rgba(148,163,184,0.18);
    margin:10px 0 10px 0;
"></div>
"""
        )

        # ====================================================
        # CAROUSEL
        # ====================================================

        _render_athlete_nav_carousel()


# ============================================================
# INJURY PREDICTION LOGIC
# ============================================================

def _injury_prediction(
    injury_risk_raw,
):

    injury_text = str(
        injury_risk_raw
    ).strip().lower()

    if injury_text in {
        "high",
        "high risk",
        "elevated",
    }:

        return (
            "HIGH PRIORITY",
            "Injury Risk Elevated",
            (
                "Your injury risk is higher than usual. "
                "Review your current training load "
                "and recovery status."
            ),
            "high",
        )

    if injury_text in {
        "medium",
        "moderate",
        "medium risk",
    }:

        return (
            "MEDIUM PRIORITY",
            "Injury Risk Moderate",
            (
                "Your injury risk is currently moderate. "
                "Monitor training load and recovery closely."
            ),
            "medium",
        )

    if injury_text in {
        "low",
        "low risk",
    }:

        return (
            "OKAY",
            "Injury Risk Low",
            (
                "Your current injury risk is low. "
                "Continue maintaining a balanced "
                "training and recovery routine."
            ),
            "low",
        )

    injury_numeric = _safe_float(
        injury_risk_raw,
        -1,
    )

    if injury_numeric >= 70:

        return (
            "HIGH PRIORITY",
            "Injury Risk Elevated",
            (
                "Your injury risk is currently elevated. "
                "Prioritise recovery and monitor training stress."
            ),
            "high",
        )

    if injury_numeric >= 40:

        return (
            "MEDIUM PRIORITY",
            "Injury Risk Moderate",
            (
                "Your injury risk is moderate. "
                "Monitor fatigue, workload, and recovery."
            ),
            "medium",
        )

    if injury_numeric >= 0:

        return (
            "OKAY",
            "Injury Risk Low",
            (
                "Your current injury risk is low. "
                "Continue following your normal recovery routine."
            ),
            "low",
        )

    return (
        "MONITOR",
        "Injury Risk Status",
        (
            "Not enough information is currently available "
            "to determine your injury risk."
        ),
        "medium",
    )


# ============================================================
# AI PREDICTION CARDS
# ============================================================

def _render_ai_prediction_cards(
    latest,
):

    fatigue_score = _safe_float(
        latest.get(
            "fatigue_score",
            0,
        )
    )

    readiness_score = _safe_float(
        latest.get(
            "readiness_score",
            0,
        )
    )

    (
        injury_priority,
        injury_title,
        injury_description,
        injury_level,
    ) = _injury_prediction(
        latest.get(
            "injury_risk",
            "Unknown",
        )
    )

    # ========================================================
    # FATIGUE
    # ========================================================

    if fatigue_score >= 70:

        fatigue_priority = (
            "HIGH PRIORITY"
        )

        fatigue_title = (
            "Fatigue Levels High"
        )

        fatigue_description = (
            "Your fatigue level is high. "
            "Consider reducing training intensity "
            "and increasing recovery."
        )

        fatigue_level = "high"

    elif fatigue_score >= 45:

        fatigue_priority = (
            "MEDIUM PRIORITY"
        )

        fatigue_title = (
            "Fatigue Levels Increasing"
        )

        fatigue_description = (
            "Fatigue levels are rising. "
            "Consider optimising your recovery strategies."
        )

        fatigue_level = "medium"

    else:

        fatigue_priority = "OKAY"

        fatigue_title = (
            "Fatigue Under Control"
        )

        fatigue_description = (
            "Your fatigue level is currently "
            "within a manageable range."
        )

        fatigue_level = "low"

    # ========================================================
    # RECOVERY
    # ========================================================

    if readiness_score >= 70:

        recovery_priority = "OKAY"

        recovery_title = (
            "Recovery On Track"
        )

        recovery_description = (
            "Your recovery is progressing well. "
            "Keep maintaining your current routine."
        )

        recovery_level = "low"

    elif readiness_score >= 45:

        recovery_priority = (
            "MEDIUM PRIORITY"
        )

        recovery_title = (
            "Recovery Needs Attention"
        )

        recovery_description = (
            "Your readiness is moderate. "
            "Consider additional rest before "
            "increasing training intensity."
        )

        recovery_level = "medium"

    else:

        recovery_priority = (
            "HIGH PRIORITY"
        )

        recovery_title = (
            "Recovery Below Target"
        )

        recovery_description = (
            "Your readiness is currently low. "
            "Prioritise recovery before "
            "demanding training sessions."
        )

        recovery_level = "high"

    # ========================================================
    # CARD HTML
    # ========================================================

    def card_html(
        priority,
        title,
        description,
        level,
        icon,
    ):

        palette = {
            "high": (
                "#ef4444",
                "rgba(127,29,29,.44)",
                "rgba(40,15,23,.82)",
            ),
            "medium": (
                "#f59e0b",
                "rgba(120,53,15,.44)",
                "rgba(45,33,16,.82)",
            ),
            "low": (
                "#22c55e",
                "rgba(20,83,45,.46)",
                "rgba(12,50,36,.82)",
            ),
        }

        (
            accent,
            bg1,
            bg2,
        ) = palette[level]

        return f"""
<div
    style="
        min-height:220px;
        padding:22px;
        border-radius:14px 14px 0 0;
        border:1px solid {accent}66;
        background:
            linear-gradient(
                135deg,
                {bg1},
                {bg2}
            );
        box-shadow:
            0 12px 30px
            rgba(0,0,0,0.18);
    "
>

    <div style="
        display:flex;
        align-items:center;
        gap:14px;
    ">

        <div style="
            width:50px;
            height:50px;
            min-width:50px;
            border-radius:50%;
            border:2px solid {accent}99;
            background:{accent}33;
            color:{accent};
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:25px;
            font-weight:900;
        ">
            {icon}
        </div>

        <div>

            <div style="
                color:{accent};
                font-size:11px;
                font-weight:850;
                letter-spacing:0.6px;
                margin-bottom:6px;
            ">
                {html.escape(priority)}
            </div>

            <div style="
                color:#f8fafc;
                font-size:18px;
                font-weight:750;
            ">
                {html.escape(title)}
            </div>

        </div>

    </div>

    <div style="
        color:#cbd5e1;
        font-size:13px;
        line-height:1.55;
        margin-top:16px;
    ">
        {html.escape(description)}
    </div>

</div>
"""

    st.html(
        """
<div style="
    margin:30px 0 12px 0;
    color:#e2e8f0;
    font-size:13px;
    font-weight:800;
    letter-spacing:1.1px;
">
    AI PREDICTIONS
</div>
"""
    )

    (
        injury_col,
        fatigue_col,
        recovery_col,
    ) = st.columns(
        3
    )

    # --------------------------------------------------------
    # INJURY
    # --------------------------------------------------------

    with injury_col:

        st.html(
            card_html(
                injury_priority,
                injury_title,
                injury_description,
                injury_level,
                "↑",
            )
        )

        if st.button(
            "View Details →",
            key=(
                "dashboard_injury_"
                "prediction_details"
            ),
            use_container_width=True,
        ):
            open_athlete_page(
                "Predictions & Coach Recommendations"
            )

    # --------------------------------------------------------
    # FATIGUE
    # --------------------------------------------------------

    with fatigue_col:

        st.html(
            card_html(
                fatigue_priority,
                fatigue_title,
                fatigue_description,
                fatigue_level,
                "!",
            )
        )

        if st.button(
            "View Details →",
            key=(
                "dashboard_fatigue_"
                "prediction_details"
            ),
            use_container_width=True,
        ):
            open_athlete_page(
                "Predictions & Coach Recommendations"
            )

    # --------------------------------------------------------
    # RECOVERY
    # --------------------------------------------------------

    with recovery_col:

        st.html(
            card_html(
                recovery_priority,
                recovery_title,
                recovery_description,
                recovery_level,
                "✓",
            )
        )

        if st.button(
            "View Details →",
            key=(
                "dashboard_recovery_"
                "prediction_details"
            ),
            use_container_width=True,
        ):
            open_athlete_page(
                "Predictions & Coach Recommendations"
            )


# ============================================================
# SUMMARY CARDS
# ============================================================

def _render_summary_cards(
    latest,
):

    readiness = _safe_float(
        latest.get(
            "readiness_score"
        )
    )

    recovery = _safe_float(
        latest.get(
            "recovery_index",
            latest.get(
                "readiness_score",
                0,
            ),
        )
    )

    training_load = _safe_float(
        latest.get(
            "training_load"
        )
    )

    twin_score = _safe_float(
        latest.get(
            "twin_score"
        )
    )

    injury_risk = latest.get(
        "injury_risk",
        "N/A",
    )

    # ========================================================
    # READINESS STATUS
    # ========================================================

    if readiness >= 70:
        readiness_status = "Ready"
        readiness_class = "good"

    elif readiness >= 45:
        readiness_status = "Moderate"
        readiness_class = "warn"

    else:
        readiness_status = "Low"
        readiness_class = "danger"

    # ========================================================
    # RECOVERY STATUS
    # ========================================================

    if recovery >= 70:
        recovery_status = "On Track"
        recovery_class = "good"

    elif recovery >= 45:
        recovery_status = "Monitor"
        recovery_class = "warn"

    else:
        recovery_status = (
            "Needs Recovery"
        )
        recovery_class = "danger"

    # ========================================================
    # INJURY STATUS
    # ========================================================

    risk_text = str(
        injury_risk
    ).lower()

    if "high" in risk_text:

        risk_status = "High Risk"
        risk_class = "danger"

    elif (
        "medium" in risk_text
        or "moderate" in risk_text
    ):

        risk_status = "Monitor"
        risk_class = "warn"

    else:

        risk_status = "Low Risk"
        risk_class = "good"

    # ========================================================
    # TRAINING LOAD STATUS
    # ========================================================

    if training_load >= 700:

        load_status = "Heavy"
        load_class = "warn"

    elif training_load >= 350:

        load_status = "Moderate"
        load_class = "info"

    else:

        load_status = "Light"
        load_class = "good"

    # ========================================================
    # TWIN SCORE STATUS
    # ========================================================

    if twin_score >= 80:

        twin_status = "Strong"
        twin_class = "good"

    elif twin_score >= 60:

        twin_status = "Stable"
        twin_class = "info"

    else:

        twin_status = (
            "Needs Attention"
        )
        twin_class = "warn"

    # ========================================================
    # CARD BUILDER
    # ========================================================

    def summary_card(
        label,
        value,
        status,
        status_class,
        icon,
    ):

        status_colours = {
            "good": (
                "#4ade80",
                "rgba(34,197,94,0.12)",
            ),
            "warn": (
                "#fbbf24",
                "rgba(245,158,11,0.12)",
            ),
            "danger": (
                "#f87171",
                "rgba(239,68,68,0.12)",
            ),
            "info": (
                "#7dd3fc",
                "rgba(14,165,233,0.12)",
            ),
        }

        (
            status_colour,
            status_background,
        ) = status_colours[
            status_class
        ]

        return f"""
<div style="
    min-height:150px;
    padding:16px;
    border-radius:14px;
    border:
        1px solid
        rgba(56,189,248,0.18);
    background:
        linear-gradient(
            145deg,
            rgba(8,47,73,0.34),
            rgba(2,12,27,0.70)
        );
">

    <div style="
        display:flex;
        align-items:center;
        gap:8px;
    ">

        <div style="
            width:30px;
            height:30px;
            border-radius:9px;
            display:flex;
            align-items:center;
            justify-content:center;
            background:
                rgba(14,165,233,0.12);
            color:#38bdf8;
            font-size:15px;
        ">
            {icon}
        </div>

        <div style="
            color:#94a3b8;
            font-size:10px;
            font-weight:800;
            letter-spacing:0.7px;
        ">
            {html.escape(label)}
        </div>

    </div>


    <div style="
        color:#f8fafc;
        margin-top:15px;
        font-size:28px;
        line-height:1;
        font-weight:850;
    ">
        {html.escape(str(value))}
    </div>


    <div style="
        display:inline-flex;
        margin-top:16px;
        padding:5px 9px;
        border-radius:999px;
        font-size:10px;
        font-weight:800;
        color:{status_colour};
        background:{status_background};
    ">
        {html.escape(status)}
    </div>

</div>
"""

    # ========================================================
    # TITLE
    # ========================================================

    st.html(
        """
<div style="
    margin:0 0 10px 0;
    color:#cbd5e1;
    font-size:12px;
    font-weight:850;
    letter-spacing:1.05px;
">
    TODAY'S SUMMARY
</div>
"""
    )

    # ========================================================
    # SUMMARY CARDS
    # ========================================================

    summary_cols = st.columns(
        5
    )

    with summary_cols[0]:

        st.html(
            summary_card(
                "READINESS",
                f"{readiness:.0f}/100",
                readiness_status,
                readiness_class,
                "⌁",
            )
        )

    with summary_cols[1]:

        st.html(
            summary_card(
                "RECOVERY",
                f"{recovery:.0f}%",
                recovery_status,
                recovery_class,
                "↻",
            )
        )

    with summary_cols[2]:

        st.html(
            summary_card(
                "INJURY RISK",
                injury_risk,
                risk_status,
                risk_class,
                "◇",
            )
        )

    with summary_cols[3]:

        st.html(
            summary_card(
                "TRAINING LOAD",
                (
                    f"{training_load:.0f} "
                    f"AU"
                ),
                load_status,
                load_class,
                "▥",
            )
        )

    with summary_cols[4]:

        st.html(
            summary_card(
                "TWIN SCORE",
                f"{twin_score:.1f}",
                twin_status,
                twin_class,
                "⬡",
            )
        )


# ============================================================
# MAIN ATHLETE HOME
# ============================================================

def athlete_feature_gallery():

    athlete_id = str(
        st.session_state.user_id
    )

    # ========================================================
    # ATHLETE PROFILE
    # ========================================================

    profile = (
        get_athlete_profile(
            athlete_id
        )
    )

    # ========================================================
    # DIGITAL TWIN HISTORY
    # ========================================================

    history_df = (
        get_athlete_twin_history(
            athlete_id
        )
    )

    # ========================================================
    # UNREAD NOTIFICATIONS
    # ========================================================

    try:

        unread_count = (
            get_unread_notification_count(
                "Athlete",
                athlete_id,
            )
        )

    except Exception:

        unread_count = 0

    # ========================================================
    # TOP HEADER + NAVIGATION
    # ========================================================

    _render_athlete_top_navigation(
        profile,
        unread_count,
    )

    # ========================================================
    # ATHLETE NAME
    # ========================================================

    athlete_name = (
        profile.get("name")
        if (
            profile
            and profile.get("name")
        )
        else athlete_id
    )

    # ========================================================
    # LATEST STATE
    # ========================================================

    latest = None

    if (
        history_df is not None
        and not history_df.empty
    ):

        history_df = (
            history_df.copy()
        )

        history_df[
            "timestamp"
        ] = pd.to_datetime(
            history_df[
                "timestamp"
            ],
            errors="coerce",
        )

        latest = (
            history_df
            .sort_values(
                "timestamp"
            )
            .iloc[-1]
        )

    # ========================================================
    # WELCOME
    # ========================================================

    st.html(
        f"""
<div style="
    margin:
        8px
        0
        22px
        0;
">

    <div style="
        color:#94a3b8;
        font-size:11px;
        font-weight:850;
        letter-spacing:1.2px;
    ">
        ATHLETE DIGITAL TWIN
    </div>

    <div style="
        color:#f8fafc;
        margin-top:5px;
        font-size:30px;
        font-weight:850;
        letter-spacing:-0.4px;
    ">
        Welcome back,
        {html.escape(str(athlete_name))}
    </div>

    <div style="
        color:#94a3b8;
        margin-top:5px;
        font-size:13px;
    ">
        Your latest Digital Twin performance
        and recovery summary
    </div>

</div>
"""
    )

    # ========================================================
    # NO DATA
    # ========================================================

    if latest is None:

        st.info(
            "No Digital Twin state is available yet. "
            "Upload athlete data to generate "
            "your first summary."
        )

        if st.button(
            "Upload Athlete Data",
            key=(
                "home_upload_first_data"
            ),
            type="primary",
        ):

            open_athlete_page(
                "Upload Garmin Data"
            )

        return

    # ========================================================
    # TODAY'S SUMMARY
    # ========================================================

    _render_summary_cards(
        latest
    )

    # ========================================================
    # AI PREDICTIONS
    # ========================================================

    _render_ai_prediction_cards(
        latest
    )