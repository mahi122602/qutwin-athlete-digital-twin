"""Read-only chart data: source observations and model estimates stay distinct."""
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
from ingestion.adaptive_table import BOUNDS
from database.access_control import guard_athlete_read
from utils.performance import request_cached

BUILD='visualisations-2026-10-21'
MEASURES={
 'heart_rate':('Average exercise heart rate','bpm','Recorded heart rate during exercise. This is not resting heart rate.'),
 'duration_minutes':('Activity duration','min','The recorded duration of each activity.'),
 'distance':('Distance','km','Recorded activity distance, in kilometres.'),
 'training_load':('Activity load','load units','Load may be imported or calculated from heart rate and duration. The source is shown on hover; different load scales are not interchangeable.'),
 'sleep_hours':('Sleep duration','hours','Sleep associated with the activity, when supplied. Missing sleep is not zero.'),
 'recovery_time':('Recovery time','hours','Recovery time as recorded or confirmed for the activity.'),
 'steps':('Steps','steps','The step count in each source observation.'),
 'calories':('Recorded energy','kcal','Energy reported by the source; this is not a model fatigue score.'),
 'avg_speed':('Average speed','km/h','Recorded average speed, after confirmed unit conversion.'),
 'total_ascent':('Elevation gain','m','Recorded ascent, in metres.'),
 'temperature':('Recorded temperature','°C','Recorded activity temperature; estimated outdoor weather is kept separate.'),
 'humidity':('Recorded humidity','%','Recorded relative humidity.'),
 'resting_heart_rate':('Resting heart rate','bpm','Recorded resting heart rate, kept separate from exercise heart rate.'),
 'hrv_ms':('Heart rate variability','ms','Recorded HRV values; different device methods may not be comparable.'),
 'session_rpe':('Perceived effort','0–10','The athlete’s reported effort; it is not a prediction.')}
ESTIMATES={
 'fatigue_score':('Estimated fatigue','/ 100','A research model estimate. Higher values mean more estimated fatigue.'),
 'readiness_score':('Estimated readiness','/ 100','An engineered readiness index, not clearance to train.'),
 'twin_score':('Twin score','/ 100','An engineered summary of the available model outputs.'),
 'health_index':('Health index','/ 100','An engineered research index, not a health diagnosis.')}
FIELDS=list(MEASURES)
DATE_FIELDS=('timestamp','timestamp_precision','activity_date_only','activity_timezone')


@dataclass
class ExplorerData:
    observations:pd.DataFrame
    estimates:pd.DataFrame
    uploads:list
    rejected_values:int=0


def object_value(value,kind=dict):
    if isinstance(value,str):
        try:value=json.loads(value)
        except (ValueError,TypeError):return kind()
    return value if isinstance(value,kind) else kind()


def active_snapshot(snapshot):
    raw=object_value(snapshot)
    return object_value(raw.get('active_assessment')) or raw


def clean_numeric(frame,catalog):
    result=frame.copy();rejected=0
    for field in catalog:
        raw=result.get(field,pd.Series(index=result.index,dtype=float))
        values=pd.to_numeric(raw,errors='coerce')
        low,high=BOUNDS.get(field,(0,100))
        valid=np.isfinite(values) & values.between(low,high)
        rejected+=int((raw.notna() & ~valid).sum())
        result[field]=values.where(valid)
    return result,rejected


def attach_dates(frame):
    result=frame.copy()
    raw=result.get('timestamp',pd.Series(index=result.index,dtype=object))
    # Processed timestamps are ISO. An ambiguous day/month string is not guessed.
    text=raw.astype(str)
    allowed=text.str.match(r'^\d{4}-\d{2}-\d{2}(?:$|[ T])')
    exact=pd.to_datetime(raw.where(allowed),utc=True,errors='coerce',format='mixed')
    day=result.get('activity_date_only',pd.Series(index=result.index,dtype=object)).astype(str)
    day_valid=pd.to_datetime(day.where(day.str.fullmatch(r'\d{4}-\d{2}-\d{2}')),utc=True,errors='coerce')
    precision=result.get('timestamp_precision',pd.Series('',index=result.index)).eq('day')
    is_day=(exact.isna() & day_valid.notna()) | precision | text.str.fullmatch(r'\d{4}-\d{2}-\d{2}')
    plot_date=exact.where(~is_day,day_valid.combine_first(exact))
    result['_plot_date']=plot_date
    result['_date_precision']=np.where(plot_date.isna(),'Unknown',np.where(is_day,'Date only','Date and time (UTC)'))
    result['_date_label']=plot_date.dt.strftime('%d %b %Y, %H:%M UTC').fillna('Activity date unknown')
    result.loc[is_day & plot_date.notna(),'_date_label']=plot_date[is_day & plot_date.notna()].dt.strftime('%d %b %Y')+' · date only'
    return result


