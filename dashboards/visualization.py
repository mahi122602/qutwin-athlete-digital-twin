import pandas as pd
import plotly.express as px
import streamlit as st


def show_athlete_timeline(history_df: pd.DataFrame):
    if history_df is None or history_df.empty:
        st.info("No timeline available yet.")
        return

    df = history_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    st.subheader("Digital Twin Timeline")

    cols = [
        "timestamp",
        "athlete_state",
        "fatigue_score",
        "injury_risk",
        "readiness_score",
        "twin_score",
        "recommendation",
    ]

    available_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[available_cols], use_container_width=True)

    if "fatigue_score" in df.columns:
        fig = px.line(
            df,
            x="timestamp",
            y="fatigue_score",
            markers=True,
            title="Fatigue Score Over Time",
        )
        st.plotly_chart(fig, use_container_width=True)

    if "readiness_score" in df.columns:
        fig = px.line(
            df,
            x="timestamp",
            y="readiness_score",
            markers=True,
            title="Readiness Score Over Time",
        )
        st.plotly_chart(fig, use_container_width=True)

    if "twin_score" in df.columns:
        fig = px.line(
            df,
            x="timestamp",
            y="twin_score",
            markers=True,
            title="Digital Twin Score Over Time",
        )
        st.plotly_chart(fig, use_container_width=True)