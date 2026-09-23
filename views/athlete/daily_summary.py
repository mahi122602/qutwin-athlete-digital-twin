"""Observed daily activity history; no synthetic readiness or injury scores."""
import pandas as pd
import streamlit as st
from database.daily_summary_repository import get_daily_summaries


def render_daily_summary_history():
    try:
        frame = get_daily_summaries(str(st.session_state.user_id))
    except Exception:
        st.error('Daily activity history could not be loaded. Please check the database connection and retry.')
        return
    if frame.empty:
        return
    with st.expander('Daily activity trends', expanded=True):
        st.caption('Samsung Health daily observations. Missing measurements remain unavailable; these records do not generate prediction scores. Multiple source records on one date are shown separately.')
        if 'step_count' in frame:
            steps = pd.to_numeric(frame['step_count'], errors='coerce')
            chart = pd.DataFrame({'Date': pd.to_datetime(frame['Date']), 'Steps': steps}).dropna()
            if not chart.empty:
                # Show multiple same-day records separately, without summing
                # potentially overlapping device summaries.
                if chart['Date'].duplicated().any():
                    st.scatter_chart(chart, x='Date', y='Steps')
                else:
                    st.line_chart(chart.sort_values('Date').set_index('Date'))
        st.download_button('Download daily observations', frame.to_csv(index=False).encode(),
                           file_name='daily_activity_history.csv', mime='text/csv', key='daily_summary_download')
