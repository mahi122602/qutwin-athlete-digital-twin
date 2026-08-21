import streamlit as st
import pandas as pd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
from database.connection_request_repository import (
    get_incoming_connection_requests,
    get_notifications,
    get_unread_notification_count,
    mark_all_notifications_read,
    respond_to_connection_request,
    send_connection_request,
    get_sent_connection_requests,
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

def _render_athlete_notification_bell():
    athlete_id = str(st.session_state.user_id)

    try:
        unread_count = get_unread_notification_count(
            "Athlete",
            athlete_id,
        )

        incoming_requests = get_incoming_connection_requests(
            "Athlete",
            athlete_id,
        )

        notifications = get_notifications(
            "Athlete",
            athlete_id,
            limit=20,
        )

    except Exception as exc:
        st.error(
            f"Notifications could not be loaded: {exc}"
        )
        return

    bell_label = (
        f"🔔 {unread_count}"
        if unread_count > 0
        else "🔔"
    )

    with st.popover(
        bell_label,
        use_container_width=True,
    ):
        st.markdown("### Notifications")

        # =====================================================
        # INCOMING COACH REQUESTS
        # =====================================================
        st.markdown("#### Connection Requests")

        if incoming_requests:

            for request in incoming_requests:

                request_id = request["request_id"]
                coach_id = request["sender_id"]
                coach_name = request.get(
                    "sender_name"
                ) or "Coach"

                request_message = (
                    request.get("message")
                    or "No message provided."
                )

                created_at = request.get(
                    "created_at"
                )

                with st.container(border=True):

                    st.markdown(
                        f"**{coach_name}**"
                    )

                    st.caption(
                        f"Coach ID: {coach_id}"
                    )

                    st.write(
                        request_message
                    )

                    if created_at:
                        st.caption(
                            f"Sent: {created_at:%d %b %Y, %H:%M}"
                        )

                    accept_col, reject_col = st.columns(2)

                    with accept_col:
                        if st.button(
                            "Accept",
                            key=f"athlete_accept_request_{request_id}",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                respond_to_connection_request(
                                    request_id=request_id,
                                    responder_role="Athlete",
                                    responder_id=athlete_id,
                                    decision="Accepted",
                                )

                            except Exception as exc:
                                st.error(
                                    f"Request could not be accepted: {exc}"
                                )

                            else:
                                st.success(
                                    f"Coach {coach_id} is now connected."
                                )
                                st.rerun()

                    with reject_col:
                        if st.button(
                            "Reject",
                            key=f"athlete_reject_request_{request_id}",
                            use_container_width=True,
                        ):
                            try:
                                respond_to_connection_request(
                                    request_id=request_id,
                                    responder_role="Athlete",
                                    responder_id=athlete_id,
                                    decision="Rejected",
                                )

                            except Exception as exc:
                                st.error(
                                    f"Request could not be rejected: {exc}"
                                )

                            else:
                                st.info(
                                    "Connection request rejected."
                                )
                                st.rerun()

        else:
            st.caption(
                "No pending connection requests."
            )

        # =====================================================
        # STATUS UPDATES
        # =====================================================
        st.divider()
        st.markdown("#### Request Updates")

        status_notifications = [
            notification
            for notification in notifications
            if notification.get("notification_type")
            in {
                "Request Accepted",
                "Request Rejected",
            }
        ]

        if status_notifications:

            for notification in status_notifications:

                is_read = notification.get(
                    "is_read",
                    False,
                )

                marker = "●" if not is_read else "○"

                st.markdown(
                    f"{marker} {notification['message']}"
                )

                created_at = notification.get(
                    "created_at"
                )

                if created_at:
                    st.caption(
                        f"{created_at:%d %b %Y, %H:%M}"
                    )

        else:
            st.caption(
                "No request updates yet."
            )

        # =====================================================
        # MARK READ
        # =====================================================
        if unread_count > 0:

            st.divider()

            if st.button(
                "Mark all as read",
                key="athlete_mark_all_notifications_read",
                use_container_width=True,
            ):
                try:
                    mark_all_notifications_read(
                        "Athlete",
                        athlete_id,
                    )

                except Exception as exc:
                    st.error(
                        f"Notifications could not be updated: {exc}"
                    )

                else:
                    st.rerun()
def athlete_dashboard():

    title_col, bell_col = st.columns(
        [8, 1]
    )

    with title_col:
        st.title("Digital Twin Dashboard")

    with bell_col:
        _render_athlete_notification_bell()

    history_df = get_athlete_twin_history(
        st.session_state.user_id
    )

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
    st.info(
        latest.get(
            "recommendation",
            "No recommendation available.",
            )
    )

# ============================================================
# AI PREDICTION CARDS
# ============================================================
    
    if st.button("Upload New Athlete Data"):
        st.session_state.current_page = "Upload Garmin Data"
        st.rerun()


def _render_athlete_coach_request_panel():
    athlete_id = str(st.session_state.user_id)

    st.subheader("Connect with a Coach")
    st.caption(
        "Send a connection request using the coach's ID."
    )

    with st.form(
        "athlete_coach_connection_form",
        clear_on_submit=True,
    ):
        coach_id = st.text_input(
            "Coach ID",
            placeholder="Enter Coach ID",
        )

        message = st.text_area(
            "Message",
            placeholder="Add an optional message for the coach...",
            max_chars=1000,
        )

        send_request = st.form_submit_button(
            "Send Request",
            type="primary",
            use_container_width=True,
        )

    if send_request:
        coach_id = coach_id.strip()

        if not coach_id:
            st.warning("Please enter a Coach ID.")

        else:
            try:
                request_id = send_connection_request(
                    sender_role="Athlete",
                    sender_id=athlete_id,
                    recipient_id=coach_id,
                    message=message,
                )

            except ValueError as exc:
                st.warning(str(exc))

            except Exception as exc:
                st.error(
                    f"Connection request could not be sent: {exc}"
                )

            else:
                st.success(
                    f"Connection request sent to Coach {coach_id}."
                )
                st.caption(
                    f"Request ID: {request_id}"
                )

    # ========================================================
    # SENT REQUESTS
    # ========================================================
    try:
        sent_requests = get_sent_connection_requests(
            "Athlete",
            athlete_id,
        )

    except Exception as exc:
        st.error(
            f"Sent requests could not be loaded: {exc}"
        )
        return

    if sent_requests:
        with st.expander(
            f"Sent Coach Requests ({len(sent_requests)})"
        ):
            for request in sent_requests:

                coach_name = (
                    request.get("recipient_name")
                    or "Coach"
                )

                coach_id = request.get(
                    "recipient_id"
                )

                status = request.get(
                    "status",
                    "Pending",
                )

                message = (
                    request.get("message")
                    or "No message provided."
                )

                created_at = request.get(
                    "created_at"
                )

                if status == "Accepted":
                    status_icon = "✅"
                elif status == "Rejected":
                    status_icon = "❌"
                else:
                    status_icon = "🕒"

                with st.container(border=True):

                    name_col, status_col = st.columns(
                        [3, 1]
                    )

                    with name_col:
                        st.markdown(
                            f"**{coach_name}**"
                        )
                        st.caption(
                            f"Coach ID: {coach_id}"
                        )

                    with status_col:
                        st.markdown(
                            f"{status_icon} **{status}**"
                        )

                    st.write(message)

                    if created_at:
                        st.caption(
                            f"Sent: {created_at:%d %b %Y, %H:%M}"
                        )

def upload_garmin_data():
    st.title("Upload Athlete Data")
    st.caption(
        "Upload exported athlete data from Garmin, Samsung Health, Strava, "
        "Fitbit, Apple Health, Polar, WHOOP, COROS, or another supported source."
    )

    _render_athlete_coach_request_panel()

    st.divider()

    st.subheader("Upload Health & Activity Data")

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
    st.caption(
        "Understand your past performance, recovery, training load, and Digital Twin state through interactive visuals."
    )

    history_df = get_athlete_twin_history(st.session_state.user_id)

    if history_df is None or history_df.empty:
        st.info("No Digital Twin history available yet.")
        return

    history_df = history_df.copy()

    # ---------------------------------------------------------
    # Prepare data
    # ---------------------------------------------------------
    if "timestamp" in history_df.columns:
        history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], errors="coerce")

    history_df = history_df.sort_values("timestamp")

    latest = history_df.iloc[-1]
    previous = history_df.iloc[-2] if len(history_df) > 1 else None

    def safe_value(row, key, default=0):
        try:
            value = row.get(key, default)
            if pd.isna(value):
                return default
            return value
        except Exception:
            return default

    def safe_delta(current, previous_value):
        if previous_value is None:
            return None
        try:
            return round(float(current) - float(previous_value), 1)
        except Exception:
            return None

    # ---------------------------------------------------------
    # Latest Snapshot Section
    # ---------------------------------------------------------
    st.markdown("## Latest Snapshot")

    fatigue = safe_value(latest, "fatigue_score")
    readiness = safe_value(latest, "readiness_score")
    twin_score = safe_value(latest, "twin_score")
    health_index = safe_value(latest, "health_index")
    injury_risk = safe_value(latest, "injury_risk", "Unknown")
    athlete_state = safe_value(latest, "athlete_state", "Unknown")
    recommendation = safe_value(latest, "recommendation", "No recommendation available.")

    prev_fatigue = safe_value(previous, "fatigue_score") if previous is not None else None
    prev_readiness = safe_value(previous, "readiness_score") if previous is not None else None
    prev_twin = safe_value(previous, "twin_score") if previous is not None else None
    prev_health = safe_value(previous, "health_index") if previous is not None else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fatigue", f"{fatigue:.1f}", delta=safe_delta(fatigue, prev_fatigue))
    c2.metric("Readiness", f"{readiness:.1f}", delta=safe_delta(readiness, prev_readiness))
    c3.metric("Twin Score", f"{twin_score:.1f}", delta=safe_delta(twin_score, prev_twin))
    c4.metric("Health Index", f"{health_index:.1f}", delta=safe_delta(health_index, prev_health))

    c5, c6 = st.columns(2)
    c5.markdown(
        f"""
        <div style="
            background: rgba(0, 180, 255, 0.12);
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h4 style="margin-bottom:6px;">Injury Risk</h4>
            <h2 style="margin-top:0;">{injury_risk}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )
    c6.markdown(
        f"""
        <div style="
            background: rgba(0, 255, 180, 0.10);
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h4 style="margin-bottom:6px;">Athlete State</h4>
            <h2 style="margin-top:0;">{athlete_state}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### Latest Recommendation")
    st.info(recommendation)

    # ---------------------------------------------------------
    # Visual Section
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("## Visual Performance Overview")
    st.caption("These visuals help you quickly understand how your body and Digital Twin state have changed over time.")

    # ---------------------------------------------
    # 1. Line chart for trends
    # ---------------------------------------------
        # ---------------------------------------------------------
    # SIDE-BY-SIDE VISUALS
    # ---------------------------------------------------------
    left_chart, right_chart = st.columns(
        [1.6, 1],
        gap="large",
    )

    # =========================================================
    # LEFT: DIGITAL TWIN TRENDS OVER TIME
    # =========================================================
    with left_chart:

        st.markdown("### Digital Twin Trends Over Time")
        st.caption(
            "See how fatigue, readiness, Twin Score, and Health Index "
            "have changed across your recorded Digital Twin states."
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
            if column in history_df.columns
        ]

        if (
            available_trend_columns
            and "timestamp" in history_df.columns
        ):
            trend_df = history_df[
                ["timestamp", *available_trend_columns]
            ].copy()

            trend_df = trend_df.rename(
                columns={
                    "fatigue_score": "Fatigue",
                    "readiness_score": "Readiness",
                    "twin_score": "Twin Score",
                    "health_index": "Health Index",
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
                line=dict(width=3),
                marker=dict(size=8),
            )

            fig_trend.update_layout(
                height=430,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                xaxis_title="Date / Time",
                yaxis_title="Score",
                legend_title="Metric",
                hovermode="x unified",
            )

            fig_trend.update_yaxes(
                range=[0, 100]
            )

            st.plotly_chart(
                fig_trend,
                use_container_width=True,
                key="history_trend_chart",
            )

        else:
            st.info(
                "Not enough historical information is available "
                "for the trend chart yet."
            )

    # =========================================================
    # RIGHT: LATEST ATHLETE CONDITION PROFILE
    # =========================================================
    with right_chart:

        st.markdown("### Latest Athlete Condition Profile")
        st.caption(
            "A quick visual summary of your latest Digital Twin condition."
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

                # Everything is displayed on a comparable 0–100 scale.
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
                            float(
                                safe_value(
                                    latest,
                                    "recovery_time",
                                    0,
                                )
                            )
                            / 12
                            * 100,
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "sleep_hours",
                                    0,
                                )
                            )
                            / 10
                            * 100,
                            0,
                        ),
                        100,
                    ),
                ],

                "Actual value": [
                    f"{safe_value(latest, 'fatigue_score', 0):.1f}",
                    f"{safe_value(latest, 'readiness_score', 0):.1f}",
                    f"{safe_value(latest, 'twin_score', 0):.1f}",
                    f"{safe_value(latest, 'health_index', 0):.1f}",
                    f"{safe_value(latest, 'training_load', 0):.1f}",
                    f"{safe_value(latest, 'recovery_time', 0):.1f} h",
                    f"{safe_value(latest, 'sleep_hours', 0):.1f} h",
                ],
            }
        )

        fig_profile = px.pie(
            latest_profile,
            names="Metric",
            values="Score",
            hole=0.52,
            custom_data=[
                "Actual value"
            ],
        )

        fig_profile.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=(
                "<b>%{label}</b>"
                "<br>Actual value: %{customdata[0]}"
                "<br>Profile share: %{percent}"
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
            key="latest_condition_profile",
        )

    # ---------------------------------------------------------
    # SECOND VISUAL ROW
    # ---------------------------------------------------------
    risk_col, state_col = st.columns(
        [1.6, 1],
        gap="large",
    )

    # =========================================================
    # LEFT: INJURY RISK TIMELINE
    # =========================================================
    with risk_col:

        st.markdown("### Injury Risk Timeline")
        st.caption(
            "See how your injury-risk level relates to fatigue "
            "across your recorded Digital Twin states."
        )

        if (
            "injury_risk" in history_df.columns
            and "timestamp" in history_df.columns
            and "fatigue_score" in history_df.columns
        ):
            risk_timeline = history_df.copy()

            hover_columns = [
                column
                for column in [
                    "readiness_score",
                    "athlete_state",
                    "recommendation",
                ]
                if column in risk_timeline.columns
            ]

            fig_risk = px.bar(
                risk_timeline,
                x="timestamp",
                y="fatigue_score",
                color="injury_risk",
                hover_data=hover_columns,
                labels={
                    "timestamp": "Date / Time",
                    "fatigue_score": "Fatigue Score",
                    "injury_risk": "Injury Risk",
                    },
            )
            fig_risk.update_traces(
                texttemplate="%{y:.1f}",
                textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b>"
                    "<br>Fatigue Score: %{y:.1f}"
                    "<br>Injury Risk: %{fullData.name}"
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
                xaxis_title="Date / Time",
                yaxis_title="Fatigue Score",
                legend_title="Injury Risk",
                bargap=0.35,
                )
            fig_risk.update_yaxes(
                range=[0, 100],
                )

            fig_risk.update_traces(
                marker=dict(
                    opacity=0.85,
                    line=dict(width=1),
                )
            )

            fig_risk.update_layout(
                height=420,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                xaxis_title="Date / Time",
                yaxis_title="Fatigue Score",
                legend_title="Injury Risk",
            )

            fig_risk.update_yaxes(
                range=[0, 100]
            )

            st.plotly_chart(
                fig_risk,
                use_container_width=True,
                key="history_injury_risk_chart",
            )

        else:
            st.info(
                "Not enough information is available "
                "for the injury-risk timeline yet."
            )

    # =========================================================
    # RIGHT: ATHLETE STATE DISTRIBUTION
    # =========================================================
    with state_col:

        st.markdown("### Athlete State History")
        st.caption(
            "See how often your Digital Twin has classified "
            "you in each athlete state."
        )

        if "athlete_state" in history_df.columns:

            state_counts = (
                history_df["athlete_state"]
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
                    "<br>Recorded states: %{value}"
                    "<br>Share: %{percent}"
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
                        text="State<br>History",
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
                key="history_state_distribution",
            )

    # ---------------------------------------------------------
    # Quick interpretation
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("## Simple Interpretation")

    insight_cols = st.columns(3)

    insight_cols[0].success(
        f"**Fatigue:** {fatigue:.1f}\n\n"
        f"This shows how physically tired your body currently is."
    )
    insight_cols[1].info(
        f"**Readiness:** {readiness:.1f}\n\n"
        f"This reflects how prepared your body is for training or performance."
    )
    insight_cols[2].warning(
        f"**Injury Risk:** {injury_risk}\n\n"
        f"This indicates your current potential risk level based on your latest state."
    )

    # ---------------------------------------------------------
    # Detailed Table Section
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("## Detailed History Records")
    st.caption("Scroll through the complete history in simplified athlete-friendly wording.")

    display_df = history_df.copy()

    rename_map = {
        "timestamp": "Date / Time",
        "heart_rate": "Heart Rate",
        "sleep_hours": "Sleep Hours",
        "training_load": "Training Load",
        "recovery_time": "Recovery Time",
        "fatigue_score": "Fatigue",
        "readiness_score": "Readiness",
        "injury_risk": "Injury Risk",
        "athlete_state": "Athlete State",
        "twin_score": "Twin Score",
        "health_index": "Health Index",
        "recommendation": "Recommendation",
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

    available_columns = [col for col in preferred_columns if col in display_df.columns]
    display_df = display_df[available_columns].rename(columns=rename_map)

    if "Date / Time" in display_df.columns:
        display_df["Date / Time"] = pd.to_datetime(
            display_df["Date / Time"],
            errors="coerce"
        ).dt.strftime("%d %b %Y, %H:%M")

    if "Heart Rate" in display_df.columns:
        display_df["Heart Rate"] = display_df["Heart Rate"].apply(
            lambda x: f"{x:.0f} bpm" if pd.notna(x) else "-"
        )

    if "Sleep Hours" in display_df.columns:
        display_df["Sleep Hours"] = display_df["Sleep Hours"].apply(
            lambda x: f"{x:.1f} h" if pd.notna(x) else "-"
        )

    if "Recovery Time" in display_df.columns:
        display_df["Recovery Time"] = display_df["Recovery Time"].apply(
            lambda x: f"{x:.1f} h" if pd.notna(x) else "-"
        )

    st.dataframe(display_df.iloc[::-1], use_container_width=True, hide_index=True)

    csv = display_df.iloc[::-1].to_csv(index=False).encode("utf-8")
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