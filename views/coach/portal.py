import streamlit as st
from views.model_evaluation_page import model_evaluation_dashboard
from views.request_pages import coach_requests_page
from views.coach.shared import COACH_NAV_ITEMS, _render_coach_top_navigation

def assigned_athletes(*args, **kwargs):
    from views.coach.assigned_athletes import assigned_athletes as page
    return page(*args, **kwargs)

def coach_dashboard(*args, **kwargs):
    from views.coach.dashboard import coach_dashboard as page
    return page(*args, **kwargs)

def coach_history(*args, **kwargs):
    from views.coach.history import coach_history as page
    return page(*args, **kwargs)

def coach_intelligence_dashboard(*args, **kwargs):
    from views.coach.intelligence_dashboard import coach_intelligence_dashboard as page
    return page(*args, **kwargs)

def coach_notifications(*args, **kwargs):
    from views.coach.notifications import coach_notifications as page
    return page(*args, **kwargs)

def coach_timeline(*args, **kwargs):
    from views.coach.timeline import coach_timeline as page
    return page(*args, **kwargs)

def coach_visualisations(*args, **kwargs):
    from views.coach.visualisations import coach_visualisations as page
    return page(*args, **kwargs)

def selected_athlete_twin_summary(*args, **kwargs):
    from views.coach.selected_athlete_twin_summary import selected_athlete_twin_summary as page
    return page(*args, **kwargs)

def coach_portal():
    """
    Complete coach-side UI.

    app.py should call this function for logged-in coaches.
    It renders the sticky top navigation first, then the selected
    coach page. No sidebar navigation is required.
    """

    valid_pages = {
        item["page"]
        for item in COACH_NAV_ITEMS
    }

    current_page = st.session_state.get(
        "current_page",
        "Digital Twin Dashboard",
    )

    if current_page not in valid_pages:
        st.session_state.current_page = (
            "Digital Twin Dashboard"
        )
        current_page = (
            "Digital Twin Dashboard"
        )

    _render_coach_top_navigation()

    coach_pages = {
        "Digital Twin Dashboard": (
            coach_dashboard
        ),
        "Assigned Athletes": (
            assigned_athletes
        ),
        "Coach Intelligence Dashboard": (
            coach_intelligence_dashboard
        ),
        "Selected Athlete Twin Summary": (
            selected_athlete_twin_summary
        ),
        "Digital Twin History": (
            coach_history
        ),
        "Digital Twin Timeline": (
            coach_timeline
        ),
        "Visualisations / Graphs": (
            coach_visualisations
        ),
        "Requests": (
            coach_requests_page
        ),
        "Notifications": (
            coach_notifications
        ),
        "Model Evaluation": (
            model_evaluation_dashboard
        ),
    }

    selected_page_function = (
        coach_pages[current_page]
    )

    selected_page_function()
