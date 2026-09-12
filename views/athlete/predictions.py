import streamlit as st
from database.recommendation_repository import get_latest_coach_recommendation
from database.twin_repository import get_athlete_twin_history

def athlete_predictions():

    st.title(
        "Predictions & Coach Recommendations"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    # --------------------------------------------------------
    # NO DIGITAL TWIN DATA
    # --------------------------------------------------------

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No predictions available yet. "
            "Upload athlete data first."
        )

        return

    # --------------------------------------------------------
    # LATEST DIGITAL TWIN STATE
    # --------------------------------------------------------

    latest = (
        history_df
        .sort_values("timestamp")
        .iloc[-1]
    )

    fatigue_score = latest.get(
        "fatigue_score",
        "N/A",
    )

    injury_risk = latest.get(
        "injury_risk",
        "N/A",
    )

    readiness_score = latest.get(
        "readiness_score",
        "N/A",
    )

    twin_score = latest.get(
        "twin_score",
        "N/A",
    )

    # --------------------------------------------------------
    # CURRENT PREDICTION SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Current Digital Twin Prediction"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Fatigue Score",
            fatigue_score,
        )

    with c2:

        st.metric(
            "Injury Risk",
            injury_risk,
        )

    with c3:

        st.metric(
            "Readiness",
            readiness_score,
        )

    with c4:

        st.metric(
            "Twin Score",
            twin_score,
        )

    st.divider()

    # --------------------------------------------------------
    # AI RECOMMENDATION
    # --------------------------------------------------------

    st.subheader(
        "AI Recommendation"
    )

    ai_recommendation = latest.get(
        "recommendation",
        "No recommendation available.",
    )

    if ai_recommendation:

        st.info(
            ai_recommendation
        )

    else:

        st.info(
            "No AI recommendation available."
        )

    st.divider()

    # --------------------------------------------------------
    # COACH FEEDBACK
    # --------------------------------------------------------

    st.subheader(
        "Coach Feedback"
    )

    coach_rec = (
        get_latest_coach_recommendation(
            st.session_state.user_id
        )
    )

    if coach_rec:

        recommendation = (
            coach_rec.get(
                "recommendation"
            )
            or coach_rec.get(
                "coach_comment"
            )
            or (
                "No coach feedback "
                "provided."
            )
        )

        st.success(
            recommendation
        )

        coach_id = (
            coach_rec.get(
                "coach_id",
                "Coach",
            )
        )

        reviewed_at = (
            coach_rec.get(
                "reviewed_at"
            )
        )

        if reviewed_at:

            st.caption(
                f"Reviewed by {coach_id} • "
                f"{reviewed_at}"
            )

        else:

            st.caption(
                f"Reviewed by {coach_id}"
            )

    else:

        st.warning(
            "No coach feedback "
            "available yet."
        )
