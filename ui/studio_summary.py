"""Dashboard triage of saved research outputs, never medical risk calibration.

Current fatigue bands follow research_prediction/predict.py (70/40).
Saved forecast bands follow forecasting/engine.py (fatigue 80/65,
readiness 40/60, injury score 75/45). Workflow priorities are labelled separately.
"""
from datetime import datetime, timezone
import json
import math


def data(value, kind=dict):
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError): return kind()
    return value if isinstance(value, kind) else kind()


def score(value):
    if isinstance(value, bool): return None
    try:
        n=float(value)
        return n if math.isfinite(n) and 0 <= n <= 100 else None
    except (TypeError, ValueError): return None


def timestamp(value):
    try:
        v=value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
        # Naive times cannot establish freshness across deployment timezones.
        return v.astimezone(timezone.utc) if v.tzinfo else None
    except (ValueError, TypeError): return None


def excerpt(value, limit=240):
    text=' '.join(str(value or '').split())
    return text[:limit].rstrip()+'…' if len(text)>limit else text


def build_summary(latest, reviews, forecast=None, errors=(), now=None):
    latest=latest or {}; snapshot=data(latest.get('snapshot'))
    now=now or datetime.now(timezone.utc)
    groups={level:{'level':level,'title':level+' risk','items':[]} for level in ('High','Medium','Low')}
    unavailable=[]
    uid=str(latest['id']) if latest else None
    def add(level,source,title,detail,action='insights',cta='View assessment',quote=None):
        groups[level]['items'].append(dict(source=source,title=title,detail=detail,action=action,
            cta=cta,upload_id=uid if action in ('insights','coach') else None,quote=quote))
    if 'uploads' in errors:
        unavailable.append('Assessment could not be loaded. Refresh to try again.')
    elif not latest:
        unavailable.append('Upload an activity to begin your assessment.')
    else:
        supported=snapshot.get('prediction_status')=='research_estimate'
        fatigue=score(snapshot.get('fatigue_score')) if supported else None
        if fatigue is None: unavailable.append('Fatigue: no usable current research estimate.')
        else:
            level='High' if fatigue>=70 else 'Medium' if fatigue>=40 else 'Low'
            add(level,'Fatigue · research estimate',f'Fatigue {fatigue:g}/100',
                f'{level} band in the current assessment. Estimated from this upload, not a measured physiological state.')
        risk=str(snapshot.get('injury_risk') or '').strip().lower() if supported else ''
        mapped={'high':'High','medium':'Medium','moderate':'Medium','low':'Low'}
        if risk in mapped:
            add(mapped[risk],'Injury · experimental category',f'{mapped[risk]} injury-risk category',
                'Unvalidated model category; not the probability of an injury. Review it with your coach.')
        else: unavailable.append('Injury risk: no usable current research category.')
        readiness=score(snapshot.get('readiness_score')) if supported else None
        # Readiness is context, not an independent risk probability or new threshold.
        if readiness is not None and fatigue is not None:
            for group in groups.values():
                for item in group['items']:
                    if item['source'].startswith('Fatigue'):
                        item['detail'] += f' Readiness context: {readiness:g}/100 (engineered index).'

    if 'reviews' in errors:
        unavailable.append('Coach recommendations could not be loaded.')
    elif latest:
        all_reviews=list(reviews or [])
        reviews=[item for item in all_reviews if item.get('assessment_is_current',True)]
        older_draft=not latest.get('recommendation_is_current',True)
        if older_draft:
            unavailable.append('Your saved recommendation and coach decisions refer to an earlier assessment. Open Prediction & recommendation for the original context.')
        rejected=[x for x in reviews if x.get('status')=='Rejected']
        revised=[x for x in reviews if x.get('status')=='Modified']
        approved=[x for x in reviews if x.get('status')=='Approved']
        pending=[x for x in reviews if x.get('status')=='Pending']
        if rejected:
            add('High','Coach · review priority','A coach declined this draft',
                'Read the feedback before relying on this recommendation. This is a review priority, not an injury diagnosis.',
                'coach','Read coach feedback',excerpt(rejected[0].get('comment')) or None)
        elif revised:
            add('Medium','Coach · review priority','Your coach revised the recommendation',
                'Read the changed advice. Other coach decisions may also be available.',
                'coach','Read revised advice',excerpt(revised[0].get('final_text') or revised[0].get('comment')) or None)
        elif approved:
            add('Low','Coach · routine follow-up','Coach approval is recorded',
                'Approval is for this saved draft; it does not establish low medical risk or clearance.',
                'coach','Read approved advice',excerpt(approved[0].get('final_text') or approved[0].get('comment')) or None)
        if pending or (not rejected and not revised and not approved):
            if latest.get('has_draft') and not older_draft:
                add('Medium','Recommendation · awaiting review','AI draft needs coach review',
                    'This is an unapproved draft. Open it to read the full assessment and recommendations.',
                    'coach','Read AI draft',excerpt(latest.get('ai_excerpt')) or None)
            else: unavailable.append('Recommendation: no saved AI draft or coach decision is available yet.')
    forecast=data(forecast)
    if 'forecast' in errors:
        unavailable.append('Forecast could not be loaded. Open Forecasting to check it.')
    elif not forecast:
        unavailable.append('Forecast: no saved run yet. Generate and save one on Forecasting.')
    else:
        generated=timestamp(forecast.get('generated_at')); uploaded=timestamp(snapshot.get('assessment_saved_at') or latest.get('uploaded_at'))
        rows=data(forecast.get('forecast_payload'),list)
        if generated is None or (latest and uploaded is None):
            unavailable.append('Forecast freshness could not be verified. Open Forecasting to refresh it.')
        elif uploaded and generated < uploaded:
            unavailable.append('Forecast predates your latest upload. Generate and save an updated run.')
        else:
            future=[]
            for row in rows:
                if not isinstance(row,dict): continue
                try: day=datetime.fromisoformat(str(row.get('Date')).replace('Z','+00:00')).date()
                except (ValueError,TypeError): continue
                if day>=now.date(): future.append((day,row))
            if not future: unavailable.append('Saved forecast has no remaining dated projections. Generate a new run.')
            else:
                ranked=[]
                for day,row in future:
                    f=score(row.get('Fatigue forecast')); rd=score(row.get('Readiness forecast')); risk=score(row.get('Injury-risk score'))
                    if any(v is None for v in (f,rd,risk)): continue
                    level='High' if f>=80 or rd<40 or risk>=75 else 'Medium' if f>=65 or rd<60 or risk>=45 else 'Low'
                    ranked.append(({'High':2,'Medium':1,'Low':0}[level],day,row,level))
                if not ranked:
                    unavailable.append('Saved forecast lacks complete usable projection values.')
                else:
                    peak=sorted(ranked,key=lambda x:(-x[0],x[1]))[0];_,day,row,level=peak
                    count=sum(x[3]==level for x in ranked)
                    add(level,'Forecast · saved projection',f'{level} projected band on {day:%d %b}',
                        f'Highest band across {len(ranked)} usable upcoming days; {count} day(s) in this band. '
                        f"Fatigue {row['Fatigue forecast']}/100; readiness {row['Readiness forecast']}/100. "
                        f"Confidence: {row.get('Confidence') or 'not supplied'}. Saved {generated:%d %b %Y} (UTC). Separate saved projection; source-upload linkage is unavailable. Not a confirmed outcome.",
                        'forecast','Open forecast')
                    if len(ranked)<len(future): unavailable.append('Some forecast days were omitted because their projection values were incomplete.')
    return {'groups':list(groups.values()),'unavailable':unavailable,
            'basis':f"Latest saved upload #{uid}" if uid else 'No saved upload',
            'note':'Research risk bands and review priorities—not a combined medical risk score. Missing information is never classified as low risk.'}
