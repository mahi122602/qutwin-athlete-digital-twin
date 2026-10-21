"""Chart source records even when one activity has no known date."""
import copy
import pandas as pd
import pytest
from services.activity_explorer import (build_explorer_data,available_measures,describe_measure,
    value_sources,export_table,MEASURES,ESTIMATES)
from ui.activity_explorer_charts import measure_chart,relationship_chart,coverage_chart,correlation_chart
from ui.studio_shell import PALETTES


def upload(records,snapshot=None,ident=2):
    return dict(id=ident,filename='Example activity.csv',uploaded_at='2026-10-21T12:00:00Z',
                records=records,snapshot=snapshot or {})


def test_one_undated_upload_has_a_real_bar_without_a_fabricated_timestamp():
    original=upload([{'heart_rate':149,'duration_minutes':214.27,'training_load':319.26}])
    before=copy.deepcopy(original);data=build_explorer_data([original])
    frame=data.observations;fig=measure_chart(frame,'heart_rate')
    assert frame['_plot_date'].isna().all()
    assert fig.data[0].type=='bar' and list(fig.data[0].x)==[149]
    assert '149.0 bpm' in describe_measure(frame,'heart_rate')
    assert 'Activity date unknown' in fig.data[0].customdata[0]
    assert original==before


def test_all_activities_in_an_export_are_retained_and_measures_need_values():
    data=build_explorer_data([upload([{'heart_rate':140},{'heart_rate':150},{'heart_rate':160}])])
    assert len(data.observations)==3
    assert available_measures(data.observations)==['heart_rate']
    assert len(measure_chart(data.observations,'heart_rate').data[0].x)==3
    assert data.estimates.empty


def test_confirmed_context_is_overlaid_only_on_its_assessed_activity():
    records=[{'_source_row':1,'heart_rate':140,'timestamp':'2026-10-01T06:00:00Z'},
             {'_source_row':2,'heart_rate':150,'timestamp':None}]
    snapshot={'_source_row':2,'sleep_hours':7,'recovery_time':6,'timestamp':'2026-10-02T06:00:00Z',
              'assessment_inputs':{'sleep_hours':7,'recovery_time':6,'timestamp':'2026-10-02T06:00:00Z'}}
    original=upload(records,snapshot);before=copy.deepcopy(original)
    frame=build_explorer_data([original]).observations
    assert frame.sleep_hours.isna().iloc[0] and frame.sleep_hours.iloc[1]==7
    assert frame['_date_label'].iloc[1].startswith('02 Oct 2026')
    assert value_sources(frame,'sleep_hours').tolist()==['Source export','Athlete confirmed']
    assert original==before


def test_unprocessed_active_revision_and_derived_load_keep_provenance():
    original=upload([{'heart_rate':150,'duration_minutes':40}],{'heart_rate':120,
        'active_assessment':{'heart_rate':150,'training_load':60,
            'training_load_origin':'QUTwin estimate: average HR × minutes / 100'}})
    data=build_explorer_data([original])
    assert data.observations.heart_rate.iloc[0]==150
    assert value_sources(data.observations,'training_load').iloc[0]=='Calculated load proxy'
    assert 'Load provenance' in export_table(data.observations)


def test_actual_day_without_start_time_is_chartable_and_labelled_date_only():
    data=build_explorer_data([upload([{'heart_rate':150,'activity_date_only':'2026-10-10','activity_timezone':'Australia/Brisbane'}])])
    frame=data.observations
    assert frame['_plot_date'].notna().all()
    assert frame['_date_precision'].iloc[0]=='Date only'
    assert frame['_date_label'].iloc[0]=='10 Oct 2026 · date only'
    assert '00:00' not in frame['_date_label'].iloc[0]
    assert len(measure_chart(frame,'heart_rate','Timeline').data[0].x)==1


def test_upload_time_and_filename_are_not_activity_dates():
    original=upload([{'heart_rate':150}]);original['filename']='Run20261010060000.csv'
    frame=build_explorer_data([original]).observations
    assert frame['_plot_date'].isna().all()
    assert frame['_date_precision'].tolist()==['Unknown']


def test_timeline_excludes_unknown_dates_and_keeps_missing_value_gaps():
    records=[{'timestamp':'2026-10-01','heart_rate':140},
             {'timestamp':'2026-10-02','heart_rate':None},
             {'timestamp':'2026-10-03','heart_rate':160},{'heart_rate':180}]
    frame=build_explorer_data([upload(records)]).observations
    fig=measure_chart(frame,'heart_rate','Timeline')
    assert len(fig.data[0].x)==3 and pd.isna(fig.data[0].y[1])
    assert fig.data[0].connectgaps is False
    assert len(measure_chart(frame,'heart_rate').data[0].x)==3


def test_model_output_is_not_replicated_across_every_sensor_record():
    snapshot={'prediction_status':'research_estimate','fatigue_score':42,'readiness_score':70,
              'model_version':'adaptive-v3','model_tier':'load_only','primary_event':'800 m'}
    data=build_explorer_data([upload([{'heart_rate':140},{'heart_rate':150},{'heart_rate':160}],snapshot)])
    assert len(data.observations)==3 and len(data.estimates)==1
    assert 'fatigue_score' not in data.observations
    assert data.estimates.fatigue_score.tolist()==[42]
    assert 'Model version' in export_table(data.estimates,ESTIMATES)


def test_analysis_only_never_becomes_a_model_prediction():
    data=build_explorer_data([upload([{'heart_rate':150,'fatigue_score':99}],
        {'prediction_status':'analysis_only','fatigue_score':99})])
    assert data.estimates.empty and 'fatigue_score' not in data.observations


