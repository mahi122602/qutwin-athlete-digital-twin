"""Display actionable setup errors, without exposing credentials or raw SQL."""
import logging
import streamlit as st
from database.workflow_schema import WorkflowSetupError, MIGRATION


def show_workflow_error(exc, context):
    logging.getLogger(__name__).exception('%s failed', context)
    code = getattr(exc,'pgcode',None) or getattr(exc,'code',None)
    if isinstance(exc,WorkflowSetupError):
        message = str(exc)
    elif code == '42501':
        message = 'The database role cannot read or write the workflow tables. Check table privileges and row-level-security access for the server-side connection.'
    elif code in ('42P01','42703'):
        message = 'A database table or column required by this version is missing. Run migration 005 in the database used by this app.'
    elif isinstance(exc, ModuleNotFoundError):
        message = 'A required Python package is missing. In your project terminal run: python -m pip install -r requirements.txt, then restart with python -m streamlit run app.py.'
    elif type(exc).__name__ in ('OperationalError','InterfaceError','PoolError'):
        message = 'The app could not reach the database. Check the existing Supabase connection settings and database availability. Your connection settings were not changed by this update.'
    else:
        message = f'{context} could not finish ({type(exc).__name__}). The server terminal contains the exact traceback; share its final error line without any credentials.'
    st.error(message)
    if code:
        st.caption(f'Diagnostic code: {code}')
    with st.expander('Database setup and recovery'):
        st.write('The app tries to create missing workflow tables automatically. If your database role cannot do that, run the migration below in Supabase → SQL Editor, then retry.')
        st.download_button('Download migration 005',MIGRATION.read_bytes(),
                           '005_upload_review_workflow.sql','text/plain',key=f'{context}_migration')
        st.code('python -m utils.check_workflow\npython -m streamlit run app.py',language='powershell')
