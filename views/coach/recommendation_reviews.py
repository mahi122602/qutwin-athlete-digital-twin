from ui.workflow_errors import show_workflow_error
import logging
import streamlit as st
from database.workflow_repository import coach_queue, review_recommendation


def recommendation_reviews():
    st.title('Recommendation Reviews')
    st.caption('Review AI drafts for your assigned athletes. Each decision belongs to one upload.')
    try:
        queue=coach_queue(str(st.session_state.user_id))
        if not queue:
            st.info('No AI recommendations to review yet.'); return
        for r in queue:
            with st.expander(f"{r['athlete_id']} · {r['filename']} · {r['status']} · #{r['upload_id']}",expanded=r['status']=='Pending'):
                st.caption(f"Uploaded {r['uploaded_at']} · Events: {', '.join(r['events'])}")
                snap=r['snapshot']
                if snap.get('prediction_status') == 'research_estimate':
                    st.warning('Experimental estimates with imputed inputs; not validated injury probabilities.')
                    st.caption(snap.get('risk_validation_warning', ''))
                    st.caption('Model-only imputations and event support:')
                    st.write(snap.get('imputed_model_inputs', {}))
                    st.write(snap.get('event_scenarios', []))
                st.write({'Fatigue':snap.get('fatigue_score'),'Injury risk':snap.get('injury_risk'),'Missing inputs':snap.get('missing_inputs',[])})
                st.markdown('**AI draft**'); st.write(r['ai_text'])
                if r['status']=='Pending':
                    with st.form(f"coach_review_{r['id']}"):
                        decision=st.radio('Decision',['Approved','Modified','Rejected'],horizontal=True)
                        comment=st.text_area('Coach notes / revised recommendation',help='For Modified, enter the full replacement recommendation. For Rejected, enter your reason.')
                        submitted=st.form_submit_button('Send decision to athlete')
                    if submitted:
                        try:
                            review_recommendation(st.session_state.user_id,r['id'],decision,comment)
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.success('Decision saved and athlete notified.'); st.rerun()
                else:
                    st.write(r.get('final_text') or r.get('comment') or r['status'])
                    st.caption(f"Reviewed {r['reviewed_at']}")
    except Exception as exc:
        show_workflow_error(exc, 'Coach reviews')
