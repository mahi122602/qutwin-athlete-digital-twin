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
    Navigate without reloading the browser URL.

    This keeps the current Streamlit authentication session alive
    and prevents the login page from flashing between pages.
    """
    st.session_state.current_page = page_name
    st.rerun()


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _photo_to_data_uri(profile_photo):
    """
    Convert the profile-photo bytes stored in PostgreSQL into
    a base64 data URI that can be used as a CSS background image.
    """

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

    # --------------------------------------------------------
    # Detect image format
    # --------------------------------------------------------
    if profile_photo.startswith(b"\x89PNG"):
        mime_type = "image/png"

    elif profile_photo.startswith(b"\xff\xd8\xff"):
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

    return f"data:{mime_type};base64,{encoded}"


# ============================================================
# MAIN ATHLETE HEADER + TOP NAVIGATION
# ============================================================

def _render_athlete_top_navigation(
    profile,
    unread_count=0,
):
    """
    Athlete main header.

    LEFT:
        clickable athlete avatar
        QUTwin brand

    RIGHT:
        notification bell
        settings

    SECOND ROW:
        eight athlete navigation buttons

    Every control uses Streamlit session-state navigation.
    """

    athlete_name = (
        profile.get("name")
        if profile and profile.get("name")
        else str(st.session_state.user_id)
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
        for part in str(athlete_name).split()
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
    # STYLES
    # ========================================================

    st.markdown(
        f"""
<style>

/* =========================================================
   STICKY TOP NAVIGATION CONTAINER
   ========================================================= */

.st-key-athlete_top_nav_shell {{
    position: sticky;
    top: 0;
    z-index: 999;

    padding:
        12px
        14px
        10px
        14px;

    margin-bottom:
        18px;

    border:
        1px solid
        rgba(56, 189, 248, 0.15);

    border-radius:
        0 0 18px 18px;

    background:
        rgba(2, 12, 27, 0.96);

    backdrop-filter:
        blur(16px);

    box-shadow:
        0 12px 30px
        rgba(0, 0, 0, 0.20);
}}


/* =========================================================
   CLICKABLE ATHLETE AVATAR
   ========================================================= */

.st-key-athlete_avatar_circle button {{
    width:
        62px !important;

    height:
        62px !important;

    min-width:
        62px !important;

    min-height:
        62px !important;

    padding:
        0 !important;

    border-radius:
        50% !important;

    border:
        3px solid
        #22d3ee !important;

    {avatar_background}

    color:
        {avatar_text_colour} !important;

    font-weight:
        850 !important;

    font-size:
        17px !important;

    box-shadow:
        0
        0
        0
        4px
        rgba(34, 211, 238, 0.10)
        !important;

    transition:
        transform
        0.16s
        ease,
        border-color
        0.16s
        ease,
        box-shadow
        0.16s
        ease;
}}


.st-key-athlete_avatar_circle button:hover {{
    transform:
        scale(1.05);

    border-color:
        #67e8f9 !important;

    box-shadow:
        0
        0
        0
        5px
        rgba(34, 211, 238, 0.18)
        !important;
}}


/* Hide initials when actual photo is being used */

.st-key-athlete_avatar_circle button p {{
    color:
        {avatar_text_colour} !important;
}}


/* =========================================================
   HEADER BELL + SETTINGS
   ========================================================= */

.st-key-athlete_header_notifications button,
.st-key-athlete_header_settings button {{
    height:
        46px !important;

    min-height:
        46px !important;

    border-radius:
        12px !important;

    border:
        1px solid
        rgba(148, 163, 184, 0.25)
        !important;

    background:
        rgba(15, 23, 42, 0.78)
        !important;
}}


.st-key-athlete_header_notifications button:hover,
.st-key-athlete_header_settings button:hover {{
    border-color:
        rgba(34, 211, 238, 0.60)
        !important;

    background:
        rgba(8, 47, 73, 0.78)
        !important;
}}


/* =========================================================
   TOP NAVIGATION BUTTONS
   ========================================================= */

.st-key-top_nav_dashboard button,
.st-key-top_nav_upload button,
.st-key-top_nav_prediction button,
.st-key-top_nav_history button,
.st-key-top_nav_timeline button,
.st-key-top_nav_visualisation button,
.st-key-top_nav_simulation button,
.st-key-top_nav_forecasting button {{
    min-height:
        48px !important;

    height:
        100% !important;

    padding:
        8px 7px !important;

    border-radius:
        10px !important;

    font-size:
        11px !important;

    font-weight:
        650 !important;

    border:
        1px solid
        rgba(56, 189, 248, 0.15)
        !important;

    background:
        rgba(15, 23, 42, 0.70)
        !important;

    transition:
        border-color
        0.15s
        ease,
        background
        0.15s
        ease;
}}


.st-key-top_nav_dashboard button:hover,
.st-key-top_nav_upload button:hover,
.st-key-top_nav_prediction button:hover,
.st-key-top_nav_history button:hover,
.st-key-top_nav_timeline button:hover,
.st-key-top_nav_visualisation button:hover,
.st-key-top_nav_simulation button:hover,
.st-key-top_nav_forecasting button:hover {{
    border-color:
        rgba(34, 211, 238, 0.60)
        !important;

    background:
        linear-gradient(
            135deg,
            rgba(37, 99, 235, 0.50),
            rgba(6, 182, 212, 0.38)
        )
        !important;
}}


