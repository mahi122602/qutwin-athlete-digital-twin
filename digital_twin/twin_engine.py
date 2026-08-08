import pandas as pd


def classify_state(fatigue_index, readiness_index, environmental_stress):
    if fatigue_index >= 0.75:
        return "High Risk"
    if fatigue_index >= 0.60:
        return "Fatigued"
    if readiness_index >= 0.75 and environmental_stress < 0.5:
        return "Ready"
    if readiness_index >= 0.55:
        return "Loaded"
    return "Recovery Needed"


def calculate_twin_score(row):
    return round(
        (
            row["readiness_index"] * 0.45
            + (1 - row["fatigue_index"]) * 0.35
            + row["recovery_index"] * 0.20
        ) * 100,
        2
    )


def build_twin_snapshot(df):
    """
    Creates the final Digital Twin snapshot from engineered athlete state data.
    """

    df = df.copy()

    required_cols = [
        "fatigue_index",
        "readiness_index",
        "recovery_index",
        "environmental_stress"
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required Digital Twin feature: {col}")

    df["twin_score"] = df.apply(calculate_twin_score, axis=1)

    df["athlete_state"] = df.apply(
        lambda row: classify_state(
            row["fatigue_index"],
            row["readiness_index"],
            row["environmental_stress"]
        ),
        axis=1
    )

    df["state_explanation"] = df.apply(
        lambda row: (
            f"Athlete is classified as {row['athlete_state']} with "
            f"fatigue index {row['fatigue_index']}, readiness index "
            f"{row['readiness_index']}, and recovery index {row['recovery_index']}."
        ),
        axis=1
    )

    return df