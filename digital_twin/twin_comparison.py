import pandas as pd


def format_change(change):
    if change is None:
        return "N/A"

    if change > 0:
        return f"↑ +{round(change, 2)}"
    if change < 0:
        return f"↓ {round(change, 2)}"

    return "No change"


def compare_twin_states(previous_state, current_state):
    if previous_state is None or len(previous_state) == 0:
        return None

    prev = previous_state.iloc[-1]
    curr = current_state.iloc[-1]

    metrics = [
        "heart_rate",
        "sleep_hours",
        "training_load",
        "recovery_time",
        "fatigue_score",
        "readiness_score",
        "twin_score",
    ]

    rows = []

    for metric in metrics:
        if metric not in curr.index or metric not in prev.index:
            continue

        previous = prev[metric]
        current = curr[metric]

        try:
            change = float(current) - float(previous)
        except Exception:
            continue

        if round(change, 2) == 0:
            continue

        rows.append({
            "Metric": metric.replace("_", " ").title(),
            "Previous": round(float(previous), 2),
            "Current": round(float(current), 2),
            "Change": format_change(change),
        })

    return pd.DataFrame(rows)