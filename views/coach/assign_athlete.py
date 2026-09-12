import streamlit as st
from views.coach.shared import _render_page_heading, open_coach_page

def assign_athlete():
    """
    Kept only so older app.py imports do not fail.

    Direct assignment is intentionally not used anymore.
    Connection consent is managed through Requests.
    """

    _render_page_heading(
        "Athlete Connections",
        (
            "Direct assignment has been replaced "
            "with two-way connection requests."
        ),
    )

    st.info(
        "Use the Requests page to connect "
        "with an athlete."
    )

    if st.button(
        "Open Requests",
        key="legacy_assign_open_requests",
        type="primary",
    ):
        open_coach_page(
            "Requests"
        )
