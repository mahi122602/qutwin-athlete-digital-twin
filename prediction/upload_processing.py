"""Upload-time analysis and explicitly experimental partial-data predictions."""
import json
import pandas as pd
from database.workflow_repository import save_upload,list_uploads
from prediction.event_context import attach_events
from research_prediction.predict import analyse
from research_prediction.longitudinal import personal_state

REQUIRED=('heart_rate','sleep_hours','training_load','recovery_time','hydration_level','temperature','humidity','previous_injury')
def missing_inputs(frame):return [k for k in REQUIRED if k not in frame or frame[k].isna().any()]

def process_upload(athlete_id,entry,selected_events):
    frame=attach_events(entry['df'].copy().reset_index(drop=True),entry['assignments'])
    if not selected_events or any(a['event'] not in selected_events for a in entry['assignments']):
        raise ValueError('Each activity must be assigned to one of the selected events.')
    frame['timestamp']=pd.to_datetime(frame.get('timestamp',pd.Series(pd.NaT,index=frame.index)),utc=True,errors='coerce')
    from ingestion.adaptive_table import FIELDS,BOUNDS
    if not frame.reindex(columns=[k for k in FIELDS if k not in ('timestamp','activity_type')]).notna().any().any():
        raise ValueError('No usable activity measurements were mapped.')
    for k,(lo,hi) in BOUNDS.items():
        if k not in frame:continue
        n=pd.to_numeric(frame[k],errors='coerce')
        if (frame[k].notna() & ~n.between(lo,hi)).any():raise ValueError(f'{k} contains invalid values.')
        frame[k]=n
    # Use earlier observations, never future records or another athlete's history.
    history=[];previous_snapshots=[]
    for upload in list_uploads(athlete_id):
        if upload.get('content_hash')==entry['digest']:continue
        history.extend(upload.get('records') or [])
        previous_snapshots.append(upload.get('snapshot') or {})
    records=json.loads(frame.to_json(orient='records',date_format='iso'))
    # History has one assessment per saved file. Predict its latest record once,
    # rather than running the forest for every sensor sample on every upload.
    eligible=frame
    if 'record_kind' in frame and frame.record_kind.eq('activity').any():eligible=frame[frame.record_kind.eq('activity')]
    order=eligible.assign(_date=eligible.timestamp).sort_values('_date',na_position='first',kind='stable')
    latest_position=frame.index.get_loc(order.index[-1])
    record=records[latest_position]
    snapshot=dict(record, **analyse(record, selected_events, history+records))
    snapshot['personal_state']=personal_state(snapshot,previous_snapshots)
    snapshot['import_schema_version']='adaptive-v2'
    snapshot['activity_record_count']=int(frame.get('record_kind',pd.Series('activity',index=frame.index)).eq('activity').sum())
    count=int(snapshot['prediction_status']=='research_estimate')
    snapshot.update(prediction_record_count=count,observation_record_count=len(frame),
        assessment_scope='Latest dated activity session; measurement-only exports use their latest measurement. All source observations are retained.',
        recommendation='AI draft pending; research estimates require coach review.',import_reports=entry.get('raw',{}).get('reports',{}))
    # Preserve measured records separately. Research imputations are never written
    # into physiological sensor columns or the existing legacy-state tables.
    status='research_estimate' if count else 'observations_only'
    saver=save_upload
    if entry.get('refresh_analysis'):
        from database.workflow_repository import refresh_unreviewed_analysis
        saver=refresh_unreviewed_analysis
    elif entry.get('correct_existing'):
        from database.workflow_repository import correct_observation_upload
        saver=correct_observation_upload
    return saver(athlete_id,entry['name'],entry['detection'].get('source','Activity export'),entry['digest'],frame,snapshot,
        selected_events,entry['assignments'],status,None)

def recalculate_saved(athlete_id,upload):
    records=upload.get('records') or []
    if not records:raise ValueError('No source observations saved for this upload.')
    return process_upload(athlete_id,{'df':pd.DataFrame(records),'assignments':upload['assignments'],
        'name':upload['filename'],'digest':upload['content_hash'],'detection':{'source':upload['source']},
        'refresh_analysis':True},upload['events'])
