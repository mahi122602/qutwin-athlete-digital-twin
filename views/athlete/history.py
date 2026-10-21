"""A visual journal backed by saved upload snapshots; no invented activity dates."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database.upload_history_repository import get_upload_history
from ui.workflow_errors import show_workflow_error
from ui.studio_shell import chapter, style_chart, score_ribbon
from ui.performance_story import journal_data, render_performance_story
from services.activity_explorer import attach_dates, available_measures

COLUMNS={'_uploaded_at':'Saved on','filename':'Activity file','events':'Upcoming events','timestamp':'Activity date','prediction_basis':'Assessment basis','fatigue_score':'Fatigue','readiness_score':'Readiness','injury_risk':'Injury category','recommendation':'AI draft','coach_feedback':'Coach decision'}
def format_upload_history(frame):
    data=frame.reindex(columns=COLUMNS).copy()
    data['_uploaded_at']=pd.to_datetime(data['_uploaded_at'],utc=True,errors='coerce',format='mixed').dt.strftime('%d %b %Y %H:%M UTC')
    dates=attach_dates(frame)
    data['timestamp']=dates['_date_label'].where(dates['_plot_date'].notna(),'—')
    return data.rename(columns=COLUMNS).astype(object).where(data.notna().rename(columns=COLUMNS),'—')

def charts(frame):
    figures=[]
    data=frame.copy()
    data['_date']=pd.to_datetime(data.get('timestamp'),errors='coerce',utc=True,format='mixed')
    data=data.dropna(subset=['_date']).sort_values('_date')
    for field,title in [('fatigue_score','Fatigue over time'),('readiness_score','Readiness over time')]:
        fig=go.Figure()
        # Separate model/input tiers rather than joining unlike estimates.
        for key in ('model_version','model_tier'):
            if key not in data:data[key]='Unspecified'
            data[key]=data[key].fillna('Unspecified')
        for (version,tier),group in data.groupby(['model_version','model_tier']):
            values=pd.to_numeric(group.get(field,pd.Series(index=group.index,dtype=float)),errors='coerce')
            fig.add_trace(go.Scatter(x=group['_date'],y=values,mode='lines+markers',connectgaps=False,name=f'{version} · {tier}',line=dict(width=3),marker=dict(size=8)))
        fig.update_layout(title=title,yaxis_title='Estimated score / 100',xaxis_title='Recorded activity date (UTC)',height=390)
        fig.update_yaxes(range=[0,100]);figures.append(style_chart(fig))
    return figures

def athlete_history():
    st.title('Your activity journal')
    chapter('03 / YOUR STORY OVER TIME','Your activities, their measurements and the advice saved alongside them. Compare sessions now; add the time perspective when activity dates are known.')
    try: frame=get_upload_history(str(st.session_state.user_id))
    except Exception as exc:show_workflow_error(exc,'History');return
    if frame.empty:st.info('Your journal starts with your first saved activity.');return
    story=journal_data(frame)
    a,b,c=st.columns(3)
    a.metric('Saved uploads',len(frame))
    b.metric('Measurements to explore',len(available_measures(story.observations)))
    c.metric('Activity dates known',f"{int(story.observations['_plot_date'].notna().sum())} / {len(frame)}")
    trend,archive,summary=st.tabs(['Performance story','All records & advice','Latest summary'])
    with trend:
        render_performance_story(frame,story)
    with archive:
        query=st.text_input('Find an activity',placeholder='Search by filename or event')
        data=frame
        if query:
            data=frame[frame.get('filename',pd.Series('',index=frame.index)).fillna('').str.contains(query,case=False,regex=False)|frame.get('events',pd.Series('',index=frame.index)).fillna('').str.contains(query,case=False,regex=False)]
        table=format_upload_history(data)
        st.dataframe(table,hide_index=True,use_container_width=True)
        st.download_button('Download my journal',table.to_csv(index=False).encode(),'qutwin_journal.csv','text/csv')
        st.caption('AI drafts and coach decisions are separate columns. A missing score is never treated as low risk.')
    with summary:
        latest=frame.iloc[0].to_dict();st.subheader(str(latest.get('filename','Latest upload')))
        score_ribbon(latest)
        st.write(latest.get('recommendation') or 'No AI draft is saved for this activity.')
        st.write(latest.get('coach_feedback') or 'No coach decision yet.')
