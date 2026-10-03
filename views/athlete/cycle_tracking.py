"""Optional, athlete-only dates with no invented end date."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from database.forecasting_repository import get_menstrual_history,add_menstrual_cycle,replace_menstrual_history

def render_cycle_tracking(athlete_id):
    today=datetime.now(ZoneInfo('Australia/Brisbane')).date()
    st.caption('Private to you. These dates provide context alongside your outlook; they do not by themselves establish fatigue or injury risk.')
    history=get_menstrual_history(athlete_id)
    with st.expander('Log or update a period',expanded=history.empty):
        with st.form('period_dates_form',clear_on_submit=True):
            left,right=st.columns(2)
            start=left.date_input('Start date',value=None,max_value=today)
            end=right.date_input('End date (leave blank if ongoing)',value=None,max_value=today)
            st.caption('To finish an ongoing record, enter its same start date and the actual end date. No estimated dates are saved.')
            submitted=st.form_submit_button('Save dates',type='primary')
        if submitted:
            if start is None:st.error('Choose the day your period started.')
            elif end is not None and end<start:st.error('The end date must be on or after the start date.')
            else:
                try:add_menstrual_cycle(athlete_id,start,end)
                except ValueError as exc:st.error(str(exc))
                except Exception:st.error('Dates could not be saved. Please try again.')
                else:st.rerun()
    if not history.empty:
        display=history[['period_start_date','period_end_date']].rename(columns={'period_start_date':'Started','period_end_date':'Ended'}).copy()
        st.dataframe(display,hide_index=True,use_container_width=True)
        st.caption('A blank end date means ongoing or not recorded.')
        with st.expander('Remove a period record'):
            by_id={int(r.cycle_id):r for r in history.itertuples()}
            selected=st.selectbox('Record',list(by_id),format_func=lambda i:str(by_id[i].period_start_date))
            confirmed=st.checkbox('Delete this period record permanently')
            if st.button('Delete record',disabled=not confirmed):
                try:replace_menstrual_history(athlete_id,history[history.cycle_id!=selected],history)
                except Exception:st.error('The record could not be deleted. Please try again.')
                else:st.rerun()
    if not history.empty and st.checkbox('Show my activity alongside these dates',key='private_cycle_overlay'):
        from database.twin_repository import get_athlete_twin_history
        from ui.studio_shell import style_chart,palette
        import plotly.graph_objects as go
        try:
            activity=get_athlete_twin_history(athlete_id).copy()
            activity['_date']=pd.to_datetime(activity.get('timestamp'),errors='coerce',utc=True,format='mixed')
            activity=activity.dropna(subset=['_date']).sort_values('_date')
            fig=go.Figure()
            for field,label in [('fatigue_score','Estimated fatigue'),('readiness_score','Estimated readiness')]:
                if field in activity:
                    fig.add_trace(go.Scatter(x=activity['_date'],y=pd.to_numeric(activity[field],errors='coerce'),mode='markers',name=label))
            for row in history.itertuples():
                if pd.notna(row.period_end_date):
                    fig.add_vrect(x0=str(row.period_start_date),x1=str(pd.Timestamp(row.period_end_date)+pd.Timedelta(days=1)),fillcolor=palette()['accent'],opacity=.12,line_width=0)
            fig.update_layout(height=360,yaxis_title='Research index / 100')
            st.plotly_chart(style_chart(fig),use_container_width=True)
            st.caption('Shaded bands are completed periods you recorded. Points are saved estimates, not measured outcomes. Overlap does not prove that your cycle caused a change.')
        except Exception:
            st.info('Your period dates are saved, but the activity comparison could not be loaded.')
    return history