def test_incompatible_model_tiers_remain_separate_timeline_series():
    uploads=[upload([{'heart_rate':150,'timestamp':f'2026-10-0{i}'}],
        {'prediction_status':'research_estimate','fatigue_score':40+i,'timestamp':f'2026-10-0{i}',
         'model_version':version,'model_tier':tier,'primary_event':'800 m'},i)
        for i,version,tier in [(1,'adaptive-v2','load_only'),(2,'adaptive-v3','load_only'),(3,'adaptive-v3','sleep_rest')]]
    data=build_explorer_data(uploads)
    fig=measure_chart(data.estimates,'fatigue_score','Timeline',ESTIMATES)
    assert len(fig.data)==3 and all(len(trace.x)==1 for trace in fig.data)


def test_known_zero_is_not_missing_and_invalid_numeric_values_are_not_charted():
    data=build_explorer_data([upload([{'steps':0,'heart_rate':900,'duration_minutes':'bad'}])])
    assert available_measures(data.observations)==['steps']
    assert list(measure_chart(data.observations,'steps').data[0].x)==[0]
    assert data.rejected_values==2
    fig=coverage_chart(data.observations)
    assert fig.data[0].x[0]==0 and fig.data[1].x[0]==1


def test_one_undated_pair_is_still_a_real_relationship_point():
    frame=build_explorer_data([upload([{'heart_rate':149,'duration_minutes':214.27}])]).observations
    fig=relationship_chart(frame,'heart_rate','duration_minutes')
    assert list(fig.data[0].x)==[149] and list(fig.data[0].y)==[214.27]
    assert correlation_chart(frame) is None


def test_correlation_needs_five_actual_pairs_not_separate_column_counts():
    rows=[{'heart_rate':140+i,'duration_minutes':30+i} for i in range(4)]
    rows += [{'heart_rate':149},{'duration_minutes':40}]
    frame=build_explorer_data([upload(rows)]).observations
    fig=correlation_chart(frame)
    assert fig is None
    rows[4]['duration_minutes']=40
    frame=build_explorer_data([upload(rows)]).observations
    fig=correlation_chart(frame)
    assert fig.data[0].customdata[0][1]==5


@pytest.mark.parametrize('theme',['dawn','dusk'])
def test_charts_and_axes_use_the_selected_theme(theme):
    p=PALETTES[theme]
    frame=build_explorer_data([upload([{'heart_rate':150,'duration_minutes':40}])]).observations
    for figure in (measure_chart(frame,'heart_rate',p=p),relationship_chart(frame,'heart_rate','duration_minutes',p),coverage_chart(frame,p)):
        assert figure.layout.font.color==p['ink']
        assert figure.layout.paper_bgcolor==p['panel']
        assert figure.layout.xaxis.color==p['ink']


def test_bars_are_paginated_and_csv_retains_every_record():
    frame=build_explorer_data([upload([{'heart_rate':100+i} for i in range(65)])]).observations
    assert len(measure_chart(frame,'heart_rate',page=1).data[0].x)==30
    assert len(measure_chart(frame,'heart_rate',page=3).data[0].x)==5
    assert len(export_table(frame))==65


def test_legacy_measurements_and_scores_are_visible_without_known_dates():
    legacy=pd.DataFrame([{'heart_rate':150,'fatigue_score':45,'readiness_score':55}])
    data=build_explorer_data([],legacy)
    assert available_measures(data.observations)==['heart_rate']
    assert data.estimates.fatigue_score.tolist()==[45]
    assert data.observations['_plot_date'].isna().all()


def test_large_timeline_samples_real_points_and_keeps_the_full_export():
    rows=[{'timestamp':time.isoformat(),'heart_rate':140+i%30} for i,time in enumerate(pd.date_range('2026-10-01',periods=5000,freq='min',tz='UTC'))]
    frame=build_explorer_data([upload(rows)]).observations
    fig=measure_chart(frame,'heart_rate','Timeline')
    assert len(fig.data[0].x)==2000 and fig.data[0].mode=='markers'
    assert pd.to_datetime(fig.data[0].x[0],utc=True)==frame['_plot_date'].iloc[0]
    assert pd.to_datetime(fig.data[0].x[-1],utc=True)==frame['_plot_date'].iloc[-1]
    assert len(export_table(frame))==5000


def test_modern_uploads_do_not_depend_on_the_legacy_state_table(monkeypatch):
    from database import workflow_repository,twin_repository
    from services.activity_explorer import load_explorer_data
    monkeypatch.setattr(workflow_repository,'list_uploads',lambda _: [upload([{'heart_rate':150}])])
    def fail(_):raise AssertionError('Legacy data should not be loaded for saved source records.')
    monkeypatch.setattr(twin_repository,'get_athlete_twin_history',fail)
    assert load_explorer_data('athlete1').observations.heart_rate.tolist()==[150]


def test_imported_load_scales_are_not_connected_to_a_calculated_proxy():
    uploads=[upload([{'training_load':value,'timestamp':f'2026-10-0{i}',
        'training_load_origin':origin}],ident=i) for i,value,origin in [
        (1,60,'Uploaded load; scale unverified'),(2,70,'Uploaded load; scale unverified'),
        (3,65,'QUTwin estimate: average HR × minutes / 100')]]
    fig=measure_chart(build_explorer_data(uploads).observations,'training_load','Timeline')
    assert len(fig.data)==3 and all(len(trace.x)==1 for trace in fig.data)
