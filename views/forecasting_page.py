from __future__ import annotations

from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

def _today():
    return datetime.now(ZoneInfo("Australia/Brisbane")).date()
from typing import Any

import pandas as pd
import streamlit as st
import textwrap

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
from forecasting.engine import calculate_cycle_summary
from forecasting.validated import build_forecast_bundle


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
    summary = calculate_cycle_summary(history_df, reference_date=_today())
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
    """Prepare cycle history for editing and explicit user-controlled deletion."""
    columns = [
        "_delete",
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
    editor_df["_delete"] = False

    editor_df["period_start_date"] = pd.to_datetime(
        editor_df["period_start_date"], errors="coerce"
    ).dt.date

    editor_df["period_end_date"] = pd.to_datetime(
        editor_df["period_end_date"], errors="coerce"
    ).dt.date

    editor_df["days_periods"] = (
        pd.to_datetime(editor_df["period_end_date"], errors="coerce")
        - pd.to_datetime(editor_df["period_start_date"], errors="coerce")
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
                value=_today(),
                max_value=_today() + timedelta(days=7),
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
        "Edit dates directly, add a new row, or tick Delete beside an incorrect "
        "entry. Nothing is deleted until you click Save table changes. Period "
        "duration, cycle span and forecasting are recalculated after saving."
    )

    editor_df = _prepare_history_for_editor(history_df)

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="menstrual_history_editor",
        column_config={
            "_delete": st.column_config.CheckboxColumn(
                "Delete",
                help=(
                    "Tick this box for an incorrect record. The record is "
                    "permanently deleted only after you click Save table changes."
                ),
                default=False,
            ),
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
                help=(
                    "Number of days between this period start and the previous "
                    "period start."
                ),
            ),
            "symptoms": st.column_config.TextColumn("Symptoms"),
            "athlete_notes": st.column_config.TextColumn("Notes"),
        },
        disabled=["cycle_id", "days_periods", "cycle_span_days"],
    )

    if "_delete" in edited_df.columns:
        delete_mask = edited_df["_delete"].fillna(False).astype(bool)
    else:
        delete_mask = pd.Series(False, index=edited_df.index)

    delete_count = int(delete_mask.sum())

    if delete_count > 0:
        st.warning(
            (
                f"{delete_count} cycle "
                f"{'record is' if delete_count == 1 else 'records are'} "
                "marked for permanent deletion. Click Save table changes to confirm."
            )
        )

    save_label = (
        "Save table changes"
        if delete_count == 0
        else (
            "Save changes & delete "
            f"{delete_count} "
            f"{'entry' if delete_count == 1 else 'entries'}"
        )
    )

    if st.button(
        save_label,
        use_container_width=True,
        key="save_cycle_table_changes",
        type="primary",
    ):
        try:
            rows_to_save = (
                edited_df.loc[~delete_mask]
                .drop(columns=["_delete"], errors="ignore")
                .reset_index(drop=True)
            )

            replace_menstrual_history(
                athlete_id=athlete_id,
                edited_df=rows_to_save,
                existing_df=history_df,
            )

        except Exception as exc:
            st.error(
                f"The cycle history could not be updated: {exc}"
            )

        else:
            if delete_count > 0:
                st.success(
                    (
                        f"{delete_count} "
                        f"{'record was' if delete_count == 1 else 'records were'} "
                        "deleted successfully."
                    )
                )
            else:
                st.success("Cycle history updated.")

            st.rerun()

    return history_df


def _render_accuracy_status(score: float | None, data_points: int) -> None:
    a,b=st.columns(2)
    a.metric('Dated daily observations',data_points)
    b.metric('Looking ahead','7 days')
    with st.expander('How much confidence should I place in this outlook?'):
        st.write('This is an experimental projection of saved indices, not a validated injury probability or a guaranteed outcome. Forecasts become less dependable further from the latest activity.')
        st.write('Backtest fit index: '+(f'{score:.1f} / 100' if score is not None else 'Not yet measurable'))
        st.caption('Derived from historical MAPE error. This index is not the percentage of future predictions that will be correct.')


def _latest_history_date(history_df: pd.DataFrame) -> date | None:
    """
    Return the newest real Digital Twin observation date.

    The supported date columns match the forecasting engine.
    """
    if history_df is None or history_df.empty:
        return None

    for candidate in (
        "timestamp",
        "date",
        "activity_date",
        "recorded_at",
        "created_at",
    ):
        if candidate not in history_df.columns:
            continue

        parsed = pd.to_datetime(
            history_df[candidate],
            errors="coerce",
        ).dropna()

        if not parsed.empty:
            return parsed.max().date()

    return None


