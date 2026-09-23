"""One dated table for measured daily summaries and existing prediction records."""
import pandas as pd
import streamlit as st
from database.daily_summary_repository import get_daily_summaries

LABELS = {
 'timestamp':'Date / Time','record_type':'Record Type','event_type':'Event',
 'prediction_status':'Prediction Status','heart_rate':'Heart Rate','sleep_hours':'Sleep Hours',
 'training_load':'Training Load','recovery_time':'Recovery Time','fatigue_score':'Fatigue',
 'readiness_score':'Readiness','injury_risk':'Injury Risk','athlete_state':'Athlete State',
 'twin_score':'Twin Score','health_index':'Health Index','step_count':'Steps',
 'recommendation':'Recommendation'
}


def combined_history(predictions, summaries):
    frames=[]
    if predictions is not None and not predictions.empty:
        old=predictions.copy()
        old['record_type']='Digital Twin'
        old['prediction_status']='Existing prediction'
        frames.append(old.reindex(columns=LABELS))
    if summaries is not None and not summaries.empty:
        daily=pd.DataFrame(index=summaries.index,columns=list(LABELS))
        daily['timestamp']=summaries['Date']
        daily['record_type']='Daily summary'
        daily['prediction_status']='Unavailable — missing prediction inputs'
        daily['athlete_state']='Observed activity only'
        for name in ['heart_rate','sleep_hours','step_count']:
            if name in summaries: daily[name]=summaries[name]
        daily['recommendation']='Daily observations saved. Additional session and recovery measurements are needed for predictions.'
        frames.append(daily)
    if not frames: return pd.DataFrame(columns=LABELS.values())
    merged=pd.concat(frames,ignore_index=True)
    # UTC is a sorting convention for mixed timezone inputs; date-only
    # summaries keep their source calendar date and do not invent a time.
    dates=pd.to_datetime(merged['timestamp'],errors='coerce',utc=True,format='mixed')
    merged=merged.assign(_date=dates).sort_values('_date',ascending=False,kind='stable',na_position='last')
    dates=merged.pop('_date')
    merged['timestamp']=dates.dt.strftime('%d %b %Y, %H:%M')
    is_summary=merged['record_type'].eq('Daily summary')
    merged.loc[is_summary,'timestamp']=dates[is_summary].dt.strftime('%d %b %Y')
    for key,unit,places in [('heart_rate','bpm',0),('sleep_hours','h',1),('recovery_time','h',1)]:
        merged[key]=pd.to_numeric(merged[key],errors='coerce').map(lambda v:f'{v:.{places}f} {unit}' if pd.notna(v) else 'Unavailable')
    return merged.rename(columns=LABELS).fillna('Unavailable')


def render_combined_history(predictions):
    try:
        summaries=get_daily_summaries(str(st.session_state.user_id))
    except Exception:
        summaries=pd.DataFrame()
        st.error('Daily summaries could not be loaded. The table below shows available Digital Twin records only.')
    table=combined_history(predictions,summaries)
    st.markdown('## Detailed History Records')
    st.caption('All saved observations and prediction records, newest activity date first. Timestamped records are displayed in UTC; daily summary dates are shown as supplied. Re-uploading older activity does not change its date. Daily summaries do not replace the latest predicted state.')
    if table.empty:
        st.info('No saved history yet.')
        return
    st.dataframe(table,use_container_width=True,hide_index=True)
    st.download_button('Download History CSV',table.to_csv(index=False).encode(),
                       'digital_twin_history.csv','text/csv',key='combined_history_csv')