def snapshot_position(frame,snapshot):
    candidates=frame
    if 'record_kind' in frame and frame.record_kind.eq('activity').any():
        candidates=frame[frame.record_kind.eq('activity')]
    if '_source_row' in candidates and snapshot.get('_source_row') is not None:
        match=candidates['_source_row'].astype(str).eq(str(snapshot['_source_row']))
        if 'archive_member' in candidates and snapshot.get('archive_member'):
            match &= candidates.archive_member.eq(snapshot['archive_member'])
        if match.sum()==1:return candidates.index[match][0]
    dates=pd.to_datetime(candidates.get('timestamp',pd.Series(pd.NaT,index=candidates.index)),utc=True,errors='coerce',format='mixed')
    return dates.sort_values(na_position='first',kind='stable').index[-1]


def build_explorer_data(uploads,legacy=None):
    observations=[];estimates=[];choices=[];rejected=0
    for sequence,upload in enumerate(uploads or []):
        key=str(upload.get('id',sequence));filename=str(upload.get('filename') or 'Saved activity')
        snapshot=active_snapshot(upload.get('snapshot'))
        source=object_value(upload.get('records'),list)
        has_source=bool(source)
        if not source:
            source=[{k:snapshot[k] for k in FIELDS+list(DATE_FIELDS) if k in snapshot}]
        rows=pd.DataFrame([r for r in source if isinstance(r,dict)]).reset_index(drop=True)
        if rows.empty:continue
        target=snapshot_position(rows,snapshot)
        # The latest snapshot may contain athlete-confirmed inputs that were never
        # written into the immutable source records. Overlay only its assessed row.
        for field in FIELDS+list(DATE_FIELDS)+['training_load_origin']:
            value=snapshot.get(field)
            if value is not None and not isinstance(value,(dict,list)) and pd.notna(value):
                if field not in rows:rows[field]=pd.Series(index=rows.index,dtype=object)
                rows.loc[target,field]=value
        confirmed=object_value(snapshot.get('assessment_inputs'))
        rows['_confirmed']=''
        rows.loc[target,'_confirmed']=','.join(confirmed)
        rows['_upload_key']=key;rows['_filename']=filename
        rows['_saved_at']=str(upload.get('uploaded_at') or '')
        rows['_origin']='Source export' if has_source else 'Saved assessment values'
        rows['_kind']=rows.get('record_kind',pd.Series('activity',index=rows.index)).fillna('activity')
        rows['_label']=[f'{"Measurement" if kind=="measurement" else "Activity"} {i+1} · {filename[:38]}' for i,kind in enumerate(rows['_kind'])]
        rows['_record_key']=[f'{key}:{i+1}' for i in range(len(rows))]
        rows['_label']=rows['_label']+' · #'+rows['_record_key']
        rows,count=clean_numeric(rows,MEASURES);rejected+=count
        rows=attach_dates(rows)
        keep=FIELDS+[k for k in rows if str(k).startswith('_') and not str(k).startswith('_source')]+['training_load_origin']
        # Retain only chart metadata and canonical measurements, not raw file text.
        observations.append(rows.reindex(columns=list(dict.fromkeys(keep))))
        choices.append({'key':key,'filename':filename,'count':len(rows)})
        status=snapshot.get('prediction_status')
        if status=='research_estimate':
            estimate={k:snapshot.get(k) for k in ESTIMATES}
            estimate.update({k:snapshot.get(k) for k in DATE_FIELDS})
            estimate.update(_upload_key=key,_filename=filename,_label=f'{filename[:42]} · #{key}',
                _record_key=f'assessment:{key}',_origin='Research estimate',_confirmed='',
                _model_version=str(snapshot.get('model_version') or 'Unspecified'),
                _model_tier=str(snapshot.get('model_tier') or 'Unspecified'),
                _primary_event=str(snapshot.get('primary_event') or 'Unspecified'),
                _assessment_revision=snapshot.get('assessment_revision',0))
            estimates.append(estimate)
    if legacy is not None and not legacy.empty:
        rows=legacy.copy().reset_index(drop=True)
        rows['_upload_key']='legacy'
        rows['_filename']='Legacy saved record';rows['_origin']='Legacy saved measurement'
        rows['_confirmed']='';rows['_kind']='activity';rows['_saved_at']=''
        rows['_label']=['Legacy activity '+str(i+1) for i in rows.index]
        rows['_record_key']=['legacy:'+str(i+1) for i in rows.index]
        rows,count=clean_numeric(rows,MEASURES);rejected+=count
        observations.append(attach_dates(rows).reindex(columns=observations[0].columns if observations else FIELDS+[k for k in rows if str(k).startswith('_')]+['_plot_date','_date_precision','_date_label']))
        choices.append({'key':'legacy','filename':'Earlier saved activities','count':len(rows)})
        for index,row in legacy.reset_index(drop=True).iterrows():
            if row.get('prediction_status') in ('analysis_only','observations_only'):continue
            if not any(pd.notna(row.get(key)) for key in ESTIMATES):continue
            estimate={key:row.get(key) for key in list(ESTIMATES)+list(DATE_FIELDS)}
            estimate.update(_upload_key='legacy',_filename='Legacy saved record',_label=f'Legacy assessment {index+1}',
                _record_key=f'legacy-assessment:{index+1}',_origin='Legacy research output',_confirmed='',
                _model_version=str(row.get('model_version') or 'Legacy / unverified'),
                _model_tier=str(row.get('model_tier') or 'Unspecified'),
                _primary_event=str(row.get('primary_event') or 'Unspecified'),_assessment_revision=0)
            estimates.append(estimate)
    observed=pd.concat(observations,ignore_index=True) if observations else pd.DataFrame()
    estimated=pd.DataFrame(estimates)
    if not estimated.empty:estimated=attach_dates(clean_numeric(estimated,ESTIMATES)[0])
    return ExplorerData(observed,estimated,choices,rejected)


