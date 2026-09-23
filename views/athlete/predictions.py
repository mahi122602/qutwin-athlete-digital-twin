from ui.workflow_errors import show_workflow_error
import logging
import streamlit as st
from database.workflow_repository import list_uploads, get_reviews
from recommendation.llm_service import generate_for_upload, setting
from ui.prediction_guidance import render_guidance


def render_coach_feedback(reviews):
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
        # Generate newly saved files using server settings only.
        pending=st.session_state.pop('workflow_generate_ids',[])
        configured = bool(setting("GEMINI_API_KEY") and setting("QUTWIN_GEMINI_MODEL"))
        if pending and configured:
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
        if not u.get('ai_text') and configured and u['id'] not in pending:
            with st.spinner('Preparing your recommendation…'):
                generate_for_upload(athlete_id, u['id'])
            u = next((row for row in list_uploads(athlete_id) if row['id'] == u['id']), u)
        if u.get('ai_text'):
            st.caption('AI draft · Coach approval is shown below when available')
            st.write(u['ai_text'])
        elif u.get('ai_status') == 'generating':
            st.info('Your recommendation is being prepared. It will appear when you return to this page.')
        else:
            st.info('Your data is saved. Recommendations are temporarily unavailable. Please check back shortly.')
            logging.getLogger(__name__).warning(
                'Recommendation unavailable: server_configured=%s status=%s',
                configured, u.get('ai_status', 'pending'))
        reviews = [r for r in get_reviews(athlete_id)
                   if r['upload_id'] == u['id'] and r['status'] != 'Pending']
        if reviews:
            st.subheader('2. Recommendation from coach')
            render_coach_feedback(reviews)
    except Exception as exc:
        show_workflow_error(exc, 'Prediction')
