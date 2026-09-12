import pandas as pd
import streamlit as st
from database.coach_repository import get_assigned_athletes
from views.coach.shared import _format_number, _get_risk_df, _render_page_heading, _risk_counts, open_coach_page

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
