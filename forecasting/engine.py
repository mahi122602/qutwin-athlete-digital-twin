from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import sqrt
from typing import Callable
import warnings

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, mean_squared_error
except ImportError as exc:  # pragma: no cover - handled in UI
    raise ImportError(
        "scikit-learn is required for the forecasting engine. "
        "Install it with: pip install scikit-learn"
    ) from exc

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except ImportError as exc:  # pragma: no cover - handled in UI
    raise ImportError(
        "statsmodels is required for ARIMA and Holt-Winters. "
        "Install it with: pip install statsmodels"
    ) from exc


TARGET_BOUNDS: dict[str, tuple[float, float]] = {
    "fatigue_score": (0.0, 100.0),
    "readiness_score": (0.0, 100.0),
    "twin_score": (0.0, 100.0),
    "health_index": (0.0, 100.0),
    "injury_risk_score": (0.0, 100.0),
}

RISK_LABEL_TO_SCORE = {
    "low": 20.0,
    "low-medium": 35.0,
    "low–medium": 35.0,
    "medium": 50.0,
    "moderate": 50.0,
    "medium-high": 65.0,
    "medium–high": 65.0,
    "high": 80.0,
    "critical": 95.0,
}


@dataclass(frozen=True)
class TargetForecast:
    target: str
    values: np.ndarray
    metrics: pd.DataFrame
    weights: dict[str, float]
    validation_score: float | None
    available_models: list[str]


@dataclass(frozen=True)
class ForecastBundle:
    table: pd.DataFrame
    evaluation: pd.DataFrame
    model_weights: pd.DataFrame
    overall_validation_score: float | None
    data_points: int
    cycle_summary: dict[str, object]


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _find_date_column(df: pd.DataFrame) -> str:
    for candidate in (
        "timestamp",
        "date",
        "activity_date",
        "recorded_at",
        "created_at",
    ):
        if candidate in df.columns:
            return candidate
    raise ValueError(
        "No date column was found. Expected one of: timestamp, date, "
        "activity_date, recorded_at, created_at."
    )


