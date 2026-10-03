from streamlit.testing.v1 import AppTest
from ui.first_upload_forecast import baseline_table
from views.athlete.simulation import scenario_values

def test_baseline_repeats_only_known_values():
    frame=baseline_table({'fatigue_score':43,'duration_minutes':30,'readiness_score':float('nan')})
    assert len(frame)==7
    assert frame['Estimated fatigue'].tolist()==[43]*7
    assert 'Estimated readiness' not in frame
    assert 'timestamp' not in frame

def test_scenario_preserves_missing_and_handles_rest():
    assert scenario_values(30,None,-100)=={'duration':0,'load':None}
    assert scenario_values(30,50,20)=={'duration':36,'load':60}

def test_forecasting_single_undated_upload_renders():
    at=AppTest.from_string('''
import streamlit as st
from unittest.mock import patch
import pandas as pd
st.session_state.user_id='test'
from views.forecasting_page import athlete_forecasting
row={'id':1,'filename':'run.csv','snapshot':{'duration_minutes':30,'fatigue_score':43}}
with patch('views.forecasting_page.ensure_forecasting_schema'),patch('views.forecasting_page.get_forecasting_profile',return_value={'gender':'Male'}),patch('views.forecasting_page.get_athlete_twin_history',return_value=pd.DataFrame()),patch('database.workflow_repository.list_uploads',return_value=[row]):
    athlete_forecasting()
''').run(timeout=20)
    assert not at.exception
    assert len(at.get('plotly_chart'))==1
    assert any('Baseline projection' in x.value for x in at.info)

def test_simulator_partial_data_and_interaction():
    at=AppTest.from_string('''
import streamlit as st
from unittest.mock import patch
st.session_state.user_id='test'
from views.athlete.simulation import athlete_simulation
with patch('views.athlete.simulation.list_uploads',return_value=[{'id':1,'filename':'run.csv','snapshot':{'duration_minutes':30,'training_load':50}}]):
    athlete_simulation()
''').run(timeout=20)
    assert not at.exception
    assert len(at.get('plotly_chart'))==1
    assert at.metric[0].value=='24.0 min'
    at.radio(key='direction_A').set_value('Longer').run()
    assert not at.exception
    assert at.metric[0].value=='36.0 min'
