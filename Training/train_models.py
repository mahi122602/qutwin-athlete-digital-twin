import os
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    r2_score,
    mean_absolute_error,
    accuracy_score,
    f1_score,
    classification_report,
)


DATA_PATH = "data/athlete_training_dataset.csv"
MODEL_DIR = "models"

os.makedirs(MODEL_DIR, exist_ok=True)


def hydration_to_score(value):
    value = str(value).lower()

    if value == "low":
        return 0.4
    if value == "medium":
        return 0.7
    if value == "high":
        return 1.0

    return 0.7


def build_training_features(df):
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
        df["environmental_stress"] = (temp_score * 0.6 + humidity_score * 0.4).clip(0, 1)

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


def main():
    df = pd.read_csv(DATA_PATH)
    df = build_training_features(df)

    features = [
        "heart_rate",
        "sleep_hours",
        "training_load",
        "recovery_time",
        "temperature",
        "humidity",
        "previous_injury",
        "hydration_score",
        "acwr",
        "recovery_index",
        "environmental_stress",
        "fatigue_index",
        "readiness_index",
    ]

    X = df[features]

    # -----------------------------
    # Fatigue Regression Model
    # -----------------------------
    y_fatigue = df["fatigue_score"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_fatigue, test_size=0.2, random_state=42
    )

    fatigue_model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        random_state=42,
    )

    fatigue_model.fit(X_train, y_train)
    fatigue_pred = fatigue_model.predict(X_test)

    print("\n--- Fatigue Model Performance ---")
    print("R2:", round(r2_score(y_test, fatigue_pred), 4))
    print("MAE:", round(mean_absolute_error(y_test, fatigue_pred), 4))

    joblib.dump(fatigue_model, os.path.join(MODEL_DIR, "fatigue_rf_model.pkl"))

    # -----------------------------
    # Injury Risk Classification Model
    # -----------------------------
    label_encoder = LabelEncoder()
    y_risk = label_encoder.fit_transform(df["injury_risk"])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_risk, test_size=0.2, random_state=42, stratify=y_risk
    )

    injury_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        class_weight="balanced",
        random_state=42,
    )

    injury_model.fit(X_train, y_train)
    injury_pred = injury_model.predict(X_test)

    print("\n--- Injury Risk Model Performance ---")
    print("Accuracy:", round(accuracy_score(y_test, injury_pred), 4))
    print("Weighted F1:", round(f1_score(y_test, injury_pred, average="weighted"), 4))
    print(classification_report(y_test, injury_pred, target_names=label_encoder.classes_))

    joblib.dump(injury_model, os.path.join(MODEL_DIR, "injury_rf_model.pkl"))
    joblib.dump(label_encoder, os.path.join(MODEL_DIR, "injury_label_encoder.pkl"))
    joblib.dump(features, os.path.join(MODEL_DIR, "model_features.pkl"))

    print("\n✅ Models saved successfully in the models folder.")


if __name__ == "__main__":
    main()