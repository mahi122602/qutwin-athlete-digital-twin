import streamlit as st

from database.connection_request_repository import (
    send_connection_request,
    get_incoming_connection_requests,
    get_sent_connection_requests,
    respond_to_connection_request,
    get_notifications,
    mark_notification_read,
)


# ============================================================
# HELPERS
# ============================================================

def _mark_request_notification_read(
    role,
    user_id,
    request_id,
):
    """
    Mark the original Connection Request notification as read
    after the user accepts or rejects the request.
    """

    try:
        notifications = get_notifications(
            role,
            user_id,
            limit=100,
        )

        for notification in notifications:

            if (
                notification.get("request_id")
                == request_id
                and
                notification.get("notification_type")
                == "Connection Request"
                and
                not notification.get("is_read", False)
            ):

                mark_notification_read(
                    notification["notification_id"],
                    role,
                    user_id,
                )

    except Exception:
        # Request processing should still succeed even if
        # notification read-state update fails.
        pass


def _status_icon(status):
    if status == "Accepted":
        return "✅"

    if status == "Rejected":
        return "❌"

    return "🕒"


def _request_management_page(role):
    """
    Shared Athlete / Coach connection-request page.

    Athlete:
        sends requests to coaches
        receives coach requests

    Coach:
        sends requests to athletes
        receives athlete requests
    """

    user_id = str(
        st.session_state.user_id
    )

    role = str(role).title()

    if role == "Athlete":
        target_role = "Coach"
        target_label = "Coach ID"

    else:
        target_role = "Athlete"
        target_label = "Athlete ID"

    # ========================================================
    # PAGE HEADER
    # ========================================================

    st.title("Connection Requests")

    st.caption(
        f"Send, receive, accept and reject "
        f"{target_role.lower()} connection requests."
    )

    # ========================================================
    # SUMMARY COUNTS
    # ========================================================

    try:

        incoming_requests = (
            get_incoming_connection_requests(
                role,
                user_id,
            )
        )

        sent_requests = (
            get_sent_connection_requests(
                role,
                user_id,
            )
        )

    except Exception as exc:

        st.error(
            f"Connection requests could not be loaded: {exc}"
        )

        return

    pending_sent = sum(
        1
        for request in sent_requests
        if request.get("status") == "Pending"
    )

    accepted_sent = sum(
        1
        for request in sent_requests
        if request.get("status") == "Accepted"
    )

    rejected_sent = sum(
        1
        for request in sent_requests
        if request.get("status") == "Rejected"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Incoming",
        len(incoming_requests),
    )

    c2.metric(
        "Pending Sent",
        pending_sent,
    )

    c3.metric(
        "Accepted",
        accepted_sent,
    )

    c4.metric(
        "Rejected",
        rejected_sent,
    )

    st.divider()

    # ========================================================
    # SEND REQUEST
    # ========================================================

    st.subheader(
        f"Send Request to {target_role}"
    )

    st.caption(
        f"Enter the {target_label} and an optional message."
    )

    form_key = (
        f"{role.lower()}_connection_request_form"
    )

    with st.form(
        form_key,
        clear_on_submit=True,
    ):

        target_id = st.text_input(
            target_label,
            placeholder=f"Enter {target_label}",
        )

        message = st.text_area(
            "Message",
            placeholder=(
                f"Write an optional message "
                f"for the {target_role.lower()}..."
            ),
            max_chars=1000,
        )

        send_button = (
            st.form_submit_button(
                "Send Request",
                type="primary",
                use_container_width=True,
            )
        )

    if send_button:

        target_id = (
            target_id.strip()
        )

        if not target_id:

            st.warning(
                f"Please enter a {target_label}."
            )

        else:

            try:

                request_id = (
                    send_connection_request(
                        sender_role=role,
                        sender_id=user_id,
                        recipient_id=target_id,
                        message=message,
                    )
                )

            except ValueError as exc:

                st.warning(
                    str(exc)
                )

            except Exception as exc:

                st.error(
                    f"Request could not be sent: {exc}"
                )

            else:

                st.success(
                    f"Connection request sent "
                    f"to {target_role} {target_id}."
                )

                st.caption(
                    f"Request ID: {request_id}"
                )

                st.rerun()

    st.divider()

    # ========================================================
    # INCOMING REQUESTS
    # ========================================================

    st.subheader(
        "Incoming Requests"
    )

    if not incoming_requests:

        st.info(
            "You currently have no pending "
            "connection requests."
        )

    else:

        for request in incoming_requests:

            request_id = (
                request["request_id"]
            )

            sender_id = (
                request["sender_id"]
            )

            sender_name = (
                request.get("sender_name")
                or target_role
            )

            request_message = (
                request.get("message")
                or "No message provided."
            )

            created_at = (
                request.get("created_at")
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
                        f"### {sender_name}"
                    )

                    st.caption(
                        f"{target_role} ID: {sender_id}"
                    )

                with status_col:

                    st.warning(
                        "Pending"
                    )

                st.write(
                    request_message
                )

                if created_at:

                    try:

                        st.caption(
                            f"Received: "
                            f"{created_at:%d %b %Y, %H:%M}"
                        )

                    except Exception:

                        st.caption(
                            f"Received: {created_at}"
                        )

                accept_col, reject_col = (
                    st.columns(2)
                )

                # ============================================
                # ACCEPT
                # ============================================

                with accept_col:

                    if st.button(
                        "Accept",
                        key=(
                            f"{role.lower()}_accept_"
                            f"{request_id}"
                        ),
                        type="primary",
                        use_container_width=True,
                    ):

                        try:

                            result = (
                                respond_to_connection_request(
                                    request_id=request_id,
                                    responder_role=role,
                                    responder_id=user_id,
                                    decision="Accepted",
                                )
                            )

                            _mark_request_notification_read(
                                role,
                                user_id,
                                request_id,
                            )

                        except Exception as exc:

                            st.error(
                                f"Request could not "
                                f"be accepted: {exc}"
                            )

                        else:

                            st.success(
                                "Connection request accepted."
                            )

                            st.rerun()

                # ============================================
                # REJECT
                # ============================================

                with reject_col:

                    if st.button(
                        "Reject",
                        key=(
                            f"{role.lower()}_reject_"
                            f"{request_id}"
                        ),
                        use_container_width=True,
                    ):

                        try:

                            result = (
                                respond_to_connection_request(
                                    request_id=request_id,
                                    responder_role=role,
                                    responder_id=user_id,
                                    decision="Rejected",
                                )
                            )

                            _mark_request_notification_read(
                                role,
                                user_id,
                                request_id,
                            )

                        except Exception as exc:

                            st.error(
                                f"Request could not "
                                f"be rejected: {exc}"
                            )

                        else:

                            st.info(
                                "Connection request rejected."
                            )

                            st.rerun()

    st.divider()

    # ========================================================
    # SENT REQUESTS
    # ========================================================

    st.subheader(
        "Sent Requests"
    )

    if not sent_requests:

        st.info(
            "You have not sent any connection requests yet."
        )

    else:

        for request in sent_requests:

            recipient_id = (
                request.get("recipient_id")
            )

            recipient_name = (
                request.get("recipient_name")
                or target_role
            )

            status = (
                request.get("status")
                or "Pending"
            )

            request_message = (
                request.get("message")
                or "No message provided."
            )

            created_at = (
                request.get("created_at")
            )

            responded_at = (
                request.get("responded_at")
            )

            icon = (
                _status_icon(
                    status
                )
            )

            with st.container(
                border=True
            ):

                name_col, status_col = (
                    st.columns(
                        [4, 1]
                    )
                )

                with name_col:

                    st.markdown(
                        f"### {recipient_name}"
                    )

                    st.caption(
                        f"{target_role} ID: {recipient_id}"
                    )

                with status_col:

                    if status == "Accepted":

                        st.success(
                            f"{icon} Accepted"
                        )

                    elif status == "Rejected":

                        st.error(
                            f"{icon} Rejected"
                        )

                    else:

                        st.warning(
                            f"{icon} Pending"
                        )

                st.write(
                    request_message
                )

                if created_at:

                    try:

                        st.caption(
                            f"Sent: "
                            f"{created_at:%d %b %Y, %H:%M}"
                        )

                    except Exception:

                        st.caption(
                            f"Sent: {created_at}"
                        )

                if responded_at:

                    try:

                        st.caption(
                            f"Responded: "
                            f"{responded_at:%d %b %Y, %H:%M}"
                        )

                    except Exception:

                        st.caption(
                            f"Responded: {responded_at}"
                        )


# ============================================================
# ATHLETE REQUEST PAGE
# ============================================================

def athlete_requests_page():

    _request_management_page(
        "Athlete"
    )


# ============================================================
# COACH REQUEST PAGE
# ============================================================

def coach_requests_page():

    _request_management_page(
        "Coach"
    )