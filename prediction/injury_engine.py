def predict_injury_risk(df):
    """
    Rule-based injury risk engine for the Digital Twin MVP.
    Later this can be replaced with Random Forest / XGBoost.
    """

    df = df.copy()

    risk_scores = []

    for _, row in df.iterrows():
        fatigue_score = float(row.get("fatigue_score", 50))
        training_load = float(row.get("training_load", 50))
        recovery_time = float(row.get("recovery_time", 8))
        previous_injury = float(row.get("previous_injury", 0))

        risk_score = (
            fatigue_score * 0.45
            + training_load * 0.25
            + previous_injury * 8
            - recovery_time * 2
        )

        if risk_score >= 65:
            risk = "High"
        elif risk_score >= 40:
            risk = "Medium"
        else:
            risk = "Low"

        risk_scores.append(risk)

    df["injury_risk"] = risk_scores

    return df