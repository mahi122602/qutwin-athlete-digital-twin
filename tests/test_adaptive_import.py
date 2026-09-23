import io
import zipfile
import pandas as pd
import pytest
from ingestion.adaptive_table import read_table,normalise_table
from ingestion.workflow_loader import load_uploaded_file
from tests.test_upload_review_workflow import db,Upload

@pytest.mark.parametrize('sep',[',',';','\t','|'])
@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','cp1252'])
def test_encodings_delimiters(sep,encoding):
 text=sep.join(['timestamp','heart_rate'])+'\n'+sep.join(['2026-09-01','150'])+'\n'
 raw,_=read_table(text.encode(encoding));df,_=normalise_table(raw)
 assert df.heart_rate.iloc[0]==150

def test_summary_does_not_double_count():
 f=Upload('run.csv',b'Split,Time,Avg HR,Max HR,Avg Temperature,GetDistance\n1,00:05:00,150,175,28,1\n2,00:05:30,160,180,28,1\nSummary,00:10:30,155,180,28,2\n')
 df,raw,_=load_uploaded_file(f)
 assert len(df)==1 and df.heart_rate.iloc[0]==155 and df.duration_minutes.iloc[0]==10.5
 assert abs(df.training_load.iloc[0]-16.275)<.011
 assert pd.isna(df.temperature.iloc[0]) and pd.isna(df.timestamp.iloc[0])
 df,_,_=load_uploaded_file(f,{'units':{'temperature':'C','distance':'km'}})
 assert df.temperature.iloc[0]==28 and df.distance.iloc[0]==2
 assert len(raw['tables']['run.csv'])==3

@pytest.mark.parametrize('suffix',['xls','xlsx','csv'])
def test_extension_is_not_format(suffix):
 df,_,_=load_uploaded_file(Upload('data.'+suffix,b'timestamp,steps\n2026-09-01,1234\n'))
 assert df.steps.iloc[0]==1234

def test_excel_wrong_extension_and_sheets():
 b=io.BytesIO()
 with pd.ExcelWriter(b,engine='openpyxl') as writer:
  pd.DataFrame({'steps':[12]}).to_excel(writer,sheet_name='First',index=False)
  pd.DataFrame({'steps':[34]}).to_excel(writer,sheet_name='Second',index=False)
 df,_,_=load_uploaded_file(Upload('data.csv',b.getvalue()),{'sheet':'Second'})
 assert df.steps.iloc[0]==34

def test_html_xls():
 df,_,_=load_uploaded_file(Upload('data.xls',b'<html><table><tr><th>timestamp</th><th>steps</th></tr><tr><td>2026-09-01</td><td>1000</td></tr></table></html>'))
 assert df.steps.iloc[0]==1000

def test_mapping_units_locale():
 raw=pd.DataFrame({'pulse':['160'],'elapsed':['600'],'temp':['86'],'dist':['1,5'],'when':['04/05/2026']})
 o={'mapping':{'heart_rate':'pulse','duration_minutes':'elapsed','temperature':'temp','distance':'dist','timestamp':'when'},'units':{'duration_minutes':'seconds','temperature':'F','distance':'mi'},'decimal':'Comma','date_order':'Day first'}
 df,r=normalise_table(raw,o)
 assert df.heart_rate.iloc[0]==160 and df.duration_minutes.iloc[0]==10
 assert df.temperature.iloc[0]==30 and df.distance.iloc[0]==pytest.approx(2.414016)
 assert df.timestamp.iloc[0].month==5

def test_ambiguous_dates_and_numbers():
 df,r=normalise_table(pd.DataFrame({'timestamp':['04/05/2026'],'steps':['1,234']}))
 assert pd.isna(df.timestamp.iloc[0]) and pd.isna(df.steps.iloc[0])
 assert len(r['issues'])==2

def test_malformed_rows_rejected():
 with pytest.raises(ValueError,match='expected 2 columns'):
  read_table(b'timestamp,steps\n2026-09-01,100,extra\n')

def test_no_wall_clock_duration():
 df,_=normalise_table(pd.DataFrame({'date':['2026-09-01'],'Time':['12:30:00'],'heart_rate':[150]}))
 assert 'duration_minutes' not in df

def test_sleep_clock():
 df,_=normalise_table(pd.DataFrame({'sleep_hours':['07:30']}))
 assert df.sleep_hours.iloc[0]==7.5

