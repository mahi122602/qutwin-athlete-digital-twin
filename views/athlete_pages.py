import streamlit as st
import pandas as pd
from database.recommendation_repository import get_latest_coach_recommendation
from ingestion.auto_loader import load_uploaded_file
from digital_twin.state_engine import build_digital_twin_state
from digital_twin.twin_engine import build_twin_snapshot
from digital_twin.twin_object import AthleteTwin
from digital_twin.simulation_engine import simulate_scenario
from dashboards.visualization import show_athlete_timeline
from digital_twin.bayesian_engine import apply_bayesian_fatigue_update
from digital_twin.forecasting_engine import forecast_metric, generate_forecast_summary
from prediction.prediction_pipeline import run_prediction_pipeline
from digital_twin.state_space_engine import apply_state_space_model
from io import BytesIO
from database.twin_repository import (
    save_uploaded_file,
    save_digital_twin_states,
    get_athlete_twin_history,
    get_latest_twin_state,
)
from database.athlete_repository import (
    get_athlete_profile,
    update_athlete_profile,
)


def athlete_profile():
    st.title("Athlete Profile")

    profile = get_athlete_profile(st.session_state.user_id)

    if profile is None:
        st.error("Athlete profile not found.")
        return

    # --------------------------------------------------
    # PREPARE EXISTING PROFILE PHOTO
    # PostgreSQL BYTEA may be returned as memoryview.
    # --------------------------------------------------
    existing_photo = profile.get("profile_photo")

    if isinstance(existing_photo, memoryview):
        existing_photo = existing_photo.tobytes()

    elif isinstance(existing_photo, bytearray):
        existing_photo = bytes(existing_photo)

    if existing_photo:
        st.image(
            BytesIO(existing_photo),
            width=140,
            caption="Current profile picture",
        )

    # --------------------------------------------------
    # PERSONAL DETAILS
    # --------------------------------------------------
    st.markdown("### Personal Details")

    name = st.text_input(
        "Name",
        value=profile.get("name") or "",
    )

    email = st.text_input(
        "Email",
        value=profile.get("email") or "",
    )

    phone = st.text_input(
        "Contact Number",
        value=profile.get("contact_number") or "",
    )

    # --------------------------------------------------
    # ATHLETE DETAILS
    # --------------------------------------------------
    st.markdown("### Athlete Details")

    current_height = profile.get("height")
    current_weight = profile.get("weight")

    height = st.number_input(
        "Height (cm)",
        min_value=100.0,
        max_value=250.0,
        value=float(current_height) if current_height is not None else 170.0,
        step=0.5,
    )

    weight = st.number_input(
        "Weight (kg)",
        min_value=30.0,
        max_value=200.0,
        value=float(current_weight) if current_weight is not None else 70.0,
        step=0.5,
    )

    injury_history = st.text_area(
        "Injury History",
        value=profile.get("injury_history") or "",
    )

    # --------------------------------------------------
    # PROFILE PICTURE
    # --------------------------------------------------
    st.markdown("### Profile Picture")

    uploaded_photo = st.file_uploader(
        "Upload a new profile picture",
        type=["png", "jpg", "jpeg"],
        key="athlete_profile_photo_uploader",
    )

    # Keep the existing photo unless the athlete uploads a new one.
    photo_bytes = existing_photo

    if uploaded_photo is not None:
        photo_bytes = uploaded_photo.getvalue()

        st.image(
            BytesIO(photo_bytes),
            width=140,
            caption="New profile picture preview",
        )

    # --------------------------------------------------
    # SAVE PROFILE
    # --------------------------------------------------
    if st.button(
        "Save Profile",
        type="primary",
        use_container_width=True,
    ):
        try:
            update_athlete_profile(
                athlete_id=st.session_state.user_id,
                name=name.strip(),
                email=email.strip(),
                contact_number=phone.strip(),
                height=height,
                weight=weight,
                injury_history=injury_history.strip(),
                profile_photo=photo_bytes,
            )

            if photo_bytes is not None:
                st.session_state.profile_photo = photo_bytes

            st.success("Profile updated successfully.")
            st.rerun()

        except Exception as exc:
            st.error("The profile could not be updated.")
            st.exception(exc)


