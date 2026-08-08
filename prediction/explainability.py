import joblib
import pandas as pd

MODEL_DIR = "models"
FEATURES_PATH = f"{MODEL_DIR}/model_features.pkl"
FATIGUE_MODEL_PATH = f"{MODEL_DIR}/fatigue_rf_model.pkl"


def explain_fatigue_prediction(row, top_n=5):
    model = joblib.load(FATIGUE_MODEL_PATH)
    features = joblib.load(FEATURES_PATH)

    feature_importance = model.feature_importances_

    explanation_df = pd.DataFrame({
        "Feature": features,
        "Importance": feature_importance,
        "Value": [row.get(feature, 0) for feature in features],
    })

    explanation_df = explanation_df.sort_values(
        by="Importance",
        ascending=False
    ).head(top_n)

    reasons = []

    for _, item in explanation_df.iterrows():
        feature = item["Feature"]
        value = item["Value"]

        if feature == "training_load":
            reasons.append(f"Training load influenced the fatigue prediction with value {value}.")
        elif feature == "sleep_hours":
            reasons.append(f"Sleep duration affected the prediction with value {value} hours.")
        elif feature == "recovery_time":
            reasons.append(f"Recovery time contributed to the prediction with value {value}.")
        elif feature == "heart_rate":
            reasons.append(f"Heart rate contributed to the prediction with value {value} bpm.")
        elif feature == "previous_injury":
            reasons.append(f"Previous injury history influenced risk with value {value}.")
        elif feature == "fatigue_index":
            reasons.append(f"Fatigue index was an important Digital Twin signal with value {value}.")
        elif feature == "readiness_index":
            reasons.append(f"Readiness index influenced the final prediction with value {value}.")
        else:
            reasons.append(f"{feature} contributed with value {value}.")

    return explanation_df, reasons