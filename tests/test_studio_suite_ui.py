from streamlit.testing.v1 import AppTest

BASE="""
import streamlit as st
st.session_state['logged_in']=True
st.session_state['role']='Athlete'
st.session_state['user_id']='test-athlete'
st.session_state.setdefault('current_page','Digital Twin History')
from ui.studio_shell import render_shell,apply_suite_theme
render_shell()
"""
def test_shell_theme_and_navigation():
    at=AppTest.from_string(BASE).run()
    assert not at.exception
    assert not any(b.key=='suite_theme' for b in at.button)
    at.session_state['studio_theme_test-athlete']='dusk'
    at.button(key='suite_nav_Forecasting').click().run()
    assert at.session_state['current_page']=='Forecasting'
    assert at.session_state['studio_theme_test-athlete']=='dusk'

def test_journal_empty_and_populated_render_without_errors():
    code=BASE+"""
import pandas as pd
from unittest.mock import patch
from views.athlete.history import athlete_history
frame=pd.DataFrame([{'timestamp':None,'_uploaded_at':'2026-09-20','filename':'run.csv','events':'400 m','fatigue_score':None,'readiness_score':None,'injury_risk':None,'recommendation':'Draft pending'}])
with patch('views.athlete.history.get_upload_history',return_value=frame):athlete_history()
apply_suite_theme()
"""
    at=AppTest.from_string(code).run();assert not at.exception
    assert len(at.tabs)==3
    assert any('actual activity dates' in x.value for x in at.info)

def test_deletion_requires_confirmation_and_does_not_run_on_render():
    code=BASE+"""
from unittest.mock import patch
from views.athlete.privacy_controls import render_delete_account
with patch('views.athlete.privacy_controls.delete_my_account') as delete:
    render_delete_account()
    st.session_state['deletion_calls']=delete.call_count
"""
    at=AppTest.from_string(code).run();assert not at.exception
    assert at.session_state['deletion_calls']==0
    at.button[-1].click().run()
    assert at.session_state['deletion_calls']==0
    assert any('type DELETE' in x.value for x in at.error)

def test_cycle_form_has_no_invented_dates():
    code=BASE+"""
import pandas as pd
from unittest.mock import patch
from views.athlete.cycle_tracking import render_cycle_tracking
with patch('views.athlete.cycle_tracking.get_menstrual_history',return_value=pd.DataFrame()):render_cycle_tracking('test-athlete')
"""
    at=AppTest.from_string(code).run();assert not at.exception
    assert all(x.value is None for x in at.date_input)
    at.button[-1].click().run()
    assert any('Choose the day' in x.value for x in at.error)

def test_assessment_recommendation_and_evidence_tabs():
    code=BASE+"""
from unittest.mock import patch
from views.athlete.predictions import athlete_predictions
uploads=[{'id':1,'uploaded_at':'2026-09-20','filename':'run.csv','events':['400 m'],'snapshot':{'model_version':'adaptive-v2','prediction_status':'research_estimate','fatigue_score':48,'readiness_score':52,'injury_risk':'Low'},'ai_text':'Saved draft for coach review','ai_status':'ready'}]
with patch('views.athlete.predictions.list_uploads',return_value=uploads),patch('views.athlete.predictions.get_reviews',return_value=[]),patch('views.athlete.predictions.setting',return_value=None):
    athlete_predictions()
"""
    at=AppTest.from_string(code).run();assert not at.exception
    assert [t.label for t in at.tabs]==['Your summary','Your recommendation']
    assert any('Saved draft' in m.value for m in at.markdown)
    assert not at.json
    assert not at.warning
    assert not at.expander

def test_male_outlook_does_not_ask_for_period_dates():
    code=BASE+"""
from unittest.mock import patch
import pandas as pd
from views.forecasting_page import athlete_forecasting
with patch('views.forecasting_page.ensure_forecasting_schema'),patch('views.forecasting_page.get_forecasting_profile',return_value={'gender':'Male'}),patch('views.forecasting_page.get_athlete_twin_history',return_value=pd.DataFrame()),patch('database.workflow_repository.list_uploads',return_value=[]):
    athlete_forecasting()
"""
    at=AppTest.from_string(code).run();assert not at.exception
    assert not at.date_input
    assert not any('menstrual' in x.label.lower() for x in at.checkbox)

def test_female_cycle_tracking_is_opt_in():
    code=BASE+"""
from unittest.mock import patch
import pandas as pd
from views.forecasting_page import athlete_forecasting
with patch('views.forecasting_page.ensure_forecasting_schema'),patch('views.forecasting_page.get_forecasting_profile',return_value={'gender':'Female','menstrual_tracking_enabled':False}),patch('views.forecasting_page.get_athlete_twin_history',return_value=pd.DataFrame()),patch('database.workflow_repository.list_uploads',return_value=[]):
    athlete_forecasting()
"""
    at=AppTest.from_string(code).run();assert not at.exception
    assert any('menstrual' in x.label.lower() and not x.value for x in at.checkbox)
    assert not at.date_input

def test_chart_fonts_override_legacy_colours_in_both_themes():
    from unittest.mock import patch
    import plotly.graph_objects as go
    from ui.studio_shell import PALETTES,style_chart
    for palette in PALETTES.values():
        fig=go.Figure(go.Scatter(x=[1,2],y=[40,60]))
        fig.update_layout(font_color='#eeeeee',xaxis_tickfont_color='#eeeeee',yaxis_title_font_color='#eeeeee')
        with patch('ui.studio_shell.palette',return_value=palette):style_chart(fig)
        assert fig.layout.xaxis.tickfont.color==palette['ink']
        assert fig.layout.yaxis.title.font.color==palette['ink']
        assert fig.layout.legend.font.size>=16
        assert fig.layout.paper_bgcolor==palette['panel']
