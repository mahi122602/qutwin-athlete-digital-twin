"""Account contracts: validation, rollback, duplicate protection, legacy login."""
from datetime import date
from pathlib import Path
import importlib.util
import json
import unittest

_file=Path(__file__).resolve().parents[1]/'services/cinematic_auth.py'
_spec=importlib.util.spec_from_file_location('cinematic_auth_under_test',_file)
auth=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(auth)

def athlete(**changes):
    data=dict(role='Athlete',user_id='test.athlete',name='Test Athlete',email='athlete@example.test',
        password='Test-only-password',confirm='Test-only-password',terms_accepted=True,
        date_of_birth='2000-10-19',gender='Female',height=172,weight=64,sport='Athletics',
        event_type='100 m',previous_injury=1,injury_history='A recovered ankle sprain.',health_consent=True)
    return {**data,**changes}

class Cursor:
    def __init__(self,*,duplicate=False,metadata_failure=False,login_row=None):
        self.calls=[];self.one=None;self.rows=[];self.closed=False
        self.duplicate=duplicate;self.metadata_failure=metadata_failure;self.login_row=login_row
    def execute(self,sql,params=None):
        self.calls.append((sql,params));self.one=None;self.rows=[]
        if 'information_schema.columns' in sql:
            self.rows=[(x,)for x in ['athlete_id','coach_id','name','password','age','height','weight','previous_injury','email','injury_history','gender']]
        if sql.startswith('INSERT INTO athletes')or sql.startswith('INSERT INTO coaches'):
            self.one=None if self.duplicate else ('test.athlete',)
        if sql.startswith('INSERT INTO qutwin_auth_profiles')and self.metadata_failure:
            raise RuntimeError('Synthetic metadata failure')
        if sql.startswith('SELECT athlete_id, password, name')or sql.startswith('SELECT coach_id, password, name'):
            self.one=self.login_row
    def fetchone(self):return self.one
    def fetchall(self):return self.rows
    def close(self):self.closed=True

class Connection:
    def __init__(self,**kwargs):self.cur=Cursor(**kwargs);self.commits=0;self.rollbacks=0;self.closed=False
    def cursor(self):return self.cur
    def commit(self):self.commits+=1
    def rollback(self):self.rollbacks+=1
    def close(self):self.closed=True

class AccountContracts(unittest.TestCase):
    def test_age_uses_birthday_and_profile_contains_no_password(self):
        result=auth.validate_signup(athlete(),today=date(2026,10,18))
        self.assertEqual(result['age'],25)
        self.assertEqual(result['profile']['sport'],'Athletics')
        self.assertNotIn('password',result['profile'])
        self.assertNotIn('confirm',result['profile'])

    def test_invalid_or_unacknowledged_health_data_is_rejected(self):
        changes=[{'height':float('nan')},{'weight':float('inf')},{'previous_injury':1.5},
            {'health_consent':False},{'terms_accepted':'true'},{'date_of_birth':'2020-02-30'},
            {'role':'Admin'},{'user_id':"x'; DROP TABLE athletes;--"},{'password':'é'*37,'confirm':'é'*37}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(auth.AuthInputError):
                auth.validate_signup(athlete(**change))

    def test_coach_does_not_require_athlete_health_fields(self):
        result=auth.validate_signup(dict(role='Coach',user_id='coach01',name='Test Coach',email='coach@example.test',
            password='Test-only-password',confirm='Test-only-password',terms_accepted=True,specialisation='Running'))
        self.assertEqual(result['profile']['specialisation'],'Running')
        self.assertNotIn('height',result)

    def test_signup_commits_credentials_and_onboarding_together(self):
        conn=Connection();result=auth.register_account(athlete(),connect=lambda:conn,hasher=lambda p:'$hashed-test')
        self.assertEqual(result['role'],'Athlete');self.assertEqual(conn.commits,1)
        self.assertEqual(conn.rollbacks,0);self.assertTrue(conn.closed and conn.cur.closed)
        queries=conn.cur.calls
        insert=next(params for sql,params in queries if sql.startswith('INSERT INTO athletes'))
        self.assertIn('$hashed-test',insert);self.assertNotIn('Test-only-password',insert)
        extra=next(params for sql,params in queries if sql.startswith('INSERT INTO qutwin_auth_profiles'))
        profile=json.loads(extra[-1]);self.assertEqual(profile['injury_history'],'A recovered ankle sprain.')
        self.assertNotIn('password',profile)

    def test_duplicate_id_cannot_report_account_created(self):
        conn=Connection(duplicate=True)
        with self.assertRaises(auth.AccountExists):
            auth.register_account(athlete(),connect=lambda:conn,hasher=lambda p:'hash')
        self.assertEqual(conn.commits,0);self.assertEqual(conn.rollbacks,1)
        self.assertFalse(any(sql.startswith('INSERT INTO qutwin_auth_profiles')for sql,_ in conn.cur.calls))

    def test_failed_metadata_save_rolls_back_account_insert(self):
        conn=Connection(metadata_failure=True)
        with self.assertRaises(RuntimeError):
            auth.register_account(athlete(),connect=lambda:conn,hasher=lambda p:'hash')
        self.assertEqual(conn.commits,0);self.assertEqual(conn.rollbacks,1)
        self.assertTrue(conn.closed and conn.cur.closed)

    def test_legacy_login_returns_database_id_only_after_password_check(self):
        conn=Connection(login_row=('legacy01','$existing-hash','Existing Athlete'))
        seen=[]
        def checker(entered,stored):seen.append((entered,stored));return entered=='right-password'
        result=auth.authenticate({'role':'Athlete','user_id':'legacy01','password':'right-password'},connect=lambda:conn,checker=checker)
        self.assertEqual(result['user_id'],'legacy01');self.assertEqual(seen,[('right-password','$existing-hash')])
        conn=Connection(login_row=('legacy01','$existing-hash','Existing Athlete'))
        self.assertIsNone(auth.authenticate({'role':'Athlete','user_id':'legacy01','password':'wrong'},connect=lambda:conn,checker=lambda *_:False))

    def test_login_does_not_interpolate_user_input_into_sql(self):
        conn=Connection();uid="' OR 1=1 --"
        self.assertIsNone(auth.authenticate({'role':'Coach','user_id':uid,'password':'arbitrary'},connect=lambda:conn,checker=lambda *_:True))
        sql,params=conn.cur.calls[0]
        self.assertNotIn(uid,sql);self.assertEqual(params,(uid,))

if __name__=='__main__':unittest.main()

