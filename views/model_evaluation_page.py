import os
import streamlit as st
import pandas as pd


def model_evaluation_dashboard():
    st.title("Model Evaluation Dashboard")

    st.info(
        "This page summarizes the research-grade evaluation of the fatigue "
        "prediction and injury risk models."
    )

    st.subheader("Fatigue Prediction Model")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R² Score", "From terminal")
    c2.metric("MAE", "From terminal")
    c3.metric("RMSE", "From terminal")
    c4.metric("5-Fold CV", "From terminal")

    st.subheader("Injury Risk Classification Model")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Accuracy", "From terminal")
    c6.metric("Precision", "From terminal")
    c7.metric("Recall", "From terminal")
    c8.metric("F1 Score", "From terminal")

    st.subheader("Feature Importance")

    fatigue_path = "reports/fatigue_feature_importance.csv"
    injury_path = "reports/injury_feature_importance.csv"

    if os.path.exists(fatigue_path):
        fatigue_df = pd.read_csv(fatigue_path)
        st.write("Fatigue Model Feature Importance")
        st.bar_chart(fatigue_df.set_index("feature")["importance"])
    else:
        st.warning("Fatigue feature importance report not found.")

    if os.path.exists(injury_path):
        injury_df = pd.read_csv(injury_path)
        st.write("Injury Model Feature Importance")
        st.bar_chart(injury_df.set_index("feature")["importance"])
    else:
        st.warning("Injury feature importance report not found.")

    st.subheader("Research Interpretation")

    st.write(
        """
        The model evaluation process supports the research validity of the Digital Twin system.
        Cross-validation is used to estimate generalisation performance, while MAE, RMSE and R²
        evaluate fatigue prediction quality. Accuracy, precision, recall and F1-score evaluate
        injury-risk classification reliability. Feature importance helps explain which athlete
        variables most strongly influence model decisions.
        """
    )