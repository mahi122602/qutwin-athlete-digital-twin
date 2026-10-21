"""Measured session details and an actionable explanation of model eligibility."""
import math
import pandas as pd
import streamlit as st
from ui.prediction_guidance import LABELS

TIER_LABELS={'complete':'Full measurement set','load_recovery':'Load + recovery measurements',
             'recovery':'Recovery measurements','load_sleep':'Load + sleep',
             'load_rest':'Load + recovery time','sleep_rest':'Sleep + recovery time',
             'load_only':'Load only'}


def number(value):
    try:
        value=float(value)
        return value if math.isfinite(value) else None
    except (TypeError,ValueError):
        return None


def measured_session(snapshot):
    definitions=[('duration_minutes','Activity duration','min'),('distance','Distance','km'),
                 ('heart_rate','Average exercise HR','bpm'),('training_load','Activity load',''),
                 ('steps','Steps',''),('calories','Energy','kcal')]
    items=[(key,label,unit,number(snapshot.get(key))) for key,label,unit in definitions]
    items=[item for item in items if item[3] is not None]
    if not items:
        return
    with st.container(border=True):
        st.subheader('Recorded activity')
        for col,(key,label,unit,value) in zip(st.columns(min(len(items),4)),items[:4]):
            col.metric(label,f'{value:,.1f}'+(' '+unit if unit else ''))
        load_origin=snapshot.get('training_load_origin') or snapshot.get('load_provenance')
        if number(snapshot.get('training_load')) is not None and load_origin:
            st.caption('Load source: '+str(load_origin))
        st.caption('These values belong to the selected activity. Load calculated from HR and duration is an estimate, not a vendor measurement.')


def model_details(snapshot):
    estimated=snapshot.get('prediction_status')=='research_estimate'
    outside=snapshot.get('outside_training_range') or []
    if not estimated:
        if outside:
            st.warning('A model input is outside the range represented in training. Your activity is saved; the measured values are shown above. Add known recovery measurements below to check another evaluated model.')
        else:
            st.info('This activity needs a supported set of measurements for numeric scores. One activity is enough; uploading duplicate files will not supply missing measurements.')
    else:
        tier=TIER_LABELS.get(snapshot.get('model_tier'),snapshot.get('model_tier','Research model'))
        mae=number(snapshot.get('validation_metrics',{}).get('fatigue_mae'))
        st.caption('Model: '+tier+' · '+str(snapshot.get('model_version',''))+
                   (f' · Held-out fatigue MAE {mae:.2f} points / 100' if mae is not None else ''))
        st.caption('Research estimate. Readiness is a calculated index; the injury category is exploratory. Accuracy on external wearable data is unverified.')
    with st.expander('How this assessment was calculated',expanded=not estimated):
        eligibility=snapshot.get('model_eligibility') or []
        rows=[]
        for spec in eligibility:
            if not spec.get('enabled',True):
                continue
            gaps=[]
            if spec.get('missing'):
                gaps.append('Missing: '+', '.join(LABELS.get(k,k.replace('_',' ')) for k in spec['missing']))
            for item in spec.get('outside_range',[]):
                gaps.append(f"{LABELS.get(item['field'],item['field'])}: {item['value']:.2f}; trained range {item['minimum']:g}–{item['maximum']:g}")
            rows.append({'Model inputs':TIER_LABELS.get(spec['tier'],spec['tier']),
                         'Status':'Used' if spec['tier']==snapshot.get('model_tier') else 'Available' if spec['eligible'] else 'Needs inputs',
                         'Details':'; '.join(gaps) or 'All required values are present and within the trained ranges.'})
        if rows:
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        if snapshot.get('used_model_inputs'):
            st.write('Inputs used: '+', '.join(LABELS.get(k,k) for k in snapshot['used_model_inputs']))
        if snapshot.get('event_basis'):
            st.write(snapshot['event_basis'])
        if snapshot.get('load_scale_unverified'):
            st.caption('The research dataset does not document its load scale. Matching a numeric range does not establish equivalence to wearable load.')
        if snapshot.get('risk_validation_warning'):
            st.caption(snapshot['risk_validation_warning'])
        st.caption('Real measurements are retained at their actual values. Inputs outside model coverage are not reduced or clamped to obtain a score.')


def recovery_form(upload,athlete_id):
    if not upload.get('records'):
        return
    from prediction.upload_processing import update_saved_assessment
    snapshot=upload['snapshot'];prefix=f"assessment_{athlete_id}_{upload['id']}_"
    with st.expander('Add known recovery measurements',expanded=snapshot.get('prediction_status')!='research_estimate'):
        st.write('Enter measurements for the activity selected above. Leave unknown values blank. Sleep and recovery time together can use the new partial model even when activity load is outside its trained range.')
        with st.form(prefix+'form'):
            cols=st.columns(2)
            fields={}
            for i,(key,label,maximum) in enumerate([
                ('sleep_hours','Sleep duration before this activity (hours)',24.),
                ('recovery_time','Recovery time for this activity (hours, as recorded)',720.),
                ('temperature','Recorded activity temperature (°C)',65.),
                ('humidity','Recorded relative humidity (%)',100.)]):
                value=number(snapshot.get(key))
                with cols[i%2]:
                    fields[key]=st.number_input(label,min_value=-60. if key=='temperature' else 0.,max_value=maximum,
                        value=value,step=.1,key=prefix+key,placeholder='Unknown')
            hydration=str(snapshot.get('hydration_level') or 'Unknown').title()
            choices=['Unknown','Low','Medium','High']
            fields['hydration_level']=st.selectbox('Hydration recorded for this activity',choices,
                index=choices.index(hydration) if hydration in choices else 0,key=prefix+'hydration')
            if fields['hydration_level']=='Unknown':fields['hydration_level']=None
            current_time=(snapshot.get('assessment_inputs') or {}).get('timestamp','')
            activity_time=st.text_input('Actual activity start time (optional, include timezone offset)',value=current_time,
                placeholder='2026-10-20T06:30:00+10:00',key=prefix+'timestamp')
            if activity_time.strip():fields['timestamp']=activity_time.strip()
            st.caption('For files with several activities, these additional measurements apply only to the latest activity being assessed. Dates help trends; a date is not required for a single-session score.')
            submitted=st.form_submit_button('Save measurements and update assessment',type='primary')
        if submitted:
            try:
                with st.spinner('Running the models on your saved activity…'):
                    update_saved_assessment(athlete_id,upload,inputs={k:v for k,v in fields.items() if v is not None})
                st.session_state[prefix+'updated']=True
                st.rerun()
            except (ValueError,PermissionError) as exc:
                st.warning(str(exc))
        if st.session_state.pop(prefix+'updated',False):
            st.success('Assessment updated. Your original activity and any earlier recommendation remain saved.')
