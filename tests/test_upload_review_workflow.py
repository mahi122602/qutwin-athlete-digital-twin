"""Workflow tests use an isolated SQLite adapter, never production credentials."""
import io
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from ingestion.workflow_loader import load_uploaded_file
from prediction.upload_processing import process_upload
from database import workflow_repository as repo

class Upload(io.BytesIO):
    def __init__(self,name,data): super().__init__(data); self.name=name

class Cursor:
    def __init__(self,db): self.cur=db.cursor()
    def __enter__(self): return self
    def __exit__(self,*a): self.cur.close()
    @property
    def description(self): return self.cur.description
    def execute(self,sql,args=()):
        sql=sql.replace('%s','?').replace('::jsonb','').replace('::text','').replace(' FOR UPDATE OF r','').replace(' FOR UPDATE','')
        sql=sql.replace("NOW()-INTERVAL '2 minutes'","datetime('now','-2 minutes')").replace('NOW()',"datetime('now')")
        self.cur.execute(sql,args); return self
    def fetchone(self):
        row=self.cur.fetchone()
        return self.convert(row) if row else None
    def fetchall(self): return [self.convert(r) for r in self.cur.fetchall()]
    def convert(self,row):
        fields=[c[0] for c in self.cur.description]
        return tuple(json.loads(v) if k in ('records','snapshot','events','assignments') and v is not None else v for k,v in zip(fields,row))

class Connection:
    def __init__(self,db): self.db=db
    def cursor(self): return Cursor(self.db)
    def commit(self): self.db.commit()
    def rollback(self): self.db.rollback()
    def close(self): pass

@pytest.fixture
def db(monkeypatch):
    db=sqlite3.connect(':memory:')
    db.create_function('to_regclass',1,lambda _:None)
    db.executescript('''
    CREATE TABLE qutwin_processed_uploads(id INTEGER PRIMARY KEY AUTOINCREMENT,athlete_id TEXT,filename TEXT,source TEXT,content_hash TEXT,
    records TEXT,snapshot TEXT,events TEXT,assignments TEXT,processing_status TEXT,legacy_upload_id INTEGER,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,ai_status TEXT DEFAULT 'pending',ai_text TEXT,ai_model TEXT,ai_error TEXT,ai_token TEXT,ai_started_at TEXT,UNIQUE(athlete_id,content_hash));
    CREATE TABLE qutwin_recommendation_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,upload_id INTEGER,coach_id TEXT,status TEXT DEFAULT 'Pending',comment TEXT,final_text TEXT,reviewed_at TEXT,UNIQUE(upload_id,coach_id));
    CREATE TABLE coach_athlete_mapping(coach_id TEXT,athlete_id TEXT);
    INSERT INTO coach_athlete_mapping VALUES('coach1','athlete1');
    CREATE TABLE notifications(recipient_role TEXT,recipient_id TEXT,notification_type TEXT,message TEXT,is_read INTEGER);
    ''')
    monkeypatch.setattr(repo,'get_connection',lambda:Connection(db))
    yield db
    db.close()

def saved():
    return repo.save_upload('athlete1','sample.csv','Generic','hash',pd.DataFrame([{'timestamp':'2026-08-01','steps':1000}]),{'prediction_status':'observations_only'},['100 m','800 m'],[], 'observations_only')

def test_duplicate_is_one_file_and_preserves_saved_time(db):
    first=saved(); second=saved()
    assert first['status']=='saved' and second['status']=='already_saved'
    assert first['id']==second['id']
    uploads=repo.list_uploads('athlete1')
    assert len(uploads)==1 and uploads[0]['uploaded_at'] is not None
    assert repo.list_uploads('another')==[]

