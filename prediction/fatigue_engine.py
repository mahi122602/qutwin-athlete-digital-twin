import pandas as pd


def predict_fatigue(df):
    """
    Simple fatigue prediction engine.
    Returns dataframe with fatigue score and readiness.
    """

    df = df.copy()

    # --------------------------
    # Heart Rate Contribution
    # --------------------------
    hr_score = (df["heart_rate"] - 60) / 80

    # --------------------------
    # Sleep Contribution
    # --------------------------
    sleep_score = (8 - df["sleep_hours"]) / 8

    # --------------------------
    # Training Load
    # --------------------------
    load_score = df["training_load"] / 100

    # --------------------------
    # Recovery
    # --------------------------
    recovery_score = 1 - (df["recovery_time"] / 24)

    fatigue = (
        0.35 * hr_score +
        0.30 * sleep_score +
        0.25 * load_score +
        0.10 * recovery_score
    )

    fatigue = fatigue.clip(0, 1)

    df["fatigue_score"] = (fatigue * 100).round(1)

    readiness = 100 - df["fatigue_score"]

    df["readiness_score"] = readiness.round(1)

    return df