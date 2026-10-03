import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database.twin_repository import get_athlete_twin_history
from ui.studio_shell import chapter,style_chart

def athlete_visualisations():
    st.title('Explore your patterns')
    chapter('EXPLORER / ONE QUESTION AT A TIME','Choose a measure and look at its recorded history. Missing dates stay off the timeline; missing values leave a gap.')
    try:history=get_athlete_twin_history(str(st.session_state.user_id))
    except Exception:st.error('Your history could not be loaded.');return
    if history is None or history.empty:st.info('Add an activity to start exploring.');return
    labels={'heart_rate':('Average heart rate','bpm'),'training_load':('Training load','proxy units'),'sleep_hours':('Sleep','hours'),'fatigue_score':('Estimated fatigue','index / 100'),'readiness_score':('Estimated readiness','index / 100')}
    available=[k for k in labels if k in history]
    if not available:st.info('These records do not yet contain chart-ready measurements.');return
    choice=st.selectbox('What would you like to explore?',available,format_func=lambda k:labels[k][0])
    data=history.copy();data['_date']=pd.to_datetime(data.get('timestamp'),errors='coerce',utc=True,format='mixed');data=data.dropna(subset=['_date']).sort_values('_date')
    if data.empty:st.info('Add the real activity dates to see a timeline.');return
    data[choice]=pd.to_numeric(data[choice],errors='coerce')
    fig=go.Figure(go.Scatter(x=data['_date'],y=data[choice],mode='markers',marker=dict(size=10),name=labels[choice][0]))
    fig.update_layout(height=470,xaxis_title='Recorded activity date (UTC)',yaxis_title=labels[choice][1])
    st.plotly_chart(style_chart(fig),use_container_width=True)
    st.caption('Each point is a saved record. Model versions and input completeness may differ; a change in an estimated score is not necessarily a physiological change.')
    with st.expander('See the values behind this chart'):
        st.dataframe(data[['_date',choice]].rename(columns={'_date':'Activity date',choice:labels[choice][0]}),hide_index=True,use_container_width=True)