def _prepare_current_forecast_window(
    full_forecast_df: pd.DataFrame,
    latest_observation_date: date | None,
    horizon: int = 7,
) -> tuple[pd.DataFrame, date | None, int]:
    """
    Display the genuine forecast rows for the current viewing window.

    If the newest real observation is old, the engine first forecasts across
    that missing interval. Only then are the seven rows for the current
    window selected. Forecast values are never simply relabelled with new dates.
    """
    if (
        full_forecast_df is None
        or full_forecast_df.empty
    ):
        return pd.DataFrame(), None, 0

    table = full_forecast_df.copy()

    table["_forecast_date"] = pd.to_datetime(
        table["Date"],
        errors="coerce",
    ).dt.date

    table = (
        table
        .dropna(subset=["_forecast_date"])
        .sort_values("_forecast_date")
    )

    today = _today()

    if latest_observation_date is None:
        display_start = today
        stale_gap_days = 0
    else:
        first_true_future_date = (
            latest_observation_date
            + timedelta(days=1)
        )

        display_start = max(
            today,
            first_true_future_date,
        )

        stale_gap_days = max(
            0,
            (today - latest_observation_date).days,
        )

    display_df = (
        table.loc[
            table["_forecast_date"]
            >= display_start
        ]
        .head(horizon)
        .drop(
            columns=["_forecast_date"],
            errors="ignore",
        )
        .reset_index(drop=True)
    )

    if not display_df.empty:
        display_df["Span"] = [
            f"Day {index} of {horizon}"
            for index in range(
                1,
                len(display_df) + 1,
            )
        ]

    return (
        display_df,
        display_start,
        stale_gap_days,
    )


def _render_forecast_window_status(
    latest_observation_date: date | None,
    display_start: date | None,
    stale_gap_days: int,
) -> None:
    """Explain the date window and freshness of the data used."""
    if display_start is None:
        return

    display_end = (
        display_start
        + timedelta(days=6)
    )

    first, second, third = st.columns(3)

    first.metric(
        "Forecast starts",
        display_start.strftime(
            "%d %b %Y"
        ),
    )

    second.metric(
        "Latest athlete data",
        (
            latest_observation_date.strftime(
                "%d %b %Y"
            )
            if latest_observation_date
            else "Not available"
        ),
    )

    third.metric(
        "Current window",
        (
            f"{display_start.strftime('%d %b')} – "
            f"{display_end.strftime('%d %b %Y')}"
        ),
    )

    if (
        latest_observation_date
        and stale_gap_days > 0
    ):
        st.warning(
            (
                f"The latest real Digital Twin observation is "
                f"{stale_gap_days} day"
                f"{'s' if stale_gap_days != 1 else ''} old. "
                "The model forecasts across that missing interval first, "
                "then shows the current seven-day window. Uploading current "
                "athlete data will improve forecast reliability."
            )
        )

    elif (
        latest_observation_date
        == _today()
    ):
        st.caption(
            (
                "A real Digital Twin observation already exists for today, "
                "so the true future forecast begins tomorrow."
            )
        )


