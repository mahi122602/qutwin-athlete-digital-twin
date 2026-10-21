import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from ui.performance_story import journal_data, story_figure


CODE = """
import streamlit as st
st.session_state.update(user_id='athlete1',role='Athlete',logged_in=True)
from ui.studio_shell import render_shell
st.session_state.setdefault('current_page','Digital Twin History')
render_shell()
from views.athlete.history import athlete_history
athlete_history()
"""


def sessions(dated=False):
    return pd.DataFrame([dict(workflow_id=10+i, filename=f'Session {i+1}.csv',
        _uploaded_at=f'2026-10-{21-i:02d}T10:00:00Z',
        activity_date_only=f'2026-10-{1+i:02d}' if dated and i<2 else None,
        timestamp_precision='day' if dated and i<2 else 'unknown',
        duration_minutes=40+i*5, heart_rate=140+i*2, training_load=50+i*3,
        prediction_status='research_estimate', fatigue_score=40+i,
        readiness_score=60-i, model_version='adaptive-v3', model_tier='load_only',
        primary_event='100 m') for i in range(6)])


def test_six_undated_uploads_keep_values_and_never_borrow_save_dates():
    frame=sessions(); original=frame.copy(deep=True)
    data=journal_data(frame)
    assert len(data.observations)==len(data.estimates)==6
    assert data.observations['_plot_date'].isna().all()
    assert data.estimates['_plot_date'].isna().all()
    assert data.observations.duration_minutes.tolist()==[40,45,50,55,60,65]
    pd.testing.assert_frame_equal(frame,original)
    chart=story_figure(data.observations,'duration_minutes','Activity comparison',selected='2')
    assert chart.data[0].type=='bar'
    assert list(chart.data[0].x)==[40,45,50,55,60,65]
    assert 'Session 3.csv' in chart.data[0].y[2]
    assert chart.data[0].marker.color[2]!=chart.data[0].marker.color[0]


def test_date_only_values_unlock_time_view_and_archive_keeps_date_precision():
    from views.athlete.history import format_upload_history
    frame=sessions(True); data=journal_data(frame)
    assert data.observations['_plot_date'].notna().sum()==2
    chart=story_figure(data.observations,'duration_minutes','Timeline')
    assert list(chart.data[0].y)==[40,45]
    table=format_upload_history(frame)
    assert table.iloc[0]['Activity date']=='01 Oct 2026 · date only'
    assert table.iloc[2]['Activity date']=='—'


def test_bad_measurements_stay_missing_and_zero_steps_remain_zero():
    frame=pd.DataFrame([dict(filename='one.csv',steps=0,heart_rate=np.nan,duration_minutes=-5,
                            _uploaded_at='2026-10-21',fatigue_score=70)])
    data=journal_data(frame)
    assert data.observations.steps.iloc[0]==0
    assert data.observations.duration_minutes.isna().all()
    assert data.observations.heart_rate.isna().all()
    assert data.estimates.empty  # Unlabelled scores are not promoted to model results.


@pytest.mark.parametrize('theme',['dawn','dusk'])
def test_real_undated_summaries_show_spotlight_comparison_and_date_action(monkeypatch,theme):
    monkeypatch.setattr('views.athlete.history.get_upload_history',lambda _:sessions())
    app=AppTest.from_string(CODE)
    app.session_state['studio_theme_athlete1']=theme
    app.run(timeout=20)
    assert not app.exception
    assert len(app.get('plotly_chart'))==1
    assert [t.label for t in app.tabs]==['Performance story','All records & advice','Latest summary']
    assert any(b.label=='Review activity & add its date' for b in app.button)
    assert not any('enable a timeline' in i.value for i in app.info)
    assert next(m.value for m in app.metric if m.label=='Activity dates known')=='0 / 6'
    app.selectbox(key='ps_athlete1_activity').select('2').run()
    assert not app.exception
    app.button(key='ps_athlete1_date').click().run()
    assert app.session_state['studio_target_upload']=='12'
    assert app.session_state['current_page']=='Predictions & Coach Recommendations'


def test_timeline_and_measurement_explorer_navigation(monkeypatch):
    monkeypatch.setattr('views.athlete.history.get_upload_history',lambda _:sessions(True))
    app=AppTest.from_string(CODE).run(timeout=20)
    assert not app.exception
    assert 'Over time' in app.radio(key='ps_athlete1_view').options
    app.radio(key='ps_athlete1_view').set_value('Timeline').run()
    assert not app.exception
    app.selectbox(key='ps_athlete1_group').select('Research estimates').run()
    assert not app.exception
    app.button(key='ps_athlete1_explore_button').click().run()
    assert app.session_state['current_page']=='Visualisations / Graphs'


def test_journal_with_only_an_unmapped_file_still_has_a_useful_next_step(monkeypatch):
    monkeypatch.setattr('views.athlete.history.get_upload_history',lambda _:pd.DataFrame([{'filename':'unmapped.csv','_uploaded_at':'2026-10-21'}]))
    app=AppTest.from_string(CODE).run(timeout=20)
    assert not app.exception and not app.get('plotly_chart')
    assert any('no usable numeric measurements' in i.value for i in app.info)
    assert app.button(key='ps_athlete1_explore_button')
