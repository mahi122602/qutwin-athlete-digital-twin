import html
import pandas as pd
import streamlit as st
from database.connection_request_repository import get_notifications, get_unread_notification_count, mark_all_notifications_read, mark_notification_read
from views.coach.shared import _get_risk_df, _render_page_heading, _render_risk_athlete_card

def coach_notifications():
    _render_page_heading(
        "Coach Notifications",
        (
            "Current fatigue and injury-risk "
            "alerts for assigned athletes, plus "
            "connection request updates."
        ),
        eyebrow="COACH ALERT CENTRE",
    )

    coach_id = str(
        st.session_state.user_id
    )

    try:
        risk_df = _get_risk_df()
    except Exception as exc:
        st.error(
            "Athlete risk information "
            "could not be loaded."
        )
        st.exception(exc)
        risk_df = pd.DataFrame()

    try:
        notifications = get_notifications(
            "Coach",
            coach_id,
            limit=100,
        )

        unread_count = int(
            get_unread_notification_count(
                "Coach",
                coach_id,
            )
            or 0
        )

    except Exception as exc:
        notifications = []
        unread_count = 0

        st.warning(
            "Request notifications could "
            "not be loaded."
        )
        st.exception(exc)

    if risk_df.empty:
        high_df = pd.DataFrame()
        medium_df = pd.DataFrame()
        low_df = pd.DataFrame()
    else:
        high_df = risk_df[
            risk_df["Overall Risk"]
            == "High"
        ]

        medium_df = risk_df[
            risk_df["Overall Risk"]
            == "Medium"
        ]

        low_df = risk_df[
            risk_df["Overall Risk"]
            == "Low"
        ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "High Risk",
        len(high_df),
    )

    c2.metric(
        "Monitor",
        len(medium_df),
    )

    c3.metric(
        "Low Risk",
        len(low_df),
    )

    c4.metric(
        "Unread Requests",
        unread_count,
    )

    st.divider()

    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

    st.subheader(
        "🔴 High Risk Athletes"
    )

    st.caption(
        (
            "An athlete appears here when "
            "fatigue OR injury risk is High."
        )
    )

    if high_df.empty:
        st.success(
            "No assigned athletes are "
            "currently high risk."
        )
    else:
        for number, (_, row) in enumerate(
            high_df.iterrows(),
            start=1,
        ):
            _render_risk_athlete_card(
                number,
                row,
                "High",
            )

    # --------------------------------------------------------
    # MEDIUM
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🟠 Athletes to Monitor"
    )

    if medium_df.empty:
        st.info(
            "No assigned athletes currently "
            "need medium-level monitoring."
        )
    else:
        for number, (_, row) in enumerate(
            medium_df.iterrows(),
            start=1,
        ):
            _render_risk_athlete_card(
                number,
                row,
                "Medium",
            )

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🟢 Low Risk Athletes"
    )

    st.caption(
        (
            "Low-risk athletes have both "
            "fatigue and injury risk in "
            "the low range."
        )
    )

    if low_df.empty:
        st.info(
            "No assigned athletes are "
            "currently in the low-risk group."
        )
    else:
        for number, (_, row) in enumerate(
            low_df.iterrows(),
            start=1,
        ):
            _render_risk_athlete_card(
                number,
                row,
                "Low",
            )

    # --------------------------------------------------------
    # REQUEST NOTIFICATIONS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🔔 Request Notifications"
    )

    if (
        unread_count > 0
        and notifications
    ):
        if st.button(
            "Mark all as read",
            key=(
                "coach_mark_all_"
                "notifications_read"
            ),
        ):
            try:
                mark_all_notifications_read(
                    "Coach",
                    coach_id,
                )
                st.rerun()
            except Exception as exc:
                st.error(
                    "Notifications could "
                    "not be updated."
                )
                st.exception(exc)

    if not notifications:
        st.info(
            "No request notifications "
            "are available."
        )
        return

    for notification in notifications:
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

        message = notification.get(
            "message",
            "",
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
                    "**"
                    + html.escape(
                        str(
                            notification_type
                        )
                    )
                    + "**"
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
                str(message)
            )

            if created_at:
                st.caption(
                    str(created_at)
                )

            if not is_read:
                if st.button(
                    "Mark as read",
                    key=(
                        "coach_notification_"
                        f"read_{notification_id}"
                    ),
                ):
                    try:
                        mark_notification_read(
                            notification_id,
                            "Coach",
                            coach_id,
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(
                            "Notification "
                            "could not be updated."
                        )
                        st.exception(exc)
