"""A transparent persistence baseline for uploads without usable time history."""
import math
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ui.studio_shell import style_chart

FIELDS={'fatigue_score':('Estimated fatigue','/ 100'),'readiness_score':('Estimated readiness','/ 100'),'duration_minutes':('Session duration','min'),'heart_rate':('Average heart rate','bpm'),'training_load':('Training-load proxy','AU')}

def finite_value(value):
    try:
        v=float(value)
        return v if math.isfinite(v) and v>=0 else None
    except (ValueError,TypeError):return None

def baseline_table(snapshot):
    values={label:finite_value(snapshot.get(key)) for key,(label,unit) in FIELDS.items()}
    values={k:v for k,v in values.items() if v is not None and (k not in ('Estimated fatigue','Estimated readiness') or v<=100)}
    return pd.DataFrame({'Planning day':[f'Day {n}' for n in range(1,8)],**{k:[v]*7 for k,v in values.items()}})

def render_first_upload_forecast(athlete_id):
    from database.workflow_repository import list_uploads
    uploads=list_uploads(str(athlete_id))
    if not uploads:
        st.info('Add your first activity to start your seven-day forecast.');return
    item=uploads[0];snapshot=item.get('snapshot') or {};table=baseline_table(snapshot)
    st.subheader('Latest-value baseline · no learned trend yet')
    st.caption('Based on your latest saved upload: '+str(item.get('filename','Activity')))
    st.info('Baseline projection · Not enough dated history to learn a trend yet. The next seven planning days repeat your latest available values under an unchanged-conditions assumption; they do not predict recovery or injury.')
    if len(table.columns)==1:
        st.write('Your file is saved, but it has no usable numeric measurements for a baseline. Add a file containing duration, heart rate, training load, fatigue or readiness to draw your projection.')
        st.dataframe(pd.DataFrame({'Planning day':table['Planning day'],'Status':['Awaiting usable measurements']*7}),hide_index=True)
        return
    metric=st.selectbox('Explore your starting point',list(table.columns[1:]),key='baseline_metric')
    unit=next(unit for label,unit in FIELDS.values() if label==metric)
    fig=go.Figure(go.Scatter(x=table['Planning day'],y=table[metric],mode='lines+markers',line=dict(dash='dot',width=3),name='Latest value repeated — not a trend'))
    fig.update_layout(height=350,yaxis_title=f'{metric} ({unit})',showlegend=False)
    if unit=='/ 100':fig.update_yaxes(range=[0,100])
    st.plotly_chart(style_chart(fig),theme=None,use_container_width=True)
    st.caption('No activity date has been invented. Days 1–7 are planning steps, not measured future sessions. More dated activities allow the forecasting model to assess a trend. These baseline values are not saved as observations.')
    with st.expander('View seven planning days'):st.dataframe(table,hide_index=True,use_container_width=True)