@pytest.mark.parametrize('decision,comment,final',[('Approved','Looks good','Actual generated draft'),('Modified','Coach revised advice','Coach revised advice'),('Rejected','Insufficient measurements',None)])
def test_review_is_linked_authorised_atomic_and_notified(db,decision,comment,final):
    result=saved(); u,token=repo.claim_ai('athlete1',result['id'])
    assert u
    assert repo.claim_ai('another',result['id'])==(None,None)
    assert repo.claim_ai('athlete1',result['id'])==(None,None)
    repo.finish_ai('athlete1',result['id'],token,text='Actual generated draft',model='test-model')
    queue=repo.coach_queue('coach1'); assert len(queue)==1
    assert repo.coach_queue('intruder')==[]
    with pytest.raises(ValueError): repo.review_recommendation('intruder',queue[0]['id'],decision,comment)
    repo.review_recommendation('coach1',queue[0]['id'],decision,comment)
    reviews=repo.get_reviews('athlete1')
    assert reviews[0]['status']==decision and reviews[0]['final_text']==final
    with pytest.raises(ValueError): repo.review_recommendation('coach1',queue[0]['id'],decision,comment)
    assert db.execute("SELECT count(*) FROM notifications WHERE lower(recipient_role)='athlete'").fetchone()[0]==1
    assert db.execute("SELECT count(*) FROM notifications WHERE lower(recipient_role)='coach'").fetchone()[0]==1


def test_failed_notification_rolls_back_decision(db):
    result=saved(); _,token=repo.claim_ai('athlete1',result['id'])
    repo.finish_ai('athlete1',result['id'],token,text='Draft',model='test')
    review=repo.coach_queue('coach1')[0]
    with patch.object(repo,'_notify',side_effect=RuntimeError('storage failed')):
        with pytest.raises(RuntimeError): repo.review_recommendation('coach1',review['id'],'Approved','')
    assert repo.get_reviews('athlete1')[0]['status']=='Pending'


def test_stale_ai_token_cannot_overwrite_draft(db):
    result=saved(); _,token=repo.claim_ai('athlete1',result['id'])
    repo.finish_ai('athlete1',result['id'],'wrong',text='Wrong draft',model='test')
    assert repo.list_uploads('athlete1')[0]['ai_text'] is None
    repo.finish_ai('athlete1',result['id'],token,text='Right draft',model='test')
    assert repo.list_uploads('athlete1')[0]['ai_text']=='Right draft'


def test_ai_requires_configuration_no_rule_fallback(db,monkeypatch):
    from recommendation import llm_service as llm
    result=saved()
    monkeypatch.setattr(llm,'setting',lambda name:'')
    llm.generate_for_upload('athlete1',result['id'])
    u=repo.list_uploads('athlete1')[0]
    assert u['ai_status']=='not_configured' and u['ai_text'] is None
    assert repo.coach_queue('coach1')==[]


def test_ai_generates_once_and_includes_all_events(db,monkeypatch):
    from recommendation import llm_service as llm
    result=saved(); requests=[]
    monkeypatch.setattr(llm,'setting',lambda name:'test-value')
    def response(req,timeout):
        requests.append(json.loads(req.data))
        return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Generated assessment'}]}}]}).encode())
    monkeypatch.setattr(llm,'urlopen',response)
    llm.generate_for_upload('athlete1',result['id']); llm.generate_for_upload('athlete1',result['id'])
    assert len(requests)==1
    context=json.loads(requests[0]['contents'][0]['parts'][0]['text'])
    assert context['selected_events']==['100 m','800 m']
    assert 'athlete_id' not in context
    assert repo.list_uploads('athlete1')[0]['ai_text']=='Generated assessment'


def test_csv_does_not_make_up_missing_physiology():
    df,_,_=load_uploaded_file(Upload('data.csv',b'timestamp,steps\n2026-09-01,4000\n'))
    assert 'heart_rate' not in df and 'sleep_hours' not in df
    assert str(df.timestamp.iloc[0]).startswith('2026-09-01')


