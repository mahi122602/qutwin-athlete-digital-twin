import pandas as pd
from datetime import datetime


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def extract_duration_minutes(value):
    try:
        if pd.isna(value):
            return 30.0

        value = str(value)

        if ":" in value:
            parts = value.split(":")
            if len(parts) == 2:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return minutes + seconds / 60

            if len(parts) == 3:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return hours * 60 + minutes + seconds / 60

        return float(value)

    except Exception:
        return 30.0


def normalise_garmin_activity_csv(df):
    """
    Converts Garmin activity CSV into model-ready features.
    Works with columns like:
    Time, Distance, Avg Speed, Avg HR, Max HR, Total Ascent, Calories.
    """

    if df.empty:
        return pd.DataFrame()

    # Prefer Summary row if available
    if "Laps" in df.columns:
        summary_df = df[df["Laps"].astype(str).str.lower() == "summary"]
        if not summary_df.empty:
            df = summary_df

    rows = []

    for _, row in df.iterrows():
        avg_hr = safe_float(row.get("Avg HR", row.get("heart_rate", 120)), 120)
        duration_minutes = extract_duration_minutes(row.get("Time", row.get("duration", "30:00")))
        distance = safe_float(row.get("Distance", 0), 0)
        avg_speed = safe_float(row.get("Avg Speed", 0), 0)
        calories = safe_float(row.get("Calories", 0), 0)
        ascent = safe_float(row.get("Total Ascent", 0), 0)

        training_load = round((avg_hr * duration_minutes) / 100, 2)

        rows.append({
            "timestamp": datetime.now(),
            "heart_rate": avg_hr,
            "sleep_hours": 7.0,
            "training_load": training_load,
            "recovery_time": 8.0,
            "hydration_level": "Medium",
            "temperature": 25.0,
            "humidity": 60.0,
            "previous_injury": 0,
            "distance": distance,
            "avg_speed": avg_speed,
            "calories": calories,
            "total_ascent": ascent,
            "duration_minutes": duration_minutes
        })

    return pd.DataFrame(rows)


def normalise_generic_input(df):
    """
    Handles already-clean datasets with columns similar to your original dataset.
    """

    required_defaults = {
        "heart_rate": 120,
        "sleep_hours": 7.0,
        "training_load": 50.0,
        "recovery_time": 8.0,
        "hydration_level": "Medium",
        "temperature": 25.0,
        "humidity": 60.0,
        "previous_injury": 0,
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    if "timestamp" not in df.columns:
        df["timestamp"] = datetime.now()

    return df