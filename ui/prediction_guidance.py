"""Distinguish invalid input, missing measurements and unvalidated model coverage."""
LABELS={'training_load':'training load','heart_rate':'average exercise heart rate','duration_minutes':'activity duration',
        'sleep_hours':'sleep duration','recovery_time':'recovery time','temperature':'temperature',
        'humidity':'humidity','hydration_score':'hydration','hydration_level':'hydration','previous_injury':'injury history'}

def prediction_guidance(snapshot,events):
    messages=[];estimated=snapshot.get('prediction_status')=='research_estimate'
    outside=snapshot.get('outside_training_range') or []
    if outside:
        detail=', '.join(LABELS.get(k,k.replace('_',' ')) for k in outside)
        messages.append(('info' if estimated else 'warning','Some measurements are outside model coverage.',
          detail+('. A separately evaluated input set was used; these measurements were excluded from its score.' if estimated else '. Your activity measurements are saved, but the model cannot reliably score this input set.'),
          'Check the source columns and units. If the values are correct, keep them. Model coverage is an app limitation; changing your event or reducing a real measurement is not a correction.'))
    elif not estimated and snapshot.get('prediction_status') in ('analysis_only','observations_only'):
        messages.append(('info','Your activity analysis is saved; a numeric estimate is not supported yet.',
          'Available models need training load, or sleep duration together with recovery time and hydration. Steps, GPS or a sport label alone do not provide those inputs.',
          'Review mapped fields and units or add measurements you actually know. The AI can still explain the available activity data and the questions your coach needs to resolve.'))
    if snapshot.get('load_scale_unverified'):
        messages.append(('info','Training-load compatibility is unverified.',
          'The supplied research dataset does not define its training-load scale. An imported load or heart-rate × duration proxy has not been validated as equivalent.',
          'Treat the displayed values as research estimates. The project needs a documented training-load definition and matching training data before claiming accurate wearable predictions.'))
    if snapshot.get('activity_date_unknown'):
        messages.append(('info','The activity date is missing or was not recognised.',
          'The upload date is saved for History. Activity trends need the date the exercise actually happened.',
          'On Upload Data, use Add missing activity date when available. For multi-activity exports, include dates in the original file.'))
    unsupported=[e for e in events if e not in ('100 m','800 m')]
    if unsupported:
        messages.append(('info','Selected events are included in AI advice.',
          ', '.join(unsupported)+' have no event-specific numerical model in the supplied dataset. A general research estimate, when available, is not a score validated for those events.',
          'Keep your actual events. Multiple selections are allowed and do not duplicate your workload. Event-specific numeric predictions need suitable labelled training examples.'))
    return messages

def render_guidance(snapshot,events):
    import streamlit as st
    for level,title,reason,action in prediction_guidance(snapshot,events):
        getattr(st,level)(f'**{title}**\n\n{reason}\n\n**What to do:** {action}')
