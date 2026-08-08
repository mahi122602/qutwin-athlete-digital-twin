def predict_fatigue_score(row):
    fatigue_index = float(row.get("fatigue_index", 0.5))
    training_load = float(row.get("training_load", 50))
    sleep_hours = float(row.get("sleep_hours", 7))
    recovery_time = float(row.get("recovery_time", 8))

    fatigue_score = (
        fatigue_index * 60
        + min(training_load / 150, 1) * 25
        + max(0, (7 - sleep_hours)) * 5
        + max(0, (8 - recovery_time)) * 3
    )

    return round(max(0, min(100, fatigue_score)), 2)