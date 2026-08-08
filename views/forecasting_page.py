from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from database.forecasting_repository import (
    add_menstrual_cycle,
    ensure_forecasting_schema,
    get_forecasting_profile,
    get_menstrual_history,
    replace_menstrual_history,
    save_forecast_run,
    set_athlete_gender,
    set_menstrual_tracking_enabled,
)
from database.recommendation_repository import get_latest_coach_recommendation
from database.twin_repository import get_athlete_twin_history
from forecasting.engine import build_forecast_bundle, calculate_cycle_summary


GENDER_OPTIONS = [
    "Female",
    "Male",
    "Non-binary",
    "Prefer not to say",
]


def _normalise_gender(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None

    aliases = {
        "f": "Female",
        "female": "Female",
        "woman": "Female",
        "m": "Male",
        "male": "Male",
        "man": "Male",
        "nonbinary": "Non-binary",
        "non-binary": "Non-binary",
        "prefer not to say": "Prefer not to say",
    }
    return aliases.get(clean.lower(), clean)


def _coach_recommendation_text(athlete_id: str) -> str | None:
    try:
        recommendation = get_latest_coach_recommendation(athlete_id)
    except Exception:
        return None

    if not recommendation:
        return None

    if isinstance(recommendation, str):
        return recommendation.strip() or None

    if hasattr(recommendation, "to_dict"):
        recommendation = recommendation.to_dict()

    if isinstance(recommendation, dict):
        for key in (
            "recommendation",
            "coach_comment",
            "coach_recommendation",
            "ai_recommendation",
        ):
            value = recommendation.get(key)
            if value:
                return str(value).strip()
    return None


def _display_cycle_summary(history_df: pd.DataFrame) -> None:
    summary = calculate_cycle_summary(history_df, reference_date=date.today())
    metric_columns = st.columns(4)

    last_period = summary.get("last_period_start")
    average_cycle = summary.get("average_cycle_length")
    average_duration = summary.get("average_period_duration")
    next_period = summary.get("estimated_next_period")

    metric_columns[0].metric(
        "Last period",
        last_period.strftime("%d %b %Y") if last_period else "Not available",
    )
    metric_columns[1].metric(
        "Average cycle length",
        f"{average_cycle} days" if average_cycle else "Not available",
    )
    metric_columns[2].metric(
        "Average period duration",
        f"{average_duration} days" if average_duration else "Not available",
    )
    metric_columns[3].metric(
        "Estimated next period",
        next_period.strftime("%d %b %Y") if next_period else "Not available",
    )


def _prepare_history_for_editor(history_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "cycle_id",
        "period_start_date",
        "period_end_date",
        "days_periods",
        "cycle_span_days",
        "symptoms",
        "athlete_notes",
    ]

    if history_df is None or history_df.empty:
        return pd.DataFrame(columns=columns)

    editor_df = history_df.copy()
    editor_df["period_start_date"] = pd.to_datetime(
        editor_df["period_start_date"], errors="coerce"
    ).dt.date
    editor_df["period_end_date"] = pd.to_datetime(
        editor_df["period_end_date"], errors="coerce"
    ).dt.date

    editor_df["days_periods"] = (
        pd.to_datetime(editor_df["period_end_date"])
        - pd.to_datetime(editor_df["period_start_date"])
    ).dt.days + 1

    starts = pd.to_datetime(editor_df["period_start_date"], errors="coerce")
    editor_df["cycle_span_days"] = starts.diff().dt.days

    for column in columns:
        if column not in editor_df.columns:
            editor_df[column] = None

    return editor_df[columns]


def _render_menstrual_tracking(athlete_id: str) -> pd.DataFrame:
    st.subheader("Menstrual cycle tracking")
    st.caption(
        "This health information is optional. Dates are used only as one "
        "personal forecasting factor and are not a medical diagnosis."
    )

    with st.container(border=True):
        left, middle, right = st.columns([1, 1, 1.4])

        with left:
            period_start = st.date_input(
                "Period starting date",
                value=date.today(),
                max_value=date.today() + timedelta(days=7),
                key="forecast_period_start",
            )

        with middle:
            default_end = period_start + timedelta(days=4)
            period_end = st.date_input(
                "Period ending date",
                value=default_end,
                min_value=period_start,
                max_value=period_start + timedelta(days=14),
                key="forecast_period_end",
            )

        with right:
            symptoms = st.multiselect(
                "Symptoms (optional)",
                [
                    "Fatigue",
                    "Cramps",
                    "Headache",
                    "Sleep disturbance",
                    "Mood change",
                    "Soreness",
                    "Other",
                ],
                key="forecast_period_symptoms",
            )

        notes = st.text_input(
            "Athlete notes (optional)",
            placeholder="Add short context such as unusual symptoms or disrupted sleep",
            key="forecast_period_notes",
        )

        period_days = (period_end - period_start).days + 1
        st.caption(f"Calculated period duration: {period_days} day(s)")

        if st.button(
            "Save cycle record",
            type="primary",
            use_container_width=True,
            key="save_cycle_record",
        ):
            try:
                add_menstrual_cycle(
                    athlete_id=athlete_id,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    symptoms=", ".join(symptoms) if symptoms else None,
                    athlete_notes=notes.strip() or None,
                )
            except Exception as exc:
                st.error(f"The cycle record could not be saved: {exc}")
            else:
                st.success("Cycle record saved.")
                st.rerun()

    history_df = get_menstrual_history(athlete_id)

    if history_df is None or history_df.empty:
        st.info("No cycle history has been saved yet.")
        return pd.DataFrame()

    _display_cycle_summary(history_df)

    st.markdown("#### Editable cycle history")
    st.caption(
        "Edit the start or end date directly, add rows, or delete rows. "
        "Period days and cycle span are recalculated after saving."
    )

    editor_df = _prepare_history_for_editor(history_df)
    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="menstrual_history_editor",
        column_config={
            "cycle_id": st.column_config.NumberColumn(
                "Record ID",
                disabled=True,
                format="%d",
            ),
            "period_start_date": st.column_config.DateColumn(
                "Period start",
                format="DD MMM YYYY",
                required=True,
            ),
            "period_end_date": st.column_config.DateColumn(
                "Period end",
                format="DD MMM YYYY",
                required=True,
            ),
            "days_periods": st.column_config.NumberColumn(
                "Days periods were",
                disabled=True,
                format="%d days",
            ),
            "cycle_span_days": st.column_config.NumberColumn(
                "Span from previous start",
                disabled=True,
                format="%d days",
                help="Number of days between this period start and the previous period start.",
            ),
            "symptoms": st.column_config.TextColumn("Symptoms"),
            "athlete_notes": st.column_config.TextColumn("Notes"),
        },
        disabled=["cycle_id", "days_periods", "cycle_span_days"],
    )

    if st.button(
        "Save table changes",
        use_container_width=True,
        key="save_cycle_table_changes",
    ):
        try:
            replace_menstrual_history(
                athlete_id=athlete_id,
                edited_df=edited_df,
                existing_df=history_df,
            )
        except Exception as exc:
            st.error(f"The edited cycle history could not be saved: {exc}")
        else:
            st.success("Cycle history updated.")
            st.rerun()

    return history_df


