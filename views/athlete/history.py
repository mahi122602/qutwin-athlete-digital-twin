from ui.workflow_errors import show_workflow_error
"""Upload-time history and four views of the saved snapshots; no calendar filling."""
import logging
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database.upload_history_repository import get_upload_history

COLUMNS={'_uploaded_at':'Uploaded Date / Time','filename':'File','source':'Data Source','events':'Events',
 'prediction_basis':'Prediction Basis','upload_status':'Status','rows_extracted':'Records in File','timestamp':'Latest Activity Date',
 'heart_rate':'Heart Rate','sleep_hours':'Sleep Hours','training_load':'Training Load','recovery_time':'Recovery Time',
 'model_tier':'Model Input Tier','model_version':'Model Version','fatigue_score':'Fatigue','readiness_score':'Readiness','injury_risk':'Injury Risk','athlete_state':'Athlete State',
 'twin_score':'Twin Score','health_index':'Health Index','recommendation':'Recommendation','coach_feedback':'Coach Feedback'}


def format_upload_history(frame):
    if frame is None or frame.empty: return pd.DataFrame(columns=COLUMNS.values())
    data=frame.copy()
    data['_uploaded_at']=pd.to_datetime(data['_uploaded_at'],utc=True,errors='coerce')
    data=data.sort_values('_uploaded_at',ascending=False,kind='stable').reindex(columns=list(COLUMNS))
    for key in ('_uploaded_at','timestamp'):
        data[key]=pd.to_datetime(data[key],utc=True,errors='coerce').dt.strftime('%d %b %Y, %H:%M:%S UTC')
    return data.rename(columns=COLUMNS).astype(object).where(pd.notna(data.rename(columns=COLUMNS)),'—')


def charts(frame):
    data=frame.sort_values('_uploaded_at').copy()
    figs=[]
    for field,title in [('fatigue_score','Fatigue score'),('injury_risk','Injury risk')]:
        series=data[field] if field in data else pd.Series(index=data.index,dtype=float)
        if field=='injury_risk':
            values=series.astype(str).str.lower().map({'low':1,'medium':2,'high':3})
        else: values=pd.to_numeric(series,errors='coerce')
        fig=go.Figure(go.Scatter(x=data['_uploaded_at'],y=values,mode='lines+markers',connectgaps=False,line_color='#22d3ee'))
        fig.update_layout(title=title,xaxis_title='Upload date (UTC)',yaxis_title='Score / 100' if field=='fatigue_score' else 'Risk category')
        if field=='injury_risk': fig.update_yaxes(tickvals=[1,2,3],ticktext=['Low','Medium','High'],range=[.5,3.5])
        else: fig.update_yaxes(range=[0,100])
        figs.append(fig)
    latest=frame.iloc[0]
    # The pie represents composition of normalised indices, NOT probabilities.
    parts={label:pd.to_numeric(latest.get(key),errors='coerce') for label,key in [('Fatigue','fatigue_score'),('Readiness','readiness_score'),('Recovery','recovery_index')]}
    if pd.notna(parts['Recovery']): parts['Recovery']*=100
    parts={k:max(0,float(v)) for k,v in parts.items() if pd.notna(v)}
    pie=go.Figure()
    if parts and sum(parts.values())>0:
        pie.add_trace(go.Pie(labels=list(parts),values=list(parts.values()),hole=.35))
    else: pie.add_annotation(text='No condition scores for this upload',showarrow=False)
    pie.update_layout(title='Latest Athlete Condition Profile')
    figs.append(pie)
    radar=go.Figure()
    for _,row in frame.head(5).iloc[::-1].iterrows():
        vals=[pd.to_numeric(row.get(k),errors='coerce') for k in ('fatigue_score','readiness_score','twin_score','health_index')]
        if any(pd.isna(v) for v in vals): continue
        labels=['Fatigue','Readiness','Twin score','Health index']
        radar.add_trace(go.Scatterpolar(r=vals+[vals[0]],theta=labels+[labels[0]],name=str(row['_uploaded_at']),mode='lines+markers'))
    if not radar.data: radar.add_annotation(text='Complete scores needed for state comparison',showarrow=False)
    radar.update_layout(title='Athlete state history',polar={'radialaxis':{'range':[0,100]}})
    figs.append(radar)
    for fig in figs:
        fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',height=370,margin=dict(l=30,r=20,t=50,b=35))
    return figs


def athlete_history():
    st.title('Digital Twin History')
    try: frame=get_upload_history(str(st.session_state.user_id))
    except Exception as exc:
        show_workflow_error(exc, 'History')
        return
    if frame.empty:
        st.info('No saved uploads yet. Click Upload and proceed on Upload Data.'); return
    latest=frame.iloc[0]
    if latest.get('prediction_status') == 'research_estimate':
        st.warning('Latest scores are experimental research estimates. Input-specific models use available measurements; injury categories are exploratory and not validated probabilities.')
        st.caption(latest.get('risk_validation_warning', ''))
    st.subheader('Latest Snapshot')
    st.caption(f"{latest['filename']} · Saved {latest['_uploaded_at']}")
    for col,(label,key) in zip(st.columns(4),[('Fatigue','fatigue_score'),('Readiness','readiness_score'),('Injury risk','injury_risk'),('Twin score','twin_score')]):
        value=latest.get(key); col.metric(label,value if pd.notna(value) else 'Unavailable')
    st.subheader('Latest Recommendation')
    text=latest.get('recommendation')
    st.write(text if isinstance(text,str) else 'No recommendation for this upload.')
    feedback=latest.get('coach_feedback')
    if isinstance(feedback,str): st.write('Coach: '+feedback)
    st.subheader('Detailed History Records')
    table=format_upload_history(frame)
    st.dataframe(table,use_container_width=True,hide_index=True)
    st.caption('One row per saved file, newest upload first. Scores describe its latest activity. Missing values remain unavailable; no extra days are inserted.')
    st.download_button('Download Upload History',table.to_csv(index=False).encode(),'upload_history.csv','text/csv')
    st.subheader('Visual Performance Overview')
    if 'prediction_status' in frame and frame['prediction_status'].eq('research_estimate').any():
        st.caption('Charts include experimental estimates. Changes between different model versions or input completeness may not represent physiological change.')
    figures=charts(frame)
    for start in (0,2):
        for col,figure in zip(st.columns(2),figures[start:start+2]):
            with col: st.plotly_chart(figure,use_container_width=True)
    st.caption('Pie slices show relative index composition, not health probabilities. Radar compares up to five recent uploads on a 0–100 scale; higher fatigue means more fatigue, not better condition.')
    st.subheader('Simple Interpretation')
    if latest.get('prediction_status') in ('observations_only', 'analysis_only'):
        st.write('Your latest upload is saved. Its measurements are available, but no evaluated model covers this input set. Older scores are not substituted. Open Prediction for its activity analysis and AI advice.')
    else:
        st.write('The latest saved upload is shown above. The line charts track available upload snapshots; breaks indicate unavailable scores. Review the coach decision before treating the AI draft as an approved plan.')
