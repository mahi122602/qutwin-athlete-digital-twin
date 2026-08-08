import os
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import (
    r2_score,
    mean_absolute_error,
    mean_squared_error,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

DATA_PATH = "data/athlete_training_dataset.csv"
MODEL_DIR = "models"


def hydration_to_score(value):
    value = str(value).lower()

    if value == "low":
        return 0.4
    if value == "medium":
        return 0.7
    if value == "high":
        return 1.0

    return 0.7


def prepare_dataset(df):
    df = df.copy()

    if "hydration_score" not in df.columns:
        df["hydration_score"] = df["hydration_level"].apply(hydration_to_score)

    if "acwr" not in df.columns:
        df["acwr"] = (
            df["training_load"]
            / df["training_load"].rolling(window=7, min_periods=1).mean()
        ).replace([np.inf, -np.inf], 1).fillna(1)

    if "recovery_index" not in df.columns:
        df["recovery_index"] = (
            (df["sleep_hours"] / 9) * 0.45
            + (df["recovery_time"] / 10) * 0.35
            + df["hydration_score"] * 0.20
        ).clip(0, 1)

    if "environmental_stress" not in df.columns:
        temp_score = ((df["temperature"] - 15) / 25).clip(0, 1)
        humidity_score = ((df["humidity"] - 40) / 60).clip(0, 1)
        df["environmental_stress"] = (
            temp_score * 0.6 + humidity_score * 0.4
        ).clip(0, 1)

    if "fatigue_index" not in df.columns:
        df["fatigue_index"] = (
            0.30 * (df["heart_rate"] / 200).clip(0, 1)
            + 0.35 * (df["training_load"] / 150).clip(0, 1)
            + 0.20 * (1 - (df["sleep_hours"] / 9).clip(0, 1))
            + 0.15 * (1 - (df["recovery_time"] / 10).clip(0, 1))
        ).clip(0, 1)

    if "readiness_index" not in df.columns:
        df["readiness_index"] = (
            0.50 * (1 - df["fatigue_index"])
            + 0.35 * df["recovery_index"]
            + 0.15 * (1 - df["environmental_stress"])
        ).clip(0, 1)

    return df


def evaluate_models():
    df = pd.read_csv(DATA_PATH)
    df = prepare_dataset(df)

    features = joblib.load(os.path.join(MODEL_DIR, "model_features.pkl"))

    fatigue_model = joblib.load(os.path.join(MODEL_DIR, "fatigue_rf_model.pkl"))
    injury_model = joblib.load(os.path.join(MODEL_DIR, "injury_rf_model.pkl"))
    label_encoder = joblib.load(os.path.join(MODEL_DIR, "injury_label_encoder.pkl"))

    X = df[features]

    # -----------------------------
    # Fatigue Regression Evaluation
    # -----------------------------
    y_fatigue = df["fatigue_score"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_fatigue,
        test_size=0.2,
        random_state=42,
    )

    fatigue_predictions = fatigue_model.predict(X_test)

    fatigue_r2 = r2_score(y_test, fatigue_predictions)
    fatigue_mae = mean_absolute_error(y_test, fatigue_predictions)
    fatigue_rmse = np.sqrt(mean_squared_error(y_test, fatigue_predictions))

    fatigue_cv_scores = cross_val_score(
        fatigue_model,
        X,
        y_fatigue,
        cv=5,
        scoring="r2",
    )

    print("\n==============================")
    print("FATIGUE MODEL EVALUATION")
    print("==============================")
    print(f"R² Score: {fatigue_r2:.4f}")
    print(f"MAE: {fatigue_mae:.4f}")
    print(f"RMSE: {fatigue_rmse:.4f}")
    print(f"5-Fold CV R² Mean: {fatigue_cv_scores.mean():.4f}")
    print(f"5-Fold CV R² Std: {fatigue_cv_scores.std():.4f}")

    # -----------------------------
    # Injury Classification Evaluation
    # -----------------------------
    y_injury = label_encoder.transform(df["injury_risk"])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_injury,
        test_size=0.2,
        random_state=42,
        stratify=y_injury,
    )

    injury_predictions = injury_model.predict(X_test)

    injury_accuracy = accuracy_score(y_test, injury_predictions)
    injury_precision = precision_score(y_test, injury_predictions, average="weighted")
    injury_recall = recall_score(y_test, injury_predictions, average="weighted")
    injury_f1 = f1_score(y_test, injury_predictions, average="weighted")

    injury_cv_scores = cross_val_score(
        injury_model,
        X,
        y_injury,
        cv=5,
        scoring="f1_weighted",
    )

    print("\n==============================")
    print("INJURY RISK MODEL EVALUATION")
    print("==============================")
    print(f"Accuracy: {injury_accuracy:.4f}")
    print(f"Precision: {injury_precision:.4f}")
    print(f"Recall: {injury_recall:.4f}")
    print(f"F1 Score: {injury_f1:.4f}")
    print(f"5-Fold CV F1 Mean: {injury_cv_scores.mean():.4f}")
    print(f"5-Fold CV F1 Std: {injury_cv_scores.std():.4f}")

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, injury_predictions))

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            injury_predictions,
            target_names=label_encoder.classes_,
        )
    )

    # -----------------------------
    # Feature Importance
    # -----------------------------
    fatigue_importance = pd.DataFrame({
        "feature": features,
        "importance": fatigue_model.feature_importances_,
    }).sort_values(by="importance", ascending=False)

    injury_importance = pd.DataFrame({
        "feature": features,
        "importance": injury_model.feature_importances_,
    }).sort_values(by="importance", ascending=False)

    os.makedirs("reports", exist_ok=True)

    fatigue_importance.to_csv(
        "reports/fatigue_feature_importance.csv",
        index=False,
    )

    injury_importance.to_csv(
        "reports/injury_feature_importance.csv",
        index=False,
    )

    print("\nFeature importance reports saved in reports/ folder.")


if __name__ == "__main__":
    evaluate_models()