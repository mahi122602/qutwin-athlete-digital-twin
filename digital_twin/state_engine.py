import pandas as pd
import numpy as np


def calculate_acwr(training_load_series):
    """
    Acute:Chronic Workload Ratio.
    Acute load = recent 7-day average.
    Chronic load = recent 28-day average.
    For MVP, if not enough history exists, use available rolling windows.
    """
    acute_load = training_load_series.rolling(window=7, min_periods=1).mean()
    chronic_load = training_load_series.rolling(window=28, min_periods=1).mean()

    acwr = acute_load / chronic_load.replace(0, np.nan)
    return acwr.fillna(1.0)


def calculate_recovery_index(sleep_hours, recovery_time, hydration_level):
    hydration_score = {
        "Low": 0.4,
        "Medium": 0.7,
        "High": 1.0
    }.get(str(hydration_level), 0.7)

    recovery_index = (
        (sleep_hours / 9) * 0.45
        + (recovery_time / 10) * 0.35
        + hydration_score * 0.20
    )

    return round(max(0, min(1, recovery_index)), 3)


def calculate_environmental_stress(temperature, humidity):
    temp_score = min(max((temperature - 15) / 25, 0), 1)
    humidity_score = min(max((humidity - 40) / 60, 0), 1)

    stress = (temp_score * 0.6) + (humidity_score * 0.4)
    return round(max(0, min(1, stress)), 3)


def calculate_fatigue_index(heart_rate, training_load, sleep_hours, recovery_time):
    fatigue = (
        0.30 * min(heart_rate / 200, 1)
        + 0.35 * min(training_load / 150, 1)
        + 0.20 * (1 - min(sleep_hours / 9, 1))
        + 0.15 * (1 - min(recovery_time / 10, 1))
    )

    return round(max(0, min(1, fatigue)), 3)


def calculate_readiness_index(fatigue_index, recovery_index, environmental_stress):
    readiness = (
        0.50 * (1 - fatigue_index)
        + 0.35 * recovery_index
        + 0.15 * (1 - environmental_stress)
    )

    return round(max(0, min(1, readiness)), 3)


def classify_athlete_state(fatigue_index, readiness_index, injury_risk_label=None):
    if injury_risk_label == "High":
        return "High Risk"

    if fatigue_index >= 0.75:
        return "Fatigued"

    if readiness_index >= 0.75:
        return "Ready"

    if readiness_index >= 0.55:
        return "Loaded"

    return "Recovery Needed"


def build_digital_twin_state(model_ready_df):
    """
    Converts extracted Garmin/model-ready data into Digital Twin state vectors.
    """
    df = model_ready_df.copy()

    required_defaults = {
        "heart_rate": 120,
        "sleep_hours": 7,
        "training_load": 50,
        "recovery_time": 8,
        "hydration_level": "Medium",
        "temperature": 25,
        "humidity": 60,
        "previous_injury": 0,
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    if "timestamp" not in df.columns:
        df["timestamp"] = pd.Timestamp.now()

    df = df.sort_values("timestamp").reset_index(drop=True)

    df["acwr"] = calculate_acwr(df["training_load"])
    df["recovery_index"] = df.apply(
        lambda row: calculate_recovery_index(
            row["sleep_hours"],
            row["recovery_time"],
            row["hydration_level"]
        ),
        axis=1
    )

    df["environmental_stress"] = df.apply(
        lambda row: calculate_environmental_stress(
            row["temperature"],
            row["humidity"]
        ),
        axis=1
    )

    df["fatigue_index"] = df.apply(
        lambda row: calculate_fatigue_index(
            row["heart_rate"],
            row["training_load"],
            row["sleep_hours"],
            row["recovery_time"]
        ),
        axis=1
    )

    df["readiness_index"] = df.apply(
        lambda row: calculate_readiness_index(
            row["fatigue_index"],
            row["recovery_index"],
            row["environmental_stress"]
        ),
        axis=1
    )

    df["athlete_state"] = df.apply(
        lambda row: classify_athlete_state(
            row["fatigue_index"],
            row["readiness_index"]
        ),
        axis=1
    )

    return df