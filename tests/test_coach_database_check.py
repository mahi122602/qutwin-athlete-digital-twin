"""CLI checks must not write records, leak connection errors or migrate by default."""
from unittest.mock import MagicMock, patch
from utils import check_coach_database as check


def test_schema_check_is_read_only_and_does_not_read_user_records():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = ('public',)
    cur.fetchall.return_value = []
    issues = check.inspect_database(conn)
    statements = [call.args[0] for call in cur.execute.call_args_list]
    assert len(issues) == len(check.FEATURES)
    assert statements[0] == 'SET TRANSACTION READ ONLY'
    assert not any(command in sql.upper() for sql in statements for command in ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE'))
    assert all('FROM athletes' not in sql and 'FROM qutwin_coach_teams' not in sql for sql in statements)


def test_default_cli_does_not_apply_schema_and_closes_the_connection():
    conn = MagicMock()
    with patch('database.connection.get_connection', return_value=conn), \
         patch.object(check, 'inspect_database', return_value=[]), \
         patch('database.workflow_schema.ensure_schema') as workflow, \
         patch('database.coach_schema.ensure_schema') as coach:
        assert check.main([]) == 0
        workflow.assert_not_called()
        coach.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_setup_cli_uses_the_same_configured_connection_for_both_migrations():
    conn = MagicMock()
    with patch('database.connection.get_connection', return_value=conn), \
         patch.object(check, 'inspect_database', return_value=[]), \
         patch('database.workflow_schema.ensure_schema') as workflow, \
         patch('database.coach_schema.ensure_schema') as coach:
        assert check.main(['--setup']) == 0
        workflow.assert_called_once_with(conn, force=True)
        coach.assert_called_once_with(conn, force=True)


def test_connection_failure_cannot_echo_private_error_text(capsys):
    with patch('database.connection.get_connection', side_effect=RuntimeError('password=private_fixture_value')):
        assert check.main([]) == 1
    assert 'private_fixture_value' not in capsys.readouterr().out
