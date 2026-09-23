"""Regression coverage for the latest replacement package; no production services."""
import io
import json
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from ingestion.workflow_loader import load_uploaded_file
from ingestion.adaptive_table import normalise_table
from ingestion.ai_mapping import validate_suggestion
from research_prediction.predict import analyse,bundle
from research_prediction.history import comparable_history
from research_prediction.longitudinal import personal_state
from tests.test_upload_review_workflow import db,Upload


def test_all_supported_input_tiers_have_separate_models():
    cases=[({'training_load':60},'load_only'),
           ({'sleep_hours':7,'recovery_time':7,'hydration_level':'Medium'},'recovery'),
           ({'training_load':60,'sleep_hours':7,'recovery_time':7,'hydration_level':'Medium'},'load_recovery'),
           ({'training_load':60,'sleep_hours':7,'recovery_time':7,'hydration_level':'Medium','temperature':25,'humidity':60},'complete')]
    for record,tier in cases:
        before=dict(record);s=analyse(record,['800 m'])
        assert s['model_tier']==tier and s['prediction_status']=='research_estimate'
        assert s['imputed_model_inputs']=={} and record==before
        assert len(s['used_model_inputs'])==len(bundle()['report']['tiers'][tier]['features'])


def test_large_real_workload_not_clamped_or_falsified():
    s=analyse({'training_load':319.26,'heart_rate':149,'duration_minutes':214.27},['200 m','1500 m'])
    assert s['prediction_status']=='analysis_only'
    assert s['analysis']['features']['training_load']==319.26
    assert 'fatigue_score' not in s


def test_supported_recovery_can_be_assessed_without_out_of_range_load():
    s=analyse({'training_load':319.26,'sleep_hours':7,'recovery_time':7,'hydration_level':'Medium'},['800 m'])
    assert s['model_tier']=='recovery'
    assert 'training_load' not in s['used_model_inputs']
    assert 'training_load' in s['ignored_model_inputs']


def test_unsupported_events_do_not_get_duplicated_fake_specific_scores():
    s=analyse({'training_load':60},['200 m','5 km'])
    assert 0<=s['fatigue_score']<=100
    assert all('fatigue_score' not in e for e in s['event_scenarios'])
    assert not s['event_supported']


def test_resting_heart_rate_is_not_exercise_heart_rate():
    df,_=normalise_table(pd.DataFrame({'RestingHeartRate':[60],'duration_minutes':[30]}))
    assert df.resting_heart_rate.iloc[0]==60
    assert 'heart_rate' not in df and df.training_load.isna().all()


def test_filename_date_requires_confirmation():
    f=Upload('SomeRun20260625061537.csv',b'heart_rate,duration_minutes\n150,40\n')
    df,raw,_=load_uploaded_file(f)
    assert pd.isna(df.timestamp.iloc[0])
    assert raw['reports'][f.name]['date_candidate']=='2026-06-25 06:15:37'
    df,_,_=load_uploaded_file(f,{'activity_timestamp':'2026-06-25T06:15:37+10:00'})
    assert df.timestamp.iloc[0]==pd.Timestamp('2026-06-24T20:15:37Z')
    assert df.timestamp_origin.iloc[0]=='Confirmed by athlete'


def test_apple_only_joins_heart_rate_within_workout():
    xml=b'''<HealthData>
    <Workout startDate="2026-09-01T10:00:00Z" endDate="2026-09-01T10:30:00Z" duration="30" durationUnit="min" totalDistance="5000" totalDistanceUnit="m" workoutActivityType="HKWorkoutActivityTypeRunning"/>
    <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" value="150" startDate="2026-09-01T10:10:00Z"/>
    <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" value="160" startDate="2026-09-01T10:20:00Z"/>
    <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" value="55" startDate="2026-09-01T06:00:00Z"/>
    <Record type="HKQuantityTypeIdentifierStepCount" unit="count" value="200" startDate="2026-09-01T11:00:00Z"/>
    </HealthData>'''
    df,_,_=load_uploaded_file(Upload('apple.xml',xml))
    row=df[df.record_kind.eq('activity')].iloc[0]
    assert row.heart_rate==155 and row.distance==5 and row.duration_minutes==30
    assert len(df)==3 and df.resting_heart_rate.dropna().tolist()==[55]


