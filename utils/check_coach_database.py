"""Check the configured coach database; use --setup to prepare migrations 005/008."""
import argparse
import sys

FEATURES = {
    'coaches': ('Coach accounts', {'coach_id', 'name'}, None),
    'athletes': ('Individual athlete accounts', {'athlete_id', 'name'}, None),
    'coach_athlete_mapping': ('Coach/athlete connections', {'coach_id', 'athlete_id'}, 'mapping_id'),
    'connection_requests': ('Connection requests', {'request_id', 'coach_id', 'athlete_id', 'status'}, 'request_id'),
    'notifications': ('Notifications and read status', {'notification_id', 'recipient_role', 'recipient_id', 'is_read'}, 'notification_id'),
    'uploaded_files': ('Upload metadata', {'upload_id', 'athlete_id', 'filename'}, 'upload_id'),
    'digital_athlete_state': ('Athlete activity and twin history', {'state_id', 'athlete_id'}, 'state_id'),
    'qutwin_processed_uploads': ('Processed uploads and AI drafts', {'id', 'athlete_id', 'records', 'snapshot', 'events', 'ai_text'}, 'id'),
    'qutwin_recommendation_reviews': ('Coach decisions and feedback', {'id', 'upload_id', 'coach_id', 'status', 'final_text'}, 'id'),
    'qutwin_coach_profiles': ('Coach profile details', {'coach_id', 'email', 'organisation', 'specialties'}, None),
    'qutwin_coach_teams': ('Teams and descriptions', {'id', 'coach_id', 'name', 'description'}, 'id'),
    'qutwin_team_members': ('Team membership', {'team_id', 'coach_id', 'athlete_id'}, None),
}


def inspect_database(conn):
    """Only inspect metadata and grants; never select user records or write them."""
    issues = []
    with conn.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute("SELECT current_schema()")
        schema = cur.fetchone()[0]
        cur.execute("""SELECT table_name,column_name FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name=ANY(%s)""", (list(FEATURES),))
        columns = {}
        for table, column in cur.fetchall():
            columns.setdefault(table, set()).add(column)
        for table, (label, required, serial) in FEATURES.items():
            absent = sorted(required - columns.get(table, set()))
            if absent:
                print(label + ': MISSING table/columns (' + table + ': ' + ', '.join(absent) + ')')
                issues.append(table)
                continue
            qualified = schema + '.' + table
            cur.execute("""SELECT has_table_privilege(CURRENT_USER,%s,'SELECT'),
                has_table_privilege(CURRENT_USER,%s,'INSERT'),
                has_table_privilege(CURRENT_USER,%s,'UPDATE'),
                has_table_privilege(CURRENT_USER,%s,'DELETE')""", (qualified,) * 4)
            grants = cur.fetchone()
            denied = [action for action, granted in zip(('SELECT', 'INSERT', 'UPDATE', 'DELETE'), grants) if not granted]
            cur.execute("""SELECT c.relrowsecurity,c.relforcerowsecurity,
                (r.rolsuper OR r.rolbypassrls OR (c.relowner=r.oid AND NOT c.relforcerowsecurity))
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN pg_roles r WHERE n.nspname=%s AND c.relname=%s AND r.rolname=CURRENT_USER""", (schema, table))
            access = cur.fetchone()
            if access and access[0] and not access[2]:
                denied.append('verify RLS policies for the server connection role')
            if serial:
                cur.execute('SELECT pg_get_serial_sequence(%s,%s)', (qualified, serial))
                sequence = cur.fetchone()[0]
                if sequence:
                    cur.execute("SELECT has_sequence_privilege(CURRENT_USER,%s,'USAGE') OR has_sequence_privilege(CURRENT_USER,%s,'UPDATE')", (sequence, sequence))
                    if not cur.fetchone()[0]:
                        denied.append('sequence access for new records')
            if denied:
                print(label + ': CHECK ACCESS (' + ', '.join(denied) + ')')
                issues.append(table)
            else:
                print(label + ': READY')
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true', help='Apply missing additive workflow/coach migrations to the configured existing database')
    args = parser.parse_args(argv)
    conn = None
    try:
        from database.connection import get_connection
        conn = get_connection()
        if args.setup:
            from database.workflow_schema import ensure_schema as workflow_setup
            from database.coach_schema import ensure_schema as coach_setup
            workflow_setup(conn, force=True)
            coach_setup(conn, force=True)
            print('Workflow and coach setup completed in the configured database.')
        issues = inspect_database(conn)
        if issues:
            print('Some schema/access checks need attention. See PROJECT_SETUP.md; check the database this app uses.')
            return 1
        print('Schema and server-role access checks passed. No athlete/team records were written by this check.')
        print('Confirm a saved team after signing out and back in to verify your live app connection.')
        return 0
    except Exception as exc:
        code = getattr(exc, 'pgcode', None) or getattr(exc, 'code', None)
        print('Database check failed:', type(exc).__name__, 'code=' + str(code or 'not supplied'))
        print('Check PostgreSQL availability, configuration and owner permissions. Credentials are not printed.')
        return 1
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


if __name__ == '__main__':
    sys.exit(main())
