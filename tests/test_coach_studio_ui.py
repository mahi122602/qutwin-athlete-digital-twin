"""Smoke all live UI routes with isolated fixture data, never a real database."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
FIXTURE=Path(__file__).parent/'fixtures'/'coach_studio_preview.py'
@pytest.mark.parametrize('theme',['dawn','dusk'])
@pytest.mark.parametrize('page',['Dashboard','Athletes','Teams','Team Detail','Athlete Detail','Intelligence','Visualisation','Forecasting','History','Timeline','Model Evaluation','Reviews','Connections','Notifications','Profile'])
def test_coach_pages_render(theme,page):
    app=AppTest.from_file(str(FIXTURE),default_timeout=15)
    app.session_state['coach_page']=page
    app.session_state['studio_theme_preview-coach']=theme
    app.run()
    assert not app.exception
    assert not app.error

def test_theme_and_row_navigation():
    app=AppTest.from_file(str(FIXTURE),default_timeout=15).run()
    app.button(key='coach_theme').click().run()
    assert app.session_state['studio_theme_preview-coach']=='dusk'
    app.button(key='csnavAthletes').click().run()
    app.button(key='view_roster_athlete1').click().run()
    assert app.session_state['coach_page']=='Athlete Detail'
    assert app.session_state['coach_athlete']=='athlete1'
    assert app.selectbox(key='cs_select_Athlete Detail').value=='athlete1'
    assert not app.exception