def prepare_daily_history(history_df: pd.DataFrame) -> pd.DataFrame:
    """Convert Digital Twin history into one clean row per calendar day."""
    if history_df is None or history_df.empty:
        return pd.DataFrame()

    df = history_df.copy()
    date_col = _find_date_column(df)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)

    if df.empty:
        return pd.DataFrame()

    if "injury_risk" in df.columns and "injury_risk_score" not in df.columns:
        numeric_risk = pd.to_numeric(df["injury_risk"], errors="coerce")
        mapped_risk = (
            df["injury_risk"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(RISK_LABEL_TO_SCORE)
        )
        df["injury_risk_score"] = numeric_risk.fillna(mapped_risk)

    possible_numeric = [
        "fatigue_score",
        "readiness_score",
        "twin_score",
        "health_index",
        "injury_risk_score",
        "heart_rate",
        "resting_heart_rate",
        "hrv",
        "sleep_hours",
        "training_load",
        "recovery_time",
        "temperature",
        "humidity",
        "hydration_score",
    ]

    for column in possible_numeric:
        if column in df.columns:
            df[column] = _safe_numeric(df[column])

    df["forecast_date"] = df[date_col].dt.normalize()
    numeric_cols = [
        column
        for column in possible_numeric
        if column in df.columns and df[column].notna().any()
    ]

    if not numeric_cols:
        return pd.DataFrame()

    daily = (
        df.groupby("forecast_date", as_index=False)[numeric_cols]
        .mean(numeric_only=True)
        .sort_values("forecast_date")
    )

    full_dates = pd.date_range(
        daily["forecast_date"].min(),
        daily["forecast_date"].max(),
        freq="D",
    )
    daily = daily.set_index("forecast_date").reindex(full_dates)
    daily.index.name = "forecast_date"

    # Interpolate short gaps only. Longer gaps remain missing and are later
    # handled target-by-target, avoiding false continuity across long periods.
    daily[numeric_cols] = daily[numeric_cols].interpolate(
        method="linear", limit=3, limit_direction="both"
    )
    daily = daily.reset_index()

    for target, (lower, upper) in TARGET_BOUNDS.items():
        if target in daily.columns:
            daily[target] = daily[target].clip(lower, upper)

    # Derive a Health Index only when the component scores exist.
    if "health_index" not in daily.columns:
        required = {"readiness_score", "fatigue_score", "twin_score"}
        if required.issubset(daily.columns):
            daily["health_index"] = (
                daily["readiness_score"] * 0.50
                + (100.0 - daily["fatigue_score"]) * 0.30
                + daily["twin_score"] * 0.20
            ).clip(0, 100)

    return daily


def _clean_series(series: pd.Series) -> pd.Series:
    result = _safe_numeric(series).dropna().astype(float)
    result.index = range(len(result))
    return result


def _forecast_naive(series: pd.Series, horizon: int) -> np.ndarray:
    clean = _clean_series(series)
    if clean.empty:
        raise ValueError("Cannot forecast an empty series.")
    return np.repeat(float(clean.iloc[-1]), horizon)


def _regression_row(values: list[float], next_index: int) -> list[float]:
    if not values:
        raise ValueError("Regression forecast needs at least one value.")

    def lag(k: int) -> float:
        return float(values[-k]) if len(values) >= k else float(values[0])

    recent_3 = values[-3:] if len(values) >= 3 else values
    recent_7 = values[-7:] if len(values) >= 7 else values
    day_of_week = next_index % 7

    return [
        lag(1),
        lag(2),
        lag(3),
        lag(7),
        float(np.mean(recent_3)),
        float(np.mean(recent_7)),
        float(next_index),
        float(np.sin(2.0 * np.pi * day_of_week / 7.0)),
        float(np.cos(2.0 * np.pi * day_of_week / 7.0)),
    ]


def _build_regression_training(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    clean = _clean_series(series)
    values = clean.tolist()
    X: list[list[float]] = []
    y: list[float] = []

    # Seven lags are desirable, but the function still works with a smaller
    # series by beginning at four observations.
    start = 7 if len(values) >= 14 else 4
    for index in range(start, len(values)):
        X.append(_regression_row(values[:index], index))
        y.append(values[index])

    if len(X) < 3:
        raise ValueError("Not enough observations for multiple linear regression.")

    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


def _forecast_mlr(series: pd.Series, horizon: int) -> np.ndarray:
    clean = _clean_series(series)
    X, y = _build_regression_training(clean)
    model = LinearRegression()
    model.fit(X, y)

    recursive_values = clean.tolist()
    predictions: list[float] = []
    for _ in range(horizon):
        next_index = len(recursive_values)
        row = np.asarray([_regression_row(recursive_values, next_index)])
        prediction = float(model.predict(row)[0])
        predictions.append(prediction)
        recursive_values.append(prediction)

    return np.asarray(predictions, dtype=float)


def _has_weekly_seasonality(series: pd.Series) -> bool:
    clean = _clean_series(series)
    if len(clean) < 21:
        return False
    lagged = clean.autocorr(lag=7)
    return bool(pd.notna(lagged) and abs(float(lagged)) >= 0.25)


def _forecast_holt_winters(series: pd.Series, horizon: int) -> np.ndarray:
    clean = _clean_series(series)
    if len(clean) < 21:
        raise ValueError("At least 21 observations are required to test weekly seasonality.")
    if not _has_weekly_seasonality(clean):
        raise ValueError("Weekly seasonality was not detected; Holt-Winters was skipped.")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            clean,
            trend="add",
            damped_trend=True,
            seasonal="add",
            seasonal_periods=7,
            initialization_method="estimated",
        ).fit(optimized=True, use_brute=False)

    return np.asarray(model.forecast(horizon), dtype=float)


def _forecast_arima(series: pd.Series, horizon: int) -> np.ndarray:
    clean = _clean_series(series)
    if len(clean) < 10:
        raise ValueError("Not enough observations for ARIMA.")

    candidates = [
        (1, 0, 0),
        (0, 1, 1),
        (1, 1, 0),
        (1, 1, 1),
        (2, 1, 0),
        (0, 1, 2),
    ]

    best_fit = None
    best_aic = np.inf
    for order in candidates:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = ARIMA(
                    clean,
                    order=order,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit()
            if np.isfinite(fit.aic) and fit.aic < best_aic:
                best_fit = fit
                best_aic = float(fit.aic)
        except Exception:
            continue

    if best_fit is None:
        raise ValueError("No ARIMA candidate could be fitted.")

    return np.asarray(best_fit.forecast(horizon), dtype=float)


MODEL_FUNCTIONS: dict[str, Callable[[pd.Series, int], np.ndarray]] = {
    "Multiple Linear Regression": _forecast_mlr,
    "Holt-Winters": _forecast_holt_winters,
    "ARIMA": _forecast_arima,
    "Naive baseline": _forecast_naive,
}


def _mape_percent(actual: np.ndarray, predicted: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = np.isfinite(actual) & np.isfinite(predicted) & (np.abs(actual) >= 1.0)
    if not np.any(mask):
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100.0)


def _metric_row(model_name: str, actual: list[float], predicted: list[float]) -> dict[str, float | str]:
    y_true = np.asarray(actual, dtype=float)
    y_pred = np.asarray(predicted, dtype=float)
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = sqrt(mse)
    mape = _mape_percent(y_true, y_pred)
    score = max(0.0, 100.0 - mape) if np.isfinite(mape) else float("nan")
    return {
        "Model": model_name,
        "MAE": round(mae, 3),
        "MSE": round(mse, 3),
        "RMSE": round(rmse, 3),
        "MAPE (%)": round(mape, 3) if np.isfinite(mape) else np.nan,
        "MAPE-based score (%)": round(score, 3) if np.isfinite(score) else np.nan,
        "Backtest observations": int(len(y_true)),
    }


def evaluate_models(series: pd.Series, max_origins: int = 14) -> pd.DataFrame:
    """One-step rolling-origin validation for each available method."""
    clean = _clean_series(series)
    if len(clean) < 8:
        return pd.DataFrame()

    minimum_train = 7
    origins = list(range(minimum_train, len(clean)))
    origins = origins[-max_origins:]
    rows: list[dict[str, float | str]] = []

    for model_name, model_function in MODEL_FUNCTIONS.items():
        actual: list[float] = []
        predicted: list[float] = []

        for origin in origins:
            train = clean.iloc[:origin]
            true_value = float(clean.iloc[origin])
            try:
                forecast = model_function(train, 1)
                predicted_value = float(forecast[0])
            except Exception:
                continue

            if np.isfinite(predicted_value):
                actual.append(true_value)
                predicted.append(predicted_value)

        # Require at least three comparable forecasts to avoid displaying a
        # misleading metric from one lucky observation.
        if len(actual) >= 3:
            rows.append(_metric_row(model_name, actual, predicted))

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(["RMSE", "MAE"]).reset_index(drop=True)


def _weights_from_metrics(metrics: pd.DataFrame) -> dict[str, float]:
    if metrics is None or metrics.empty:
        return {"Naive baseline": 1.0}

    usable = metrics.loc[
        metrics["RMSE"].notna() & np.isfinite(metrics["RMSE"].astype(float))
    ].copy()
    if usable.empty:
        return {"Naive baseline": 1.0}

    inverse = 1.0 / np.maximum(usable["RMSE"].astype(float).to_numpy(), 1e-6)
    normalised = inverse / inverse.sum()
    return {
        str(model): float(weight)
        for model, weight in zip(usable["Model"].tolist(), normalised)
    }


def _evaluate_forecast_combination(
    series: pd.Series,
    weights: dict[str, float],
    max_origins: int = 14,
) -> pd.DataFrame:
    """Backtest the exact inverse-RMSE forecast combination."""
    clean = _clean_series(series)
    if len(clean) < 8 or not weights:
        return pd.DataFrame()

    origins = list(range(7, len(clean)))[-max_origins:]
    actual: list[float] = []
    predicted: list[float] = []

    for origin in origins:
        train = clean.iloc[:origin]
        component_predictions: list[tuple[float, float]] = []

        for model_name, weight in weights.items():
            model_function = MODEL_FUNCTIONS.get(model_name)
            if model_function is None:
                continue
            try:
                value = float(model_function(train, 1)[0])
            except Exception:
                continue
            if np.isfinite(value):
                component_predictions.append((value, float(weight)))

        if not component_predictions:
            continue

        total_weight = sum(weight for _, weight in component_predictions)
        if total_weight <= 0:
            continue

        combination = sum(
            value * weight for value, weight in component_predictions
        ) / total_weight
        actual.append(float(clean.iloc[origin]))
        predicted.append(float(combination))

    if len(actual) < 3:
        return pd.DataFrame()

    return pd.DataFrame(
        [_metric_row("Forecast Combination", actual, predicted)]
    )


def forecast_target(
    series: pd.Series,
    target: str,
    horizon: int = 7,
) -> TargetForecast:
    clean = _clean_series(series)
    if clean.empty:
        raise ValueError(f"No usable values were available for {target}.")

    base_metrics = evaluate_models(clean)
    weights = _weights_from_metrics(base_metrics)
    combination_metrics = _evaluate_forecast_combination(clean, weights)
    metrics = (
        pd.concat([base_metrics, combination_metrics], ignore_index=True)
        if not base_metrics.empty and not combination_metrics.empty
        else base_metrics
    )
    model_forecasts: dict[str, np.ndarray] = {}

    for model_name in list(weights):
        try:
            model_forecasts[model_name] = MODEL_FUNCTIONS[model_name](clean, horizon)
        except Exception:
            continue

    if not model_forecasts:
        model_forecasts["Naive baseline"] = _forecast_naive(clean, horizon)
        weights = {"Naive baseline": 1.0}
    else:
        # Re-normalise after any final-fit failures.
        weights = {
            model: weights[model]
            for model in model_forecasts
            if model in weights
        }
        total = sum(weights.values()) or 1.0
        weights = {model: value / total for model, value in weights.items()}

    combined = np.zeros(horizon, dtype=float)
    for model_name, values in model_forecasts.items():
        combined += values * weights[model_name]

    lower, upper = TARGET_BOUNDS.get(target, (-np.inf, np.inf))
    combined = np.clip(combined, lower, upper)

    validation_score: float | None = None
    if metrics is not None and not metrics.empty:
        combination_row = metrics.loc[
            metrics["Model"] == "Forecast Combination",
            "MAPE-based score (%)",
        ]
        if not combination_row.empty and pd.notna(combination_row.iloc[0]):
            validation_score = float(combination_row.iloc[0])
        else:
            # Fallback when there is too little history to backtest the exact
            # combination on at least three rolling forecast origins.
            scores = metrics.set_index("Model")["MAPE-based score (%)"].to_dict()
            weighted_scores = [
                float(scores[model]) * weight
                for model, weight in weights.items()
                if model in scores and pd.notna(scores[model])
            ]
            score_weights = [
                weight
                for model, weight in weights.items()
                if model in scores and pd.notna(scores[model])
            ]
            if weighted_scores and sum(score_weights) > 0:
                validation_score = float(sum(weighted_scores) / sum(score_weights))

    return TargetForecast(
        target=target,
        values=combined,
        metrics=metrics,
        weights=weights,
        validation_score=validation_score,
        available_models=list(model_forecasts),
    )


def _normalise_cycles(cycles_df: pd.DataFrame | None) -> pd.DataFrame:
    if cycles_df is None or cycles_df.empty:
        return pd.DataFrame(
            columns=["period_start_date", "period_end_date", "days_periods"]
        )

    cycles = cycles_df.copy()
    for column in ("period_start_date", "period_end_date"):
        cycles[column] = pd.to_datetime(cycles[column], errors="coerce").dt.normalize()
    cycles = cycles.dropna(subset=["period_start_date", "period_end_date"])
    cycles = cycles.loc[cycles["period_end_date"] >= cycles["period_start_date"]]
    cycles = cycles.sort_values("period_start_date").drop_duplicates(
        subset=["period_start_date"], keep="last"
    )
    cycles["days_periods"] = (
        cycles["period_end_date"] - cycles["period_start_date"]
    ).dt.days + 1
    return cycles.reset_index(drop=True)


def calculate_cycle_summary(
    cycles_df: pd.DataFrame | None,
    reference_date: date | pd.Timestamp | None = None,
) -> dict[str, object]:
    cycles = _normalise_cycles(cycles_df)
    if cycles.empty:
        return {
            "last_period_start": None,
            "average_cycle_length": None,
            "average_period_duration": None,
            "estimated_next_period": None,
            "cycle_count": 0,
        }

    start_dates = cycles["period_start_date"]
    cycle_lengths = start_dates.diff().dt.days.dropna()
    valid_lengths = cycle_lengths[(cycle_lengths >= 18) & (cycle_lengths <= 60)]

    average_cycle = (
        int(round(float(valid_lengths.median()))) if not valid_lengths.empty else 28
    )
    average_duration = int(
        round(float(cycles["days_periods"].clip(1, 14).median()))
    )
    last_start = start_dates.max()
    next_period = last_start + pd.Timedelta(days=average_cycle)

    if reference_date is not None:
        reference = pd.Timestamp(reference_date).normalize()
        expected_end = next_period + pd.Timedelta(days=average_duration - 1)
        while expected_end < reference:
            next_period += pd.Timedelta(days=average_cycle)
            expected_end = next_period + pd.Timedelta(days=average_duration - 1)

    return {
        "last_period_start": last_start.date(),
        "average_cycle_length": average_cycle,
        "average_period_duration": average_duration,
        "estimated_next_period": next_period.date(),
        "cycle_count": int(len(cycles)),
    }


def _period_mask(dates: pd.Series, cycles: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=dates.index)
    for _, cycle in cycles.iterrows():
        mask |= dates.between(
            cycle["period_start_date"], cycle["period_end_date"], inclusive="both"
        )
    return mask


def estimate_personal_period_effect(
    daily_history: pd.DataFrame,
    cycles_df: pd.DataFrame | None,
    target: str,
) -> float:
    """Estimate an athlete-specific during-period change with shrinkage.

    No population-level menstrual assumption is imposed. The adjustment is
    estimated only from this athlete's own overlapping Digital Twin history.
    """
    cycles = _normalise_cycles(cycles_df)
    if cycles.empty or target not in daily_history.columns:
        return 0.0

    data = daily_history[["forecast_date", target]].dropna().copy()
    if len(data) < 10:
        return 0.0

    data["forecast_date"] = pd.to_datetime(data["forecast_date"]).dt.normalize()
    in_period = _period_mask(data["forecast_date"], cycles)
    period_values = data.loc[in_period, target]
    other_values = data.loc[~in_period, target]

    if len(period_values) < 3 or len(other_values) < 5:
        return 0.0

    raw_effect = float(period_values.mean() - other_values.mean())
    # Shrink estimates from small samples toward zero and cap extreme values.
    shrinkage = min(1.0, len(period_values) / 10.0)
    return float(np.clip(raw_effect * shrinkage, -10.0, 10.0))


def _cycle_context_for_dates(
    forecast_dates: pd.DatetimeIndex,
    cycles_df: pd.DataFrame | None,
) -> tuple[list[str], list[bool], dict[str, object]]:
    cycles = _normalise_cycles(cycles_df)
    summary = calculate_cycle_summary(
        cycles, reference_date=forecast_dates.min() if len(forecast_dates) else None
    )
    contexts: list[str] = []
    expected_period_flags: list[bool] = []

    if cycles.empty:
        return (
            ["Insufficient cycle history"] * len(forecast_dates),
            [False] * len(forecast_dates),
            summary,
        )

    last_start = pd.Timestamp(summary["last_period_start"])
    average_cycle = int(summary["average_cycle_length"] or 28)
    average_duration = int(summary["average_period_duration"] or 5)
    expected_start = pd.Timestamp(summary["estimated_next_period"])
    expected_end = expected_start + pd.Timedelta(days=average_duration - 1)

    # Move an old estimate forward by whole personal cycle lengths so the
    # seven-day table describes the next relevant window rather than a date
    # that may already have passed.
    first_forecast_date = forecast_dates.min().normalize()
    while expected_end < first_forecast_date:
        expected_start += pd.Timedelta(days=average_cycle)
        expected_end = expected_start + pd.Timedelta(days=average_duration - 1)

    for forecast_date in forecast_dates:
        cycle_day = int((forecast_date.normalize() - last_start).days % average_cycle) + 1
        expected = expected_start <= forecast_date.normalize() <= expected_end
        expected_period_flags.append(expected)

        if expected:
            period_day = int((forecast_date.normalize() - expected_start).days) + 1
            contexts.append(f"Estimated period day {period_day}")
        else:
            days_until = int((expected_start - forecast_date.normalize()).days)
            if days_until >= 0:
                contexts.append(f"Cycle day {cycle_day}; ~{days_until} days to expected period")
            else:
                contexts.append(f"Cycle day {cycle_day}; expected date passed")

    return contexts, expected_period_flags, summary


def _risk_label(score: float) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _recommendation(
    fatigue: float,
    readiness: float,
    risk_score: float,
    expected_period: bool,
) -> str:
    if risk_score >= 75 or fatigue >= 80 or readiness < 40:
        base = "Prioritise recovery and request coach review before high-intensity training."
    elif risk_score >= 45 or fatigue >= 65 or readiness < 60:
        base = "Use a reduced-load session and monitor sleep, soreness and recovery."
    else:
        base = "Continue the planned session while monitoring recovery indicators."

    if expected_period:
        return base + " Record symptoms and adapt only to the athlete's actual response."
    return base


def _confidence_label(score: float | None, observations: int, horizon_day: int) -> str:
    if score is None or observations < 14:
        return "Low"
    horizon_penalty = (horizon_day - 1) * 1.5
    adjusted = score - horizon_penalty
    if adjusted >= 80 and observations >= 28:
        return "High"
    if adjusted >= 65 and observations >= 18:
        return "Moderate"
    return "Low"


def _display_models(target_forecast: TargetForecast) -> str:
    names = [name for name in target_forecast.available_models if name != "Naive baseline"]
    if not names:
        return "Naive baseline"
    return " + ".join(names)


def build_forecast_bundle(
    history_df: pd.DataFrame,
    gender: str | None,
    cycles_df: pd.DataFrame | None = None,
    coach_recommendation: str | None = None,
    horizon: int = 7,
) -> ForecastBundle:
    daily = prepare_daily_history(history_df)
    if daily.empty:
        raise ValueError("No usable Digital Twin history is available for forecasting.")

    target_names = [
        target
        for target in (
            "fatigue_score",
            "readiness_score",
            "twin_score",
            "health_index",
            "injury_risk_score",
        )
        if target in daily.columns and daily[target].notna().sum() >= 1
    ]

    if "fatigue_score" not in target_names:
        raise ValueError("No usable fatigue_score observation is available.")

    forecasts: dict[str, TargetForecast] = {}
    evaluation_frames: list[pd.DataFrame] = []
    weight_rows: list[dict[str, object]] = []

    for target in target_names:
        target_forecast = forecast_target(daily[target], target, horizon=horizon)
        forecasts[target] = target_forecast

        if target_forecast.metrics is not None and not target_forecast.metrics.empty:
            target_metrics = target_forecast.metrics.copy()
            target_metrics.insert(0, "Target", target)
            evaluation_frames.append(target_metrics)

        for model, weight in target_forecast.weights.items():
            weight_rows.append(
                {
                    "Target": target,
                    "Model": model,
                    "Combination weight": round(float(weight), 4),
                }
            )

    future_dates = pd.date_range(
        pd.to_datetime(daily["forecast_date"]).max() + pd.Timedelta(days=1),
        periods=horizon,
        freq="D",
    )

    is_female = str(gender or "").strip().lower() in {
        "female",
        "woman",
        "f",
    }
    if is_female:
        cycle_context, period_flags, cycle_summary = _cycle_context_for_dates(
            future_dates, cycles_df
        )
    else:
        cycle_context = ["Not applicable"] * horizon
        period_flags = [False] * horizon
        cycle_summary = calculate_cycle_summary(None)

    fatigue = forecasts["fatigue_score"].values.copy()
    readiness = (
        forecasts["readiness_score"].values.copy()
        if "readiness_score" in forecasts
        else np.clip(100.0 - fatigue, 0.0, 100.0)
    )
    twin = (
        forecasts["twin_score"].values.copy()
        if "twin_score" in forecasts
        else np.clip((readiness + (100.0 - fatigue)) / 2.0, 0.0, 100.0)
    )
    health = (
        forecasts["health_index"].values.copy()
        if "health_index" in forecasts
        else np.clip(
            readiness * 0.50 + (100.0 - fatigue) * 0.30 + twin * 0.20,
            0.0,
            100.0,
        )
    )
    risk = (
        forecasts["injury_risk_score"].values.copy()
        if "injury_risk_score" in forecasts
        else np.clip(0.55 * fatigue + 0.45 * (100.0 - readiness), 0.0, 100.0)
    )

    # Apply only athlete-specific period effects observed in their own history.
    if is_female and cycles_df is not None and not cycles_df.empty:
        fatigue_effect = estimate_personal_period_effect(
            daily, cycles_df, "fatigue_score"
        )
        readiness_effect = estimate_personal_period_effect(
            daily, cycles_df, "readiness_score"
        ) if "readiness_score" in daily.columns else -fatigue_effect

        for index, expected in enumerate(period_flags):
            if expected:
                fatigue[index] = np.clip(fatigue[index] + fatigue_effect, 0, 100)
                readiness[index] = np.clip(readiness[index] + readiness_effect, 0, 100)
                twin[index] = np.clip(
                    (readiness[index] + (100.0 - fatigue[index])) / 2.0,
                    0,
                    100,
                )
                health[index] = np.clip(
                    readiness[index] * 0.50
                    + (100.0 - fatigue[index]) * 0.30
                    + twin[index] * 0.20,
                    0,
                    100,
                )

    validation_scores = [
        forecast.validation_score
        for forecast in forecasts.values()
        if forecast.validation_score is not None
    ]
    overall_score = (
        float(np.mean(validation_scores)) if validation_scores else None
    )

    primary_models = _display_models(forecasts["fatigue_score"])
    coach_text = coach_recommendation or "No approved coach recommendation available."

    rows: list[dict[str, object]] = []
    for index, forecast_date in enumerate(future_dates):
        risk_label = _risk_label(float(risk[index]))
        ai_recommendation = _recommendation(
            float(fatigue[index]),
            float(readiness[index]),
            float(risk[index]),
            bool(period_flags[index]),
        )
        result = (
            f"{risk_label} risk; fatigue {fatigue[index]:.1f}; "
            f"readiness {readiness[index]:.1f}"
        )
        rows.append(
            {
                "Date": forecast_date.date(),
                "Span": f"Day {index + 1} of {horizon}",
                "Cycle context": cycle_context[index],
                "Fatigue forecast": round(float(fatigue[index]), 1),
                "Readiness forecast": round(float(readiness[index]), 1),
                "Injury-risk score": round(float(risk[index]), 1),
                "Injury-risk result": risk_label,
                "Digital Twin score": round(float(twin[index]), 1),
                "Health index": round(float(health[index]), 1),
                "Forecast result": result,
                "AI recommendation": ai_recommendation,
                "Coach recommendation": coach_text,
                "Forecast method": primary_models,
                "Confidence": _confidence_label(
                    overall_score,
                    len(daily),
                    index + 1,
                ),
            }
        )

    evaluation = (
        pd.concat(evaluation_frames, ignore_index=True)
        if evaluation_frames
        else pd.DataFrame()
    )
    weights = pd.DataFrame(weight_rows)

    return ForecastBundle(
        table=pd.DataFrame(rows),
        evaluation=evaluation,
        model_weights=weights,
        overall_validation_score=overall_score,
        data_points=int(len(daily)),
        cycle_summary=cycle_summary,
    )
