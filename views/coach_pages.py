import streamlit as st
import pandas as pd

from database.recommendation_repository import save_coach_recommendation
from digital_twin.forecasting_engine import forecast_metric, generate_forecast_summary

from database.coach_repository import (
    assign_athlete_to_coach,
    get_assigned_athletes,
    get_coach_athlete_risk_dashboard,
)

from database.twin_repository import get_athlete_twin_history
from dashboards.visualization import show_athlete_timeline


def _get_risk_df():
    risk_rows = get_coach_athlete_risk_dashboard(st.session_state.user_id)

    if not risk_rows:
        return pd.DataFrame()

    risk_df = pd.DataFrame({
        "Athlete ID": [r[0] for r in risk_rows],
        "Name": [r[1] for r in risk_rows],
        "Fatigue Score": [r[2] for r in risk_rows],
        "Injury Risk": [r[3] for r in risk_rows],
        "Readiness Score": [r[4] for r in risk_rows],
        "Twin Score": [r[5] for r in risk_rows],
        "Athlete State": [r[6] for r in risk_rows],
        "Recommendation": [r[7] for r in risk_rows],
        "Last Updated": [r[8] for r in risk_rows],
    })

    risk_order = {"High": 1, "Medium": 2, "Low": 3}
    risk_df["Risk Rank"] = risk_df["Injury Risk"].map(risk_order).fillna(4)

    risk_df["Fatigue Score"] = pd.to_numeric(risk_df["Fatigue Score"], errors="coerce")
    risk_df["Readiness Score"] = pd.to_numeric(risk_df["Readiness Score"], errors="coerce")
    risk_df["Twin Score"] = pd.to_numeric(risk_df["Twin Score"], errors="coerce")

    risk_df = risk_df.sort_values(
        by=["Risk Rank", "Fatigue Score"],
        ascending=[True, False],
    )

    return risk_df.drop(columns=["Risk Rank"])


