import streamlit as st
from database.twin_repository import get_athlete_twin_history
from dashboards.visualization import show_athlete_timeline
from views.coach.shared import _get_risk_df, _render_page_heading

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
