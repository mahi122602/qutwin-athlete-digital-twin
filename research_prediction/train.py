"""Offline model selection. No training or downloading runs during page navigation."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, balanced_accuracy_score, f1_score
from catboost import CatBoostRegressor, CatBoostClassifier
from research_prediction.features import NUMERIC, model_frame, canonical_event

ROOT=Path(__file__).resolve().parents[1]
TIERS={'complete':NUMERIC, 'load_recovery':['training_load','sleep_hours','recovery_time','hydration_score'],
       'recovery':['sleep_hours','recovery_time','hydration_score'], 'load_only':['training_load']}

def make_model(name, target, columns):
    prepare=ColumnTransformer([
        ('numeric',Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]),columns),
        ('event',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['event'])])
    if name=='linear':
        model=Ridge(alpha=10) if target=='fatigue' else LogisticRegression(max_iter=1000,class_weight='balanced')
    elif name=='forest':
        cls=RandomForestRegressor if target=='fatigue' else RandomForestClassifier
        extra={} if target=='fatigue' else {'class_weight':'balanced'}
        model=cls(n_estimators=120,max_depth=8,min_samples_leaf=10,random_state=42,n_jobs=1,**extra)
    else:
        cls=CatBoostRegressor if target=='fatigue' else CatBoostClassifier
        extra={} if target=='fatigue' else {'auto_class_weights':'Balanced'}
        model=cls(iterations=160,depth=4,learning_rate=.04,random_seed=42,verbose=False,
                  allow_writing_files=False,thread_count=1,**extra)
    return Pipeline([('prepare',prepare),('model',model)])

def metrics(y,f,r,rp,baseline):
    return {'fatigue_mae':float(mean_absolute_error(y,f)),
            'fatigue_rmse':float(np.sqrt(mean_squared_error(y,f))), 'fatigue_r2':float(r2_score(y,f)),
            'mean_baseline_mae':float(mean_absolute_error(y,baseline)),
            'risk_balanced_accuracy':float(balanced_accuracy_score(r,rp)),
            'risk_weighted_f1':float(f1_score(r,rp,average='weighted',zero_division=0)),
            'absolute_error_90th_percentile':float(np.quantile(np.abs(y-f),.9))}

def main():
    path=ROOT/'data/athlete_training_dataset.csv';data=pd.read_csv(path)
    required={'athlete_id','race_type','fatigue_score','injury_risk',*NUMERIC[:-1],'hydration_level'}
    if required-set(data):raise ValueError('Training dataset missing columns: '+', '.join(sorted(required-set(data))))
    data['event_type']=data.race_type.map(canonical_event);X=model_frame(data)
    y=pd.to_numeric(data.fatigue_score,errors='raise').to_numpy();risk=data.injury_risk.astype(str).to_numpy();groups=data.athlete_id
    if X[NUMERIC].isna().any().any() or not np.isfinite(y).all():raise ValueError('Training measurements/targets require review; no silent row dropping.')
    if not set(risk)<= {'Low','Medium','High'}:raise ValueError('Document the risk label mapping before training.')
    dev,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(X,y,groups))
    if groups.iloc[dev].nunique()<5:raise ValueError('At least five development athletes are needed.')
    fitted={};reports={}
    dates=pd.to_datetime(data.get('date'),dayfirst=True,errors='coerce')
    for tier,columns in TIERS.items():
        scores={};chosen={}
        for target,labels in [('fatigue',y),('risk',risk)]:
            ranking={}
            for name in ('linear','forest','catboost'):
                fold_scores=[]
                for train,val in GroupKFold(3).split(X.iloc[dev],y[dev],groups.iloc[dev]):
                    tr,va=dev[train],dev[val];m=make_model(name,target,columns)
                    m.fit(X.iloc[tr],labels[tr]);p=np.asarray(m.predict(X.iloc[va])).reshape(-1)
                    fold_scores.append(mean_absolute_error(y[va],p) if target=='fatigue' else balanced_accuracy_score(risk[va],p))
                ranking[name]=float(np.mean(fold_scores))
            chosen[target]=(min if target=='fatigue' else max)(ranking,key=ranking.get);scores[target]=ranking
        pair={target:make_model(name,target,columns).fit(X.iloc[dev],y[dev] if target=='fatigue' else risk[dev]) for target,name in chosen.items()}
        fp=pair['fatigue'].predict(X.iloc[test]);rp=np.asarray(pair['risk'].predict(X.iloc[test])).reshape(-1)
        report={'features':columns,'selected_models':chosen,'development_group_cv':scores,
                'metrics':metrics(y[test],fp,risk[test],rp,np.repeat(y[dev].mean(),len(test))),
                'ranges':{c:[float(X.iloc[dev][c].min()),float(X.iloc[dev][c].max())] for c in columns}}
        # Separate temporal diagnostic; three dates are not a robust forecasting benchmark.
        unique=sorted(dates.dropna().unique())
        if len(unique)>=3:
            tr=np.flatnonzero(dates<unique[-1]);te=np.flatnonzero(dates==unique[-1])
            fm=make_model(chosen['fatigue'],'fatigue',columns).fit(X.iloc[tr],y[tr])
            rm=make_model(chosen['risk'],'risk',columns).fit(X.iloc[tr],risk[tr])
            report['temporal_diagnostic']=metrics(y[te],fm.predict(X.iloc[te]),risk[te],np.asarray(rm.predict(X.iloc[te])).reshape(-1),np.repeat(y[tr].mean(),len(te)))
        fitted[tier]=pair;reports[tier]=report
        print(tier,chosen,report['metrics'],flush=True)
    report={'version':'adaptive-v2','sklearn_version':sklearn.__version__,'catboost_version':'1.2.8',
      'training_data_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':len(data),'athletes':int(groups.nunique()),
      'development_athletes':int(groups.iloc[dev].nunique()),'held_out_athletes':int(groups.iloc[test].nunique()),
      'supported_events':sorted(X.event.unique()),'unique_training_dates':int(dates.nunique()),
      'validation':'Model selection: three-fold grouped development CV. Reported metrics: untouched 20% athlete holdout. Bundled models fitted on development athletes only.',
      'tiers':reports,'metrics':{k:v['metrics'] for k,v in reports.items()},
      'ranges':{c:[float(X.iloc[dev][c].min()),float(X.iloc[dev][c].max())] for c in NUMERIC},
      'limitations':['Research dataset labels; no verified prospective injury outcomes or injury horizon.',
        'Training-load definition is undocumented. Wearable load and HR-duration proxy are not established as equivalent to training load.',
        'Only 100 m and 800 m occur in training. Other events receive context-aware AI advice, not invented event-specific scores.',
        'Only three training dates; no claim of validated long-term forecasting or fitted personal physiology.',
        'Readiness, Twin Score and Health Index are engineered summaries, not separately validated outcomes.',
        'Holdout error summaries are not individual confidence intervals or clinical validation.'],
      'excluded_inputs':{'heart_rate':'Resting vs exercise context undocumented in training.', 'previous_injury':'Training values 4–9 have no supplied coding definition.'}}
    joblib.dump({'tiers':fitted,'report':report},ROOT/'research_prediction/adaptive_models.joblib',compress=3)
    (ROOT/'research_prediction/validation.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
