import streamlit as st
from views.coach.shared import _get_risk_df, _render_page_heading, _risk_counts

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
