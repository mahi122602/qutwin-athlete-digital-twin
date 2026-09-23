from unittest.mock import patch
import io
import sys
import pytest
from database import workflow_schema as schema


class FakeConnection:
    def __init__(self, name='test'):
        self.name=name; self.sql=[]; self.commits=0; self.rollbacks=0; self.closed=False
    def get_dsn_parameters(self): return {'dbname':self.name,'user':'test','password':'must-not-be-cached'}
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self,sql): self.sql.append(sql)
    def commit(self): self.commits+=1
    def rollback(self): self.rollbacks+=1
    def close(self): self.closed=True


@pytest.fixture(autouse=True)
def reset_schema_cache():
    schema._verified.clear()
    yield
    schema._verified.clear()


def test_missing_tables_are_created_before_returning_connection():
    conn=FakeConnection()
    with patch.object(schema,'open_connection',return_value=conn), patch.object(schema,'_missing',side_effect=[{'qutwin_processed_uploads':['id']},{}]):
        assert schema.get_connection() is conn
    assert conn.commits==1
    assert any('CREATE TABLE IF NOT EXISTS qutwin_processed_uploads' in q for q in conn.sql)
    assert all('password' not in str(key) and 'must-not-be-cached' not in str(key) for key in schema._verified)


def test_healthy_database_needs_no_schema_write_and_is_cached():
    conn=FakeConnection()
    with patch.object(schema,'_missing',return_value={}):
        schema.ensure_schema(conn)
        before=len(conn.sql)
        schema.ensure_schema(conn)
    assert len(conn.sql)==before
    assert not any('CREATE TABLE' in q for q in conn.sql)


def test_cache_is_separate_for_different_databases():
    with patch.object(schema,'_missing',return_value={}) as inspect:
        schema.ensure_schema(FakeConnection('one'))
        schema.ensure_schema(FakeConnection('two'))
    assert inspect.call_count==2


def test_permission_failure_rolls_back_closes_and_allows_retry():
    class Denied(Exception): pgcode='42501'
    conn=FakeConnection()
    original=conn.execute
    def execute(sql):
        if 'CREATE TABLE' in sql: raise Denied()
        original(sql)
    conn.execute=execute
    with patch.object(schema,'open_connection',return_value=conn), patch.object(schema,'_missing',return_value={'notifications':['request_id']}):
        with pytest.raises(schema.WorkflowSetupError,match='denied') as error:
            schema.get_connection()
    assert error.value.code=='42501'
    assert conn.closed and conn.rollbacks==1 and not schema._verified
    good=FakeConnection()
    with patch.object(schema,'_missing',return_value={}): schema.ensure_schema(good)
    assert good.commits==1


def test_incomplete_schema_after_migration_is_not_marked_ready():
    conn=FakeConnection()
    with patch.object(schema,'_missing',return_value={'qutwin_processed_uploads':['id']}):
        with pytest.raises(schema.WorkflowSetupError,match='differs'):
            schema.ensure_schema(conn)
    assert conn.rollbacks==1 and not schema._verified


def test_missing_xml_dependency_does_not_break_csv_upload():
    from ingestion.workflow_loader import load_uploaded_file, xml_records
    f=io.BytesIO(b'timestamp,steps\n2026-09-01,1000\n');f.name='file.csv'
    with patch.dict(sys.modules,{'defusedxml':None}):
        df,_,_=load_uploaded_file(f)
        assert len(df)==1
        with pytest.raises(ValueError,match='pip install'):
            xml_records(b'<HealthData/>')


def test_setup_error_renders_recovery_not_generic_database_banner():
    from streamlit.testing.v1 import AppTest
    import views.athlete.predictions as page
    with patch.object(page,'list_uploads',side_effect=schema.WorkflowSetupError('Automatic database setup was denied by this database role.','42501')):
        app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='test'\nfrom views.athlete.predictions import athlete_predictions\nathlete_predictions()").run()
    assert not app.exception
    assert 'denied' in app.error[0].value
    assert len(app.get('download_button'))==1
