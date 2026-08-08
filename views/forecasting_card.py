from __future__ import annotations

import streamlit as st


def render_forecasting_card(open_athlete_page) -> None:
    """Render the Forecasting feature as a normal athlete-home card."""
    with st.container(border=True):
        st.caption("09")
        st.subheader("Forecasting")

        horizon_col, pathway_col = st.columns(2)
        with horizon_col:
            st.metric("Forecast Horizon", "7 Days")
        with pathway_col:
            st.metric("Pathway", "Gender-aware")

        st.caption(
            "View fatigue, readiness, injury-risk and Digital Twin forecasts. "
            "Female athletes can also use optional menstrual-cycle tracking."
        )

        if st.button(
            "View Forecast",
            key="open_forecasting",
            use_container_width=True,
        ):
            open_athlete_page("Forecasting")
