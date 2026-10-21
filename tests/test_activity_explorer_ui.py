from streamlit.testing.v1 import AppTest
import pandas as pd
import pytest
from services.activity_explorer import build_explorer_data

CODE="""
import streamlit as st
st.session_state.update(user_id='athlete1',role='Athlete',logged_in=True)
from ui.studio_shell import apply_suite_theme
apply_suite_theme()
from views.athlete.visualisations import athlete_visualisations
athlete_visualisations()
"""


def data(records=None):
    return build_explorer_data([{'id':2,'filename':'Example.csv','uploaded_at':'2026-10-21',
        'records':records or [{'heart_rate':149,'duration_minutes':214.27,'training_load':319.26}],
        'snapshot':{}}])


@pytest.mark.parametrize('theme',['dawn','dusk'])
def test_single_undated_activity_renders_charts_instead_of_the_old_date_wall(monkeypatch,theme):
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:data())
    app=AppTest.from_string(CODE);app.session_state['studio_theme_athlete1']=theme
    app.run(timeout=20)
    assert not app.exception
    assert len(app.get('plotly_chart'))>=3
    assert [t.label for t in app.tabs]==['Understand your activity','Compare measurements','Technical details']
    assert any('149.0 bpm' in m.value for m in app.markdown)
    assert app.radio[0].options==['Activity comparison']
    assert not any('Add the real activity dates to see a timeline' in i.value for i in app.info)


def test_recorded_dates_unlock_timeline_and_switching_to_an_undated_measure_still_works(monkeypatch):
    dataset=data([{'heart_rate':140,'timestamp':'2026-10-01'},
                  {'heart_rate':150,'timestamp':'2026-10-02'},{'duration_minutes':40}])
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:dataset)
    app=AppTest.from_string(CODE).run()
    assert 'Timeline' in app.radio[0].options
    app.radio[0].set_value('Timeline').run()
    assert not app.exception
    app.selectbox(key='ax_athlete1_observed_measure').select('duration_minutes').run()
    assert not app.exception and app.radio[0].value=='Activity comparison'


def test_missing_fields_are_not_offered_and_no_data_has_a_clear_message(monkeypatch):
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:data([{'heart_rate':150}]))
    app=AppTest.from_string(CODE).run()
    assert not app.exception
    assert app.selectbox(key='ax_athlete1_observed_measure').options==['Average exercise heart rate']
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:build_explorer_data([]))
    app.run()
    assert not app.exception and not app.get('plotly_chart')
    assert any('starts with a saved activity' in i.value for i in app.info)


def test_saved_upload_filter_changes_the_chart_and_full_export(monkeypatch):
    dataset=build_explorer_data([{'id':i,'filename':f'Example{i}.csv','records':[{'heart_rate':value}],'snapshot':{}}
                                for i,value in [(1,140),(2,160)]])
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:dataset)
    app=AppTest.from_string(CODE).run()
    app.selectbox(key='ax_athlete1_upload').select('2').run()
    assert not app.exception
    assert any('160.0 bpm' in m.value for m in app.markdown)
    assert app.dataframe[0].value['Average exercise heart rate (bpm)'].tolist()==[160]


def test_known_date_link_targets_the_selected_upload(monkeypatch):
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:data())
    app=AppTest.from_string(CODE).run()
    app.button(key='ax_athlete1_date_link').click().run()
    assert app.session_state['current_page']=='Predictions & Coach Recommendations'
    assert app.session_state['studio_target_upload']=='2'


def test_coach_explorer_uses_the_same_charts_without_the_athlete_edit_link(monkeypatch):
    monkeypatch.setattr('ui.activity_explorer.load_explorer_data',lambda _:data())
    code="""import streamlit as st
st.session_state.update(user_id='coach1',role='Coach',logged_in=True)
from ui.activity_explorer import render_activity_explorer
render_activity_explorer('athlete1',key_prefix='ax_coach_athlete1_')
"""
    app=AppTest.from_string(code).run()
    assert not app.exception and app.get('plotly_chart')
    assert not any(b.label=='Add a known activity date' for b in app.button)


def test_explorer_rejects_another_athlete_before_reading_any_records(monkeypatch):
    from database import workflow_repository
    calls=[]
    monkeypatch.setattr(workflow_repository,'list_uploads',lambda athlete:calls.append(athlete) or [])
    code="""import streamlit as st
st.session_state.update(user_id='athlete1',role='Athlete',logged_in=True)
from services.activity_explorer import load_explorer_data
try:load_explorer_data('another-athlete')
except PermissionError as exc:st.warning(str(exc))
"""
    app=AppTest.from_string(code).run()
    assert not app.exception and app.warning
    assert calls==[]
