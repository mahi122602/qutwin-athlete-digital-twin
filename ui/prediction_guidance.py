"""User-facing explanations; model limits must never be called invalid input."""
import json
from pathlib import Path

LABELS={'training_load':'training load','heart_rate':'average heart rate','duration_minutes':'activity duration',
        'sleep_hours':'sleep duration','recovery_time':'recovery time','temperature':'temperature',
        'humidity':'humidity','hydration_score':'hydration','hydration_level':'hydration','previous_injury':'injury history'}

def prediction_guidance(snapshot, events):
    messages=[]
    outside=snapshot.get('outside_training_range') or []
    if outside:
        report=json.loads((Path(__file__).resolve().parents[1]/'research_prediction/validation.json').read_text())
        parts=[]
        for field in outside:
            value=snapshot.get(field, snapshot.get('analysis',{}).get('features',{}).get(field))
            bounds=report.get('ranges',{}).get(field)
            detail=f"{LABELS.get(field,field.replace('_',' '))}: {value}"
            if bounds:detail+=f" (model training range: {bounds[0]:g}–{bounds[1]:g})"
            parts.append(detail)
        messages.append(('warning','Your file was saved, but this model cannot assess this activity.',
            'Outside the model’s supported range: '+ '; '.join(parts)+'.',
            'On Upload Data, check the mapped columns and units against the original file, especially heart rate and duration. Correct only genuine mistakes. If the measurements are correct, keep them: a model trained for this activity and workload is needed. Changing event selections or repeatedly recalculating will not fix this limitation.'))
    elif snapshot.get('prediction_status') in ('analysis_only','observations_only'):
        messages.append(('warning','Your file was saved, but there is not enough usable information for a score.',
            'This research model needs a usable training-load value, or average heart rate and duration from which the app can derive an estimate.',
            'On Upload Data, review column mapping and units. Upload an activity-session export with those measurements, or enter only values you actually know. Do not guess missing measurements.'))
    if snapshot.get('activity_date_unknown'):
        messages.append(('info','The activity date is missing or was not recognised.',
            'The file’s saved date is available, but it does not tell us when the activity happened.',
            'Map the activity date/time column in Upload Data, check its date format and timezone, or enter the known activity timestamp. This is needed for time trends; it is separate from the model-range problem.'))
    unsupported=[e for e in events if e not in ('100 m','800 m')]
    if unsupported:
        messages.append(('info','Some selected events do not have a trained event-specific model.',
            'Events: '+', '.join(unsupported)+'. The current training dataset covers only 100 m and 800 m.',
            'Keep your real event selections. Selecting multiple events is allowed; choosing a different event just to obtain a score would misrepresent your data. These events need suitable training data before event-specific predictions are supported.'))
    return messages

def render_guidance(snapshot,events):
    import streamlit as st
    for level,title,reason,action in prediction_guidance(snapshot,events):
        getattr(st,level)(f'**{title}**\n\n{reason}\n\n**What to do:** {action}')
