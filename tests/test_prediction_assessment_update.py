"""Single-upload inference, real missing inputs, revision storage and draft provenance."""
import copy
import json
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from research_prediction.predict import analyse, bundle, ANALYSIS_VERSION
from research_prediction.features import model_frame
from prediction.upload_processing import process_upload, update_saved_assessment
from prediction.assessment_versions import assessment_token
from database import workflow_repository as repo
from tests.test_upload_review_workflow import db, Connection, Upload


@pytest.fixture
def revisions(db,monkeypatch):
    from database import prediction_assessments as persistence
    monkeypatch.setattr(persistence,'get_connection',lambda:Connection(db))
    return db


def save_session(record=None):
    record=record or {'heart_rate':149,'duration_minutes':214.27,'training_load':319.26,
                      'training_load_origin':'QUTwin estimate: average HR × minutes / 100'}
    return process_upload('athlete1',dict(df=pd.DataFrame([record]),name='long_activity.csv',
        digest='one-activity',assignments=[],planned_events_only=True,detection={'source':'CSV'}),
        ['100 m','400 m','200 m','800 m','1500 m'])


@pytest.mark.parametrize('record,tier',[
    ({'training_load':60,'sleep_hours':7},'load_sleep'),
    ({'training_load':60,'recovery_time':7},'load_rest'),
    ({'training_load':319.26,'sleep_hours':7,'recovery_time':7},'sleep_rest')])
def test_new_partial_tiers_run_the_actual_fitted_pipeline(record,tier):
    result=analyse(dict(record,event_type='800 m'),['800 m'])
    frame=model_frame(pd.DataFrame([dict(record,event_type='800 m')]))
    expected=float(bundle()['tiers'][tier]['fatigue'].predict(frame)[0])
    assert result['model_tier']==tier
    assert result['fatigue_score']==round(expected,2)
    assert result['imputed_model_inputs']=={}
    assert bundle()['report']['tiers'][tier]['enabled']


def test_diagnostics_name_the_real_blocker_not_the_file_count():
    result=analyse({'training_load':319.26,'heart_rate':149,'duration_minutes':214.27},['800 m'])
    assert result['prediction_status']=='analysis_only'
    load=next(t for t in result['model_eligibility'] if t['tier']=='load_only')
    assert load['missing']==[]
    assert load['outside_range']==[dict(field='training_load',value=319.26,minimum=45.,maximum=87.)]
    assert 'fatigue_score' not in result
    assert result['analysis']['features']['training_load']==319.26


def test_hydration_score_survives_an_empty_text_label():
    result=model_frame(pd.DataFrame([{'hydration_score':.7,'hydration_level':None}]))
    assert result.hydration_score.iloc[0]==.7


def test_known_context_updates_one_upload_without_fabricating_source_data(revisions):
    save_session();old=repo.list_uploads('athlete1')[0];before=copy.deepcopy(old['records'])
    update_saved_assessment('athlete1',old,{'sleep_hours':7,'recovery_time':7})
    rows=repo.list_uploads('athlete1');new=rows[0]
    assert len(rows)==1 and new['id']==old['id'] and new['uploaded_at']==old['uploaded_at']
    assert new['records']==before
    assert new['records'][0].get('sleep_hours') is None
    assert new['snapshot']['model_tier']=='sleep_rest'
    assert new['snapshot']['used_model_inputs']==['sleep_hours','recovery_time']
    assert new['snapshot']['training_load']==319.26
    assert new['snapshot']['assessment_inputs']=={'sleep_hours':7.,'recovery_time':7.}
    raw=json.loads(revisions.execute('SELECT snapshot FROM qutwin_processed_uploads').fetchone()[0])
    assert len(raw['assessment_history'])==1
    assert 'fatigue_score' not in raw['assessment_history'][0]
    assert repo.list_uploads('another-athlete')==[]


def test_revised_scores_preserve_the_draft_and_completed_coach_decision(revisions):
    save_session({'training_load':60,'timestamp':'2026-09-01T06:00:00Z'})
    old=repo.list_uploads('athlete1')[0]
    _,token=repo.claim_ai('athlete1',old['id'])
    repo.finish_ai('athlete1',old['id'],token,text='Original draft',model='test')
    review=repo.coach_queue('coach1')[0]
    repo.review_recommendation('coach1',review['id'],'Approved','Original decision')
    original=repo.list_uploads('athlete1')[0]
    update_saved_assessment('athlete1',original,{'sleep_hours':7,'recovery_time':7})
    current=repo.list_uploads('athlete1')[0]
    assert current['ai_text']=='Original draft'
    assert not current['recommendation_is_current']
    assert current['recommendation_snapshot']==old['snapshot']
    assert current['snapshot']['model_tier']!='load_only'
    decision=repo.get_reviews('athlete1')[0]
    assert decision['status']=='Approved' and decision['final_text']=='Original draft'
    assert not decision['assessment_is_current']
    queue=repo.coach_queue('coach1')[0]
    assert queue['snapshot']==old['snapshot']
    assert not queue['assessment_is_current']


