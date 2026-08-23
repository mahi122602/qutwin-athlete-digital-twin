import streamlit as st
import pandas as pd
import plotly.express as px

from io import BytesIO

from database.recommendation_repository import (
    get_latest_coach_recommendation,
)

from ingestion.auto_loader import load_uploaded_file

from digital_twin.state_engine import (
    build_digital_twin_state,
)

from digital_twin.twin_engine import (
    build_twin_snapshot,
)

from digital_twin.twin_object import (
    AthleteTwin,
)

from digital_twin.simulation_engine import (
    simulate_scenario,
)

from dashboards.visualization import (
    show_athlete_timeline,
)

from digital_twin.bayesian_engine import (
    apply_bayesian_fatigue_update,
)

from digital_twin.forecasting_engine import (
    forecast_metric,
    generate_forecast_summary,
)

from prediction.prediction_pipeline import (
    run_prediction_pipeline,
)

from digital_twin.state_space_engine import (
    apply_state_space_model,
)

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


# ============================================================
# ATHLETE PROFILE
# ============================================================

def athlete_profile():

    st.title("Athlete Profile")

    profile = get_athlete_profile(
        st.session_state.user_id
    )

    if profile is None:

        st.error(
            "Athlete profile not found."
        )

        return

    # --------------------------------------------------------
    # EXISTING PROFILE PHOTO
    # --------------------------------------------------------

    existing_photo = profile.get(
        "profile_photo"
    )

    if isinstance(
        existing_photo,
        memoryview,
    ):

        existing_photo = (
            existing_photo.tobytes()
        )

    elif isinstance(
        existing_photo,
        bytearray,
    ):

        existing_photo = bytes(
            existing_photo
        )

    if existing_photo:

        st.image(
            BytesIO(existing_photo),
            width=140,
            caption="Current profile picture",
        )

    # --------------------------------------------------------
    # PERSONAL DETAILS
    # --------------------------------------------------------

    st.markdown(
        "### Personal Details"
    )

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
        value=(
            profile.get("contact_number")
            or ""
        ),
    )

    # --------------------------------------------------------
    # ATHLETE DETAILS
    # --------------------------------------------------------

    st.markdown(
        "### Athlete Details"
    )

    current_height = profile.get(
        "height"
    )

    current_weight = profile.get(
        "weight"
    )

    height = st.number_input(
        "Height (cm)",
        min_value=100.0,
        max_value=250.0,
        value=(
            float(current_height)
            if current_height is not None
            else 170.0
        ),
        step=0.5,
    )

    weight = st.number_input(
        "Weight (kg)",
        min_value=30.0,
        max_value=200.0,
        value=(
            float(current_weight)
            if current_weight is not None
            else 70.0
        ),
        step=0.5,
    )

    injury_history = st.text_area(
        "Injury History",
        value=(
            profile.get("injury_history")
            or ""
        ),
    )

    # --------------------------------------------------------
    # PROFILE PICTURE
    # --------------------------------------------------------

    st.markdown(
        "### Profile Picture"
    )

    uploaded_photo = st.file_uploader(
        "Upload a new profile picture",
        type=[
            "png",
            "jpg",
            "jpeg",
        ],
        key=(
            "athlete_profile_photo_uploader"
        ),
    )

    photo_bytes = existing_photo

    if uploaded_photo is not None:

        photo_bytes = (
            uploaded_photo.getvalue()
        )

        st.image(
            BytesIO(photo_bytes),
            width=140,
            caption=(
                "New profile picture preview"
            ),
        )

    # --------------------------------------------------------
    # SAVE PROFILE
    # --------------------------------------------------------

    if st.button(
        "Save Profile",
        type="primary",
        use_container_width=True,
    ):

        try:

            update_athlete_profile(
                athlete_id=(
                    st.session_state.user_id
                ),
                name=name.strip(),
                email=email.strip(),
                contact_number=(
                    phone.strip()
                ),
                height=height,
                weight=weight,
                injury_history=(
                    injury_history.strip()
                ),
                profile_photo=photo_bytes,
            )

            if photo_bytes is not None:

                st.session_state.profile_photo = (
                    photo_bytes
                )

            st.success(
                "Profile updated successfully."
            )

            st.rerun()

        except Exception as exc:

            st.error(
                "The profile could not be updated."
            )

            st.exception(exc)