def available_measures(frame,catalog=MEASURES):
    return [key for key in catalog if key in frame and pd.to_numeric(frame[key],errors='coerce').notna().any()]


def value_sources(frame,field):
    source=frame.get('_origin',pd.Series('Source export',index=frame.index)).copy()
    confirmed=frame.get('_confirmed',pd.Series('',index=frame.index)).fillna('').str.split(',').map(lambda values:field in values)
    source.loc[confirmed]='Athlete confirmed'
    if field=='training_load':
        proxy=frame.get('training_load_origin',pd.Series('',index=frame.index)).fillna('').str.contains('QUTwin estimate|HR ×|heart rate ×',regex=True)
        source.loc[proxy]='Calculated load proxy'
    return source


def describe_measure(frame,field,catalog=MEASURES):
    label,unit,meaning=catalog[field]
    values=frame[field].dropna()
    if values.empty:return 'This measure is not recorded in the selected activities.'
    if len(values)==1:
        text=f'{label}: {values.iloc[0]:,.1f} {unit} in this saved observation.'
    else:
        text=f'{len(values):,} saved observations contain {label.lower()}. Values range from {values.min():,.1f} to {values.max():,.1f} {unit}.'
    unknown=int(frame.loc[values.index,'_plot_date'].isna().sum())
    if unknown==1:text+=' One observation has no activity date, so it appears in the activity comparison.'
    elif unknown:text+=f' {unknown:,} of these observations have no activity date, so they appear in the activity comparison.'
    return text+' '+meaning


def export_table(frame,catalog=MEASURES):
    if frame.empty:return pd.DataFrame()
    fields=available_measures(frame,catalog)
    extra=['training_load_origin'] if catalog is MEASURES and 'training_load' in fields else []
    if catalog is ESTIMATES:extra=['_model_version','_model_tier','_primary_event','_assessment_revision']
    result=frame.reindex(columns=['_record_key','_filename','_date_label','_date_precision','_origin','_confirmed']+extra+fields).copy()
    return result.rename(columns={'_record_key':'Record ID','_filename':'Source file','_date_label':'Activity date',
        '_date_precision':'Date precision','_origin':'Source','_confirmed':'Athlete-confirmed fields',
        'training_load_origin':'Load provenance','_model_version':'Model version','_model_tier':'Model inputs',
        '_primary_event':'Model event reference','_assessment_revision':'Assessment revision',
        **{k:f'{catalog[k][0]} ({catalog[k][1]})' for k in fields}})


@guard_athlete_read
@request_cached
def load_explorer_data(athlete_id):
    from database.workflow_repository import list_uploads
    uploads=list_uploads(athlete_id)
    if uploads:return build_explorer_data(uploads)
    from database.twin_repository import get_athlete_twin_history
    return build_explorer_data([],legacy=get_athlete_twin_history(athlete_id))
