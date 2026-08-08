import joblib
import pandas as pd

MODEL_DIR = "models"

FATIGUE_MODEL_PATH = f"{MODEL_DIR}/fatigue_rf_model.pkl"
INJURY_MODEL_PATH = f"{MODEL_DIR}/injury_rf_model.pkl"
INJURY_ENCODER_PATH = f"{MODEL_DIR}/injury_label_encoder.pkl"
FEATURES_PATH = f"{MODEL_DIR}/model_features.pkl"


def hydration_to_score(value):
    value = str(value).lower()

    if value == "low":
        return 0.4
    if value == "medium":
        return 0.7
    if value == "high":
        return 1.0

    return 0.7


def prepare_model_features(df):
    df = df.copy()

    if "hydration_score" not in df.columns:
        df["hydration_score"] = df["hydration_level"].apply(hydration_to_score)

    model_features = joblib.load(FEATURES_PATH)

    for col in model_features:
        if col not in df.columns:
            df[col] = 0

    return df[model_features]


def run_prediction_pipeline(df):
    df = df.copy()

    fatigue_model = joblib.load(FATIGUE_MODEL_PATH)
    injury_model = joblib.load(INJURY_MODEL_PATH)
    injury_encoder = joblib.load(INJURY_ENCODER_PATH)

    X = prepare_model_features(df)

    df["fatigue_score"] = fatigue_model.predict(X).round(2)

    injury_pred_encoded = injury_model.predict(X)
    df["injury_risk"] = injury_encoder.inverse_transform(injury_pred_encoded)

    if hasattr(injury_model, "predict_proba"):
        probabilities = injury_model.predict_proba(X)
        df["prediction_confidence"] = probabilities.max(axis=1).round(3)
    else:
        df["prediction_confidence"] = 0.8

    df["readiness_score"] = (
        100
        - df["fatigue_score"]
        + (df.get("recovery_index", 0.6) * 20)
        - (df.get("environmental_stress", 0.3) * 10)
    ).clip(0, 100).round(2)

    df["recommendation"] = df.apply(generate_ai_recommendation, axis=1)

    return df


def generate_ai_recommendation(row):
    fatigue = float(row.get("fatigue_score", 50))
    readiness = float(row.get("readiness_score", 50))
    injury = row.get("injury_risk", "Medium")

    if injury == "High" or fatigue >= 75:
        return (
            "High priority: reduce training intensity, increase recovery time, "
            "monitor sleep and hydration, and avoid high-impact sessions."
        )

    if injury == "Medium" or fatigue >= 55:
        return (
            "Moderate priority: continue controlled training, improve recovery, "
            "monitor fatigue trend, and reassess before intense activity."
        )

    if readiness >= 75:
        return "Low priority: athlete appears ready for planned training with routine monitoring."

    return "Monitor athlete condition and maintain hydration, sleep, and recovery discipline."