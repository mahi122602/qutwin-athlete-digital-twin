from ui.workflow_errors import show_workflow_error
import logging
import streamlit as st
from database.workflow_repository import list_uploads, get_reviews
from recommendation.llm_service import generate_for_upload, setting


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
    from ui.studio_shell import chapter, score_ribbon
    st.title('Prediction & recommendation')
    chapter('01 / UNDERSTAND & ACT', 'See what your activity tells us, what remains uncertain, and what your coach recommends.')
    athlete_id=str(st.session_state.user_id)
    try:
        # Prepare newly saved uploads; existing saved drafts are reused below.
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
        st.caption('Upcoming events: '+', '.join(u['events']))
        if not u.get('ai_text') and snapshot.get('model_version') != 'adaptive-v2':
            st.info('This saved file can be re-analysed with the updated analysis pipeline. Its original upload date and measurements are retained.')
            if st.button('Recalculate this saved upload', key=f"recalculate_{u['id']}"):
                from prediction.upload_processing import recalculate_saved
                with st.spinner('Analysing saved measurements…'):
                    recalculate_saved(athlete_id, u)
                st.session_state['workflow_generate_ids'] = [u['id']]
                st.rerun()
        research = snapshot.get('prediction_status') == 'research_estimate'
        score_ribbon(snapshot)
        overview, advice = st.tabs(['Your summary', 'Your recommendation'])
        with overview:
            st.subheader('The useful takeaway')
            if research:
                st.write('Your activity produced a research estimate. Use the recommendation tab to read the AI draft and check your coach’s decision before acting on it.')
            else:
                st.write('Your recorded measurements are saved. Where there is not enough evidence for a score, the app explains what is missing instead of substituting an older result.')
            if snapshot.get('activity_date_unknown'):
                st.caption('Add the activity date in Add activity when you know it to include this session in your timeline.')
            if not research and snapshot.get('missing_inputs'):
                from ui.prediction_guidance import LABELS
                names = list(dict.fromkeys(LABELS.get(k, k.replace('_', ' ')) for k in snapshot['missing_inputs']))
                st.info('For a fuller assessment, add known measurements in Add activity: ' + ', '.join(names) + '. Leave anything unknown blank.')
        with advice:
            st.subheader('Your AI draft')
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
            reviews = [r for r in get_reviews(athlete_id)
                       if r['upload_id'] == u['id'] and r['status'] != 'Pending']
            if reviews:
                st.subheader('Coach’s decision')
                render_coach_feedback(reviews)
    except Exception as exc:
        show_workflow_error(exc, 'Prediction')