def athlete_dashboard():
    st.title("Digital Twin Dashboard")

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("No Digital Twin state available yet.")
        st.write("Upload Garmin data to create your first Digital Twin state.")

        if st.button("Upload Garmin Data"):
            st.session_state.current_page = "Upload Garmin Data"
            st.rerun()

        return

    latest = history_df.sort_values("timestamp").iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fatigue", latest.get("fatigue_score", "N/A"))
    c2.metric("Readiness", latest.get("readiness_score", "N/A"))
    c3.metric("Injury Risk", latest.get("injury_risk", "N/A"))
    c4.metric("Twin Score", latest.get("twin_score", "N/A"))

    st.success("Latest AI Recommendation")
    st.info(latest.get("recommendation", "No recommendation available."))

    if st.button("Upload New Athlete Data"):
        st.session_state.current_page = "Upload Garmin Data"
        st.rerun()


def upload_garmin_data():
    st.title("Upload Athlete Data")
    st.caption(
        "Upload exported athlete data from Garmin, Samsung Health, Strava, "
        "Fitbit, Apple Health, Polar, WHOOP, COROS, or another supported source."
        )

    uploaded_file = st.file_uploader(
        "Upload athlete health, wearable, or activity data",
        type=[
        "zip",
        "csv",
        "xlsx",
        "xls",
        "fit",
        "tcx",
        "gpx",
        "xml",
        "json",
        ],
    )

    if uploaded_file is None:
        st.info(
            "Upload athlete data to generate a new Digital Twin state."
            )
        return

    try:
        model_ready_df, raw_preview, detection = load_uploaded_file(uploaded_file)

        detected_source = detection.get("source", "Unknown")
        detected_file_type = detection.get("file_type", "unknown").upper()
        detected_category = detection.get("category", "Unknown")
        detection_confidence = detection.get("confidence", "Low")
        original_device = detection.get("original_device_source")

        st.success("File detected successfully.")
        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Source",
            detected_source,
            )

        col2.metric(
            "File type",
            detected_file_type,
            )
        col3.metric(
            "Data category",
            detected_category,
            )
        col4.metric(
            "Detection confidence",
            detection_confidence,
            )
        if original_device:
            st.caption(
                f"Original device/source detected: **{original_device}**"
                )
        detected_type = f"{detected_source} {detected_file_type}"

        if model_ready_df is None or model_ready_df.empty:
            st.warning("No model-ready features could be extracted from this file.")
            return

        model_ready_df = build_digital_twin_state(model_ready_df)
        model_ready_df = build_twin_snapshot(model_ready_df)
        model_ready_df = run_prediction_pipeline(model_ready_df)
        model_ready_df = apply_state_space_model(model_ready_df)

        model_ready_df["health_index"] = (
            model_ready_df["readiness_score"] * 0.50
            + (100 - model_ready_df["fatigue_score"]) * 0.30
            + model_ready_df["twin_score"] * 0.20
        ).round(1)

        previous_state = get_latest_twin_state(st.session_state.user_id)
        model_ready_df = apply_bayesian_fatigue_update(
            model_ready_df,
            previous_state,
            )

        athlete_twin = AthleteTwin(
            
            athlete_id=st.session_state.user_id,
            current_state=model_ready_df,
            previous_state=previous_state,
        )

        model_ready_df = athlete_twin.apply_memory()

        st.subheader("Extracted Digital Twin Features")

        display_columns = [
            "timestamp",
            "heart_rate",
            "sleep_hours",
            "training_load",
            "recovery_time",
            "fatigue_score",
            "readiness_score",
            "injury_risk",
            "athlete_state",
            "twin_score",
            "health_index",
            "recommendation",
        ]

        available_columns = [c for c in display_columns if c in model_ready_df.columns]

        st.dataframe(
            model_ready_df[available_columns].head(20),
            use_container_width=True,
        )

        if st.button("Save as Digital Twin State"):
            upload_id = save_uploaded_file(
                athlete_id=st.session_state.user_id,
                filename=uploaded_file.name,
                file_type=detected_type,
                rows_extracted=len(model_ready_df),
            )

            save_digital_twin_states(
                athlete_id=st.session_state.user_id,
                upload_id=upload_id,
                df=model_ready_df,
            )

            st.success("Digital Twin state saved successfully.")

        with st.expander("Raw Extracted Data Preview"):
            if raw_preview:
                for name, df in raw_preview.items():
                    st.write(f"### {name}")
                    if df is not None and not df.empty:
                        st.dataframe(df.head(10), use_container_width=True)
                    else:
                        st.info("No data found.")
            else:
                st.info("No raw preview available.")

    except Exception as e:
        st.error(f"File processing failed: {e}")