def test_new_draft_is_bound_to_the_current_saved_assessment(revisions):
    save_session();old=repo.list_uploads('athlete1')[0]
    update_saved_assessment('athlete1',old,{'sleep_hours':7,'recovery_time':7})
    current=repo.list_uploads('athlete1')[0]
    claimed,token=repo.claim_ai('athlete1',old['id'])
    assert claimed['snapshot']==current['snapshot']
    repo.finish_ai('athlete1',old['id'],token,text='Current draft',model='test')
    assert repo.list_uploads('athlete1')[0]['recommendation_is_current']
    assert repo.get_reviews('athlete1')[0]['assessment_is_current']


def test_stale_session_cross_athlete_and_generating_draft_cannot_be_overwritten(revisions):
    save_session();old=repo.list_uploads('athlete1')[0]
    with pytest.raises(PermissionError):
        update_saved_assessment('intruder',old,{'sleep_hours':7,'recovery_time':7})
    update_saved_assessment('athlete1',old,{'sleep_hours':7,'recovery_time':7})
    with pytest.raises(ValueError,match='another session'):
        update_saved_assessment('athlete1',old,{})
    current=repo.list_uploads('athlete1')[0]
    repo.claim_ai('athlete1',old['id'])
    with pytest.raises(ValueError,match='recommendation to finish'):
        update_saved_assessment('athlete1',current,{'sleep_hours':6,'recovery_time':6})
    assert repo.list_uploads('athlete1')[0]['snapshot']==current['snapshot']


@pytest.mark.parametrize('inputs',[{'sleep_hours':float('nan')},{'sleep_hours':25},
    {'timestamp':'2026-10-20T06:30:00'},{'fatigue_score':80},{'hydration_level':'excellent'}])
def test_invalid_context_does_not_change_the_saved_assessment(revisions,inputs):
    save_session();old=repo.list_uploads('athlete1')[0]
    with pytest.raises(ValueError):update_saved_assessment('athlete1',old,inputs)
    assert repo.list_uploads('athlete1')[0]['snapshot']==old['snapshot']


def test_original_unknown_measurements_stay_unknown_after_pipeline_upgrade(revisions):
    save_session();old=repo.list_uploads('athlete1')[0]
    update_saved_assessment('athlete1',old)
    current=repo.list_uploads('athlete1')[0]['snapshot']
    assert current['prediction_status']=='analysis_only'
    assert current['analysis_version']==ANALYSIS_VERSION
    assert 'fatigue_score' not in current and current['assessment_inputs']=={}


def test_recovery_form_updates_the_visible_model_result_in_both_themes(monkeypatch):
    import views.athlete.predictions as view
    import prediction.upload_processing as processing
    record={'training_load':319.26,'heart_rate':149,'duration_minutes':214.27}
    calls=[];html=[]
    for theme in ('dawn','dusk'):
        upload=dict(id=8,uploaded_at='2026-09-22',filename='long_activity.csv',events=['100 m','800 m'],
            records=[record],snapshot=dict(record,**analyse(record,['100 m','800 m'])),ai_text=None,ai_status='pending')
        def update(athlete,old,inputs=None):
            calls.append((athlete,inputs))
            active=dict(record,**(inputs or {}))
            upload['snapshot']=dict(active,**analyse(active,upload['events']),assessment_inputs=inputs)
        monkeypatch.setattr(view,'list_uploads',lambda _: [copy.deepcopy(upload)])
        monkeypatch.setattr(view,'get_reviews',lambda _: [])
        monkeypatch.setattr(view,'setting',lambda _: '')
        monkeypatch.setattr(processing,'update_saved_assessment',update)
        monkeypatch.setattr(view.st,'html',lambda value:html.append(value))
        app=AppTest.from_string("import streamlit as st\nst.session_state.update(user_id='athlete1',role='Athlete',logged_in=True)\nfrom views.athlete.predictions import athlete_predictions\nathlete_predictions()")
        app.session_state['studio_theme_athlete1']=theme
        app.run(timeout=20)
        assert not app.exception
        assert any('319.26' in str(frame.value) for frame in app.dataframe)
        app.number_input(key='assessment_athlete1_8_sleep_hours').set_value(7)
        app.number_input(key='assessment_athlete1_8_recovery_time').set_value(7)
        next(b for b in app.button if b.label=='Save measurements and update assessment').click().run()
        assert not app.exception
        assert calls[-1]==('athlete1',{'sleep_hours':7.,'recovery_time':7.})
        assert upload['snapshot']['model_tier']=='sleep_rest'
        score=f"{upload['snapshot']['fatigue_score']:.1f} / 100"
        assert any(score in text for text in html)
        assert any('Sleep + recovery time' in caption.value for caption in app.caption)


def test_partial_tier_selection_did_not_use_the_athlete_holdout():
    report=bundle()['report']
    for name in ('load_sleep','load_rest','sleep_rest'):
        spec=report['tiers'][name]
        development=spec['development_group_cv']['fatigue'][spec['selected_models']['fatigue']]
        assert development < .99*spec['event_only_development_mae']
    assert report['held_out_athletes']==67
