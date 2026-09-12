import streamlit as st
from views.coach.shared import _get_risk_df, _render_page_heading

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
