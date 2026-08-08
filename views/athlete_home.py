import streamlit as st
import pandas as pd
from io import BytesIO
from database.athlete_repository import get_athlete_profile
from database.twin_repository import get_athlete_twin_history
from views.forecasting_card import render_forecasting_card


def open_athlete_page(page_name):
    st.session_state.current_page = page_name
    st.rerun()


def athlete_feature_gallery():
    athlete_id = st.session_state.user_id

    profile = get_athlete_profile(athlete_id)
    history_df = get_athlete_twin_history(athlete_id)

    athlete_name = (
        profile.get("name")
        if profile and profile.get("name")
        else athlete_id
    )

    latest = None

    if history_df is not None and not history_df.empty:
        history_df["timestamp"] = pd.to_datetime(
            history_df["timestamp"],
            errors="coerce",
        )

        latest = (
            history_df
            .sort_values("timestamp")
            .iloc[-1]
        )

    st.markdown(
        f"""
        <div class="gallery-heading">
            <div class="gallery-eyebrow">ATHLETE DIGITAL TWIN</div>
            <h1>Welcome back, {athlete_name}</h1>
            <p>Your Digital Twin experience</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    row1 = st.columns(4)

    # --------------------------------------------------
# CARD 1 — PROFILE
# --------------------------------------------------
    with row1[0]:
        with st.container(border=True):
            st.caption("01")
            st.subheader("Profile")

            if profile:
                profile_photo = profile.get("profile_photo")

                if profile_photo:
                    if isinstance(profile_photo, memoryview):
                        profile_photo = profile_photo.tobytes()

                    elif isinstance(profile_photo, bytearray):
                        profile_photo = bytes(profile_photo)

                    if isinstance(profile_photo, bytes):
                        profile_photo = BytesIO(profile_photo)

                    st.image(profile_photo, width=120)

            st.write(f"**{athlete_name}**")
            st.caption("Athlete profile and personal information")

            if st.button(
                "View Profile",
                key="open_profile",
                use_container_width=True,
            ):
                open_athlete_page("Profile")

    # --------------------------------------------------
    # CARD 2 — DIGITAL TWIN DASHBOARD
    # --------------------------------------------------
    with row1[1]:
        with st.container(border=True):
            st.caption("02")
            st.subheader("Digital Twin Dashboard")

            if latest is not None:
                st.metric(
                    "Twin Score",
                    f"{float(latest.get('twin_score', 0)):.1f}",
                )

                c1, c2 = st.columns(2)

                c1.metric(
                    "Fatigue",
                    f"{float(latest.get('fatigue_score', 0)):.1f}",
                )

                c2.metric(
                    "Readiness",
                    f"{float(latest.get('readiness_score', 0)):.1f}%",
                )
            else:
                st.info("No Digital Twin state yet.")

            if st.button(
                "Open Dashboard",
                key="open_dashboard",
                use_container_width=True,
            ):
                open_athlete_page("Digital Twin Dashboard")

    # --------------------------------------------------
    # CARD 3 — UPLOAD GARMIN
    # --------------------------------------------------
    with row1[2]:
        with st.container(border=True):
            st.caption("03")
            st.subheader("Upload Garmin Data")

            st.markdown("### Upload activity")
            st.caption(
                "Import Garmin ZIP, FIT, CSV, or Excel activity data."
            )

            if latest is not None:
                timestamp = latest.get("timestamp")

                if pd.notna(timestamp):
                    st.write(f"Last state: **{timestamp:%d %b %Y}**")

            if st.button(
                "Upload Data",
                key="open_upload",
                use_container_width=True,
            ):
                open_athlete_page("Upload Garmin Data")

    # --------------------------------------------------
    # CARD 4 — PREDICTIONS
    # --------------------------------------------------
    with row1[3]:
        with st.container(border=True):
            st.caption("04")
            st.subheader("Predictions")

            if latest is not None:
                st.metric(
                    "Injury Risk",
                    latest.get("injury_risk", "N/A"),
                )

                st.metric(
                    "Fatigue Prediction",
                    f"{float(latest.get('fatigue_score', 0)):.1f}",
                )
            else:
                st.info("No prediction available.")

            if st.button(
                "View Predictions",
                key="open_predictions",
                use_container_width=True,
            ):
                open_athlete_page(
                    "Predictions & Coach Recommendations"
                )

    st.write("")

    row2 = st.columns(4)

    # --------------------------------------------------
    # CARD 5 — HISTORY
    # --------------------------------------------------
    with row2[0]:
        with st.container(border=True):
            st.caption("05")
            st.subheader("Digital Twin History")

            state_count = (
                len(history_df)
                if history_df is not None
                else 0
            )

            st.metric("Saved States", state_count)
            st.caption("Review previous Digital Twin records.")

            if st.button(
                "View History",
                key="open_history",
                use_container_width=True,
            ):
                open_athlete_page("Digital Twin History")

    # --------------------------------------------------
    # CARD 6 — TIMELINE
    # --------------------------------------------------
    with row2[1]:
        with st.container(border=True):
            st.caption("06")
            st.subheader("Digital Twin Timeline")

            if latest is not None:
                st.write(
                    f"Current state: **"
                    f"{latest.get('digital_twin_state', latest.get('athlete_state', 'N/A'))}"
                    f"**"
                )

                st.caption(
                    "Follow changes in fatigue, readiness and recovery."
                )
            else:
                st.info("No timeline available.")

            if st.button(
                "View Timeline",
                key="open_timeline",
                use_container_width=True,
            ):
                open_athlete_page("Digital Twin Timeline")

    # --------------------------------------------------
    # CARD 7 — VISUALISATIONS
    # --------------------------------------------------
    with row2[2]:
        with st.container(border=True):
            st.caption("07")
            st.subheader("Visualisations")

            if latest is not None:
                st.metric(
                    "Readiness",
                    f"{float(latest.get('readiness_score', 0)):.1f}%",
                )

                st.caption(
                    "Historical trends and seven-day forecasts."
                )
            else:
                st.info("No graph data available.")

            if st.button(
                "View Graphs",
                key="open_visualisations",
                use_container_width=True,
            ):
                open_athlete_page("Visualisations / Graphs")

    # --------------------------------------------------
    # CARD 8 — SIMULATION
    # --------------------------------------------------
    with row2[3]:
        with st.container(border=True):
            st.caption("08")
            st.subheader("What-if Simulation")

            st.markdown("### Test a scenario")
            st.caption(
                "Explore how sleep, recovery and training load "
                "could affect future outcomes."
            )

            if st.button(
                "Run Simulation",
                key="open_simulation",
                use_container_width=True,
            ):
                open_athlete_page("What-if Simulation")

    st.write("")

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader("Model Evaluation")
            st.caption(
                "Review cross-validation, R², MAE, RMSE, "
                "accuracy, precision, recall and F1-score."
            )

        with col2:
            if st.button(
                "Open Evaluation",
                key="open_evaluation",
                use_container_width=True,
            ):
                open_athlete_page("Model Evaluation")
    # --------------------------------------------------
# CARD 9 — FORECASTING
# --------------------------------------------------
    forecast_row = st.columns(4)
    with forecast_row[0]:
        render_forecasting_card(open_athlete_page)