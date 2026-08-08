def classify_state_space(row):
    fatigue = float(row.get("fatigue_score", 50))
    readiness = float(row.get("readiness_score", 50))
    injury_risk = row.get("injury_risk", "Medium")

    if injury_risk == "High" or fatigue >= 85:
        return "Critical"

    if fatigue >= 70:
        return "Fatigued"

    if fatigue >= 55:
        return "High Load"

    if readiness >= 75:
        return "Ready"

    if readiness >= 60:
        return "Recovering"

    return "Recovery Needed"


def user_friendly_status(state):
    mapping = {
        "Critical": "High Risk – Prioritise recovery and coach review.",
        "Fatigued": "Fatigue is high – Reduce intensity today.",
        "High Load": "Training load is elevated – Monitor recovery.",
        "Ready": "Ready to Train.",
        "Recovering": "Recovering well – Light training recommended.",
        "Recovery Needed": "Recovery Needed – Focus on rest, sleep and hydration.",
    }

    return mapping.get(state, "Monitor athlete condition.")


def apply_state_space_model(df):
    df = df.copy()

    df["digital_twin_state"] = df.apply(classify_state_space, axis=1)
    df["user_status_message"] = df["digital_twin_state"].apply(user_friendly_status)

    return df