/* =========================================================
   AI VIEW DETAILS BUTTONS
   ========================================================= */

.st-key-dashboard_injury_prediction_details button,
.st-key-dashboard_fatigue_prediction_details button,
.st-key-dashboard_recovery_prediction_details button {{
    margin-top:
        -2px;

    min-height:
        40px !important;

    border-radius:
        0 0 12px 12px !important;

    font-size:
        12px !important;

    font-weight:
        700 !important;
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

        (
            avatar_col,
            brand_col,
            spacer_col,
            bell_col,
            settings_col,
        ) = st.columns(
            [
                0.65,
                2.0,
                5.8,
                0.8,
                0.8,
            ],
            vertical_alignment="center",
        )

        # ----------------------------------------------------
        # CLICKABLE AVATAR
        # ----------------------------------------------------

        with avatar_col:

            if st.button(
                initials,
                key="athlete_avatar_circle",
                help=f"Open {athlete_name}'s profile",
            ):
                open_athlete_page(
                    "Profile"
                )

        # ----------------------------------------------------
        # QUTWIN BRAND
        # ----------------------------------------------------

        with brand_col:

            st.html(
                """
<div style="
    padding-left:4px;
">
    <div style="
        color:#f8fafc;
        font-size:27px;
        font-weight:850;
        line-height:1;
        letter-spacing:-0.4px;
    ">
        QUTwin
    </div>

    <div style="
        color:#94a3b8;
        font-size:11px;
        margin-top:6px;
    ">
        Athlete Digital Twin
    </div>
</div>
"""
            )

        # ----------------------------------------------------
        # NOTIFICATION BELL
        # ----------------------------------------------------

        with bell_col:

            bell_label = (
                f"🔔 {unread_count}"
                if unread_count > 0
                else "🔔"
            )

            if st.button(
                bell_label,
                key="athlete_header_notifications",
                help="Notifications",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Notifications"
                )

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        with settings_col:

            if st.button(
                "⚙️",
                key="athlete_header_settings",
                help="Settings",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Settings"
                )

        # ----------------------------------------------------
        # DIVIDER
        # ----------------------------------------------------

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
        # ONE-ROW NAVIGATION
        # ====================================================

        nav = st.columns(8)

        with nav[0]:

            if st.button(
                "Digital Twin Dashboard",
                key="top_nav_dashboard",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Digital Twin Dashboard"
                )

        with nav[1]:

            if st.button(
                "Upload Garmin",
                key="top_nav_upload",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Upload Garmin Data"
                )

        with nav[2]:

            if st.button(
                "Prediction",
                key="top_nav_prediction",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Predictions & Coach Recommendations"
                )

        with nav[3]:

            if st.button(
                "Digital Twin History",
                key="top_nav_history",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Digital Twin History"
                )

        with nav[4]:

            if st.button(
                "Digital Twin Timeline",
                key="top_nav_timeline",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Digital Twin Timeline"
                )

        with nav[5]:

            if st.button(
                "Visualisation",
                key="top_nav_visualisation",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Visualisations / Graphs"
                )

        with nav[6]:

            if st.button(
                "What-if Simulation",
                key="top_nav_simulation",
                use_container_width=True,
            ):
                open_athlete_page(
                    "What-if Simulation"
                )

        with nav[7]:

            if st.button(
                "Forecasting",
                key="top_nav_forecasting",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Forecasting"
                )


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
    # FATIGUE CARD LOGIC
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
    # RECOVERY CARD LOGIC
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
    # CARD HTML BUILDER
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

    # ========================================================
    # SECTION HEADING
    # ========================================================

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

    # ========================================================
    # THREE AI CARDS
    # ========================================================

    injury_col, fatigue_col, recovery_col = st.columns(
        3
    )

    # --------------------------------------------------------
    # INJURY RISK
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
            key="dashboard_injury_prediction_details",
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
            key="dashboard_fatigue_prediction_details",
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
            key="dashboard_recovery_prediction_details",
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
        recovery_status = "Needs Recovery"
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
        twin_status = "Needs Attention"
        twin_class = "warn"

    # ========================================================
    # SUMMARY CARD BUILDER
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
    # SECTION TITLE
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
    # FIVE SUMMARY CARDS
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
                f"{training_load:.0f} AU",
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
# MAIN ATHLETE HOME PAGE
# ============================================================

def athlete_feature_gallery():

    athlete_id = str(
        st.session_state.user_id
    )

    # ========================================================
    # ATHLETE PROFILE
    # ========================================================

    profile = get_athlete_profile(
        athlete_id
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
    # UNREAD NOTIFICATION COUNT
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
        if profile
        and profile.get("name")
        else athlete_id
    )

    # ========================================================
    # LATEST DIGITAL TWIN STATE
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
    # NO DIGITAL TWIN DATA
    # ========================================================

    if latest is None:

        st.info(
            "No Digital Twin state is available yet. "
            "Upload athlete data to generate "
            "your first summary."
        )

        if st.button(
            "Upload Athlete Data",
            key="home_upload_first_data",
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