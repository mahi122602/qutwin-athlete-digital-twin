def simulate_scenario(latest_state, sleep_change=0, training_load_change=0, recovery_change=0):
    simulated = latest_state.copy()

    simulated["sleep_hours"] = max(0, float(simulated.get("sleep_hours", 7)) + sleep_change)
    simulated["training_load"] = max(0, float(simulated.get("training_load", 50)) + training_load_change)
    simulated["recovery_time"] = max(0, float(simulated.get("recovery_time", 8)) + recovery_change)

    fatigue_score = (
        min(simulated["training_load"] / 150, 1) * 45
        + max(0, 8 - simulated["sleep_hours"]) * 6
        + max(0, 8 - simulated["recovery_time"]) * 4
    )

    readiness_score = max(0, min(100, 100 - fatigue_score))

    if fatigue_score >= 75:
        injury_risk = "High"
    elif fatigue_score >= 50:
        injury_risk = "Medium"
    else:
        injury_risk = "Low"

    simulated["simulated_fatigue_score"] = round(fatigue_score, 2)
    simulated["simulated_readiness_score"] = round(readiness_score, 2)
    simulated["simulated_injury_risk"] = injury_risk

    return simulated