def athlete_predictions():
    st.title("Predictions & Coach Recommendations")

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("No predictions available yet. Upload Garmin data first.")
        return

    latest = history_df.sort_values("timestamp").iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fatigue Score", latest.get("fatigue_score", "N/A"))
    c2.metric("Injury Risk", latest.get("injury_risk", "N/A"))
    c3.metric("Readiness", latest.get("readiness_score", "N/A"))
    c4.metric("Twin Score", latest.get("twin_score", "N/A"))

    st.success("AI Recommendation")
    st.info(latest.get("recommendation", "No recommendation available."))

    coach_rec = get_latest_coach_recommendation(st.session_state.user_id)

    st.success("Coach Feedback")
    
    if coach_rec:
        st.info(coach_rec["recommendation"])
        st.caption(
        f"Approved by {coach_rec['coach_id']} • Reviewed at {coach_rec['reviewed_at']}"
    )
    else:
        st.warning("No coach feedback available yet.")

def athlete_history():
    st.title("Digital Twin History")

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("No Digital Twin history available yet.")
        return

    st.dataframe(history_df, use_container_width=True)

    csv = history_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download History CSV",
        csv,
        "digital_twin_history.csv",
        "text/csv",
    )


def athlete_timeline():
    st.title("Digital Twin Timeline")

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("No timeline available yet.")
        return

    show_athlete_timeline(history_df)


def athlete_visualisations():
    st.title("Visualisations / Graphs")

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("No visualisations available yet.")
        return

    chart_cols = [
        "heart_rate",
        "training_load",
        "fatigue_score",
        "readiness_score",
        "twin_score",
        "health_index",
    ]

    available_cols = [c for c in chart_cols if c in history_df.columns]

    if available_cols:
        chart_df = history_df.sort_values("timestamp")
        st.subheader("Digital Twin Historical Trends")
        st.line_chart(chart_df[available_cols])
    else:
        st.info("No chart-ready metrics available.")

    st.subheader("7-Day Digital Twin Forecast")

    fatigue_forecast = forecast_metric(history_df, "fatigue_score", days=7)
    readiness_forecast = forecast_metric(history_df, "readiness_score", days=7)

    if not fatigue_forecast.empty:
        st.write("Fatigue Forecast")
        st.line_chart(
            fatigue_forecast.set_index("forecast_date")["forecast_value"]
        )

    if not readiness_forecast.empty:
        st.write("Readiness Forecast")
        st.line_chart(
            readiness_forecast.set_index("forecast_date")["forecast_value"]
        )

    st.info(generate_forecast_summary(fatigue_forecast, readiness_forecast))


def athlete_simulation():
    st.title("What-if Simulation")

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("Save at least one Digital Twin state before running simulations.")
        return

    latest_state = history_df.sort_values("timestamp").iloc[-1].to_dict()

    sleep_change = st.slider("Change Sleep Hours", -4.0, 4.0, 0.0, 0.5)
    training_change = st.slider("Change Training Load", -50.0, 50.0, 0.0, 5.0)
    recovery_change = st.slider("Change Recovery Time", -5.0, 5.0, 0.0, 0.5)

    simulated = simulate_scenario(
        latest_state,
        sleep_change=sleep_change,
        training_load_change=training_change,
        recovery_change=recovery_change,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Simulated Fatigue", simulated["simulated_fatigue_score"])
    c2.metric("Simulated Readiness", f"{simulated['simulated_readiness_score']}%")
    c3.metric("Simulated Injury Risk", simulated["simulated_injury_risk"])