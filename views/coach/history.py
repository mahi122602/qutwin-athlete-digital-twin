import streamlit as st
from database.twin_repository import get_athlete_twin_history
from views.coach.shared import _get_risk_df, _render_page_heading

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
