from unittest.mock import MagicMock,patch
import pytest
import pandas as pd
from database import account_privacy as privacy

def connection():
    conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
    cur.rowcount=1
    return conn,cur

def test_delete_requires_literal_confirmation_before_database():
    with patch.object(privacy,'_athlete_actor',return_value='a'),patch.object(privacy,'get_connection') as connect:
        with pytest.raises(ValueError):privacy.delete_my_account('pw','delete')
        connect.assert_not_called()

def test_bad_password_rolls_back_without_deletes():
    conn,cur=connection();cur.fetchone.return_value=('hash',)
    with patch.object(privacy,'_athlete_actor',return_value='a'),patch.object(privacy,'get_connection',return_value=conn),patch.object(privacy,'check_password',return_value=False):
        with pytest.raises(ValueError):privacy.delete_my_account('bad','DELETE')
    conn.rollback.assert_called_once();conn.commit.assert_not_called()
    assert not any('DELETE FROM' in str(c.args[0]) for c in cur.execute.call_args_list)

def test_deletion_is_scoped_and_children_first():
    conn,cur=connection();cur.fetchone.return_value=('hash',)
    cur.fetchall.side_effect=[[(t,'athlete_id') for t in ['athletes','uploaded_files','digital_athlete_state','menstrual_cycle_history','qutwin_processed_uploads','connection_requests']]+[('notifications','recipient_id'),('qutwin_recommendation_reviews','upload_id')],[('digital_athlete_state','uploaded_files')]]
    with patch.object(privacy,'_athlete_actor',return_value='mine'),patch.object(privacy,'get_connection',return_value=conn),patch.object(privacy,'check_password',return_value=True):privacy.delete_my_account('pw','DELETE')
    calls=cur.execute.call_args_list
    for call in calls:
        if 'DELETE' in str(call.args[0]):assert 'WHERE' in str(call.args[0]) and 'mine' in str(call.args[1])
    conn.commit.assert_called_once();conn.rollback.assert_not_called()
    statements=[str(c.args[0]) for c in calls]
    assert next(i for i,s in enumerate(statements) if 'Identifier(\'digital_athlete_state\')' in s)<next(i for i,s in enumerate(statements) if 'Identifier(\'uploaded_files\')' in s)

def test_failed_delete_rolls_back_everything():
    conn,cur=connection();cur.fetchone.return_value=('hash',);cur.fetchall.side_effect=RuntimeError('database error')
    with patch.object(privacy,'_athlete_actor',return_value='a'),patch.object(privacy,'get_connection',return_value=conn),patch.object(privacy,'check_password',return_value=True):
        with pytest.raises(RuntimeError):privacy.delete_my_account('pw','DELETE')
    conn.rollback.assert_called_once();conn.commit.assert_not_called()

def test_dependency_cycles_fail_closed():
    with pytest.raises(ValueError):privacy.deletion_order({'a','b'},[('a','b'),('b','a')])

def test_disconnect_closes_pending_requests_and_scopes_both_ids():
    conn,cur=connection();cur.fetchone.return_value=('athlete',)
    with patch.object(privacy,'_athlete_actor',return_value='athlete'),patch.object(privacy,'get_connection',return_value=conn):privacy.disconnect_coach('coach')
    writes=[c for c in cur.execute.call_args_list if 'UPDATE' in str(c.args[0]) or 'DELETE' in str(c.args[0])]
    assert all(c.args[1]==('athlete','coach') for c in writes if 'SELECT' not in str(c.args[0]))
    conn.commit.assert_called_once()

def test_coach_disconnection_is_checked_each_read():
    from database import access_control as ac
    conn,cur=connection();cur.fetchone.side_effect=[(1,),None]
    with patch.object(ac,'get_connection',return_value=conn):
        ac.require_coach_connection('coach','athlete')
        with pytest.raises(PermissionError):ac.require_coach_connection('coach','athlete')

def test_missing_activity_dates_not_replaced_with_upload_dates():
    from views.athlete.history import charts,format_upload_history
    data=pd.DataFrame([{'timestamp':None,'_uploaded_at':'2026-09-20','fatigue_score':30,'readiness_score':70}])
    figures=charts(data)
    assert all(not fig.data for fig in figures)
    assert format_upload_history(data).iloc[0]['Activity date']=='—'

def test_ongoing_period_saves_null_not_invented_end():
    from database import forecasting_repository as repo
    from datetime import date
    conn,cur=connection();cur=conn.cursor.return_value.__enter__.return_value
    with patch.object(repo,'_get_connection',return_value=conn):repo.add_menstrual_cycle('a',date(2026,1,1),None)
    assert cur.execute.call_args.args[1][2] is None

def test_period_dates_reject_future_and_reversed():
    from database import forecasting_repository as repo
    from datetime import date
    with pytest.raises(ValueError):repo.add_menstrual_cycle('a',date(2099,1,1),None)
    with pytest.raises(ValueError):repo.add_menstrual_cycle('a',date(2026,1,2),date(2026,1,1))

def test_health_records_denied_to_coach_even_if_connected():
    from database.access_control import guard_private_health
    import streamlit as st
    called=[]
    @guard_private_health
    def read(athlete_id):called.append(athlete_id)
    with patch('streamlit.runtime.scriptrunner.get_script_run_ctx',return_value=object()),patch.object(st,'session_state',{'logged_in':True,'role':'Coach','user_id':'coach'}):
        with pytest.raises(PermissionError):read('athlete')
    assert called==[]

def test_athlete_cannot_read_other_athlete_records():
    from database.access_control import guard_athlete_read
    import streamlit as st
    @guard_athlete_read
    def read(athlete_id):return 'data'
    with patch('streamlit.runtime.scriptrunner.get_script_run_ctx',return_value=object()),patch.object(st,'session_state',{'logged_in':True,'role':'Athlete','user_id':'mine'}):
        with pytest.raises(PermissionError):read('someone_else')
        assert read('mine')=='data'
