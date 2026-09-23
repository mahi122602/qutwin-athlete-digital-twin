"""Fitted local-level state estimate over dated, version-consistent research scores.

This is a statistical smoothing diagnostic, never an additional injury prediction.
Missing calendar dates stay missing; no synthetic History entries are created.
"""
import warnings
import numpy as np
import pandas as pd

def personal_state(current, previous):
    timestamp=pd.to_datetime(current.get('timestamp'),utc=True,errors='coerce')
    if pd.isna(timestamp) or current.get('fatigue_score') is None:return {'status':'not_ready','reason':'A dated fatigue estimate is needed.'}
    usable=[]
    for s in previous:
        t=pd.to_datetime(s.get('timestamp'),utc=True,errors='coerce')
        if (pd.notna(t) and t<timestamp and s.get('model_version')==current.get('model_version')
            and s.get('model_tier')==current.get('model_tier') and s.get('primary_event')==current.get('primary_event')):
            try:v=float(s.get('fatigue_score'))
            except (ValueError,TypeError):continue
            if np.isfinite(v):usable.append((t,v))
    daily={}
    for t,v in sorted(usable):daily[t.normalize()]=v
    if len(daily)<14:return {'status':'not_ready','reason':'At least 14 earlier observed days with comparable model estimates are needed; missing days are not zero.'}
    if (timestamp-min(daily)).days>730:return {'status':'not_ready','reason':'Use recent comparable history within two years.'}
    try:
        from statsmodels.tsa.statespace.structural import UnobservedComponents
        series=pd.Series(daily).sort_index().asfreq('D')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit=UnobservedComponents(series,level='local level').fit(disp=False,maxiter=100)
        if not fit.mle_retvals.get('converged',False):return {'status':'not_ready','reason':'The personal state model did not converge.'}
        steps=max(1,(timestamp.normalize()-series.index[-1]).days)
        forecast=fit.get_forecast(steps);mean=float(forecast.predicted_mean.iloc[-1]);variance=float(forecast.var_pred_mean.iloc[-1])
        observation_variance=max(float(current.get('validation_metrics',{}).get('fatigue_rmse',10))**2,1e-6)
        gain=variance/(variance+observation_variance);posterior=mean+gain*(float(current['fatigue_score'])-mean)
        return {'status':'available','method':'Local-level state-space model fitted to earlier days; Gaussian update with current estimate',
                'earlier_observed_days':len(daily),'prior_fatigue':round(mean,2),'updated_fatigue_state':round(posterior,2),
                'posterior_standard_deviation':round(float(np.sqrt((1-gain)*variance)),2),
                'limitation':'Smoothed research estimates, not measured physiology; correlated model errors can invalidate uncertainty assumptions.'}
    except (ValueError,RuntimeError,np.linalg.LinAlgError):
        return {'status':'not_ready','reason':'History does not support a stable personal state model yet.'}