# ============================================================
# ATHLETE DIGITAL TWIN DASHBOARD
# ============================================================

def athlete_dashboard():

    st.title(
        "Digital Twin Dashboard"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No Digital Twin state "
            "available yet."
        )

        st.write(
            "Upload athlete data to create "
            "your first Digital Twin state."
        )

        if st.button(
            "Upload Athlete Data",
            type="primary",
        ):

            # Keep internal route name for
            # compatibility with app.py.
            st.session_state.current_page = (
                "Upload Garmin Data"
            )

            st.rerun()

        return

    latest = (
        history_df
        .sort_values("timestamp")
        .iloc[-1]
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Fatigue",
        latest.get(
            "fatigue_score",
            "N/A",
        ),
    )

    c2.metric(
        "Readiness",
        latest.get(
            "readiness_score",
            "N/A",
        ),
    )

    c3.metric(
        "Injury Risk",
        latest.get(
            "injury_risk",
            "N/A",
        ),
    )

    c4.metric(
        "Twin Score",
        latest.get(
            "twin_score",
            "N/A",
        ),
    )

    st.success(
        "Latest AI Recommendation"
    )

    st.info(
        latest.get(
            "recommendation",
            "No recommendation available.",
        )
    )

    if st.button(
        "Upload New Athlete Data"
    ):

        st.session_state.current_page = (
            "Upload Garmin Data"
        )

        st.rerun()


# ============================================================
# UPLOAD ATHLETE DATA
# ============================================================

