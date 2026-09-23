import streamlit as st
from database.upload_history_repository import get_upload_history as get_athlete_twin_history

def athlete_dashboard():

    st.title(
        "Digital Twin Dashboard"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No Digital Twin state "
            "available yet."
        )

        st.write(
            "Upload athlete data to create "
            "your first Digital Twin state."
        )

        if st.button(
            "Upload Athlete Data",
            type="primary",
        ):

            # Keep internal route name for
            # compatibility with app.py.
            st.session_state.current_page = (
                "Upload Garmin Data"
            )

            st.rerun()

        return

    latest = (
        history_df.iloc[0]
    )

    if latest.get('prediction_status')=='research_estimate':
        st.info('Experimental estimates from the latest saved upload. Review Prediction for coverage and coach decisions.')
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Fatigue",
        latest.get(
            "fatigue_score",
            "N/A",
        ),
    )

    c2.metric(
        "Readiness",
        latest.get(
            "readiness_score",
            "N/A",
        ),
    )

    c3.metric(
        "Injury Risk",
        latest.get(
            "injury_risk",
            "N/A",
        ),
    )

    c4.metric(
        "Twin Score",
        latest.get(
            "twin_score",
            "N/A",
        ),
    )

    st.success(
        "Latest AI Recommendation"
    )

    st.info(
        latest.get(
            "recommendation",
            "No recommendation available.",
        )
    )

    if st.button(
        "Upload New Athlete Data"
    ):

        st.session_state.current_page = (
            "Upload Garmin Data"
        )

        st.rerun()