def test_tcx_lap_average_and_units():
    xml=b'''<TrainingCenterDatabase><Activities><Activity Sport="Running"><Id>2026-09-01T10:00:00Z</Id><Lap><TotalTimeSeconds>600</TotalTimeSeconds><DistanceMeters>2000</DistanceMeters><AverageHeartRateBpm><Value>150</Value></AverageHeartRateBpm></Lap></Activity></Activities></TrainingCenterDatabase>'''
    df,_,_=load_uploaded_file(Upload('activity.tcx',xml))
    assert df.duration_minutes.iloc[0]==10 and df.distance.iloc[0]==2 and df.heart_rate.iloc[0]==150


def test_gpx_distance_does_not_bridge_segments():
    xml=b'''<gpx><trk><trkseg><trkpt lat="0" lon="0"><time>2026-09-01T10:00:00Z</time></trkpt><trkpt lat="0" lon="0.01"><time>2026-09-01T10:10:00Z</time></trkpt></trkseg><trkseg><trkpt lat="45" lon="90"><time>2026-09-01T10:15:00Z</time></trkpt></trkseg></trk></gpx>'''
    df,_,_=load_uploaded_file(Upload('track.gpx',xml))
    assert df.distance.iloc[0]==pytest.approx(1.11195,rel=.001)
    assert df.duration_minutes.iloc[0]==15 and df.heart_rate.isna().all()


def test_ai_mapping_rejects_invented_fields_and_columns():
    result=validate_suggestion({'fields':{'heart_rate':{'column':'Pulse'},'fatigue_score':{'column':'Output'},'sleep_hours':{'column':'Invented'}}},['Pulse','Output'])
    assert result=={'mapping':{'heart_rate':'Pulse'},'units':{}}
    with pytest.raises(ValueError):validate_suggestion({'fields':[]},['Pulse'])


def test_latest_workout_not_later_unrelated_step_sample(db):
    from prediction.upload_processing import process_upload
    from database.workflow_repository import list_uploads
    frame=pd.DataFrame([{'timestamp':'2026-09-01','training_load':60,'record_kind':'activity'},
                        {'timestamp':'2026-09-02','steps':9000,'record_kind':'measurement'}])
    entry={'df':frame,'assignments':[{'record':1,'event':'800 m'},{'record':2,'event':'800 m'}],
           'name':'mixed.xml','digest':'mixed','detection':{'source':'Apple'}}
    process_upload('athlete1',entry,['800 m'])
    saved=list_uploads('athlete1')[0]
    assert saved['snapshot']['training_load']==60 and saved['snapshot']['prediction_status']=='research_estimate'
    assert len(saved['records'])==2


def test_reanalysis_preserves_original_date_id_and_blocks_ai_overwrite(db):
    from database import workflow_repository as repo
    from prediction.upload_processing import recalculate_saved
    repo.save_upload('athlete1','old.csv','CSV','old',pd.DataFrame([{'training_load':60,'timestamp':None}]),
       {'model_version':'research-v1','fatigue_score':50},['800 m'],[{'record':1,'event':'800 m'}],'research_estimate')
    old=repo.list_uploads('athlete1')[0];recalculate_saved('athlete1',old)
    new=repo.list_uploads('athlete1')[0]
    assert new['id']==old['id'] and new['uploaded_at']==old['uploaded_at']
    assert new['snapshot']['previous_assessment']['fatigue_score']==50
    _,token=repo.claim_ai('athlete1',new['id']);repo.finish_ai('athlete1',new['id'],token,text='Reviewed draft',model='test')
    with pytest.raises(ValueError,match='cannot be overwritten'):recalculate_saved('athlete1',new)


def test_comparable_forecast_excludes_old_version_and_unknown_dates():
    frame=pd.DataFrame([{'timestamp':'2026-09-01','uploaded_at':'2026-09-01','model_version':'v1','model_tier':'load_only'},
          {'timestamp':'2026-09-02','uploaded_at':'2026-09-02','model_version':'v2','model_tier':'load_only'},
          {'timestamp':None,'uploaded_at':'2026-09-03','model_version':'v2','model_tier':'load_only'}])
    result=comparable_history(frame)
    assert len(result)==1 and result.model_version.iloc[0]=='v2'


