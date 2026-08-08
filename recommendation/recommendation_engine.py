def generate_recommendation(row):
    injury_risk = row.get("injury_risk", "Medium")
    fatigue_score = float(row.get("fatigue_score", 50))
    readiness_score = float(row.get("readiness_score", 50))

    if injury_risk == "High" or fatigue_score >= 75:
        return (
            "High priority: reduce training intensity, increase recovery time, "
            "monitor sleep and hydration, and avoid high-impact sessions."
        )

    if injury_risk == "Medium" or fatigue_score >= 55:
        return (
            "Moderate priority: continue controlled training, improve recovery, "
            "monitor fatigue trend, and reassess before intense activity."
        )

    if readiness_score >= 75:
        return (
            "Low priority: athlete appears ready for planned training with routine monitoring."
        )

    return (
        "Monitor athlete condition and maintain hydration, sleep, and recovery discipline."
    )