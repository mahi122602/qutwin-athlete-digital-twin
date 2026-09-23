import streamlit as st
from database.twin_repository import get_athlete_twin_history
from digital_twin.forecasting_engine import forecast_metric, generate_forecast_summary
from views.coach.shared import _format_number, _get_risk_df, _render_page_heading

def selected_athlete_twin_summary():
    _render_page_heading(
        "Selected Athlete Twin Summary",
        (
            "Review the latest state, approve "
            "recommendations and inspect forecast trends."
        ),
    )

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info(
            "No athlete Digital Twin data "
            "is available yet."
        )
        return

    options = risk_df[
        "Athlete ID"
    ].tolist()

    selected_athlete = st.selectbox(
        "Select Athlete",
        options,
        key="coach_summary_athlete",
    )

    selected_row = risk_df[
        risk_df["Athlete ID"]
        == selected_athlete
    ].iloc[0]

    athlete_name = (
        selected_row.get("Name")
        or selected_athlete
    )

    st.subheader(
        f"Current State · {athlete_name}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Fatigue",
        _format_number(
            selected_row[
                "Fatigue Score"
            ]
        ),
    )

    c2.metric(
        "Injury Risk",
        selected_row[
            "Injury Level"
        ],
    )

    c3.metric(
        "Readiness",
        _format_number(
            selected_row[
                "Readiness Score"
            ],
            "%",
        ),
    )

    c4.metric(
        "Twin Score",
        _format_number(
            selected_row[
                "Twin Score"
            ],
        ),
    )

    st.subheader("Coach Review & Approval")
    st.caption("AI drafts and decisions are linked to each uploaded file in Recommendation Reviews.")
    if st.button("Open Recommendation Reviews", key="summary_open_reviews", type="primary"):
        st.session_state.current_page = "Recommendation Reviews"
        st.rerun()
    st.divider()

    st.subheader(
        "7-Day Digital Twin Forecast"
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
            "Not enough Digital Twin history "
            "is available for forecasting."
        )
        return

    fatigue_forecast = forecast_metric(
        history_df,
        "fatigue_score",
        days=7,
    )

    readiness_forecast = forecast_metric(
        history_df,
        "readiness_score",
        days=7,
    )

    if (
        fatigue_forecast is not None
        and not fatigue_forecast.empty
    ):
        st.write(
            "Predicted Fatigue Trend"
        )

        st.line_chart(
            fatigue_forecast.set_index(
                "forecast_date"
            )["forecast_value"]
        )

    if (
        readiness_forecast is not None
        and not readiness_forecast.empty
    ):
        st.write(
            "Predicted Readiness Trend"
        )

        st.line_chart(
            readiness_forecast.set_index(
                "forecast_date"
            )["forecast_value"]
        )

    st.success(
        "Forecast Summary"
    )

    st.info(
        generate_forecast_summary(
            fatigue_forecast,
            readiness_forecast,
        )
    )