def test_plausibility():
 df,r=normalise_table(pd.DataFrame({'heart_rate':[900],'humidity':[120],'previous_injury':[.5]}))
 assert df.heart_rate.isna().all() and df.previous_injury.isna().all() and len(r['issues'])==3

def test_duplicate_headers_require_mapping():
 raw,_=read_table(b'heart_rate,heart_rate\n150,160\n')
 assert raw.columns.is_unique

def test_zip_member_failure_visible():
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  z.writestr('good.csv','timestamp,steps\n2026-09-01,100\n');z.writestr('bad.csv','timestamp,steps\n2026-09-02,2,3\n')
 with pytest.raises(ValueError,match='bad.csv'):load_uploaded_file(Upload('export.zip',b.getvalue()))

def test_partial_prediction_does_not_borrow_old_score(db,monkeypatch):
 from prediction.upload_processing import process_upload
 import database.twin_repository as twin
 monkeypatch.setattr(twin,'get_latest_twin_state',lambda _:None)
 data=b'timestamp,heart_rate,sleep_hours,training_load,recovery_time,hydration_level,temperature,humidity,previous_injury\n2026-09-01,150,8,60,8,Medium,25,50,0\n2026-09-02,160,,40,12,Medium,24,50,0\n'
 df,raw,det=load_uploaded_file(Upload('data.csv',data));calls=[]
 monkeypatch.setattr('prediction.upload_processing.save_upload',lambda *a:calls.append(a) or {'status':'saved','id':1})
 process_upload('athlete1',{'df':df,'raw':raw,'detection':det,'name':'data.csv','digest':'partial','assignments':[{'record':1,'event':'5 km'},{'record':2,'event':'5 km'}]},['5 km'])
 snapshot=calls[0][5]
 assert snapshot['prediction_record_count']==0 and snapshot['prediction_status']=='analysis_only'
 assert 'fatigue_score' not in snapshot and calls[0][-1] is None

def test_correct_existing_preserves_history_entry(db):
 from database import workflow_repository as repo
 df=pd.DataFrame([{'steps':100}]);args=('athlete1','a.csv','Export','hash',df,{'steps':100},['5 km'],[],'observations_only')
 first=repo.save_upload(*args);when=repo.list_uploads('athlete1')[0]['uploaded_at']
 result=repo.correct_observation_upload('athlete1','a.csv','Export','hash',pd.DataFrame([{'steps':200}]),{'steps':200},['5 km'],[],'observations_only')
 assert result['id']==first['id']
 rows=repo.list_uploads('athlete1');assert len(rows)==1 and rows[0]['uploaded_at']==when and rows[0]['snapshot']['steps']==200
 _,token=repo.claim_ai('athlete1',first['id'])
 with pytest.raises(ValueError,match='cannot be overwritten'):repo.correct_observation_upload(*args)

def test_import_settings_apply_then_upload(monkeypatch):
 from streamlit.testing.v1 import AppTest
 import streamlit as st
 import views.athlete.upload as page
 f=Upload('summary.csv',b'Split,Time,Avg HR,Avg Temperature\n1,00:02:00,150,28\nSummary,00:02:00,150,28\n');f.size=len(f.getvalue())
 monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:[f]);saved=[]
 monkeypatch.setattr(page,'process_upload',lambda *a:saved.append(a) or {'status':'saved','id':1})
 app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='athlete1'\nfrom views.athlete.upload import upload_garmin_data\nupload_garmin_data()\n").run()
 assert not app.exception
 next(s for s in app.selectbox if s.label=='temperature unit').select('C')
 next(b for b in app.button if b.label=='Apply import settings').click().run()
 assert not app.exception
 app.multiselect[0].select('5 km').run()
 next(s for s in app.selectbox if s.label=='Event assignment').select('5 km').run()
 next(b for b in app.button if b.label=='Upload and proceed').click().run()
 assert not app.exception and len(saved)==1
 assert len(saved[0][1]['df'])==1 and saved[0][1]['df'].temperature.iloc[0]==28

def test_time_only_does_not_invent_date():
 df,_=normalise_table(pd.DataFrame({'timestamp':['12:30:00'],'heart_rate':[150]}))
 assert pd.isna(df.timestamp.iloc[0])