def _render_accuracy_status(score: float | None, data_points: int) -> None:
    score_text = "Not yet measurable" if score is None else f"{score:.1f}%"
    first, second, third = st.columns(3)
    first.metric("Backtested forecast score", score_text)
    second.metric("Historical daily observations", data_points)
    third.metric("Forecast horizon", "7 days")

    if score is None:
        st.warning(
            "There is not enough history to measure forecast performance yet. "
            "The page will still provide a baseline forecast, but it must not be "
            "described as 80% accurate."
        )
    elif score >= 80:
        st.success(
            "The current rolling-origin backtest meets the 80% MAPE-based "
            "performance target. This is measured performance, not a permanent guarantee."
        )
    else:
        st.warning(
            f"The current backtested score is {score:.1f}%, below the 80% target. "
            "Collect more longitudinal records and improve the model before claiming "
            "80% forecast performance."
        )


def _render_forecast_table(forecast_df: pd.DataFrame, female_path: bool) -> None:
    display_df = forecast_df.copy()

    if not female_path and "Cycle context" in display_df.columns:
        display_df = display_df.drop(columns=["Cycle context"])

    preferred_order = [
        "Date",
        "Span",
        "Cycle context",
        "Forecast result",
        "Fatigue forecast",
        "Readiness forecast",
        "Injury-risk score",
        "Injury-risk result",
        "Digital Twin score",
        "Health index",
        "AI recommendation",
        "Coach recommendation",
        "Forecast method",
        "Confidence",
    ]
    display_columns = [column for column in preferred_order if column in display_df]

    st.dataframe(
        display_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "Fatigue forecast": st.column_config.ProgressColumn(
                "Fatigue", min_value=0, max_value=100, format="%.1f"
            ),
            "Readiness forecast": st.column_config.ProgressColumn(
                "Readiness", min_value=0, max_value=100, format="%.1f"
            ),
            "Injury-risk score": st.column_config.ProgressColumn(
                "Injury risk", min_value=0, max_value=100, format="%.1f"
            ),
            "Digital Twin score": st.column_config.ProgressColumn(
                "Twin score", min_value=0, max_value=100, format="%.1f"
            ),
            "Health index": st.column_config.ProgressColumn(
                "Health index", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )


def _render_forecast_visualisation(
    forecast_df: pd.DataFrame,
    female_path: bool,
) -> None:
    """Display the same seven-day forecast as interactive line charts."""
    st.markdown("#### Seven-day forecast visualisation")
    st.caption(
        "Select the forecast measures to compare across the next seven days. "
        "The chart uses the same values shown in the forecast table above."
    )

    metric_options = [
        "Fatigue forecast",
        "Readiness forecast",
        "Injury-risk score",
        "Digital Twin score",
        "Health index",
    ]
    available_metrics = [
        column for column in metric_options if column in forecast_df.columns
    ]

    if not available_metrics:
        st.info("No numeric forecast measures are available for visualisation.")
        return

    default_metrics = [
        column
        for column in (
            "Fatigue forecast",
            "Readiness forecast",
            "Digital Twin score",
        )
        if column in available_metrics
    ]

    selected_metrics = st.multiselect(
        "Forecast measures",
        options=available_metrics,
        default=default_metrics or available_metrics[:1],
        key="seven_day_forecast_chart_metrics",
    )

    if not selected_metrics:
        st.info("Select at least one forecast measure to display the chart.")
        return

    chart_df = forecast_df[["Date", *selected_metrics]].copy()
    chart_df["Date"] = pd.to_datetime(chart_df["Date"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Date"]).sort_values("Date")

    for column in selected_metrics:
        chart_df[column] = pd.to_numeric(chart_df[column], errors="coerce")

    chart_df = chart_df.set_index("Date")
    st.line_chart(chart_df[selected_metrics], use_container_width=True)

    summary_columns = [
        column
        for column in (
            "Date",
            "Span",
            "Forecast result",
            "Injury-risk result",
            "Confidence",
        )
        if column in forecast_df.columns
    ]

    if female_path and "Cycle context" in forecast_df.columns:
        summary_columns.insert(2, "Cycle context")

    if summary_columns:
        with st.expander("View seven-day visual summary"):
            st.dataframe(
                forecast_df[summary_columns],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn(
                        "Date", format="DD MMM YYYY"
                    ),
                },
            )


def athlete_forecasting() -> None:
    """Render gender-aware menstrual and general seven-day forecasting."""
    st.title("Forecasting")
    st.caption(
        "Seven-day Digital Twin forecast using multiple linear regression, "
        "time-series analysis, Holt-Winters when weekly seasonality is detected, "
        "ARIMA/Box-Jenkins modelling, and validation-weighted forecast combination."
    )

    athlete_id = st.session_state.get("user_id")
    if not athlete_id:
        st.error("No logged-in athlete ID was found.")
        return

    try:
        ensure_forecasting_schema()
        profile = get_forecasting_profile(str(athlete_id))
    except Exception as exc:
        st.error(
            "The forecasting database setup could not be completed. "
            "Run the supplied migration and check the database connection."
        )
        st.exception(exc)
        return

    gender = _normalise_gender(profile.get("gender"))

    if gender not in GENDER_OPTIONS:
        st.warning(
            "Gender is missing from the athlete profile. Save it below so the "
            "correct forecasting pathway can be selected."
        )
        selected_gender = st.selectbox(
            "Gender",
            GENDER_OPTIONS,
            key="forecast_missing_gender",
        )
        if st.button("Save gender to profile", type="primary"):
            try:
                set_athlete_gender(str(athlete_id), selected_gender)
            except Exception as exc:
                st.error(f"Gender could not be saved: {exc}")
            else:
                st.success("Gender saved.")
                st.rerun()
        return

    female_path = gender == "Female"
    st.info(
        f"Forecasting pathway: **{'Menstrual-aware' if female_path else 'General athlete'}** "
        f"— profile gender: **{gender}**"
    )

    cycles_df = pd.DataFrame()
    if female_path:
        current_tracking = bool(profile.get("menstrual_tracking_enabled", False))
        tracking_enabled = st.checkbox(
            "Enable optional menstrual-cycle tracking",
            value=current_tracking,
            key="menstrual_tracking_consent",
            help=(
                "This controls whether period history is stored and used as an "
                "additional personal forecasting factor."
            ),
        )

        if tracking_enabled != current_tracking:
            try:
                set_menstrual_tracking_enabled(str(athlete_id), tracking_enabled)
            except Exception as exc:
                st.error(f"The menstrual tracking preference could not be saved: {exc}")
            else:
                st.rerun()

        if tracking_enabled:
            cycles_df = _render_menstrual_tracking(str(athlete_id))
        else:
            st.info(
                "Menstrual tracking is disabled. The athlete will receive the "
                "general seven-day forecast."
            )
            female_path = False

    st.divider()
    st.subheader("Seven-day Digital Twin forecast")

    try:
        history_df = get_athlete_twin_history(str(athlete_id))
    except Exception as exc:
        st.error(f"Digital Twin history could not be loaded: {exc}")
        return

    if history_df is None or history_df.empty:
        st.info(
            "No Digital Twin history is available. Upload and save Garmin data "
            "before generating a forecast."
        )
        return

    coach_text = _coach_recommendation_text(str(athlete_id))

    try:
        bundle = build_forecast_bundle(
            history_df=history_df,
            gender="Female" if female_path else gender,
            cycles_df=cycles_df if female_path else None,
            coach_recommendation=coach_text,
            horizon=7,
        )
    except Exception as exc:
        st.error(f"The seven-day forecast could not be generated: {exc}")
        return

    _render_accuracy_status(
        score=bundle.overall_validation_score,
        data_points=bundle.data_points,
    )
    _render_forecast_table(bundle.table, female_path=female_path)
    _render_forecast_visualisation(bundle.table, female_path=female_path)

    with st.expander("Model evaluation and forecast-combination details"):
        st.markdown(
            "The model is evaluated with rolling-origin backtesting. MAE, MSE, "
            "RMSE and MAPE are calculated separately for every forecast target. "
            "Combination weights are based on inverse validation RMSE."
        )

        if bundle.evaluation is not None and not bundle.evaluation.empty:
            st.dataframe(bundle.evaluation, use_container_width=True, hide_index=True)
        else:
            st.info("More historical observations are required for model evaluation.")

        if bundle.model_weights is not None and not bundle.model_weights.empty:
            st.markdown("##### Forecast-combination weights")
            st.dataframe(bundle.model_weights, use_container_width=True, hide_index=True)

    if st.button(
        "Save this forecast run",
        use_container_width=True,
        key="save_forecast_run",
    ):
        try:
            run_id = save_forecast_run(
                athlete_id=str(athlete_id),
                gender_path="menstrual-aware" if female_path else "general",
                validation_score=bundle.overall_validation_score,
                forecast_df=bundle.table,
                evaluation_df=bundle.evaluation,
            )
        except Exception as exc:
            st.error(f"The forecast run could not be saved: {exc}")
        else:
            st.success(f"Forecast run {run_id} saved.")
