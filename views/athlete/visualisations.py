import streamlit as st
from digital_twin.forecasting_engine import forecast_metric, generate_forecast_summary
from database.twin_repository import get_athlete_twin_history

def athlete_visualisations():

    st.title(
        "Visualisations / Graphs"
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
            "No visualisations available yet."
        )

        return

    chart_cols = [
        "heart_rate",
        "training_load",
        "fatigue_score",
        "readiness_score",
        "twin_score",
        "health_index",
    ]

    available_cols = [
        column
        for column in chart_cols
        if column
        in history_df.columns
    ]

    if available_cols:

        chart_df = (
            history_df
            .sort_values(
                "timestamp"
            )
        )

        st.subheader(
            "Digital Twin Historical Trends"
        )

        st.line_chart(
            chart_df[
                available_cols
            ]
        )

    else:

        st.info(
            "No chart-ready metrics available."
        )

    # --------------------------------------------------------
    # FORECAST PREVIEW
    # --------------------------------------------------------

    st.subheader(
        "7-Day Digital Twin Forecast"
    )

    fatigue_forecast = (
        forecast_metric(
            history_df,
            "fatigue_score",
            days=7,
        )
    )

    readiness_forecast = (
        forecast_metric(
            history_df,
            "readiness_score",
            days=7,
        )
    )

    if not fatigue_forecast.empty:

        st.write(
            "Fatigue Forecast"
        )

        st.line_chart(
            fatigue_forecast
            .set_index(
                "forecast_date"
            )[
                "forecast_value"
            ]
        )

    if not readiness_forecast.empty:

        st.write(
            "Readiness Forecast"
        )

        st.line_chart(
            readiness_forecast
            .set_index(
                "forecast_date"
            )[
                "forecast_value"
            ]
        )

    st.info(
        generate_forecast_summary(
            fatigue_forecast,
            readiness_forecast,
        )
    )
