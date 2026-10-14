"""Safe coach error details and read-only checks against the app's database."""
import logging
import re
import traceback


# Only structural names from this app's existing SQL are shown in the UI.
REQUIRED_COLUMNS = {
    'coaches': {'coach_id', 'name'},
    'athletes': {'athlete_id', 'name'},
    'coach_athlete_mapping': {'coach_id', 'athlete_id'},
    'qutwin_processed_uploads': {
        'id', 'athlete_id', 'filename', 'uploaded_at', 'snapshot', 'ai_status'},
    'qutwin_coach_teams': {'id', 'coach_id', 'name', 'description'},
    'qutwin_team_members': {'team_id', 'coach_id', 'athlete_id'},
    'qutwin_coach_profiles': {'coach_id', 'email', 'organisation', 'specialties'},
    'qutwin_recommendation_reviews': {'id', 'upload_id', 'coach_id', 'status'},
}

GUIDANCE = {
    '42P01': 'A required database table could not be found. Check database setup below to identify it.',
    '42703': 'A database column expected by the code is missing. Check database setup below.',
    '42501': 'The app database role does not have permission for this operation. Check its table permissions; keep access restricted to the server.',
    '42883': 'The query uses an incompatible database type or an unavailable function. The table check alone cannot resolve this; the server traceback is needed.',
    '42804': 'The query and stored database column types do not agree. The server traceback identifies the affected operation.',
    '08001': 'The app could not connect to its database. Check the running app database configuration.',
    '08006': 'The database connection failed. Check connectivity and the running app database configuration.',
    '28P01': 'Database authentication failed. Check the password in the running app configuration.',
}


def safe_error_details(exc):
    """Never render the raw exception, query, connection URL or record values."""
    kind = type(exc).__name__
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,80}', kind):
        kind = 'Exception'
    state = getattr(exc, 'pgcode', None) or getattr(exc, 'sqlstate', None) or getattr(exc, 'code', None)
    if state is None and exc.__cause__ is not None:
        state = getattr(exc.__cause__, 'pgcode', None)
    state = state if isinstance(state, str) and re.fullmatch(r'[A-Z0-9]{5}', state) else None
    details = {'Error type': kind}
    if state:
        details['Database code'] = state
    diag = getattr(exc, 'diag', None)
    table = getattr(diag, 'table_name', None)
    column = getattr(diag, 'column_name', None)
    if table not in REQUIRED_COLUMNS and state == '42P01':
        # PostgreSQL often omits diag.table_name for an UndefinedTable error.
        match = re.search(r'relation "(?:public\.)?([a-z_]+)" does not exist', str(exc))
        table = match.group(1) if match else None
    if table in REQUIRED_COLUMNS:
        details['Table'] = table
    known_columns = set().union(*REQUIRED_COLUMNS.values())
    if column in known_columns:
        details['Column'] = column
    known_files = (
        'views/coach/studio.py', 'database/coach_studio.py',
        'database/coach_identity.py', 'database/workflow_repository.py',
        'database/connection.py', 'database/twin_repository.py',
        'database/connection_request_repository.py', 'utils/performance.py',
    )
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        path = frame.filename.replace('\\', '/')
        relative = next((name for name in known_files if path.endswith('/' + name)), None)
        if relative:
            details['Code location'] = f'{relative}:{frame.lineno}'
            break
    hint = GUIDANCE.get(state)
    if type(exc).__name__ in ('WorkflowSetupError', 'CoachSetupError'):
        hint = str(exc)  # These classes contain only controlled setup guidance.
    if not hint:
        hint = ('A required Python package is unavailable. Install the project requirements and restart.'
                if isinstance(exc, ModuleNotFoundError) else
                'This error is not identified by the migration warning. Use the server traceback to locate the failing operation.')
    return details, hint


def database_setup_report():
    """SELECT only; use the very same connection helper as the running app."""
    from database.connection import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT requested.table_name,
                    to_regclass('public.' || requested.table_name) IS NOT NULL,
                    CASE WHEN to_regclass('public.' || requested.table_name) IS NULL
                        THEN FALSE
                        ELSE has_table_privilege(
                            to_regclass('public.' || requested.table_name), 'SELECT')
                    END,
                    ARRAY(SELECT attname::text FROM pg_attribute
                        WHERE attrelid=to_regclass('public.' || requested.table_name)
                          AND attnum>0 AND NOT attisdropped)
                FROM unnest(%s::text[]) AS requested(table_name)
                ORDER BY requested.table_name
            ''', (list(REQUIRED_COLUMNS),))
            result = []
            for table, exists, readable, columns in cur.fetchall():
                missing = sorted(REQUIRED_COLUMNS[table] - set(columns or [])) if exists else []
                result.append({
                    'Table': table,
                    'Exists': bool(exists),
                    'Can read': bool(readable),
                    'Missing columns': ', '.join(missing) if missing else '',
                    'Status': 'Missing table' if not exists else 'Cannot read' if not readable
                              else 'Missing columns' if missing else 'Ready',
                })
            return result
    finally:
        conn.close()


def show_coach_error(exc, context='page'):
    import streamlit as st
    logging.getLogger(__name__).exception('Coach studio operation failed (%s)', context)
    details, hint = safe_error_details(exc)
    st.error('This coach ' + context + ' could not be loaded or saved. See the troubleshooting details below.')
    with st.expander('Troubleshooting details', expanded=True):
        st.code('\n'.join(f'{key}: {value}' for key, value in details.items()), language='text')
        st.write(hint)
        if st.button('Check database setup', key='coach_db_check_' + context):
            try:
                with st.spinner('Checking the database used by this running app…'):
                    report = database_setup_report()
            except Exception as check_error:
                check_details, check_hint = safe_error_details(check_error)
                st.warning('The database check could not be completed.')
                st.code('\n'.join(f'{key}: {value}' for key, value in check_details.items()), language='text')
                st.write(check_hint)
            else:
                st.dataframe(report, hide_index=True, use_container_width=True)
                problems = [row for row in report if row['Status'] != 'Ready']
                if not problems:
                    st.info('The checked tables and columns are present and readable. This does not test every query or write operation; the original error details and server traceback are still needed.')
                elif any(row['Table'] in {'qutwin_coach_profiles', 'qutwin_coach_teams', 'qutwin_team_members'}
                         and row['Status'] == 'Missing table' for row in problems):
                    st.write('The coach migration is missing tables in the database this app is using. Apply database/migrations/008_coach_studio.sql to that same database.')
                else:
                    st.write('The check identifies a missing earlier workflow table, a missing column, or a permissions problem. Migration 008 creates only the three coach tables and does not repair every earlier schema issue.')
