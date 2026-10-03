"""Chronological forecasting of recorded indices, never injury probabilities.
No backward interpolation. Model choice, interval calibration and test windows
are disjoint in target dates. Empirical bands have no guaranteed coverage.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

TARGETS={'fatigue_score':'Fatigue forecast','readiness_score':'Readiness forecast','twin_score':'Digital Twin score','health_index':'Health index'}
METHODS=('Last value','Recent median','Exponential level','Damped trend','Weekly repeat')

@dataclass
class Bundle:
    table:pd.DataFrame
    evaluation:pd.DataFrame
    model_weights:pd.DataFrame
    overall_validation_score:object
    data_points:int
    cycle_summary:dict


def predict(values,method,horizon):
    raw=np.asarray(values,dtype=float)
    good=raw[np.isfinite(raw)]
    if not len(good):return np.full(horizon,np.nan)
    last=good[-1]
    if method=='Last value':result=np.repeat(last,horizon)
    elif method=='Recent median':result=np.repeat(np.median(good[-7:]),horizon)
    elif method=='Exponential level':
        level=good[0]
        for value in good[1:]:level=.3*value+.7*level
        result=np.repeat(level,horizon)
    elif method=='Damped trend':
        recent=raw[-14:];x=np.flatnonzero(np.isfinite(recent))
        if len(x)<4:return predict(raw,'Last value',horizon)
        slope=np.polyfit(x,recent[x],1)[0]
        result=last+slope*np.cumsum(.85**np.arange(1,horizon+1))
    elif method=='Weekly repeat':
        if len(raw)<28 or not np.isfinite(raw[-7:]).all():return predict(raw,'Last value',horizon)
        result=np.resize(raw[-7:],horizon)
    else:raise ValueError('Unknown forecasting method')
    return np.clip(result,0,100)


def clean_history(history):
    if history is None or history.empty or 'timestamp' not in history:return pd.DataFrame()
    d=history.copy();d['day']=pd.to_datetime(d.timestamp,utc=True,errors='coerce',format='mixed').dt.floor('D')
    d=d.dropna(subset=['day'])
    cols=[]
    for key in TARGETS:
        if key in d:
            d[key]=pd.to_numeric(d[key],errors='coerce');d[key]=d[key].where(d[key].between(0,100));cols.append(key)
    if not cols or d.empty:return pd.DataFrame()
    # A daily index is the mean of available same-day assessments, not summed workload.
    return d.groupby('day')[cols].mean().sort_index().asfreq('D')


def errors(values,method,start,end,horizon=7):
    rows=[]
    for origin in range(max(7,start),end-horizon+1):
        if np.isfinite(values[:origin]).sum()<4:continue
        forecasts=predict(values[:origin],method,horizon)
        for h in range(horizon):
            actual=values[origin+h]
            if np.isfinite(actual):rows.append((h+1,float(actual-forecasts[h])))
    return rows


def fit_target(values,horizon):
    n=len(values);method='Last value';stage='Baseline · limited history';rows=[];bands={}
    # Date partitions, not shuffled rows; seven-day targets never cross a boundary.
    select_end=int(n*.5);cal_end=int(n*.75)
    if n>=56 and np.isfinite(values).sum()>=35:
        losses={}
        for candidate in METHODS:
            err=errors(values,candidate,14,select_end)
            if len(err)>=21:losses[candidate]=np.mean([abs(e) for _,e in err])
        if losses:
            method=min(losses,key=losses.get);stage='History-based projection'
            calibration=errors(values,method,select_end,cal_end)
            test=errors(values,method,cal_end,n)
            baseline=errors(values,'Last value',cal_end,n)
            for h in range(1,8):
                c=[abs(e) for step,e in calibration if step==h]
                t=[e for step,e in test if step==h]
                b=[e for step,e in baseline if step==h]
                width=float(np.quantile(c,.9,method='higher')) if len(c)>=10 else None
                if width is not None:bands[h]=width
                rows.append({'Horizon':h,'Method':method,'Test forecasts':len(t),
                    'MAE (points)':float(np.mean(np.abs(t))) if t else None,
                    'Baseline MAE (points)':float(np.mean(np.abs(b))) if b else None,
                    'RMSE (points)':float(np.sqrt(np.mean(np.square(t)))) if t else None,
                    'Band coverage on test':float(np.mean(np.abs(t)<=width)) if t and width is not None else None,
                    'Calibration forecasts':len(c)})
    point=predict(values,method,horizon)
    lower=np.full(horizon,np.nan);upper=lower.copy()
    for i in range(horizon):
        if i+1 in bands:
            lower[i]=max(0,point[i]-bands[i+1]);upper[i]=min(100,point[i]+bands[i+1])
    return point,lower,upper,rows,method,stage


def build_forecast_bundle(history_df,gender=None,cycles_df=None,coach_recommendation=None,horizon=7):
    if not 1<=horizon<=37:raise ValueError('Forecast horizon must be 1–37 days')
    daily=clean_history(history_df)
    if daily.empty:raise ValueError('No dated numeric index history is available')
    table=pd.DataFrame({'Date':pd.date_range(daily.index[-1]+pd.Timedelta(days=1),periods=horizon).date})
    evaluation=[];weights=[];stages=[]
    for target,label in TARGETS.items():
        if target not in daily or daily[target].notna().sum()==0:continue
        values=daily[target].to_numpy(dtype=float)
        point,low,high,rows,method,stage=fit_target(values,horizon)
        table[label]=np.round(point,1);table[label+' lower']=np.round(low,1);table[label+' upper']=np.round(high,1)
        for row in rows:row['Target']=label;evaluation.append(row)
        weights.append({'Target':label,'Selected method':method});stages.append(stage)
    if len(table.columns)==1:raise ValueError('No usable index measurements')
    table['Confidence']='History-based projection' if any(x=='History-based projection' for x in stages) else 'Baseline · limited history'
    table['Injury-risk result']='Not validated'
    table['Coach recommendation']=coach_recommendation or 'No approved coach recommendation available.'
    table['Forecast method']='; '.join(x['Target']+': '+x['Selected method'] for x in weights)
    return Bundle(table,pd.DataFrame(evaluation),pd.DataFrame(weights),None,int(daily.notna().any(axis=1).sum()),{})
