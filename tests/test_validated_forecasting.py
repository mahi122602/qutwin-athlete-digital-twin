import numpy as np
import pandas as pd
from forecasting.validated import clean_history,fit_target,build_forecast_bundle,errors


def history(n=100):
    return pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=n,tz='UTC'),'fatigue_score':45+8*np.sin(np.arange(n)/4)})

def test_missing_calendar_days_stay_missing():
    d=clean_history(pd.DataFrame({'timestamp':['2026-01-01','2026-01-04'],'fatigue_score':[20,80]}))
    assert len(d)==4 and d.fatigue_score.isna().sum()==2

def test_no_invented_readiness_or_injury_probability():
    b=build_forecast_bundle(history())
    assert len(b.table)==7
    assert 'Readiness forecast' not in b.table and 'Injury-risk score' not in b.table
    assert set(b.table['Injury-risk result'])=={'Not validated'}
    assert b.overall_validation_score is None

def test_test_period_cannot_select_method_or_calibrate_bands():
    y=history().fatigue_score.to_numpy()
    first=fit_target(y,7)
    altered=y.copy();altered[75:]=99
    second=fit_target(altered,7)
    assert first[4]==second[4]
    np.testing.assert_allclose(first[0]-first[1],second[0]-second[1])
    assert first[3]!=second[3]

def test_short_history_is_unvalidated_baseline():
    result=fit_target(np.array([40.,55.,30.]),7)
    assert np.all(result[0]==30) and np.isnan(result[1]).all() and result[3]==[]

def test_invalid_scores_not_clipped_into_observations():
    d=clean_history(pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=3),'fatigue_score':[-4,50,120]}))
    assert d.fatigue_score.notna().sum()==1

def test_errors_use_only_prior_observations():
    # Last value is 10 when forecast begins; later actual changes cannot alter it.
    y=np.array([10.]*7+[90.]*7)
    rows=errors(y,'Last value',7,14)
    assert rows==[(h,80.) for h in range(1,8)]

def test_bounds_and_horizon_specific_intervals():
    b=build_forecast_bundle(history(),horizon=10)
    assert b.table['Fatigue forecast'].between(0,100).all()
    assert b.table['Fatigue forecast lower'].iloc[:7].notna().all()
    assert b.table['Fatigue forecast lower'].iloc[7:].isna().all()
    assert set(b.evaluation.Horizon)==set(range(1,8))

def test_forecast_horizon_page_renders_and_changes_day():
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_string('''
import streamlit as st
import numpy as np
import pandas as pd
from forecasting.validated import build_forecast_bundle
from ui.forecast_horizon import render_forecast_horizon
h=pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=100),'fatigue_score':45+8*np.sin(np.arange(100)/4)})
b=build_forecast_bundle(h)
render_forecast_horizon(b.table,b)
''').run(timeout=20)
    assert not at.exception
    at.select_slider(key='horizon_focus').set_value(5).run(timeout=20)
    assert not at.exception
    assert len(at.get('plotly_chart'))==1
