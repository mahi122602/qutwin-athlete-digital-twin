from ui.workflow_errors import show_workflow_error
import logging
import json
import streamlit as st
from database.workflow_repository import list_uploads, get_reviews
from recommendation.llm_service import generate_for_upload, setting


def render_coach_feedback(reviews):
    for r in reviews:
        st.markdown(f"**Coach {r['coach_id']} · {r['status']}**")
        if not r.get('assessment_is_current',True):
            st.caption('This decision refers to the earlier assessment and draft, before the saved measurements were updated.')
        if r['status']=='Rejected':
            st.warning('This AI draft was rejected. It is not an approved training recommendation.')
        if r.get('final_text'):
            st.write(r['final_text'])
        if r.get('comment') and r.get('comment')!=r.get('final_text'):
            st.write(r['comment'])
        if r.get('reviewed_at'):
            st.caption(f"Reviewed: {r['reviewed_at']}")


def athlete_predictions():
    from ui.studio_shell import chapter, score_ribbon
    from ui.prediction_results import measured_session, model_details, recovery_form
    st.title('Prediction & recommendation')
    chapter('01 / UNDERSTAND & ACT', 'See what your activity tells us, what remains uncertain, and what your coach recommends.')
    athlete_id=str(st.session_state.user_id)
    try:
        # Prepare newly saved uploads; existing saved drafts are reused below.
        pending=st.session_state.pop('workflow_generate_ids',[])
        configured = bool(setting("GEMINI_API_KEY") and setting("QUTWIN_GEMINI_MODEL"))
        uploads=list_uploads(athlete_id)
        if not uploads:
            st.info('Upload activity data to create a linked prediction and recommendation. Earlier uploads remain in History.')
            return
        upload_ids = [str(item['id']) for item in uploads]
        selection_key = 'prediction_selected_upload_' + str(athlete_id)
        target = st.session_state.pop('studio_target_upload', None)
        if target is None and pending:
            target = str(pending[-1])
        if str(target) in upload_ids:
            st.session_state[selection_key] = str(target)
        if st.session_state.get(selection_key) not in upload_ids:
            st.session_state[selection_key] = upload_ids[0]
        by_id = {str(item['id']): item for item in uploads}
        selected = st.selectbox('Saved upload', upload_ids, key=selection_key,
            format_func=lambda uid: f"{by_id[uid]['uploaded_at']} · {by_id[uid]['filename']} · #{uid}")
        u = by_id[selected]; snapshot=u['snapshot']
        # Upgrade the selected saved analysis once. A model-version check alone
        # misses feature-processing fixes; the pipeline has its own revision.
        if u.get('records'):
            from research_prediction.predict import bundle, ANALYSIS_VERSION
            stale=(snapshot.get('model_version')!=bundle()['report']['version'] or
                   snapshot.get('analysis_version')!=ANALYSIS_VERSION)
            if stale and u.get('ai_status')!='generating':
                from prediction.upload_processing import update_saved_assessment
                with st.spinner('Updating the assessment from your saved measurements…'):
                    update_saved_assessment(athlete_id,u)
                u=next(row for row in list_uploads(athlete_id) if str(row['id'])==selected)
                snapshot=u['snapshot']
        if pending and configured:
            with st.spinner('Preparing your AI recommendation for coach review…'):
                for upload_id in pending:
                    generate_for_upload(athlete_id,upload_id)
            u=next((row for row in list_uploads(athlete_id) if str(row['id'])==selected),u)
            snapshot=u['snapshot']
        st.caption('Upcoming events: '+', '.join(u['events']))
        research = snapshot.get('prediction_status') == 'research_estimate'
        measured_session(snapshot)
        score_ribbon(snapshot)
        overview, advice = st.tabs(['Your summary', 'Your recommendation'])
        with overview:
            st.subheader('The useful takeaway')
            if research:
                st.write('Your activity produced a research estimate. Use the recommendation tab to read the AI draft and check your coach’s decision before acting on it.')
            else:
                st.write('Your activity measurements are available above. The model details below show exactly which inputs need attention before a numeric score can be calculated.')
            model_details(snapshot)
            recovery_form(u,athlete_id)
            if snapshot.get('activity_date_unknown'):
                st.caption('The activity date is unknown. You can add the actual time in the measurements form; the missing date does not block a single-session estimate.')
            with st.expander('Download this assessment'):
                st.download_button('Download assessment and model evidence',json.dumps(snapshot,indent=2,default=str),
                    file_name=f"QUTwin_assessment_{u['id']}.json",mime='application/json',key=f"assessment_download_{u['id']}")
        with advice:
            st.subheader('Your AI draft')
            if not u.get('ai_text') and configured and u['id'] not in pending:
                with st.spinner('Preparing your recommendation…'):
                    generate_for_upload(athlete_id, u['id'])
                u = next((row for row in list_uploads(athlete_id) if row['id'] == u['id']), u)
            if u.get('ai_text'):
                if not u.get('recommendation_is_current',True):
                    st.info('This saved draft and its coach decisions refer to the earlier assessment. They are retained for your records; they do not assess the newly added measurements.')
                    previous=u.get('recommendation_snapshot') or {}
                    if previous.get('fatigue_score') is not None:
                        st.caption(f"Earlier assessment fatigue: {previous['fatigue_score']} / 100 · {previous.get('model_version','original model')}")
                else:
                    st.caption('AI draft · Coach approval is shown below when available')
                st.write(u['ai_text'])
            elif u.get('ai_status') == 'generating':
                st.info('Your recommendation is being prepared. It will appear when you return to this page.')
            elif not configured:
                st.info('AI drafting is not configured for this deployment. Your recorded measurements and available model results are still saved. Your coach can review them.')
            elif u.get('ai_status')=='failed':
                st.warning('The AI service could not prepare this draft. Your activity and model results are saved. The app retries eligible failed requests when you return; no draft is invented.')
            else:
                st.info('Your data is saved. Recommendations are temporarily unavailable. Please check back shortly.')
            reviews = [r for r in get_reviews(athlete_id)
                       if r['upload_id'] == u['id'] and r['status'] != 'Pending']
            if reviews:
                st.subheader('Coach’s decision')
                render_coach_feedback(reviews)
    except Exception as exc:
        show_workflow_error(exc, 'Prediction')
