import pandas as pd
import streamlit as st
from database.coach_repository import get_assigned_athletes
from views.coach.shared import _render_page_heading

def assigned_athletes():
    _render_page_heading(
        "Assigned Athletes",
        (
            "Athletes who have an active "
            "coach-athlete connection."
        ),
    )

    athletes = get_assigned_athletes(
        st.session_state.user_id
    )

    if not athletes:
        st.info(
            "No athletes are assigned yet."
        )
        return

    assigned_df = pd.DataFrame(
        {
            "Athlete ID": [
                a[0]
                for a in athletes
            ],
            "Name": [
                a[1]
                for a in athletes
            ],
            "Age": [
                a[2]
                for a in athletes
            ],
            "Height": [
                a[3]
                for a in athletes
            ],
            "Weight": [
                a[4]
                for a in athletes
            ],
            "Previous Injury": [
                a[5]
                for a in athletes
            ],
        }
    )

    st.dataframe(
        assigned_df,
        use_container_width=True,
        hide_index=True,
    )
