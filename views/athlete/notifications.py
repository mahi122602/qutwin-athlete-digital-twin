import streamlit as st
from datetime import datetime, timedelta
from database.connection_request_repository import get_notifications, get_unread_notification_count, get_incoming_connection_requests, respond_to_connection_request, mark_notification_read, mark_all_notifications_read
from views.athlete.account_helpers import _notification_destination, _notification_icon

def athlete_notifications_page():
    """
    Dedicated Athlete Notifications page.

    Shows:
    - pending coach connection requests
    - Accept / Reject controls
    - notifications from the last 14 days
    - unread/read state
    """

    athlete_id = str(
        st.session_state.user_id
    )

    st.title("Notifications")

    st.caption(
        "Connection requests, request updates, "
        "risk alerts, coach recommendations and "
        "other important updates from the last 14 days."
    )

    # ========================================================
    # LOAD NOTIFICATIONS
    # ========================================================

    try:

        notifications = get_notifications(
            "Athlete",
            athlete_id,
            limit=100,
        )

        incoming_requests = (
            get_incoming_connection_requests(
                "Athlete",
                athlete_id,
            )
        )

        unread_count = (
            get_unread_notification_count(
                "Athlete",
                athlete_id,
            )
        )

    except Exception as exc:

        st.error(
            f"Notifications could not be loaded: {exc}"
        )

        return

    # ========================================================
    # PAGE SUMMARY
    # ========================================================

    summary_col_1, summary_col_2 = (
        st.columns(2)
    )

    with summary_col_1:

        st.metric(
            "Unread Notifications",
            unread_count,
        )

    with summary_col_2:

        st.metric(
            "Pending Coach Requests",
            len(incoming_requests),
        )

    if unread_count > 0:

        if st.button(
            "Mark all notifications as read",
            key="notification_page_mark_all_read",
        ):

            try:

                mark_all_notifications_read(
                    "Athlete",
                    athlete_id,
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    f"Notifications could not be updated: {exc}"
                )

    st.divider()

    # ========================================================
    # CONNECTION REQUESTS
    # ========================================================

    st.subheader(
        "Coach Connection Requests"
    )

    if not incoming_requests:

        st.info(
            "You do not currently have any "
            "pending coach connection requests."
        )

    else:

        for request in incoming_requests:

            request_id = (
                request["request_id"]
            )

            coach_id = (
                request["sender_id"]
            )

            coach_name = (
                request.get("sender_name")
                or "Coach"
            )

            message = (
                request.get("message")
                or "No message provided."
            )

            created_at = (
                request.get("created_at")
            )

            with st.container(
                border=True
            ):

                title_col, badge_col = (
                    st.columns(
                        [4, 1]
                    )
                )

                with title_col:

                    st.markdown(
                        f"### 🤝 {coach_name}"
                    )

                    st.caption(
                        f"Coach ID: {coach_id}"
                    )

                with badge_col:

                    st.warning(
                        "Pending"
                    )

                st.write(message)

                if created_at:

                    try:

                        st.caption(
                            "Received: "
                            f"{created_at:%d %b %Y, %H:%M}"
                        )

                    except Exception:

                        st.caption(
                            f"Received: {created_at}"
                        )

                accept_col, reject_col = (
                    st.columns(2)
                )

                with accept_col:

                    if st.button(
                        "Accept",
                        key=(
                            f"notification_accept_"
                            f"{request_id}"
                        ),
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

                            # Mark original request
                            # notification as read.
                            for notification in notifications:

                                if (
                                    notification.get(
                                        "request_id"
                                    )
                                    == request_id
                                    and
                                    notification.get(
                                        "notification_type"
                                    )
                                    == "Connection Request"
                                ):

                                    mark_notification_read(
                                        notification[
                                            "notification_id"
                                        ],
                                        "Athlete",
                                        athlete_id,
                                    )

                            st.success(
                                f"You are now connected "
                                f"with Coach {coach_id}."
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Request could not be accepted: {exc}"
                            )

                with reject_col:

                    if st.button(
                        "Reject",
                        key=(
                            f"notification_reject_"
                            f"{request_id}"
                        ),
                        use_container_width=True,
                    ):

                        try:

                            respond_to_connection_request(
                                request_id=request_id,
                                responder_role="Athlete",
                                responder_id=athlete_id,
                                decision="Rejected",
                            )

                            for notification in notifications:

                                if (
                                    notification.get(
                                        "request_id"
                                    )
                                    == request_id
                                    and
                                    notification.get(
                                        "notification_type"
                                    )
                                    == "Connection Request"
                                ):

                                    mark_notification_read(
                                        notification[
                                            "notification_id"
                                        ],
                                        "Athlete",
                                        athlete_id,
                                    )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Request could not be rejected: {exc}"
                            )

    # ========================================================
    # LAST 14 DAYS
    # ========================================================

    st.divider()

    st.subheader(
        "Last 14 Days"
    )

    cutoff = (
        datetime.now()
        - timedelta(days=14)
    )

    recent_notifications = []

    for notification in notifications:

        created_at = (
            notification.get(
                "created_at"
            )
        )

        if created_at is None:

            recent_notifications.append(
                notification
            )

            continue

        try:

            if created_at >= cutoff:

                recent_notifications.append(
                    notification
                )

        except TypeError:

            recent_notifications.append(
                notification
            )

    if not recent_notifications:

        st.info(
            "No notifications were received "
            "during the last 14 days."
        )

        return

    # ========================================================
    # NOTIFICATION CARDS
    # ========================================================

    for notification in recent_notifications:

        notification_id = (
            notification[
                "notification_id"
            ]
        )

        notification_type = (
            notification.get(
                "notification_type",
                "Notification",
            )
        )

        notification_message = (
            notification.get(
                "message"
            )
            or "Notification update."
        )

        is_read = bool(
            notification.get(
                "is_read",
                False,
            )
        )

        created_at = (
            notification.get(
                "created_at"
            )
        )

        icon = _notification_icon(
            notification_type
        )

        destination = (
            _notification_destination(
                notification_type
            )
        )

        with st.container(
            border=True
        ):

            title_col, status_col = (
                st.columns(
                    [4, 1]
                )
            )

            with title_col:

                st.markdown(
                    f"### {icon} "
                    f"{notification_type}"
                )

            with status_col:

                if is_read:

                    st.caption(
                        "Read"
                    )

                else:

                    st.info(
                        "New"
                    )

            st.write(
                notification_message
            )

            if created_at:

                try:

                    st.caption(
                        f"{created_at:%d %b %Y, %H:%M}"
                    )

                except Exception:

                    st.caption(
                        str(created_at)
                    )

            action_col_1, action_col_2 = (
                st.columns(
                    [1, 1]
                )
            )

            # -----------------------------------------------
            # MARK READ
            # -----------------------------------------------

            with action_col_1:

                if not is_read:

                    if st.button(
                        "Mark as read",
                        key=(
                            f"mark_notification_"
                            f"{notification_id}"
                        ),
                        use_container_width=True,
                    ):

                        try:

                            mark_notification_read(
                                notification_id,
                                "Athlete",
                                athlete_id,
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Notification could not "
                                f"be updated: {exc}"
                            )

            # -----------------------------------------------
            # OPEN RELATED PAGE
            # -----------------------------------------------

            with action_col_2:

                if destination:

                    if st.button(
                        "Open related page →",
                        key=(
                            f"open_notification_"
                            f"{notification_id}"
                        ),
                        use_container_width=True,
                    ):

                        if not is_read:

                            try:

                                mark_notification_read(
                                    notification_id,
                                    "Athlete",
                                    athlete_id,
                                )

                            except Exception:

                                pass

                        st.session_state.current_page = (
                            destination
                        )

                        st.rerun()