def test_multievent_assignments_survive_sort(db,monkeypatch):
    import database.twin_repository as twin
    monkeypatch.setattr(twin,'get_latest_twin_state',lambda _:None)
    cols='timestamp,heart_rate,sleep_hours,training_load,recovery_time,hydration_level,temperature,humidity,previous_injury\n'
    data=(cols+'2026-09-02,120,8,65,8,Medium,25,50,0\n2026-09-01,150,7,60,8,Medium,25,60,0\n').encode()
    df,_,det=load_uploaded_file(Upload('activity.csv',data))
    entry={'df':df,'assignments':[{'record':1,'event':'800 m'},{'record':2,'event':'100 m'}],'name':'activity.csv','digest':'other','detection':det}
    captured={}
    def save(*args): captured['args']=args; return {'id':1,'status':'saved'}
    with patch('prediction.upload_processing.save_upload',save):
        process_upload('athlete1',entry,['100 m','800 m'])
    args=captured['args']; snap=args[5]
    assert snap['event_type']=='800 m'
    assert snap['prediction_status']=='research_estimate'
    assert 0<=snap['fatigue_score']<=100
    assert args[4]['event_type'].tolist()==['800 m','100 m']
    assert args[-1] is None  # Experimental values never enter legacy state storage.
    assert {x['event'] for x in snap['event_scenarios']} == {'100 m','800 m'}


def test_observations_save_without_model_prediction(db):
    df,_,det=load_uploaded_file(Upload('data.csv',b'timestamp,steps\n2026-08-01,4000\n2026-08-02,5000\n'))
    entry={'df':df,'assignments':[{'record':1,'event':'100 m'},{'record':2,'event':'800 m'}],'name':'daily.csv','digest':'daily','detection':det}
    process_upload('athlete1',entry,['100 m','800 m'])
    u=repo.list_uploads('athlete1')[0]
    assert len(u['records'])==2 and 'fatigue_score' not in u['snapshot']
    assert u['snapshot']['steps']==5000


def test_xml_and_zip():
    import zipfile
    xml=b'<TrainingCenterDatabase><Activities><Activity><Lap><TotalTimeSeconds>120</TotalTimeSeconds><Track><Trackpoint><Time>2026-09-01T10:00:00Z</Time><HeartRateBpm><Value>120</Value></HeartRateBpm></Trackpoint></Track></Lap></Activity></Activities></TrainingCenterDatabase>'
    df,_,_=load_uploaded_file(Upload('run.tcx',xml))
    assert df.heart_rate.iloc[0]==120 and df.duration_minutes.iloc[0]==2
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('run.tcx',xml); z.writestr('other.csv','timestamp,steps\n2026-09-02,5000\n')
    merged,_,_=load_uploaded_file(Upload('activities.zip',buf.getvalue()))
    assert len(merged)==2


def test_history_charts_only_uploaded_points():
    from views.athlete.history import charts, format_upload_history
    frame=pd.DataFrame([{'_uploaded_at':pd.Timestamp('2026-09-03',tz='UTC'),'fatigue_score':40,'injury_risk':'Low','readiness_score':70,'twin_score':65,'health_index':60,'recovery_index':.7},
                        {'_uploaded_at':pd.Timestamp('2026-09-01',tz='UTC'),'fatigue_score':50,'injury_risk':'Medium'}])
    figures=charts(frame)
    assert len(figures)==4
    assert len(figures[0].data[0].x)==2
    assert figures[2].data[0].type=='pie' and figures[3].data[0].type=='scatterpolar'
    assert len(format_upload_history(frame))==2


def test_uploaded_score_is_not_presented_as_prediction():
    df,_,_=load_uploaded_file(Upload('data.csv',b'timestamp,steps,fatigue_score,injury_risk\n2026-09-01,4000,99,High\n'))
    assert 'fatigue_score' not in df and 'injury_risk' not in df
    assert str(df.uploaded_fatigue_score.iloc[0])=='99'


