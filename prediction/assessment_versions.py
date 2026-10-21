"""Separate current numeric analysis from the assessment behind an existing draft."""
import hashlib
import json

INTERNAL = {'active_assessment', 'assessment_history', 'recommendation_assessment'}


def original_assessment(snapshot):
    return {k: v for k, v in (snapshot or {}).items() if k not in INTERNAL}


def current_assessment(snapshot):
    snapshot = snapshot or {}
    return dict(snapshot.get('active_assessment') or original_assessment(snapshot))


def recommendation_assessment(snapshot):
    snapshot = snapshot or {}
    return dict(snapshot.get('recommendation_assessment') or original_assessment(snapshot))


def assessment_token(snapshot):
    text = json.dumps(snapshot or {}, sort_keys=True, default=str, allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def present_upload(upload):
    result = dict(upload)
    raw = result.get('snapshot') or {}
    current = current_assessment(raw)
    bound = recommendation_assessment(raw)
    result.update(snapshot=current, recommendation_snapshot=bound,
                  recommendation_is_current=not result.get('ai_text') or assessment_token(current) == assessment_token(bound))
    return result