def _render_forecast_table(
    forecast_df: pd.DataFrame,
    female_path: bool,
) -> None:
    """
    Render a simplified athlete-facing seven-day forecast table.

    Technical fields remain available to the forecasting engine and the
    model-evaluation section, but they are intentionally hidden here.
    """
    if (
        forecast_df is None
        or forecast_df.empty
    ):
        st.info(
            "No forecast results are available."
        )
        return

    display_df = forecast_df.copy()

    rename_map = {
        "Span": "Day",
        "Fatigue forecast": "Fatigue",
        "Readiness forecast": "Readiness",
        "Injury-risk score": "Injury risk",
        "Injury-risk result": "Risk level",
        "Digital Twin score": "Twin score",
        "Health index": "Health index",
        "AI recommendation": "AI recommendation",
        "Coach recommendation": "Coach recommendation",
    }

    display_df = display_df.rename(
        columns=rename_map
    )

    def wrap_recommendation(
        value: Any,
        width: int = 58,
    ) -> str:
        if value is None:
            return "No recommendation"

        try:
            if pd.isna(value):
                return "No recommendation"
        except (
            TypeError,
            ValueError,
        ):
            pass

        clean = str(value).strip()

        if not clean:
            return "No recommendation"

        wrapped_lines = textwrap.wrap(
            clean,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )

        return "\n".join(
            wrapped_lines
        )

    for column in (
        "AI recommendation",
        "Coach recommendation",
    ):
        if column in display_df.columns:
            display_df[column] = (
                display_df[column]
                .apply(
                    wrap_recommendation
                )
            )

    preferred_order = [
        "Date",
        "Day",
        "Fatigue",
        "Readiness",
        "Injury risk",
        "Risk level",
        "Twin score",
        "Health index",
        "AI recommendation",
        "Coach recommendation",
    ]

    display_columns = [
        column
        for column in preferred_order
        if column in display_df.columns
    ]

    st.dataframe(
        display_df[
            display_columns
        ],
        use_container_width=True,
        hide_index=True,
        row_height=82,
        column_config={
            "Date": st.column_config.DateColumn(
                "Date",
                format="DD MMM YYYY",
                width="small",
            ),
            "Day": st.column_config.TextColumn(
                "Day",
                width="small",
            ),
            "Fatigue": st.column_config.ProgressColumn(
                "Fatigue",
                min_value=0,
                max_value=100,
                format="%.1f",
                width="medium",
            ),
            "Readiness": st.column_config.ProgressColumn(
                "Readiness",
                min_value=0,
                max_value=100,
                format="%.1f",
                width="medium",
            ),
            "Injury risk": st.column_config.ProgressColumn(
                "Injury risk",
                min_value=0,
                max_value=100,
                format="%.1f",
                width="medium",
            ),
            "Risk level": st.column_config.TextColumn(
                "Risk level",
                width="small",
            ),
            "Twin score": st.column_config.ProgressColumn(
                "Twin score",
                min_value=0,
                max_value=100,
                format="%.1f",
                width="medium",
            ),
            "Health index": st.column_config.ProgressColumn(
                "Health index",
                min_value=0,
                max_value=100,
                format="%.1f",
                width="medium",
            ),
            "AI recommendation": st.column_config.TextColumn(
                "AI recommendation",
                width="large",
            ),
            "Coach recommendation": st.column_config.TextColumn(
                "Coach recommendation",
                width="large",
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
    import plotly.graph_objects as go
    from ui.studio_shell import style_chart
    figure=go.Figure()
    for metric in selected_metrics:
        figure.add_trace(go.Scatter(x=chart_df.index,y=chart_df[metric],mode='lines+markers',name=metric,connectgaps=False,line=dict(width=3)))
    figure.update_layout(height=440,yaxis_title='Projected index / 100',xaxis_title='Forecast date')
    figure.update_yaxes(range=[0,100])
    st.plotly_chart(style_chart(figure),use_container_width=True,theme=None)

    summary_columns = [
        column
        for column in (
            "Date",
            "Span",
            "Fatigue forecast",
            "Readiness forecast",
            "Injury-risk result",
            "Digital Twin score",
            "Health index",
        )
        if column in forecast_df.columns
    ]

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



@st.cache_data(
    show_spinner=False,
    ttl=300,
)
def _build_forecast_bundle_cached(
    history_df: pd.DataFrame,
    gender: str,
    cycles_df: pd.DataFrame | None,
    coach_recommendation: str | None,
    horizon: int,
):
    """
    Cache the expensive multi-model forecast for a short period.

    Streamlit reruns the page whenever a widget changes. Without caching,
    Chronological model selection and rolling-origin evaluation would all
    be fitted again on every rerun.
    """
    return build_forecast_bundle(
        history_df=history_df,
        gender=gender,
        cycles_df=cycles_df,
        coach_recommendation=coach_recommendation,
        horizon=horizon,
    )



def athlete_forecasting() -> None:
    """Render gender-aware menstrual and general seven-day forecasting."""
    from ui.studio_shell import chapter
    st.title("Your seven-day forecast")
    chapter("02 / LOOK AHEAD", "Explore projected changes, see how much history supports them, and plan a conversation with your coach.")
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

    female_path = gender == "Female"
    male_path = gender == "Male"
    if gender not in GENDER_OPTIONS:
        st.caption('General forecasting. You can add your profile preferences in Settings; they are not required to continue.')

    cycles_df = pd.DataFrame()
    if female_path:
        current_tracking = bool(profile.get("menstrual_tracking_enabled", False))
        tracking_enabled = st.checkbox(
            "Enable optional menstrual-cycle tracking",
            value=current_tracking,
            key="menstrual_tracking_consent",
            help=(
                "This controls whether period history is stored and used as an "
                "optional context alongside your forecast. It does not change risk scores."
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
            from views.athlete.cycle_tracking import render_cycle_tracking
            with st.expander("My cycle · optional and private", expanded=False):
                cycles_df = render_cycle_tracking(str(athlete_id))
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
        from research_prediction.history import comparable_history
        raw_forecast_history = history_df.copy()
        history_df = comparable_history(history_df)
        from ui.forecast_data_check import render_data_check
        render_data_check(raw_forecast_history, history_df)
        if not history_df.empty and 'model_version' in history_df and history_df.model_version.notna().any():
            st.info('Forecast input uses dated research estimates with the same model version, input tier and event. These projections have not been externally validated.')
    except Exception as exc:
        st.error(f"Digital Twin history could not be loaded: {exc}")
        return

    if history_df is None or history_df.empty or history_df['timestamp'].dt.floor('D').nunique() < 3:
        from ui.first_upload_forecast import render_first_upload_forecast
        render_first_upload_forecast(athlete_id)
        return

    coach_text = _coach_recommendation_text(str(athlete_id))

    # ========================================================
    # CURRENT-DATE FORECAST ALIGNMENT
    # ========================================================

    latest_observation_date = (
        _latest_history_date(
            history_df
        )
    )

    today = _today()

    if latest_observation_date is None:
        first_engine_forecast_date = today
        days_to_bridge = 0
        display_start = today
        stale_gap_days = 0
    else:
        first_engine_forecast_date = (
            latest_observation_date
            + timedelta(days=1)
        )

        days_to_bridge = max(
            0,
            (
                today
                - first_engine_forecast_date
            ).days,
        )

        display_start = max(
            today,
            first_engine_forecast_date,
        )

        stale_gap_days = max(
            0,
            (
                today
                - latest_observation_date
            ).days,
        )

    # Show the date window immediately so the page never looks empty
    # while the multi-model forecast is being calculated.
    _render_forecast_window_status(
        latest_observation_date=(
            latest_observation_date
        ),
        display_start=display_start,
        stale_gap_days=stale_gap_days,
    )

    # Forecast all hidden bridge dates first, then the visible seven days.
    # Example:
    # latest real data = 15 Aug, today = 27 Aug
    # internal forecast = 16 Aug -> 02 Sep
    # visible forecast  = 27 Aug -> 02 Sep
    internal_horizon = (
        days_to_bridge
        + 7
    )

    if days_to_bridge > 30:
        st.error(
            (
                "The latest Digital Twin observation is too old for a "
                "responsible current seven-day forecast. Upload current "
                "athlete data before generating a new forecast."
            )
        )
        return

    gender_for_model = (
        "Female"
        if female_path
        else gender
    )

    # Context remains visible privately; no unvalidated cycle adjustment to risk.
    cycles_for_model = None
    if female_path and not cycles_df.empty:
        st.caption("Your period dates are saved privately. Numeric projections currently use activity history only; a validated cycle-aware model is not available.")

    try:
        with st.spinner(
            (
                "Generating the current seven-day forecast. "
                "The model is comparing baseline and time-series "
                "methods before displaying the results..."
            )
        ):
            bundle = (
                _build_forecast_bundle_cached(
                    history_df=history_df,
                    gender=gender_for_model,
                    cycles_df=cycles_for_model,
                    coach_recommendation=(
                        coach_text
                    ),
                    horizon=internal_horizon,
                )
            )

    except Exception as exc:
        st.error(
            "The seven-day forecast could not be generated."
        )
        st.exception(exc)
        return

    (
        forecast_table,
        _,
        _,
    ) = _prepare_current_forecast_window(
        full_forecast_df=bundle.table,
        latest_observation_date=(
            latest_observation_date
        ),
        horizon=7,
    )

    if forecast_table.empty:
        st.error(
            (
                "The forecasting engine completed, but no rows matched "
                "the current seven-day window. This usually means the "
                "forecast dates and Digital Twin history dates are not aligned."
            )
        )
        return

    from ui.forecast_horizon import render_forecast_horizon
    render_forecast_horizon(forecast_table, bundle)

    if st.button(
        "Save this forecast run",
        use_container_width=True,
        key="save_forecast_run",
    ):
        try:
            run_id = save_forecast_run(
                athlete_id=str(athlete_id),
                gender_path=(
                    "general"
                    if female_path
                    else "male"
                    if male_path
                    else "general"
                    ),
                validation_score=bundle.overall_validation_score,
                forecast_df=forecast_table,
                evaluation_df=bundle.evaluation,
            )
        except Exception as exc:
            st.error(f"The forecast run could not be saved: {exc}")
        else:
            st.success(f"Forecast run {run_id} saved.")
