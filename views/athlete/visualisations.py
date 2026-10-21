"""Activity explorer that also works for one undated, measured upload."""
import streamlit as st
from ui.studio_shell import chapter
from ui.activity_explorer import render_activity_explorer

def athlete_visualisations():
    st.title('Explore your patterns')
    chapter('EXPLORER / FROM MEASUREMENTS TO UNDERSTANDING',
            'See recorded values straight away. Explore activity comparisons, known-date timelines and the data behind each chart.')
    render_activity_explorer(str(st.session_state.user_id),allow_date_link=True)
