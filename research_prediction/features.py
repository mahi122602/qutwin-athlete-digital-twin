import numpy as np
import pandas as pd

NUMERIC=['training_load','sleep_hours','recovery_time','temperature','humidity','hydration_score']
EVENTS={'100 m':100,'200 m':200,'400 m':400,'800 m':800,'1500 m':1500,'5 km':5000,'10 km':10000,'Half Marathon':21097.5,'Marathon':42195}

def canonical_event(value):
    s=str(value).lower().replace('race','').replace(' ','').strip()
    return next((k for k in EVENTS if k.lower().replace(' ','')==s),str(value))

def model_frame(frame):
    out=frame.reindex(columns=NUMERIC).apply(pd.to_numeric,errors='coerce')
    if 'hydration_level' in frame:
        out['hydration_score']=frame.hydration_level.astype(str).str.lower().map({'low':.4,'medium':.7,'high':1.})
    out['event']=frame.get('event_type',pd.Series('Unknown',index=frame.index)).map(canonical_event)
    return out

def derive_features(record,history=(),events=()):
    """Only arithmetic from real measurements; never fill unknown health data."""
    r=dict(record);values={};origin={};notes=[]
    def num(k):
        try:
            x=float(r.get(k));return x if np.isfinite(x) else None
        except (ValueError,TypeError):return None
    hr,duration,distance=num('heart_rate'),num('duration_minutes'),num('distance')
    if duration is not None and duration>0:
        values['duration_minutes']=duration;origin['duration_minutes']='Uploaded duration'
        if distance is not None and distance>0:
            values['pace_min_per_km']=duration/distance
            values['speed_kmh']=60*distance/duration
            origin.update(pace_min_per_km='Duration / distance',speed_kmh='Distance / duration')
    if hr is not None:values['exercise_heart_rate']=hr;origin['exercise_heart_rate']='Uploaded average heart rate; not assumed resting HR'
    load=num('training_load')
    if load is None and hr is not None and duration is not None and duration>0:
        load=hr*duration/100;origin['training_load']='QUTwin estimate: average HR × minutes / 100'
    elif load is not None:origin['training_load']=str(r.get('training_load_origin') or 'Uploaded/imported load; verify its scale matches model training')
    if load is not None:values['training_load']=load
    timestamp=pd.to_datetime(r.get('timestamp'),utc=True,errors='coerce')
    valid=[]
    if pd.notna(timestamp):
        for row in history:
            t=pd.to_datetime(row.get('timestamp'),utc=True,errors='coerce')
            try:v=float(row.get('training_load'))
            except (ValueError,TypeError):continue
            if pd.notna(t) and t<timestamp and np.isfinite(v):valid.append((t,v))
        # Exact duplicate dated loads cannot inflate the personal baseline.
        valid=list(dict.fromkeys(valid))
        recent=[v for t,v in valid if t>=timestamp-pd.Timedelta(days=28)]
        if len(recent)>=3 and load is not None:
            baseline=float(np.median(recent));values['prior_load_median_28d']=baseline
            if baseline>0:values['load_vs_prior_median']=load/baseline
            mad=float(np.median(np.abs(np.array(recent)-baseline)))
            if mad>0:values['load_robust_z']=(load-baseline)/(1.4826*mad)
            origin['prior_load_median_28d']=f'{len(recent)} earlier observed loads; unrecorded days are not zeros'
        else:notes.append('At least three earlier dated observations are needed for a personal workload baseline.')
    else:notes.append('Activity date is unknown; temporal features are not calculated from upload time.')
    event_context=[]
    for event in dict.fromkeys(events):
        e=canonical_event(event);item={'event':e,'distance_m':EVENTS.get(e)}
        if distance is not None and item['distance_m']:
            item['uploaded_distance_over_event_distance']=distance*1000/item['distance_m']
        event_context.append(item)
    if num('session_rpe') is not None and duration is not None:
        values['session_rpe_load']=num('session_rpe')*duration
        origin['session_rpe_load']='Session RPE × duration minutes; distinct from model training_load'
    for field in ('steps','calories','sleep_hours','resting_heart_rate','hrv_ms','total_ascent'):
        if num(field) is not None:values[field]=num(field);origin[field]='Uploaded measurement'
    return {'features':values,'provenance':origin,'notes':notes,'event_context':event_context}
