def calculate_percentage_change(current, previous):
    try:
        if previous is None or previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 2)
    except Exception:
        return 0


def compare_with_previous_state(current_row, previous_row):
    if previous_row is None:
        return {
            "heart_rate_trend": 0,
            "sleep_trend": 0,
            "training_load_trend": 0,
            "readiness_trend": 0,
            "fatigue_trend": 0,
            "trend_summary": "First recorded Digital Twin state. No previous state available for comparison."
        }

    heart_rate_trend = calculate_percentage_change(
        current_row.get("heart_rate"), previous_row.get("heart_rate")
    )

    sleep_trend = calculate_percentage_change(
        current_row.get("sleep_hours"), previous_row.get("sleep_hours")
    )

    training_load_trend = calculate_percentage_change(
        current_row.get("training_load"), previous_row.get("training_load")
    )

    readiness_trend = calculate_percentage_change(
        current_row.get("readiness_index"), previous_row.get("readiness_index")
    )

    fatigue_trend = calculate_percentage_change(
        current_row.get("fatigue_index"), previous_row.get("fatigue_index")
    )

    summary = (
        f"Compared with the previous Digital Twin state: "
        f"heart rate changed by {heart_rate_trend}%, "
        f"sleep changed by {sleep_trend}%, "
        f"training load changed by {training_load_trend}%, "
        f"readiness changed by {readiness_trend}%, "
        f"and fatigue changed by {fatigue_trend}%."
    )

    return {
        "heart_rate_trend": heart_rate_trend,
        "sleep_trend": sleep_trend,
        "training_load_trend": training_load_trend,
        "readiness_trend": readiness_trend,
        "fatigue_trend": fatigue_trend,
        "trend_summary": summary
    }