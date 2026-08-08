def predict_injury_risk(row):
    fatigue_score = float(row.get("fatigue_score", 50))
    previous_injury = float(row.get("previous_injury", 0))
    training_load = float(row.get("training_load", 50))
    recovery_time = float(row.get("recovery_time", 8))

    risk_score = (
        fatigue_score * 0.45
        + previous_injury * 8
        + min(training_load, 150) * 0.25
        - recovery_time * 2
    )

    if risk_score >= 65:
        return "High"
    elif risk_score >= 40:
        return "Medium"
    return "Low"