def test_predictions_and_history_render(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import views.athlete.predictions as prediction
    import views.athlete.history as history
    upload={'id':1,'uploaded_at':'2026-09-13T10:00:00Z','filename':'session.csv','events':['100 m','800 m'],
        'snapshot':{'fatigue_score':40,'injury_risk':'Low','readiness_score':70,'twin_score':65,'missing_inputs':[]},
        'ai_text':'Actual generated draft','ai_model':'test-model'}
    monkeypatch.setattr(prediction,'list_uploads',lambda _: [upload])
    monkeypatch.setattr(prediction,'get_reviews',lambda _: [{'upload_id':1,'coach_id':'coach1','status':'Rejected','comment':'Needs more data','final_text':None,'reviewed_at':'2026-09-13'}])
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='athlete1'\nfrom views.athlete.predictions import athlete_predictions\nathlete_predictions()")
    app.run(); assert not app.exception
    assert len(app.metric)==4
    assert any('rejected' in w.value for w in app.warning)
    frame=pd.DataFrame([dict(upload['snapshot'],_uploaded_at=pd.Timestamp('2026-09-13',tz='UTC'),filename='session.csv',source='CSV',recommendation='Generated',coach_feedback='Rejected')])
    monkeypatch.setattr(history,'get_upload_history',lambda _:frame)
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='athlete1'\nfrom views.athlete.history import athlete_history\nathlete_history()")
    app.run(); assert not app.exception
    assert len(app.get('plotly_chart'))==4
    assert len(app.dataframe[0].value)==1


def test_uploader_renders_missing_inputs_and_saves(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    import views.athlete.upload as page
    uploaded=Upload('measurements.csv',b'timestamp,steps\n2026-09-01,4000\n')
    uploaded.size=len(uploaded.getvalue())
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[uploaded])
    calls=[]
    monkeypatch.setattr(page,'process_upload',lambda *args:calls.append(args) or {'status':'saved','id':1})
    code="""import streamlit as st
st.session_state.user_id='athlete1'
from views.athlete.upload import upload_garmin_data
upload_garmin_data()
"""
    app=AppTest.from_string(code).run()
    assert not app.exception
    app.multiselect[0].select('100 m').run()
    next(x for x in app.selectbox if x.label=='Event assignment').select('100 m').run()
    assert not app.exception
    process=next(b for b in app.button if b.label=='Upload and proceed')
    assert not process.disabled
    process.click().run()
    assert not app.exception
    assert len(calls)==1
    assert app.session_state['current_page']=='Predictions & Coach Recommendations'


def test_save_failure_rolls_back_file_metadata(db,monkeypatch):
    db.execute('CREATE TABLE uploaded_files(upload_id INTEGER PRIMARY KEY,athlete_id TEXT,filename TEXT,file_type TEXT,rows_extracted INTEGER)')
    import database.activity_upload_repository as activity
    monkeypatch.setattr(activity,'_insert_states',lambda *args:(_ for _ in ()).throw(RuntimeError('insert failed')))
    with pytest.raises(RuntimeError):
        repo.save_upload('athlete1','a.csv','CSV','a',pd.DataFrame([{'steps':1}]),{},['100 m'],[],'predicted',pd.DataFrame([{'fatigue_score':40}]))
    assert db.execute('SELECT count(*) FROM qutwin_processed_uploads').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM uploaded_files').fetchone()[0]==0


def test_existing_daily_file_is_adopted_without_new_date(db):
    db.execute('CREATE TABLE qutwin_daily_uploads(athlete_id TEXT,content_hash TEXT,created_at TEXT)')
    db.execute("INSERT INTO qutwin_daily_uploads VALUES('athlete1','hash','2026-08-01 10:00:00')")
    db.commit()
    db.create_function('to_regclass',1,lambda n:n if n=='qutwin_daily_uploads' else None)
    result=saved()
    assert result['status']=='already_saved'
    assert repo.list_uploads('athlete1')[0]['uploaded_at']=='2026-08-01 10:00:00'


def test_coach_ui_modification(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import views.coach.recommendation_reviews as page
    entry={'id':1,'upload_id':1,'athlete_id':'athlete1','filename':'a.csv','status':'Pending','uploaded_at':'2026-09-13',
           'events':['100 m'],'snapshot':{},'ai_text':'AI draft','ai_model':'test'}
    monkeypatch.setattr(page,'coach_queue',lambda _:[entry])
    calls=[]
    def review(*args):
        calls.append(args); entry.update(status=args[2],final_text=args[3],reviewed_at='2026-09-13')
    monkeypatch.setattr(page,'review_recommendation',review)
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='coach1'\nfrom views.coach.recommendation_reviews import recommendation_reviews\nrecommendation_reviews()").run()
    app.radio[0].set_value('Modified')
    app.text_area[0].set_value('My revised plan')
    app.button[0].click().run()
    assert not app.exception
    assert calls==[('coach1',1,'Modified','My revised plan')]
