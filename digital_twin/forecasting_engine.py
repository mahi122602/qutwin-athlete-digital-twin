import pandas as pd


def forecast_metric(history_df, metric, days=7):
    df = history_df.copy()

    if df is None or df.empty or metric not in df.columns:
        return pd.DataFrame()

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[metric])

    if len(df) < 2:
        return pd.DataFrame()

    last_value = df[metric].iloc[-1]
    previous_value = df[metric].iloc[-2]
    daily_change = last_value - previous_value

    future_rows = []

    last_date = df["timestamp"].iloc[-1]

    for day in range(1, days + 1):
        predicted_value = last_value + daily_change * day

        if metric in ["fatigue_score", "readiness_score", "twin_score", "health_index"]:
            predicted_value = max(0, min(100, predicted_value))

        future_rows.append({
            "day": day,
            "forecast_date": last_date + pd.Timedelta(days=day),
            "metric": metric,
            "forecast_value": round(predicted_value, 2),
        })

    return pd.DataFrame(future_rows)


def generate_forecast_summary(fatigue_forecast, readiness_forecast):
    if fatigue_forecast.empty:
        return "Not enough history available for forecasting."

    final_fatigue = fatigue_forecast["forecast_value"].iloc[-1]

    if not readiness_forecast.empty:
        final_readiness = readiness_forecast["forecast_value"].iloc[-1]
    else:
        final_readiness = None

    if final_fatigue >= 80:
        return "Forecast indicates fatigue may reach a high-risk level. Coach review and recovery planning are recommended."

    if final_fatigue >= 65:
        return "Forecast indicates fatigue may increase. Monitor training load, sleep and recovery closely."

    if final_readiness is not None and final_readiness >= 70:
        return "Forecast indicates the athlete is likely to remain in a suitable training condition."

    return "Forecast is stable. Continue monitoring future Digital Twin states."