"""Coach ownership and UI tests; no live database or athlete data required."""
from unittest.mock import MagicMock,patch
from datetime import datetime,timezone,timedelta
import pytest
from database import coach_studio as db
from views.coach.studio import attention

def connection():
    c=MagicMock();return c,c.cursor.return_value.__enter__.return_value

def test_known_high_signal_not_hidden_by_missing_injury():
    s={'timestamp':datetime.now(timezone.utc).isoformat(),'fatigue_score':80,'injury_risk':None}
    assert attention(s)=='High'
    s['fatigue_score']=10
    assert attention(s)=='Not assessed'

def test_stale_future_missing_data_never_low():
    for stamp in [None,(datetime.now(timezone.utc)-timedelta(days=8)).isoformat(),(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()]:
        assert attention({'timestamp':stamp,'fatigue_score':10,'readiness_score':80,'injury_risk':'Low'})=='Not assessed'

def test_foreign_team_is_denied_before_mutation():
    conn,cur=connection();cur.fetchone.return_value=None
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection',return_value=conn):
        with pytest.raises(PermissionError):db.change_member(8,'athlete')
    assert len(cur.execute.call_args_list)==1
    assert cur.execute.call_args.args[1]==(8,'mine')
    conn.rollback.assert_called_once()

def test_disconnected_athlete_cannot_be_added():
    conn,cur=connection();cur.fetchone.side_effect=[(8,),None]
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection',return_value=conn):
        with pytest.raises(PermissionError):db.change_member(8,'athlete')
    assert not any('INSERT' in c.args[0] for c in cur.execute.call_args_list)

def test_disconnect_only_removes_relationship():
    conn,cur=connection()
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection',return_value=conn):db.disconnect('athlete')
    assert all(c.args[1]==('mine','athlete') for c in cur.execute.call_args_list)
    assert not any('DELETE FROM athletes' in c.args[0] for c in cur.execute.call_args_list)
    conn.commit.assert_called_once()

def test_delete_confirmation_and_password_fail_closed():
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection') as con:
        with pytest.raises(ValueError):db.delete_profile('pw','delete')
        con.assert_not_called()
    conn,cur=connection();cur.fetchone.return_value=('hash',)
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection',return_value=conn),patch.object(db,'check_password',return_value=False):
        with pytest.raises(ValueError):db.delete_profile('bad','DELETE')
    assert not any('DELETE' in c.args[0] for c in cur.execute.call_args_list)
    conn.rollback.assert_called_once()

def test_delete_preserves_athlete_owned_data():
    conn,cur=connection();cur.fetchone.side_effect=[('hash',),('coach_recommendations',)]
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection',return_value=conn),patch.object(db,'check_password',return_value=True):db.delete_profile('pw','DELETE')
    sql=[c.args[0] for c in cur.execute.call_args_list]
    assert not any('DELETE FROM athletes' in s or 'DELETE FROM qutwin_processed_uploads' in s for s in sql)
    assert any("status='Pending'" in s and 'DELETE' in s for s in sql)
    conn.commit.assert_called_once()

def test_successful_team_add_checks_ownership_and_connection():
    conn,cur=connection();cur.fetchone.side_effect=[(8,),(1,)]
    with patch.object(db,'actor',return_value=('Coach','mine')),patch.object(db,'get_connection',return_value=conn):db.change_member(8,'athlete')
    assert cur.execute.call_args.args[1]==(8,'mine','athlete')
    conn.commit.assert_called_once()