def upload_garmin_data():
    """
    Internal function name retained for compatibility with
    the existing app.py route.

    The user-facing page is now source-neutral.
    """

    st.title(
        "Upload Athlete Data"
    )

    st.caption(
        "Upload exported athlete health, wearable, "
        "or activity data from a supported source."
    )

    st.divider()

    st.subheader(
        "Upload Health & Activity Data"
    )

    uploaded_file = st.file_uploader(
        (
            "Upload athlete health, wearable, "
            "or activity data"
        ),
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
            "Upload athlete data to generate "
            "a new Digital Twin state."
        )

        return

    try:

        (
            model_ready_df,
            raw_preview,
            detection,
        ) = load_uploaded_file(
            uploaded_file
        )

        # ----------------------------------------------------
        # DETECTION IS STILL USED INTERNALLY
        # BUT IS NO LONGER DISPLAYED TO THE ATHLETE
        # ----------------------------------------------------

        detected_source = detection.get(
            "source",
            "Unknown",
        )

        detected_file_type = (
            detection.get(
                "file_type",
                "unknown",
            )
            .upper()
        )

        detected_type = (
            f"{detected_source} "
            f"{detected_file_type}"
        )

        st.success(
            "File detected successfully."
        )

        # ----------------------------------------------------
        # VALIDATE MODEL-READY FEATURES
        # ----------------------------------------------------

        if (
            model_ready_df is None
            or model_ready_df.empty
        ):

            st.warning(
                "No model-ready features could "
                "be extracted from this file."
            )

            return

        # ----------------------------------------------------
        # DIGITAL TWIN PIPELINE
        # ----------------------------------------------------

        model_ready_df = (
            build_digital_twin_state(
                model_ready_df
            )
        )

        model_ready_df = (
            build_twin_snapshot(
                model_ready_df
            )
        )

        model_ready_df = (
            run_prediction_pipeline(
                model_ready_df
            )
        )

        model_ready_df = (
            apply_state_space_model(
                model_ready_df
            )
        )

        model_ready_df[
            "health_index"
        ] = (
            model_ready_df[
                "readiness_score"
            ]
            * 0.50
            + (
                100
                - model_ready_df[
                    "fatigue_score"
                ]
            )
            * 0.30
            + model_ready_df[
                "twin_score"
            ]
            * 0.20
        ).round(1)

        previous_state = (
            get_latest_twin_state(
                st.session_state.user_id
            )
        )

        model_ready_df = (
            apply_bayesian_fatigue_update(
                model_ready_df,
                previous_state,
            )
        )

        athlete_twin = AthleteTwin(
            athlete_id=(
                st.session_state.user_id
            ),
            current_state=model_ready_df,
            previous_state=previous_state,
        )

        model_ready_df = (
            athlete_twin.apply_memory()
        )

        # ----------------------------------------------------
        # EXTRACTED DIGITAL TWIN FEATURES
        # ----------------------------------------------------

        st.subheader(
            "Extracted Digital Twin Features"
        )

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

        available_columns = [
            column
            for column in display_columns
            if column
            in model_ready_df.columns
        ]

        st.dataframe(
            model_ready_df[
                available_columns
            ].head(20),
            use_container_width=True,
        )

        # ----------------------------------------------------
        # SAVE DIGITAL TWIN STATE
        # ----------------------------------------------------

        if st.button(
            "Save as Digital Twin State",
            type="primary",
        ):

            upload_id = save_uploaded_file(
                athlete_id=(
                    st.session_state.user_id
                ),
                filename=(
                    uploaded_file.name
                ),
                file_type=(
                    detected_type
                ),
                rows_extracted=(
                    len(model_ready_df)
                ),
            )

            save_digital_twin_states(
                athlete_id=(
                    st.session_state.user_id
                ),
                upload_id=upload_id,
                df=model_ready_df,
            )

            st.success(
                "Digital Twin state "
                "saved successfully."
            )

        # ----------------------------------------------------
        # RAW DATA PREVIEW
        # ----------------------------------------------------

        with st.expander(
            "Raw Extracted Data Preview"
        ):

            if raw_preview:

                for (
                    name,
                    df,
                ) in raw_preview.items():

                    st.write(
                        f"### {name}"
                    )

                    if (
                        df is not None
                        and not df.empty
                    ):

                        st.dataframe(
                            df.head(10),
                            use_container_width=True,
                        )

                    else:

                        st.info(
                            "No data found."
                        )

            else:

                st.info(
                    "No raw preview available."
                )

    except Exception as exc:

        st.error(
            f"File processing failed: {exc}"
        )


# ============================================================
# ATHLETE PREDICTIONS
# ============================================================

def athlete_predictions():

    st.title(
        "Predictions & Coach Recommendations"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    # --------------------------------------------------------
    # NO DIGITAL TWIN DATA
    # --------------------------------------------------------

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No predictions available yet. "
            "Upload athlete data first."
        )

        return

    # --------------------------------------------------------
    # LATEST DIGITAL TWIN STATE
    # --------------------------------------------------------

    latest = (
        history_df
        .sort_values("timestamp")
        .iloc[-1]
    )

    fatigue_score = latest.get(
        "fatigue_score",
        "N/A",
    )

    injury_risk = latest.get(
        "injury_risk",
        "N/A",
    )

    readiness_score = latest.get(
        "readiness_score",
        "N/A",
    )

    twin_score = latest.get(
        "twin_score",
        "N/A",
    )

    # --------------------------------------------------------
    # CURRENT PREDICTION SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Current Digital Twin Prediction"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Fatigue Score",
            fatigue_score,
        )

    with c2:

        st.metric(
            "Injury Risk",
            injury_risk,
        )

    with c3:

        st.metric(
            "Readiness",
            readiness_score,
        )

    with c4:

        st.metric(
            "Twin Score",
            twin_score,
        )

    st.divider()

    # --------------------------------------------------------
    # AI RECOMMENDATION
    # --------------------------------------------------------

    st.subheader(
        "AI Recommendation"
    )

    ai_recommendation = latest.get(
        "recommendation",
        "No recommendation available.",
    )

    if ai_recommendation:

        st.info(
            ai_recommendation
        )

    else:

        st.info(
            "No AI recommendation available."
        )

    st.divider()

    # --------------------------------------------------------
    # COACH FEEDBACK
    # --------------------------------------------------------

    st.subheader(
        "Coach Feedback"
    )

    coach_rec = (
        get_latest_coach_recommendation(
            st.session_state.user_id
        )
    )

    if coach_rec:

        recommendation = (
            coach_rec.get(
                "recommendation"
            )
            or coach_rec.get(
                "coach_comment"
            )
            or (
                "No coach feedback "
                "provided."
            )
        )

        st.success(
            recommendation
        )

        coach_id = (
            coach_rec.get(
                "coach_id",
                "Coach",
            )
        )

        reviewed_at = (
            coach_rec.get(
                "reviewed_at"
            )
        )

        if reviewed_at:

            st.caption(
                f"Reviewed by {coach_id} • "
                f"{reviewed_at}"
            )

        else:

            st.caption(
                f"Reviewed by {coach_id}"
            )

    else:

        st.warning(
            "No coach feedback "
            "available yet."
        )


