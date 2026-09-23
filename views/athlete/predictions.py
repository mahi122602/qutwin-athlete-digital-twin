from ui.workflow_errors import show_workflow_error
import logging
import streamlit as st
from database.workflow_repository import list_uploads, get_reviews
from recommendation.llm_service import generate_for_upload, setting
from ui.prediction_guidance import render_guidance


def render_coach_feedback(reviews):
    if not reviews:
        st.info('No coach feedback yet. An AI draft must first be generated and sent to your assigned coach. Their approval, changes or rejection will appear here after review.')
    for r in reviews:
        st.markdown(f"**Coach {r['coach_id']} · {r['status']}**")
        if r['status']=='Rejected':
            st.warning('This AI draft was rejected. It is not an approved training recommendation.')
        if r.get('final_text'):
            st.write(r['final_text'])
        if r.get('comment') and r.get('comment')!=r.get('final_text'):
            st.write(r['comment'])
        if r.get('reviewed_at'):
            st.caption(f"Reviewed: {r['reviewed_at']}")


def athlete_predictions():
    st.title('Predictions & Coach Recommendations')
    st.caption('Upload analysis · adaptive-v2')
    athlete_id=str(st.session_state.user_id)
    try:
        # Only new submissions trigger generation automatically, never normal navigation.
        pending=st.session_state.pop('workflow_generate_ids',[])
        if pending:
            with st.spinner('Preparing your AI recommendation for coach review…'):
                for upload_id in pending:
                    generate_for_upload(athlete_id,upload_id)
        uploads=list_uploads(athlete_id)
        if not uploads:
            st.info('Upload activity data to create a linked prediction and recommendation. Earlier uploads remain in History.')
            return
        index=st.selectbox('Saved upload',range(len(uploads)),format_func=lambda i:f"{uploads[i]['uploaded_at']} · {uploads[i]['filename']} · #{uploads[i]['id']}")
        u=uploads[index]; snapshot=u['snapshot']
        st.caption('Events: '+', '.join(u['events']))
        if not u.get('ai_text') and snapshot.get('model_version') != 'adaptive-v2':
            st.info('This saved file can be re-analysed with the updated analysis pipeline. Its original upload date and measurements are retained.')
            if st.button('Recalculate this saved upload', key=f"recalculate_{u['id']}"):
                from prediction.upload_processing import recalculate_saved
                with st.spinner('Analysing saved measurements…'):
                    recalculate_saved(athlete_id, u)
                st.session_state['workflow_generate_ids'] = [u['id']]
                st.rerun()
        research = snapshot.get('prediction_status') == 'research_estimate'
        if research:
            st.warning('Experimental research estimates. The app selects a model for the available measurements; no missing measurements are invented. Injury categories are exploratory, not validated injury probabilities.')
            st.warning(snapshot.get('risk_validation_warning', 'Injury classification requires external validation.'))
        if snapshot.get('observation_record_count'):
            st.caption(f"{snapshot['observation_record_count']} source records saved. "+snapshot.get('assessment_scope','Cards assess the latest activity.'))
        measured=[]
        for label,key,unit in [('Heart rate','heart_rate','bpm'),('Duration','duration_minutes','min'),('Training load','training_load','AU')]:
            if snapshot.get(key) is not None:measured.append(f"{label}: {snapshot[key]:.2f} {unit}" if isinstance(snapshot[key],(float,int)) else f"{label}: {snapshot[key]} {unit}")
        if measured:st.caption(' · '.join(measured))
        cols=st.columns(4) if any(snapshot.get(k) is not None for k in ('fatigue_score','injury_risk','readiness_score','twin_score')) else []
        for col,(label,key) in zip(cols,[('Fatigue','fatigue_score'),('Injury risk','injury_risk'),('Readiness','readiness_score'),('Twin score','twin_score')]):
            col.metric(('Exploratory ' if key=='injury_risk' else 'Estimated ') + label.lower() if research else label, snapshot.get(key) if snapshot.get(key) is not None else 'Insufficient evidence')
        render_guidance(snapshot, u['events'])
        if snapshot.get('analysis'):
            with st.expander('Technical details: features and data quality', expanded=False):
                st.write(snapshot['analysis'])
                if snapshot.get('imputed_model_inputs'):
                    st.write('Training-set median values used only inside the research model:')
                    st.json(snapshot['imputed_model_inputs'])
                st.caption('Imputation is an estimate, not a measurement. Personal time trends use only earlier dated observations.')
        if snapshot.get('event_scenarios'):
            st.write('Selected-event coverage')
            st.dataframe(snapshot['event_scenarios'], hide_index=True, use_container_width=True)
            st.caption('The training data contains only 100 m and 800 m events. Other events contribute to AI advice; their event-specific numeric scores are left blank. Selecting several events does not multiply or duplicate the uploaded workload.')
        if research:
            with st.expander('Model validation and limitations'):
                st.json(snapshot.get('validation_metrics', {}))
                st.write(snapshot.get('model_limitations', []))
                st.caption('Metrics use held-out athletes in the supplied research dataset. Metrics below are for the selected input tier on an untouched athlete holdout, not all file types or all sports. Composite readiness, Twin and health scores are engineered indices, not separately validated targets.')
        if snapshot.get('model_tier'):
            st.caption('Input tier: '+snapshot['model_tier'].replace('_',' ')+' · '+', '.join(snapshot.get('used_model_inputs',[])))
        if snapshot.get('analysis'):
            st.subheader('Activity analysis')
            features=snapshot['analysis'].get('features',{})
            if features:st.dataframe([{'Feature':k.replace('_',' '),'Value':round(v,3) if isinstance(v,(int,float)) else v} for k,v in features.items()],hide_index=True,use_container_width=True)
            state=snapshot.get('personal_state',{})
            if state.get('status')=='available':
                with st.expander('Personal time trend and state estimate'):st.json(state)
        if not research and snapshot.get('missing_inputs'):
            from ui.prediction_guidance import LABELS
            st.caption('Measurements not supplied: ' + ', '.join(LABELS.get(k,k.replace('_',' ')) for k in snapshot['missing_inputs']))
        st.subheader('1. AI-generated recommendation')
        if not setting('GEMINI_API_KEY') or not setting('QUTWIN_GEMINI_MODEL'):
            st.info('AI recommendations are not available because the app’s AI connection is not configured. This is an app setup issue, not an error in your uploaded file. Ask the app administrator to configure the service. If you manage this app, use the setup section below.')
        with st.expander('Configure AI for this session'):
            with st.form('workflow_ai_setup'):
                key_value = st.text_input('Gemini API key', type='password')
                model_value = st.text_input('Model ID', value=setting('QUTWIN_GEMINI_MODEL') or 'gemini-2.5-flash-lite')
                submitted = st.form_submit_button('Save session settings')
            if submitted:
                if not key_value.strip() or not model_value.strip():
                    st.error('Enter both an API key and a model ID.')
                else:
                    st.session_state['workflow_GEMINI_API_KEY'] = key_value.strip()
                    st.session_state['workflow_QUTWIN_GEMINI_MODEL'] = model_value.strip()
                    st.rerun()
            st.caption('Used for API requests only; not stored in upload records. Usage follows the Google project’s quota and billing tier. Clear the settings below when finished.')
            if st.button('Clear session AI settings'):
                st.session_state.pop('workflow_GEMINI_API_KEY', None)
                st.session_state.pop('workflow_QUTWIN_GEMINI_MODEL', None)
                st.rerun()
        if u.get('ai_text'):
            st.caption(f"Generated with {u['ai_model']} · Draft awaiting coach review unless approved below")
            st.write(u['ai_text'])
        else:
            if u.get('ai_error') and setting('GEMINI_API_KEY') and setting('QUTWIN_GEMINI_MODEL'):
                st.warning(u['ai_error'])
            if setting('GEMINI_API_KEY') and setting('QUTWIN_GEMINI_MODEL'):
                st.info('The AI recommendation has not been generated. Click Generate / retry below. If it fails again, ask the app administrator to check model access and account quota; your saved data will remain available.')
            if st.button('Generate / retry AI recommendation',key=f"retry_ai_{u['id']}"):
                with st.spinner('Generating recommendation…'):
                    generate_for_upload(athlete_id,u['id'])
                st.rerun()
        st.subheader('2. Recommendation from coach')
        render_coach_feedback([r for r in get_reviews(athlete_id) if r['upload_id']==u['id']])
    except Exception as exc:
        show_workflow_error(exc, 'Prediction')
