import base64
import html
from pathlib import Path

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
# ATHLETE NAVIGATION ITEMS
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
# ATHLETE NAVIGATION ITEMS RENDERER
# ============================================================

def _render_athlete_top_navigation(profile, unread_count=0):
    """Fixed, responsive navigation using the existing session-state router."""
    athlete_name = str((profile or {}).get("name") or st.session_state.user_id)
    photo_uri = _photo_to_data_uri((profile or {}).get("profile_photo"))
    initials = "".join(part[0].upper() for part in athlete_name.split() if part)[:2] or "A"
    # Dashboard is the home summary; Digital Twin retains the analytical dashboard.
    items = [{"label": "Dashboard", "page": "Athlete Home", "key": "home"}]
    items += [dict(item, label="Digital Twin") if item["key"] == "dashboard"
              else item for item in ATHLETE_NAV_ITEMS]
    current_page = st.session_state.get("current_page", "Athlete Home")
    avatar_css = ""
    if photo_uri:
        avatar_css = (
            '.st-key-athlete_avatar_circle button {'
            f'background-image: url("{photo_uri}") !important;'
            'background-size: cover !important; background-position: center !important;'
            'color: transparent !important;}'
            '.st-key-athlete_avatar_circle button p {color: transparent !important;}'
        )
    st.markdown("""
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
/* Shared athlete layout: remove inherited page padding and empty-block gaps.
   Keep spacing inside actual page content unchanged. */
body:has(.st-key-athlete_top_nav_shell) .block-container,
body:has(.st-key-athlete_top_nav_shell) .stMainBlockContainer,
body:has(.st-key-athlete_top_nav_shell) [data-testid="stMainBlockContainer"],
body:has(.st-key-athlete_top_nav_shell) [data-testid="stAppViewBlockContainer"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
    animation: none !important;
    transform: none !important;
    filter: none !important;
}
body:has(.st-key-athlete_top_nav_shell) .block-container > [data-testid="stVerticalBlock"],
body:has(.st-key-athlete_top_nav_shell) .stMainBlockContainer > [data-testid="stVerticalBlock"],
body:has(.st-key-athlete_top_nav_shell) [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
/* Older Streamlit versions wrap each container in an extra layout block. */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > .st-key-athlete_top_nav_shell),
[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-athlete_top_nav_shell) {
    height: 0 !important; min-height: 0 !important; margin: 0 !important;
    padding: 0 !important; border: 0 !important; overflow: visible !important;
    background: none !important; box-shadow: none !important; transform: none !important;
}
.st-key-athlete_page_content {
    padding: 94px 0 0 !important;
    margin-top: 0 !important;
    border: 0 !important; background: none !important; box-shadow: none !important;
}
.st-key-athlete_top_nav_shell {
    position: fixed !important; top: 0; left: 0; right: 0;
    width: 100% !important; height: 78px; z-index: 999;
    padding: 12px 24px !important; margin: 0 !important;
    background: #031320 !important;
    border-bottom: 1px solid #174451;
    box-shadow: 0 4px 18px rgba(0,0,0,.16);
    box-sizing: border-box;
}
.st-key-athlete_top_nav_shell > [data-testid="stVerticalBlock"] {gap: 0 !important;}
.st-key-athlete_top_nav_shell [data-testid="stHorizontalBlock"] {
    display: grid !important;
    grid-template-columns: 142px repeat(9, minmax(0, 1fr)) 48px 48px 48px;
    gap: 8px !important; align-items: center !important;
}
.st-key-athlete_top_nav_shell [data-testid="stColumn"] {
    width: 100% !important; min-width: 0 !important;
    flex: none !important; padding: 0 !important;
}
.st-key-athlete_top_nav_shell button {
    width: 100%; min-height: 46px !important; height: 46px !important;
    padding: 0 4px !important; border: 1px solid transparent !important;
    border-radius: 10px !important; background: transparent !important;
    color: #a9cdd3 !important; box-shadow: none !important;
}
.st-key-athlete_top_nav_shell button p {
    font-size: 14px !important; font-weight: 600 !important;
    white-space: nowrap !important; margin: 0 !important;
}
.st-key-athlete_top_nav_shell button:hover {
    background: #0c3440 !important; color: #ecfeff !important;
}
.st-key-athlete_top_nav_shell button[kind="primary"] {
    background: #103a46 !important; color: #5ee3e9 !important;
    border-color: #20717a !important;
}
.st-key-athlete_top_nav_shell button:focus-visible {
    outline: 2px solid #67e8f9 !important; outline-offset: 2px;
}
.st-key-athlete_header_notifications button,
.st-key-athlete_header_settings button,
.st-key-athlete_avatar_circle button {
    background-color: #0a2734 !important; border-color: #175362 !important;
}
.qutwin-nav-brand {font-size: 23px; font-weight: 800; color: #f0fdfa;
    height: 46px; display: flex; align-items: center; gap: 8px; white-space: nowrap;}
.qutwin-nav-brand span {color: #38c9d4;}

@media (max-width: 1450px) {
    .st-key-athlete_top_nav_shell {height: 128px; padding: 10px 16px !important;}
    .st-key-athlete_top_nav_shell [data-testid="stHorizontalBlock"] {
        grid-template-columns: repeat(9, minmax(0, 1fr)); gap: 6px !important;
    }
    .st-key-athlete_top_nav_shell [data-testid="stColumn"]:first-child {grid-column: span 6;}
    .st-key-athlete_top_nav_shell [data-testid="stColumn"]:nth-child(n+2):nth-child(-n+10) {order: 1;}
    .st-key-athlete_page_content {padding-top: 144px !important;}
    .st-key-athlete_top_nav_shell button p {font-size: 12px !important;}
}
@media (max-width: 760px) {
    .st-key-athlete_top_nav_shell {height: 180px; padding: 10px 8px !important;}
    .st-key-athlete_top_nav_shell [data-testid="stHorizontalBlock"] {
        grid-template-columns: repeat(5, minmax(0, 1fr));
    }
    .st-key-athlete_top_nav_shell [data-testid="stColumn"]:first-child {grid-column: span 2;}
    .st-key-athlete_top_nav_shell button p {font-size: 11px !important;}
    .qutwin-nav-brand {font-size: 21px;}
    .st-key-athlete_page_content {padding-top: 196px !important;}
}
</style>
""" + ("<style>" + avatar_css + "</style>" if avatar_css else ""),
                unsafe_allow_html=True)
    with st.container(key="athlete_top_nav_shell"):
        cols = st.columns([1.5] + [1] * len(items) + [0.5] * 3,
                          gap="small", vertical_alignment="center")
        with cols[0]:
            st.html('<div class="qutwin-nav-brand"><span>◈</span> QUTwin</div>')
        for col, item in zip(cols[1:1 + len(items)], items):
            with col:
                if st.button(item["label"], key=f"top_nav_{item['key']}",
                             help=f"Open {item['label']}",
                             type="primary" if current_page == item["page"] else "secondary",
                             use_container_width=True):
                    open_athlete_page(item["page"])
        with cols[1 + len(items)]:
            count = max(0, int(unread_count or 0))
            label = "🔔" + (f" {min(count, 99)}" if count else "")
            if st.button(label, key="athlete_header_notifications",
                         help=f"Notifications ({count} unread)", use_container_width=True):
                open_athlete_page("Notifications")
        with cols[2 + len(items)]:
            if st.button(initials, key="athlete_avatar_circle",
                         help=f"Open {athlete_name}'s profile", use_container_width=True):
                open_athlete_page("Profile")
        with cols[3 + len(items)]:
            if st.button("⚙️", key="athlete_header_settings",
                         help="Settings", use_container_width=True):
                open_athlete_page("Settings")







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

    with st.container(key="athlete_page_content"):
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
