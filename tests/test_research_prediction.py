"""Partial observations, research labels and correction workflow contracts."""
import copy
import pandas as pd
import pytest
from research_prediction.predict import analyse
from research_prediction.features import derive_features
from test_upload_review_workflow import db

def test_partial_inputs_produce_disclosed_estimates_without_mutating_measurements():
    record={'heart_rate':158,'duration_minutes':40.0333333333,'training_load':63.25,'event_type':'800 m'}
    before=copy.deepcopy(record)
    out=analyse(record,['200 m','800 m','5 km'])
    assert record==before
    assert out['prediction_status']=='research_estimate'
    assert 0<=out['fatigue_score']<=100
    assert out['primary_event']=='800 m'
    assert out['imputed_model_inputs']=={}
    assert out['model_tier']=='load_only'
    assert out['used_model_inputs']==['training_load']
    assert out['activity_date_unknown']
    assert [s['event_supported'] for s in out['event_scenarios']]==[False,True,False]
    assert 'exploratory' in out['risk_validation_warning'].lower()

def test_no_load_or_out_of_range_never_returns_prior_only_score():
    for record in ({'steps':5000},{'training_load':500}):
        out=analyse(record,['5 km'])
        assert out['prediction_status']=='analysis_only'
        assert 'fatigue_score' not in out

def test_feature_engineering_excludes_future_and_does_not_fill_calendar():
    history=[{'timestamp':f'2026-09-0{i}','training_load':v} for i,v in [(1,50),(2,60),(3,70),(5,1000)]]
    out=derive_features({'timestamp':'2026-09-04','training_load':80,'duration_minutes':30,'distance':5},history,['5 km'])
    assert out['features']['prior_load_median_28d']==60
    assert out['features']['pace_min_per_km']==6
    assert out['features']['load_vs_prior_median']==pytest.approx(80/60)

def test_event_changes_are_model_inputs_not_workload_multipliers():
    out=analyse({'training_load':63.25},['100 m','800 m'])
    a,b=out['event_scenarios']
    assert a['fatigue_score']!=b['fatigue_score']
    assert out['analysis']['features']['training_load']==63.25

def test_recalculate_saved_keeps_one_history_row_and_raw_missing_values(db):
    from database import workflow_repository as repo
    from prediction.upload_processing import recalculate_saved
    repo.save_upload('athlete1','partial.csv','CSV','partial-hash',pd.DataFrame([{'timestamp':None,'heart_rate':158,'training_load':63.25}]),
        {},['800 m'],[{'record':1,'event':'800 m'}],'observations_only')
    old=repo.list_uploads('athlete1')[0]
    result=recalculate_saved('athlete1',old)
    rows=repo.list_uploads('athlete1')
    assert len(rows)==1 and result['id']==old['id']
    assert rows[0]['uploaded_at']==old['uploaded_at']
    assert rows[0]['snapshot']['prediction_status']=='research_estimate'
    assert rows[0]['records'][0].get('sleep_hours') is None
    assert rows[0]['legacy_upload_id'] is None
    with pytest.raises(ValueError,match='cannot be overwritten'):
        recalculate_saved('athlete1',rows[0])

def test_research_prediction_page_discloses_limitations(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import views.athlete.predictions as view
    snap=analyse({'training_load':63.25,'heart_rate':158},['800 m','5 km'])
    upload={'id':1,'uploaded_at':'2026-09-20','filename':'test.csv','events':['800 m','5 km'],
            'snapshot':snap,'processing_status':'research_estimate','ai_text':None,'ai_error':None}
    monkeypatch.setattr(view,'list_uploads',lambda _: [upload])
    monkeypatch.setattr(view,'get_reviews',lambda _: [])
    monkeypatch.setattr(view,'setting',lambda _: '')
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='athlete1'\nfrom views.athlete.predictions import athlete_predictions\nathlete_predictions()")
    app.run()
    assert not app.exception
    assert len(app.metric)==4
    assert any('Experimental' in w.value for w in app.warning)
    assert len(app.dataframe)==2
