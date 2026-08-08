import zipfile
import json
import pandas as pd
from datetime import datetime
from preprocessing.feature_engineering import safe_float


def flatten_json(data):
    if isinstance(data, list):
        return pd.json_normalize(data)

    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return pd.json_normalize(value)
        return pd.json_normalize(data)

    return pd.DataFrame()


def find_column(df, keywords):
    for col in df.columns:
        col_lower = col.lower()
        for keyword in keywords:
            if keyword.lower() in col_lower:
                return col
    return None


def parse_garmin_zip(uploaded_file):
    activity_frames = []
    sleep_frames = []
    hydration_frames = []
    wellness_frames = []
    training_frames = []

    with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
        for file_name in zip_ref.namelist():
            lower = file_name.lower()

            if not lower.endswith(".json"):
                continue

            try:
                with zip_ref.open(file_name) as f:
                    data = json.load(f)

                df = flatten_json(data)

                if df.empty:
                    continue

                if "summarizedactivities" in lower:
                    activity_frames.append(df)

                elif "sleepdata" in lower:
                    sleep_frames.append(df)

                elif "hydrationlogfile" in lower:
                    hydration_frames.append(df)

                elif "udsfile" in lower:
                    wellness_frames.append(df)

                elif "traininghistory" in lower:
                    training_frames.append(df)

            except Exception:
                continue

    activities = pd.concat(activity_frames, ignore_index=True) if activity_frames else pd.DataFrame()
    sleep = pd.concat(sleep_frames, ignore_index=True) if sleep_frames else pd.DataFrame()
    hydration = pd.concat(hydration_frames, ignore_index=True) if hydration_frames else pd.DataFrame()
    wellness = pd.concat(wellness_frames, ignore_index=True) if wellness_frames else pd.DataFrame()
    training = pd.concat(training_frames, ignore_index=True) if training_frames else pd.DataFrame()

    model_ready = create_model_ready_from_garmin_zip(
        activities, sleep, hydration, wellness, training
    )

    raw = {
        "activities": activities,
        "sleep": sleep,
        "hydration": hydration,
        "wellness": wellness,
        "training": training
    }

    return model_ready, raw


def estimate_sleep_hours(sleep_df):
    if sleep_df.empty:
        return 7.0

    for col in sleep_df.columns:
        col_lower = col.lower()

        if "duration" in col_lower or "seconds" in col_lower:
            try:
                value = float(sleep_df[col].dropna().iloc[-1])
                if value > 100:
                    return round(value / 3600, 2)
                return round(value, 2)
            except Exception:
                pass

    return 7.0


def estimate_hydration_level(hydration_df):
    if hydration_df.empty:
        return "Medium"

    for col in hydration_df.columns:
        col_lower = col.lower()

        if "hydration" in col_lower or "volume" in col_lower or "amount" in col_lower:
            try:
                value = float(hydration_df[col].dropna().iloc[-1])
                if value < 1000:
                    return "Low"
                elif value < 2500:
                    return "Medium"
                return "High"
            except Exception:
                pass

    return "Medium"


def create_model_ready_from_garmin_zip(activity_df, sleep_df, hydration_df, wellness_df, training_df):
    if activity_df.empty:
        return pd.DataFrame()

    date_col = find_column(activity_df, ["startTime", "beginTimestamp", "activityDate", "start"])
    hr_col = find_column(activity_df, ["averageHR", "averageHeartRate", "avgHr", "heartRate"])
    duration_col = find_column(activity_df, ["duration", "elapsedDuration", "movingDuration"])
    distance_col = find_column(activity_df, ["distance"])
    calories_col = find_column(activity_df, ["calories"])
    ascent_col = find_column(activity_df, ["elevationGain", "ascent", "totalAscent"])
    speed_col = find_column(activity_df, ["averageSpeed", "avgSpeed", "speed"])
    temp_col = find_column(activity_df, ["temperature", "avgTemperature"])

    rows = []

    sleep_hours = estimate_sleep_hours(sleep_df)
    hydration_level = estimate_hydration_level(hydration_df)

    for _, row in activity_df.iterrows():
        timestamp = datetime.now()

        if date_col and pd.notna(row.get(date_col)):
            try:
                timestamp = pd.to_datetime(row.get(date_col))
            except Exception:
                timestamp = datetime.now()

        heart_rate = safe_float(row.get(hr_col, 120), 120)

        duration_minutes = 30.0
        if duration_col:
            raw_duration = safe_float(row.get(duration_col, 1800), 1800)
            duration_minutes = raw_duration / 60 if raw_duration > 100 else raw_duration

        distance = safe_float(row.get(distance_col, 0), 0) if distance_col else 0
        calories = safe_float(row.get(calories_col, 0), 0) if calories_col else 0
        ascent = safe_float(row.get(ascent_col, 0), 0) if ascent_col else 0
        avg_speed = safe_float(row.get(speed_col, 0), 0) if speed_col else 0
        temperature = safe_float(row.get(temp_col, 25), 25) if temp_col else 25

        training_load = round((heart_rate * duration_minutes) / 100, 2)

        recovery_time = max(1, round(sleep_hours + 2 - (training_load / 100), 2))

        rows.append({
            "timestamp": timestamp,
            "heart_rate": heart_rate,
            "sleep_hours": sleep_hours,
            "training_load": training_load,
            "recovery_time": recovery_time,
            "hydration_level": hydration_level,
            "temperature": temperature,
            "humidity": 60.0,
            "previous_injury": 0,
            "distance": distance,
            "avg_speed": avg_speed,
            "calories": calories,
            "total_ascent": ascent,
            "duration_minutes": duration_minutes
        })

    return pd.DataFrame(rows)