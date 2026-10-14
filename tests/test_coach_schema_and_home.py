"""Regression checks for actual-database setup and dashboard link boundaries."""
from unittest.mock import MagicMock, patch
import pytest
from database import coach_schema as schema
from ui.coach_dashboard import resolve_action


def connection(name='local-app'):
    conn=MagicMock()
    conn.get_dsn_parameters.return_value=dict(host='local',port='5432',dbname=name,user='owner')
    cur=conn.cursor.return_value.__enter__.return_value
    return conn,cur


@pytest.fixture(autouse=True)
def reset_setup_cache():
    schema._verified.clear()
    yield
    schema._verified.clear()


def ready_columns():
    return [(table,column) for table,columns in schema._required.items() for column in columns]


def test_missing_coach_tables_are_created_on_the_supplied_connection():
    conn,cur=connection();cur.fetchall.side_effect=[[],ready_columns()]
    cur.fetchone.return_value=('coaches','athletes','coach_athlete_mapping')
    schema.ensure_schema(conn)
    statements=[call.args[0] for call in cur.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS qutwin_coach_teams' in sql for sql in statements)
    assert not any('DELETE FROM athletes' in sql or 'DROP TABLE' in sql for sql in statements)
    conn.commit.assert_called_once();conn.rollback.assert_not_called()


def test_already_prepared_database_is_not_migrated():
    conn,cur=connection();cur.fetchall.return_value=ready_columns()
    schema.ensure_schema(conn)
    assert not any('CREATE TABLE' in call.args[0] for call in cur.execute.call_args_list)


def test_setup_cache_does_not_hide_a_different_database():
    first,c1=connection('db-one');c1.fetchall.return_value=ready_columns()
    second,c2=connection('db-two');c2.fetchall.return_value=ready_columns()
    schema.ensure_schema(first);schema.ensure_schema(second)
    assert c1.execute.called and c2.execute.called
    assert len(schema._verified)==2


def test_wrong_base_database_is_rejected_without_coach_migration():
    conn,cur=connection();cur.fetchall.return_value=[];cur.fetchone.return_value=(None,None,None)
    with pytest.raises(schema.CoachSetupError):schema.ensure_schema(conn)
    assert not any('CREATE TABLE' in call.args[0] for call in cur.execute.call_args_list)
    conn.rollback.assert_called_once();conn.commit.assert_not_called()


def test_setup_failure_rolls_back_and_closes_the_lease():
    conn,_=connection()
    with patch.object(schema,'workflow_connection',return_value=conn),patch.object(schema,'ensure_schema',side_effect=RuntimeError('failure')):
        with pytest.raises(RuntimeError):schema.get_connection()
    conn.close.assert_called_once()


def test_dashboard_rejects_athletes_and_teams_outside_the_loaded_coach_scope():
    athletes=[{'athlete_id':'mine'}];teams=[{'id':1}]
    assert resolve_action({'nonce':'1','action':'athlete','athlete_id':'other'},athletes,teams) is None
    assert resolve_action({'nonce':'2','action':'team','team_id':9},athletes,teams) is None
    assert resolve_action({'nonce':'3','action':'athlete','athlete_id':'mine'},athletes,teams)['athlete']=='mine'


def test_review_links_bind_upload_to_its_connected_athlete():
    athletes=[{'athlete_id':'mine'}];reviews=[{'upload_id':10,'athlete_id':'mine'}]
    assert resolve_action({'nonce':'1','action':'review','upload_id':11},athletes,[],reviews) is None
    action=resolve_action({'nonce':'2','action':'review','upload_id':10},athletes,[],reviews)
    assert action['page']=='Reviews' and action['athlete']=='mine' and action['upload']==10
    assert resolve_action({'nonce':'3','action':'review','upload_id':10},[],[],reviews) is None


def test_dashboard_unknown_actions_and_unlabelled_priority_are_rejected():
    assert resolve_action({'action':'teams'},[],[]) is None
    assert resolve_action({'nonce':'1','action':'delete_profile'},[],[]) is None
    assert resolve_action({'nonce':'2','action':'attention','level':'Unknown'},[],[]) is None
    assert resolve_action({'nonce':'3','action':'attention','level':'High'},[],[])['level']=='High'
