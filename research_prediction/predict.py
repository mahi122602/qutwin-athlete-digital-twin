"""Select a separately evaluated input tier. Never invent a missing measurement."""
from functools import lru_cache
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from research_prediction.features import NUMERIC, model_frame, derive_features, canonical_event

@lru_cache(maxsize=1)
def bundle():
    path=Path(__file__).with_name('adaptive_models.joblib')
    if not path.exists():raise RuntimeError('Model package is missing. Copy research_prediction/adaptive_models.joblib from the replacement package, then restart.')
    return joblib.load(path)

def analyse(record,events,history=()):
    analysis=derive_features(record,history,events);data=dict(record)
    if analysis['features'].get('training_load') is not None:data['training_load']=analysis['features']['training_load']
    models=bundle();report=models['report'];X=model_frame(pd.DataFrame([data]))
    missing=[k for k in NUMERIC if pd.isna(X.iloc[0][k])];observed=[k for k in NUMERIC if k not in missing]
    out={'analysis':analysis,'model_version':report['version'], 'prediction_basis':'Experimental dataset estimate; external wearable accuracy is unverified',
         'model_limitations':report['limitations'],'activity_date_unknown':pd.isna(pd.to_datetime(record.get('timestamp'),utc=True,errors='coerce')),
         'missing_inputs':missing,'observed_model_inputs':observed,'imputed_model_inputs':{}}
    outside=[k for k in observed if not report['ranges'][k][0]<=float(X.iloc[0][k])<=report['ranges'][k][1]]
    out['outside_training_range']=outside
    selected=None
    for name,spec in report['tiers'].items():
        if all(k in observed and k not in outside for k in spec['features']):selected=name;break
    if not selected:
        return dict(out,prediction_status='analysis_only',analysis_message='Measurements saved and analysed. None of the evaluated model input sets covers these measurements.',
                    required_input_sets={k:v['features'] for k,v in report['tiers'].items()})
    spec=report['tiers'][selected];pair=models['tiers'][selected]
    out.update(model_tier=selected,used_model_inputs=spec['features'],validation_metrics=spec['metrics'],selected_models=spec['selected_models'])
    out['ignored_model_inputs']=[k for k in observed if k not in spec['features']]
    origin=str(data.get('training_load_origin',''))
    out['load_scale_unverified']='training_load' in spec['features']
    out['load_provenance']=origin or 'Uploaded load; training scale undocumented'
    # Generic predictions average over learned events, rather than using an unseen all-zero category.
    requested=list(dict.fromkeys(canonical_event(e) for e in (events or [data.get('event_type','Unknown')])))
    supported=report['supported_events'];scenarios=[]
    def estimates(event):
        tx=X.copy();tx['event']=event
        return float(pair['fatigue'].predict(tx)[0]),np.asarray(pair['risk'].predict_proba(tx)[0],dtype=float)
    event_values={e:estimates(e) for e in supported}
    primary=canonical_event(data.get('event_type',requested[0]));is_supported=primary in supported
    if is_supported:fatigue,probs=event_values[primary]
    else:
        fatigue=float(np.mean([v[0] for v in event_values.values()]));probs=np.mean([v[1] for v in event_values.values()],axis=0)
    fatigue=float(np.clip(fatigue,0,100));classes=pair['risk'].named_steps['model'].classes_
    risk=str(classes[int(np.argmax(probs))])
    for event in requested:
        item={'event':event,'event_supported':event in supported}
        if event in supported:
            f,p=event_values[event];item.update(fatigue_score=round(float(np.clip(f,0,100)),2),injury_risk=str(classes[int(np.argmax(p))]))
        else:item['note']='AI context only; no event-specific numeric model in the supplied training data.'
        scenarios.append(item)
    # Composite indices use only observed components, and are not independent predictions.
    row=X.iloc[0];components=[]
    for field,weight,divisor in [('sleep_hours',.45,9),('recovery_time',.35,10),('hydration_score',.20,1)]:
        if pd.notna(row[field]):components.append((weight,float(np.clip(row[field]/divisor,0,1))))
    recovery=sum(w*v for w,v in components)/sum(w for w,v in components) if components else None
    stress=None
    if pd.notna(row.temperature) and pd.notna(row.humidity):
        stress=float(.6*np.clip((row.temperature-15)/25,0,1)+.4*np.clip((row.humidity-40)/60,0,1))
    readiness=float(np.clip(100-fatigue+(20*recovery if recovery is not None else 0)-(10*stress if stress is not None else 0),0,100))
    twin=(.45*readiness+.35*(100-fatigue)+(.2*recovery*100 if recovery is not None else 0))/(1 if recovery is not None else .8)
    health=.5*readiness+.3*(100-fatigue)+.2*twin
    state='Higher estimated fatigue' if fatigue>=70 else 'Moderate estimated fatigue' if fatigue>=40 else 'Lower estimated fatigue'
    metrics=spec['metrics']
    out.update(fatigue_score=round(fatigue,2),injury_risk=risk,readiness_score=round(readiness,2),twin_score=round(twin,2),health_index=round(health,2),
        recovery_index=None if recovery is None else round(recovery,3),environmental_stress=stress,
        fatigue_index=fatigue/100,readiness_index=readiness/100,athlete_state=state,digital_twin_state=state,
        event_scenarios=scenarios,primary_event=primary,event_supported=is_supported,prediction_status='research_estimate',
        composite_basis='Engineered indices from fatigue estimate and available recovery/environment measurements; missing components omitted and weights renormalised. Not validated readiness or clearance.',
        uncertainty_note='Held-out dataset errors, not an individual confidence interval. External export accuracy is unknown.',
        risk_validation_warning=f"Exploratory injury category: {metrics['risk_balanced_accuracy']:.1%} balanced accuracy on held-out research athletes; not a probability of future injury.")
    return out