def test_forecast_scales_change_by_actual_days():
    from digital_twin.forecasting_engine import forecast_metric
    frame=pd.DataFrame({'timestamp':['2026-09-01','2026-09-11'],'fatigue_score':[40,50]})
    f=forecast_metric(frame,'fatigue_score',1)
    assert f.forecast_value.iloc[0]==51
    assert forecast_metric(None,'fatigue_score').empty


def test_state_model_needs_real_dated_history():
    assert personal_state({'timestamp':None,'fatigue_score':50},[])['status']=='not_ready'
    current={'timestamp':'2026-09-20','fatigue_score':50,'model_version':'v2','model_tier':'complete','primary_event':'800 m'}
    assert personal_state(current,[])['status']=='not_ready'


def test_model_validation_is_not_training_accuracy():
    r=bundle()['report']
    assert r['held_out_athletes']>0 and r['development_athletes']+r['held_out_athletes']==r['athletes']
    assert r['unique_training_dates']==3
    for spec in r['tiers'].values():
        assert set(spec['development_group_cv']['fatigue'])=={'linear','forest','catboost'}
        assert 0<=spec['metrics']['risk_balanced_accuracy']<=1


def test_available_measurements_survive_every_format():
    # Content recognition, not suffix recognition, handles a mislabeled XLS.
    for suffix in ('csv','xls','xlsx','txt'):
        df,_,_=load_uploaded_file(Upload('a.'+suffix,b'heart_rate,duration_minutes\n150,40\n'))
        assert df.training_load.iloc[0]==60
    data=json.dumps({'activities':[{'heart_rate':150,'duration_minutes':40}]}).encode()
    df,_,_=load_uploaded_file(Upload('a.json',data));assert df.training_load.iloc[0]==60


def test_overview_missing_recovery_does_not_show_zero_percent(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import views.athlete_home as home
    captured=[]
    monkeypatch.setattr(home.st,'html',lambda text:captured.append(text))
    app=AppTest.from_string("from views.athlete_home import _render_summary_cards\n_render_summary_cards({'fatigue_score':50,'readiness_score':50,'twin_score':50,'injury_risk':'Low','prediction_status':'research_estimate','recovery_index':None,'training_load':None})").run()
    assert not app.exception
    assert any('Not available' in str(v) and 'RECOVERY' in str(v) for v in captured)


def test_workflow_and_legacy_history_are_merged_without_adopted_duplicate(monkeypatch):
    import database.twin_repository as twin
    import database.workflow_repository as repo
    class Connection:
        def close(self):pass
    monkeypatch.setattr(twin,'get_connection',lambda:Connection())
    monkeypatch.setattr(repo,'list_uploads',lambda _:[{'id':7,'legacy_upload_id':1,'uploaded_at':'2026-09-22','snapshot':{'timestamp':'2026-09-20','fatigue_score':40,'model_version':'adaptive-v2'},'ai_text':'Draft'}])
    monkeypatch.setattr(twin.pd,'read_sql',lambda *a,**k:pd.DataFrame([{'upload_id':1,'timestamp':'2026-09-20','fatigue_score':20},{'upload_id':2,'timestamp':'2026-09-01','fatigue_score':30}]))
    result=twin.get_athlete_twin_history.__wrapped__('athlete1')
    assert len(result)==2 and result.fatigue_score.tolist()==[40,30]


def test_notification_bell_finds_old_and_new_role_formats(db,monkeypatch):
    import database.connection_request_repository as notifications
    from tests.test_upload_review_workflow import Connection,Cursor
    monkeypatch.setattr(Cursor,'close',lambda self:self.cur.close(),raising=False)
    monkeypatch.setattr(notifications,'get_connection',lambda:Connection(db))
    db.executemany('INSERT INTO notifications VALUES(?,?,?,?,?)',[
        ('athlete','athlete1','Coach Recommendation','Old-format decision',False),
        ('Athlete','athlete1','Coach Recommendation','New-format decision',False),
        ('Athlete','other','Coach Recommendation','Private decision',False)])
    db.commit()
    assert notifications.get_unread_notification_count.__wrapped__('Athlete','athlete1')==2
    notifications.mark_all_notifications_read.__wrapped__('Athlete','athlete1')
    assert notifications.get_unread_notification_count.__wrapped__('Athlete','athlete1')==0
    assert notifications.get_unread_notification_count.__wrapped__('Athlete','other')==1
