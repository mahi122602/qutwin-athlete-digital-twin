"""Explain forecast eligibility without modifying dates or saved measurements."""
import pandas as pd
import streamlit as st

def eligibility_report(raw,eligible):
    raw=raw.copy() if raw is not None else pd.DataFrame()
    if raw.empty:return pd.DataFrame(),0
    dates=pd.to_datetime(raw.get('timestamp',pd.Series(index=raw.index,dtype=object)),utc=True,errors='coerce',format='mixed')
    included=set(eligible.index) if eligible is not None else set()
    rows=[]
    for i,r in raw.iterrows():
        reason='Included in comparable history' if i in included else ('Activity date missing or unreadable' if pd.isna(dates.loc[i]) else 'Different model version, input set or event context')
        rows.append({'Saved assessment':str(r.get('workflow_upload_id',r.get('upload_id',i))),
                     'Activity date':dates.loc[i].strftime('%d %b %Y') if pd.notna(dates.loc[i]) else 'Missing',
                     'Forecast use':reason,'Fatigue':r.get('fatigue_score'),'Readiness':r.get('readiness_score')})
    count=0 if eligible is None or eligible.empty else pd.to_datetime(eligible.timestamp,utc=True).dt.floor('D').nunique()
    return pd.DataFrame(rows),count

def render_data_check(raw,eligible):
    report,days=eligibility_report(raw,eligible)
    a,b,c=st.columns(3)
    a.metric('Saved assessments',len(report));b.metric('Comparable assessments',len(eligible));c.metric('Distinct activity days',days)
    if days<3:
        st.info(f'Why this projection is flat: {days} comparable activity day(s) are available. This view repeats the latest saved values; it has not learned a trend from your uploads.')
    st.caption('File count is not the same as time history. Multiple uploads from the same day still represent one calendar day. Current uploads save one assessment per file, even if the file contains many source records.')
    with st.expander('See which saved assessments can be used',expanded=days<3):
        if report.empty:st.write('No saved assessment history was returned.')
        else:st.dataframe(report,hide_index=True,use_container_width=True)
        st.write('Missing date: add the actual activity date using Add activity. Different assessment basis: records remain saved, but are kept separate so unlike scores are not treated as a personal trend. Upload dates cannot substitute for exercise dates.')
    if days<3 and st.button('Open Add activity to review dates',key='forecast_review_dates'):
        st.session_state.current_page='Upload Garmin Data';st.rerun()