# ============================================================
# ATHLETE HISTORY
# ============================================================

def athlete_history():

    st.title(
        "Digital Twin History"
    )

    st.caption(
        "Understand your past performance, recovery, "
        "training load, and Digital Twin state through "
        "interactive visuals."
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No Digital Twin history "
            "available yet."
        )

        return

    history_df = history_df.copy()

    # --------------------------------------------------------
    # PREPARE DATA
    # --------------------------------------------------------

    if "timestamp" in history_df.columns:

        history_df[
            "timestamp"
        ] = pd.to_datetime(
            history_df["timestamp"],
            errors="coerce",
        )

    history_df = (
        history_df.sort_values(
            "timestamp"
        )
    )

    latest = history_df.iloc[-1]

    previous = (
        history_df.iloc[-2]
        if len(history_df) > 1
        else None
    )

    def safe_value(
        row,
        key,
        default=0,
    ):

        try:

            value = row.get(
                key,
                default,
            )

            if pd.isna(value):

                return default

            return value

        except Exception:

            return default

    def safe_delta(
        current,
        previous_value,
    ):

        if previous_value is None:

            return None

        try:

            return round(
                float(current)
                - float(previous_value),
                1,
            )

        except Exception:

            return None

    def format_metric(
        value,
    ):

        try:

            return (
                f"{float(value):.1f}"
            )

        except (
            TypeError,
            ValueError,
        ):

            return "N/A"

    # --------------------------------------------------------
    # LATEST SNAPSHOT
    # --------------------------------------------------------

    st.markdown(
        "## Latest Snapshot"
    )

    fatigue = safe_value(
        latest,
        "fatigue_score",
    )

    readiness = safe_value(
        latest,
        "readiness_score",
    )

    twin_score = safe_value(
        latest,
        "twin_score",
    )

    health_index = safe_value(
        latest,
        "health_index",
    )

    injury_risk = safe_value(
        latest,
        "injury_risk",
        "Unknown",
    )

    athlete_state = safe_value(
        latest,
        "athlete_state",
        "Unknown",
    )

    recommendation = safe_value(
        latest,
        "recommendation",
        "No recommendation available.",
    )

    prev_fatigue = (
        safe_value(
            previous,
            "fatigue_score",
        )
        if previous is not None
        else None
    )

    prev_readiness = (
        safe_value(
            previous,
            "readiness_score",
        )
        if previous is not None
        else None
    )

    prev_twin = (
        safe_value(
            previous,
            "twin_score",
        )
        if previous is not None
        else None
    )

    prev_health = (
        safe_value(
            previous,
            "health_index",
        )
        if previous is not None
        else None
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Fatigue",
        format_metric(fatigue),
        delta=safe_delta(
            fatigue,
            prev_fatigue,
        ),
    )

    c2.metric(
        "Readiness",
        format_metric(readiness),
        delta=safe_delta(
            readiness,
            prev_readiness,
        ),
    )

    c3.metric(
        "Twin Score",
        format_metric(twin_score),
        delta=safe_delta(
            twin_score,
            prev_twin,
        ),
    )

    c4.metric(
        "Health Index",
        format_metric(health_index),
        delta=safe_delta(
            health_index,
            prev_health,
        ),
    )

    c5, c6 = st.columns(2)

    c5.markdown(
        f"""
        <div style="
            background: rgba(0, 180, 255, 0.12);
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h4 style="margin-bottom:6px;">
                Injury Risk
            </h4>
            <h2 style="margin-top:0;">
                {injury_risk}
            </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c6.markdown(
        f"""
        <div style="
            background: rgba(0, 255, 180, 0.10);
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h4 style="margin-bottom:6px;">
                Athlete State
            </h4>
            <h2 style="margin-top:0;">
                {athlete_state}
            </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "### Latest Recommendation"
    )

    st.info(
        recommendation
    )

    # --------------------------------------------------------
    # VISUAL PERFORMANCE OVERVIEW
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "## Visual Performance Overview"
    )

    st.caption(
        "These visuals help you quickly understand "
        "how your body and Digital Twin state have "
        "changed over time."
    )

    # --------------------------------------------------------
    # SIDE-BY-SIDE VISUALS
    # --------------------------------------------------------

    left_chart, right_chart = (
        st.columns(
            [1.6, 1],
            gap="large",
        )
    )

    # ========================================================
    # DIGITAL TWIN TRENDS
    # ========================================================

    with left_chart:

        st.markdown(
            "### Digital Twin Trends Over Time"
        )

        st.caption(
            "See how fatigue, readiness, Twin Score, "
            "and Health Index have changed across your "
            "recorded Digital Twin states."
        )

        trend_columns = [
            "fatigue_score",
            "readiness_score",
            "twin_score",
            "health_index",
        ]

        available_trend_columns = [
            column
            for column in trend_columns
            if column
            in history_df.columns
        ]

        if (
            available_trend_columns
            and "timestamp"
            in history_df.columns
        ):

            trend_df = history_df[
                [
                    "timestamp",
                    *available_trend_columns,
                ]
            ].copy()

            trend_df = trend_df.rename(
                columns={
                    "fatigue_score":
                        "Fatigue",
                    "readiness_score":
                        "Readiness",
                    "twin_score":
                        "Twin Score",
                    "health_index":
                        "Health Index",
                }
            )

            melted = trend_df.melt(
                id_vars="timestamp",
                var_name="Metric",
                value_name="Score",
            )

            fig_trend = px.line(
                melted,
                x="timestamp",
                y="Score",
                color="Metric",
                markers=True,
            )

            fig_trend.update_traces(
                line=dict(
                    width=3,
                ),
                marker=dict(
                    size=8,
                ),
            )

            fig_trend.update_layout(
                height=430,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                xaxis_title=(
                    "Date / Time"
                ),
                yaxis_title="Score",
                legend_title="Metric",
                hovermode="x unified",
            )

            fig_trend.update_yaxes(
                range=[
                    0,
                    100,
                ]
            )

            st.plotly_chart(
                fig_trend,
                use_container_width=True,
                key=(
                    "history_trend_chart"
                ),
            )

        else:

            st.info(
                "Not enough historical information "
                "is available for the trend chart yet."
            )

    # ========================================================
    # LATEST ATHLETE CONDITION PROFILE
    # ========================================================

    with right_chart:

        st.markdown(
            "### Latest Athlete Condition Profile"
        )

        st.caption(
            "A quick visual summary of your "
            "latest Digital Twin condition."
        )

        latest_profile = pd.DataFrame(
            {
                "Metric": [
                    "Fatigue",
                    "Readiness",
                    "Twin Score",
                    "Health Index",
                    "Training Load",
                    "Recovery",
                    "Sleep",
                ],

                "Score": [
                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "fatigue_score",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "readiness_score",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "twin_score",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "health_index",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "training_load",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            (
                                float(
                                    safe_value(
                                        latest,
                                        "recovery_time",
                                        0,
                                    )
                                )
                                / 12
                                * 100
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            (
                                float(
                                    safe_value(
                                        latest,
                                        "sleep_hours",
                                        0,
                                    )
                                )
                                / 10
                                * 100
                            ),
                            0,
                        ),
                        100,
                    ),
                ],

                "Actual value": [
                    (
                        f"{float(safe_value(latest, 'fatigue_score', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'readiness_score', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'twin_score', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'health_index', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'training_load', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'recovery_time', 0)):.1f} h"
                    ),
                    (
                        f"{float(safe_value(latest, 'sleep_hours', 0)):.1f} h"
                    ),
                ],
            }
        )

        fig_profile = px.pie(
            latest_profile,
            names="Metric",
            values="Score",
            hole=0.52,
            custom_data=[
                "Actual value",
            ],
        )

        fig_profile.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=(
                "<b>%{label}</b>"
                "<br>Actual value: "
                "%{customdata[0]}"
                "<br>Profile share: "
                "%{percent}"
                "<extra></extra>"
            ),
        )

        fig_profile.update_layout(
            height=430,
            margin=dict(
                l=10,
                r=10,
                t=20,
                b=20,
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.20,
                xanchor="center",
                x=0.5,
            ),
            annotations=[
                dict(
                    text=(
                        "Latest<br>"
                        "Condition"
                    ),
                    x=0.5,
                    y=0.5,
                    font_size=18,
                    showarrow=False,
                )
            ],
        )

        st.plotly_chart(
            fig_profile,
            use_container_width=True,
            key=(
                "latest_condition_profile"
            ),
        )

    # --------------------------------------------------------
    # SECOND VISUAL ROW
    # --------------------------------------------------------

    risk_col, state_col = (
        st.columns(
            [1.6, 1],
            gap="large",
        )
    )

    # ========================================================
    # INJURY RISK TIMELINE
    # ========================================================

    with risk_col:

        st.markdown(
            "### Injury Risk Timeline"
        )

        st.caption(
            "See how your injury-risk level relates "
            "to fatigue across your recorded "
            "Digital Twin states."
        )

        if (
            "injury_risk"
            in history_df.columns
            and "timestamp"
            in history_df.columns
            and "fatigue_score"
            in history_df.columns
        ):

            risk_timeline = (
                history_df.copy()
            )

            hover_columns = [
                column
                for column in [
                    "readiness_score",
                    "athlete_state",
                    "recommendation",
                ]
                if column
                in risk_timeline.columns
            ]

            fig_risk = px.bar(
                risk_timeline,
                x="timestamp",
                y="fatigue_score",
                color="injury_risk",
                hover_data=(
                    hover_columns
                ),
                labels={
                    "timestamp":
                        "Date / Time",
                    "fatigue_score":
                        "Fatigue Score",
                    "injury_risk":
                        "Injury Risk",
                },
            )

            fig_risk.update_traces(
                texttemplate="%{y:.1f}",
                textposition="outside",
                marker=dict(
                    opacity=0.85,
                    line=dict(
                        width=1,
                    ),
                ),
                hovertemplate=(
                    "<b>%{x}</b>"
                    "<br>Fatigue Score: "
                    "%{y:.1f}"
                    "<br>Injury Risk: "
                    "%{fullData.name}"
                    "<extra></extra>"
                ),
            )

            fig_risk.update_layout(
                height=420,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                xaxis_title=(
                    "Date / Time"
                ),
                yaxis_title=(
                    "Fatigue Score"
                ),
                legend_title=(
                    "Injury Risk"
                ),
                bargap=0.35,
            )

            fig_risk.update_yaxes(
                range=[
                    0,
                    100,
                ]
            )

            st.plotly_chart(
                fig_risk,
                use_container_width=True,
                key=(
                    "history_injury_risk_chart"
                ),
            )

        else:

            st.info(
                "Not enough information is available "
                "for the injury-risk timeline yet."
            )

    # ========================================================
    # ATHLETE STATE DISTRIBUTION
    # ========================================================

    with state_col:

        st.markdown(
            "### Athlete State History"
        )

        st.caption(
            "See how often your Digital Twin has "
            "classified you in each athlete state."
        )

        if (
            "athlete_state"
            in history_df.columns
        ):

            state_counts = (
                history_df[
                    "athlete_state"
                ]
                .fillna("Unknown")
                .value_counts()
                .reset_index()
            )

            state_counts.columns = [
                "Athlete State",
                "Count",
            ]

            fig_state = px.pie(
                state_counts,
                names="Athlete State",
                values="Count",
                hole=0.55,
            )

            fig_state.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate=(
                    "<b>%{label}</b>"
                    "<br>Recorded states: "
                    "%{value}"
                    "<br>Share: "
                    "%{percent}"
                    "<extra></extra>"
                ),
            )

            fig_state.update_layout(
                height=420,
                margin=dict(
                    l=10,
                    r=10,
                    t=20,
                    b=20,
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.18,
                    xanchor="center",
                    x=0.5,
                ),
                annotations=[
                    dict(
                        text=(
                            "State<br>"
                            "History"
                        ),
                        x=0.5,
                        y=0.5,
                        font_size=17,
                        showarrow=False,
                    )
                ],
            )

            st.plotly_chart(
                fig_state,
                use_container_width=True,
                key=(
                    "history_state_distribution"
                ),
            )

    # --------------------------------------------------------
    # SIMPLE INTERPRETATION
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "## Simple Interpretation"
    )

    insight_cols = st.columns(3)

    insight_cols[0].success(
        f"**Fatigue:** "
        f"{format_metric(fatigue)}\n\n"
        "This shows how physically tired "
        "your body currently is."
    )

    insight_cols[1].info(
        f"**Readiness:** "
        f"{format_metric(readiness)}\n\n"
        "This reflects how prepared your body "
        "is for training or performance."
    )

    insight_cols[2].warning(
        f"**Injury Risk:** "
        f"{injury_risk}\n\n"
        "This indicates your current potential "
        "risk level based on your latest state."
    )

    # --------------------------------------------------------
    # DETAILED HISTORY TABLE
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "## Detailed History Records"
    )

    st.caption(
        "Scroll through the complete history "
        "in simplified athlete-friendly wording."
    )

    display_df = (
        history_df.copy()
    )

    rename_map = {
        "timestamp":
            "Date / Time",
        "heart_rate":
            "Heart Rate",
        "sleep_hours":
            "Sleep Hours",
        "training_load":
            "Training Load",
        "recovery_time":
            "Recovery Time",
        "fatigue_score":
            "Fatigue",
        "readiness_score":
            "Readiness",
        "injury_risk":
            "Injury Risk",
        "athlete_state":
            "Athlete State",
        "twin_score":
            "Twin Score",
        "health_index":
            "Health Index",
        "recommendation":
            "Recommendation",
    }

    preferred_columns = [
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

    available_columns = [
        column
        for column
        in preferred_columns
        if column
        in display_df.columns
    ]

    display_df = (
        display_df[
            available_columns
        ]
        .rename(
            columns=rename_map
        )
    )

    if (
        "Date / Time"
        in display_df.columns
    ):

        display_df[
            "Date / Time"
        ] = (
            pd.to_datetime(
                display_df[
                    "Date / Time"
                ],
                errors="coerce",
            )
            .dt.strftime(
                "%d %b %Y, %H:%M"
            )
        )

    if (
        "Heart Rate"
        in display_df.columns
    ):

        display_df[
            "Heart Rate"
        ] = display_df[
            "Heart Rate"
        ].apply(
            lambda value: (
                f"{value:.0f} bpm"
                if pd.notna(value)
                else "-"
            )
        )

    if (
        "Sleep Hours"
        in display_df.columns
    ):

        display_df[
            "Sleep Hours"
        ] = display_df[
            "Sleep Hours"
        ].apply(
            lambda value: (
                f"{value:.1f} h"
                if pd.notna(value)
                else "-"
            )
        )

    if (
        "Recovery Time"
        in display_df.columns
    ):

        display_df[
            "Recovery Time"
        ] = display_df[
            "Recovery Time"
        ].apply(
            lambda value: (
                f"{value:.1f} h"
                if pd.notna(value)
                else "-"
            )
        )

    st.dataframe(
        display_df.iloc[::-1],
        use_container_width=True,
        hide_index=True,
    )

    csv = (
        display_df
        .iloc[::-1]
        .to_csv(
            index=False
        )
        .encode("utf-8")
    )

    st.download_button(
        "Download History CSV",
        csv,
        "digital_twin_history.csv",
        "text/csv",
    )


# ============================================================
# ATHLETE TIMELINE
# ============================================================

def athlete_timeline():

    st.title(
        "Digital Twin Timeline"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No timeline available yet."
        )

        return

    show_athlete_timeline(
        history_df
    )


# ============================================================
# ATHLETE VISUALISATIONS
# ============================================================

def athlete_visualisations():

    st.title(
        "Visualisations / Graphs"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "No visualisations available yet."
        )

        return

    chart_cols = [
        "heart_rate",
        "training_load",
        "fatigue_score",
        "readiness_score",
        "twin_score",
        "health_index",
    ]

    available_cols = [
        column
        for column in chart_cols
        if column
        in history_df.columns
    ]

    if available_cols:

        chart_df = (
            history_df
            .sort_values(
                "timestamp"
            )
        )

        st.subheader(
            "Digital Twin Historical Trends"
        )

        st.line_chart(
            chart_df[
                available_cols
            ]
        )

    else:

        st.info(
            "No chart-ready metrics available."
        )

    # --------------------------------------------------------
    # FORECAST PREVIEW
    # --------------------------------------------------------

    st.subheader(
        "7-Day Digital Twin Forecast"
    )

    fatigue_forecast = (
        forecast_metric(
            history_df,
            "fatigue_score",
            days=7,
        )
    )

    readiness_forecast = (
        forecast_metric(
            history_df,
            "readiness_score",
            days=7,
        )
    )

    if not fatigue_forecast.empty:

        st.write(
            "Fatigue Forecast"
        )

        st.line_chart(
            fatigue_forecast
            .set_index(
                "forecast_date"
            )[
                "forecast_value"
            ]
        )

    if not readiness_forecast.empty:

        st.write(
            "Readiness Forecast"
        )

        st.line_chart(
            readiness_forecast
            .set_index(
                "forecast_date"
            )[
                "forecast_value"
            ]
        )

    st.info(
        generate_forecast_summary(
            fatigue_forecast,
            readiness_forecast,
        )
    )


# ============================================================
# WHAT-IF SIMULATION
# ============================================================

def athlete_simulation():

    st.title(
        "What-if Simulation"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "Save at least one Digital Twin state "
            "before running simulations."
        )

        return

    latest_state = (
        history_df
        .sort_values(
            "timestamp"
        )
        .iloc[-1]
        .to_dict()
    )

    sleep_change = st.slider(
        "Change Sleep Hours",
        -4.0,
        4.0,
        0.0,
        0.5,
    )

    training_change = st.slider(
        "Change Training Load",
        -50.0,
        50.0,
        0.0,
        5.0,
    )

    recovery_change = st.slider(
        "Change Recovery Time",
        -5.0,
        5.0,
        0.0,
        0.5,
    )

    simulated = (
        simulate_scenario(
            latest_state,
            sleep_change=(
                sleep_change
            ),
            training_load_change=(
                training_change
            ),
            recovery_change=(
                recovery_change
            ),
        )
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Simulated Fatigue",
        simulated[
            "simulated_fatigue_score"
        ],
    )

    c2.metric(
        "Simulated Readiness",
        (
            f"{simulated['simulated_readiness_score']}%"
        ),
    )

    c3.metric(
        "Simulated Injury Risk",
        simulated[
            "simulated_injury_risk"
        ],
    )