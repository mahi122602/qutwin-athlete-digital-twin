import logging
import streamlit as st
from database.account_privacy import connected_coaches,disconnect_coach,delete_my_account

def render_connections():
    st.subheader('Your coaching circle')
    st.caption('Connected coaches can view your shared activity and assessments. Disconnecting removes their future access through QUTwin; it cannot recall copies they already downloaded.')
    try:coaches=connected_coaches()
    except Exception:st.error('Your coach connections could not be loaded. Please try again.');return
    if not coaches:st.info('You have no connected coaches. Send a request or accept an invitation below.')
    for coach_id,name in coaches:
        with st.container(border=True):
            st.write(f'**{name}** · {coach_id}')
            with st.expander('Manage this connection'):
                ok=st.checkbox('Disconnect this coach and revoke access to my data',key=f'disconnect_confirm_{coach_id}')
                if st.button('Disconnect coach',key=f'disconnect_{coach_id}',disabled=not ok):
                    try:disconnect_coach(coach_id)
                    except Exception:st.error('Disconnection failed. Your connection has not been confirmed as removed.')
                    else:st.rerun()

def render_delete_account():
    st.divider()
    with st.expander('Delete my account permanently'):
        st.warning('This removes your profile, uploaded activity records, predictions, AI drafts, coach reviews, saved forecasts, period records and coach connections from the active QUTwin database. You cannot undo this in the app.')
        st.caption('Closing the app or logging out does not delete your account. Provider backups and copies previously downloaded or sent to an AI provider are not erased by this action; the operator must handle their retention separately.')
        with st.form('delete_account_confirmation',clear_on_submit=True):
            password=st.text_input('Current password',type='password')
            confirmation=st.text_input('Type DELETE to confirm')
            consent=st.checkbox('I understand that I cannot restore my account in QUTwin.')
            submitted=st.form_submit_button('Permanently delete my account')
        if submitted:
            if not consent or confirmation!='DELETE':st.error('Confirm the checkbox and type DELETE to continue.');return
            try:delete_my_account(password,confirmation)
            except ValueError as exc:st.error(str(exc));return
            except Exception:
                logging.getLogger(__name__).exception('Account deletion failed')
                st.error('Deletion could not be completed. The database transaction was rolled back. Contact the app administrator.');return
            st.cache_data.clear()
            st.session_state.clear()
            st.session_state['account_deleted_notice']=True
            st.rerun()