def coach_dashboard():
    st.title("Coach Digital Twin Dashboard")

    risk_df = _get_risk_df()
    athletes = get_assigned_athletes(st.session_state.user_id)

    assigned_count = len(athletes) if athletes else 0

    if risk_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Assigned Athletes", assigned_count)
        c2.metric("High Risk", 0)
        c3.metric("Average Readiness", "N/A")
        st.info("No athlete Digital Twin data available yet.")
        return

    high_count = (risk_df["Injury Risk"] == "High").sum()
    medium_count = (risk_df["Injury Risk"] == "Medium").sum()
    low_count = (risk_df["Injury Risk"] == "Low").sum()
    avg_readiness = risk_df["Readiness Score"].mean()
    avg_fatigue = risk_df["Fatigue Score"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Assigned Athletes", assigned_count)
    c2.metric("High Risk", int(high_count))
    c3.metric("Medium Risk", int(medium_count))
    c4.metric("Low Risk", int(low_count))

    c5, c6 = st.columns(2)
    c5.metric("Average Fatigue", f"{avg_fatigue:.1f}" if pd.notna(avg_fatigue) else "N/A")
    c6.metric("Average Readiness", f"{avg_readiness:.1f}%" if pd.notna(avg_readiness) else "N/A")

    st.subheader("Latest Priority Alert")
    top = risk_df.iloc[0]

    if top["Injury Risk"] == "High":
        st.error(
            f"Immediate attention: {top['Athlete ID']} — "
            f"fatigue {top['Fatigue Score']}, "
            f"readiness {top['Readiness Score']}%."
        )
    elif top["Injury Risk"] == "Medium":
        st.warning(
            f"Monitor closely: {top['Athlete ID']} — "
            f"fatigue {top['Fatigue Score']}, "
            f"readiness {top['Readiness Score']}%."
        )
    else:
        st.success("No high-risk athletes currently detected.")


def assign_athlete():
    st.title("Assign Athlete to Coach")

    athlete_to_assign = st.text_input("Enter Athlete ID")

    if st.button("Assign Athlete"):
        if athlete_to_assign:
            assign_athlete_to_coach(st.session_state.user_id, athlete_to_assign)
            st.success(f"Athlete {athlete_to_assign} assigned successfully.")
        else:
            st.warning("Please enter an Athlete ID.")


def assigned_athletes():
    st.title("Assigned Athletes")

    athletes = get_assigned_athletes(st.session_state.user_id)

    if not athletes:
        st.info("No athletes assigned yet.")
        return

    assigned_df = pd.DataFrame({
        "Athlete ID": [a[0] for a in athletes],
        "Name": [a[1] for a in athletes],
        "Age": [a[2] for a in athletes],
        "Height": [a[3] for a in athletes],
        "Weight": [a[4] for a in athletes],
        "Previous Injury": [a[5] for a in athletes],
    })

    st.dataframe(assigned_df, use_container_width=True)


def coach_intelligence_dashboard():
    st.title("Coach Intelligence Dashboard")

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info("No risk data available yet. Athletes need to upload data first.")
        return

    st.subheader("Athlete Risk Ranking")
    st.caption("Sorted automatically: High risk first, then Medium, then Low.")

    st.dataframe(risk_df, use_container_width=True)

    high_count = (risk_df["Injury Risk"] == "High").sum()
    medium_count = (risk_df["Injury Risk"] == "Medium").sum()
    low_count = (risk_df["Injury Risk"] == "Low").sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("High Risk", int(high_count))
    c2.metric("Medium Risk", int(medium_count))
    c3.metric("Low Risk", int(low_count))


def selected_athlete_twin_summary():
    st.title("Selected Athlete Twin Summary")

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info("No athlete Digital Twin data available yet.")
        return

    selected_athlete = st.selectbox(
        "Select Athlete",
        risk_df["Athlete ID"].tolist(),
    )

    selected_row = risk_df[
        risk_df["Athlete ID"] == selected_athlete
    ].iloc[0]

    st.subheader(f"Current Digital Twin State: {selected_athlete}")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Fatigue", selected_row["Fatigue Score"])
    c2.metric("Injury Risk", selected_row["Injury Risk"])
    c3.metric("Readiness", selected_row["Readiness Score"])
    c4.metric("Twin Score", selected_row["Twin Score"])

    st.success("AI Recommendation")
    st.info(selected_row["Recommendation"])

    st.divider()

    st.subheader("Coach Review & Approval")

    coach_note = st.text_area(
        "Edit or write coach recommendation",
        value=selected_row["Recommendation"],
        height=140,
    )

    approval_status = st.radio(
        "Approval Decision",
        ["Approved", "Rejected"],
        horizontal=True,
    )

    if st.button("Save Coach Decision"):
        if coach_note.strip():

            save_coach_recommendation(
                coach_id=st.session_state.user_id,
                athlete_id=selected_athlete,
                ai_recommendation=selected_row["Recommendation"],
                coach_comment=coach_note,
                approval_status=approval_status,
            )

            if approval_status == "Approved":
                st.success("Recommendation approved and saved.")
            else:
                st.warning("Recommendation rejected and saved.")

        else:
            st.warning("Please write a recommendation before saving.")

    st.divider()

    st.subheader("7-Day Digital Twin Forecast")

    history_df = get_athlete_twin_history(selected_athlete)

    if history_df is not None and not history_df.empty:

        fatigue_forecast = forecast_metric(
            history_df,
            "fatigue_score",
            days=7,
        )

        readiness_forecast = forecast_metric(
            history_df,
            "readiness_score",
            days=7,
        )

        if not fatigue_forecast.empty:
            st.write("Predicted Fatigue Trend")
            st.line_chart(
                fatigue_forecast.set_index("forecast_date")[
                    "forecast_value"
                ]
            )

        if not readiness_forecast.empty:
            st.write("Predicted Readiness Trend")
            st.line_chart(
                readiness_forecast.set_index("forecast_date")[
                    "forecast_value"
                ]
            )

        st.success("Forecast Summary")
        st.info(
            generate_forecast_summary(
                fatigue_forecast,
                readiness_forecast,
            )
        )

    else:
        st.info(
            "Not enough Digital Twin history available for forecasting."
        )


def coach_history():
    st.title("Digital Twin History")

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info("No athlete data available.")
        return

    selected_athlete = st.selectbox(
        "Select Athlete",
        risk_df["Athlete ID"].tolist(),
    )

    history_df = get_athlete_twin_history(selected_athlete)

    if history_df is None or history_df.empty:
        st.info("No Digital Twin history available for this athlete.")
        return

    st.dataframe(history_df, use_container_width=True)


def coach_timeline():
    st.title("Digital Twin Timeline")

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info("No athlete data available.")
        return

    selected_athlete = st.selectbox(
        "Select Athlete",
        risk_df["Athlete ID"].tolist(),
    )

    history_df = get_athlete_twin_history(selected_athlete)

    if history_df is None or history_df.empty:
        st.info("No timeline available for this athlete.")
        return

    show_athlete_timeline(history_df)


def coach_visualisations():
    st.title("Visualisations / Graphs")

    risk_df = _get_risk_df()

    if risk_df.empty:
        st.info("No coach analytics available yet.")
        return

    st.subheader("Team Fatigue Overview")
    st.bar_chart(risk_df.set_index("Athlete ID")["Fatigue Score"])

    st.subheader("Team Readiness Overview")
    st.bar_chart(risk_df.set_index("Athlete ID")["Readiness Score"])

    st.subheader("Twin Score Overview")
    st.bar_chart(risk_df.set_index("Athlete ID")["Twin Score"])