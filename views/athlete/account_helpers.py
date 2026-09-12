import streamlit as st
from authentication.session import logout_user

def perform_logout():
    """
    Reset navigation before logout_user() performs its rerun.
    """

    st.session_state.auth_page = "Login"

    st.session_state.current_page = (
        "Athlete Home"
    )

    logout_user()

def _notification_icon(
    notification_type,
):

    if notification_type == "Request Accepted":
        return "✅"

    if notification_type == "Request Rejected":
        return "❌"

    if notification_type == "Connection Request":
        return "🤝"

    if notification_type == "Risk Alert":
        return "⚠️"

    if notification_type == "Coach Recommendation":
        return "💬"

    return "🔔"

def _notification_destination(
    notification_type,
):
    """
    Return the appropriate Athlete page for a notification.

    Risk alerts:
        Digital Twin Dashboard

    Coach recommendations:
        Prediction page

    Request status:
        Profile for now.
    """

    if notification_type == "Risk Alert":
        return "Digital Twin Dashboard"

    if notification_type == "Coach Recommendation":
        return (
            "Predictions & Coach Recommendations"
        )

    if notification_type in {
        "Request Accepted",
        "Request Rejected",
    }:
        return "Profile"

    return None
