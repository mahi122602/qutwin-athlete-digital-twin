"""Daily measurements use the current per-file workflow, not the retired writer."""
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from tests.test_upload_review_workflow import Upload,db
from ingestion.workflow_loader import load_uploaded_file
from prediction.upload_processing import process_upload
from database.workflow_repository import list_uploads


def test_summary_saved_once_without_fabricated_predictions(db):
    f=Upload('com.samsung.shealth.activity.day_summary.csv',b'com.samsung.shealth.activity.day_summary,1,6\nday_time,step_count,datauuid\n2026-08-15,42,a,\n2026-08-16,43,b,\n')
    df,raw,det=load_uploaded_file(f)
    entry={'df':df,'raw':raw,'detection':det,'name':f.name,'digest':'daily',
      'assignments':[{'record':1,'event':'800 m'},{'record':2,'event':'800 m'}]}
    process_upload('athlete1',entry,['800 m']);process_upload('athlete1',entry,['800 m'])
    saved=list_uploads('athlete1')
    assert len(saved)==1 and len(saved[0]['records'])==2
    assert saved[0]['snapshot']['steps']==43
    assert saved[0]['snapshot']['prediction_status']=='analysis_only'
    assert 'fatigue_score' not in saved[0]['snapshot']
