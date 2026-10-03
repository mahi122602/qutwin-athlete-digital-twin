"""Presentation-only model for the training studio. No synthetic health scores."""
import json
import math
from datetime import datetime, timezone

ROUTES = {
    'studio': 'Athlete Home', 'twin': 'Digital Twin Dashboard',
    'upload': 'Upload Garmin Data', 'events': 'Upload Garmin Data',
    'insights': 'Predictions & Coach Recommendations', 'activity': 'Predictions & Coach Recommendations',
    'coach': 'Predictions & Coach Recommendations', 'history': 'Digital Twin History',
    'requests': 'Requests', 'forecast': 'Forecasting', 'whatif': 'What-if Simulation',
    'visuals': 'Visualisations / Graphs', 'notifications': 'Notifications',
    'profile': 'Profile', 'settings': 'Settings',
}


def obj(value, expected=dict):
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError): return expected()
    return value if isinstance(value, expected) else expected()


def number(value):
    if isinstance(value, bool): return None
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError): return None


def duration_label(minutes):
    value = number(minutes)
    if value is None or not math.isfinite(value * 60):
        return 'Duration not recorded'
    seconds = int(round(value * 60))
    hours, remainder = divmod(seconds, 3600)
    mins, secs = divmod(remainder, 60)
    parts = []
    if hours: parts.append(f'{hours} hr')
    if mins: parts.append(f'{mins} min')
    if secs: parts.append(f'{secs} sec')
    return ' '.join(parts) or '0 min'


def metric(snapshot, key, unit, label):
    value = number(snapshot.get(key))
    return {'value': f'{value:,.0f}' if value is not None else '—',
            'unit': unit if value is not None else '', 'label': label,
            'available': value is not None}


def date_label(value):
    if value is None: return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        # Explicit timezone, never guess an athlete's location from deployment.
        if dt.tzinfo: dt = dt.astimezone(timezone.utc)
        return dt.strftime('%d %b %Y')
    except (ValueError, TypeError, OverflowError): return None


def build_studio_model(profile, uploads, reviews, unread=0, errors=()):
    profile = profile or {}
    name = str(profile.get('name') or 'Athlete').strip() or 'Athlete'
    uploads = list(uploads or [])
    latest = uploads[0] if uploads else {}
    snap = obj(latest.get('snapshot'))
    events = [str(e) for e in obj(latest.get('events'), list) if e]
    measurements = [metric(snap, 'heart_rate', 'bpm', 'Average heart rate'),
                    metric(snap, 'duration_minutes', 'min', 'Duration'),
                    metric(snap, 'calories', 'kcal', 'Energy')]
    trail = []
    for u in uploads:
        s = obj(u.get('snapshot'))
        duration = number(s.get('duration_minutes'))
        kind = str(s.get('activity_type') or 'Activity').strip()
        if kind.lower() in ('unknown', 'none', 'nan'): kind = 'Activity'
        title = f'{duration_label(duration)} · {kind}' if duration is not None else kind
        activity_date = date_label(s.get('timestamp'))
        saved = date_label(u.get('uploaded_at'))
        trail.append({'id': str(u['id']), 'title': title, 'duration': duration_label(duration), 'kind': kind, 'filename': str(u.get('filename') or 'Activity export'),
                      'date': activity_date or (f'Saved {saved}' if saved else 'Date not available'),
                      'date_note': 'Activity date (UTC)' if activity_date else 'Activity date unknown'})
    assessed = any(number(snap.get(k)) is not None for k in ('fatigue_score', 'readiness_score', 'twin_score'))
    assessment = 'Review available insights' if assessed else 'View activity summary' if latest else 'Start with your first activity'
    status = 'Research estimates' if assessed else 'Activity saved · assessment limited' if latest else 'Your journey starts here'
    matches = list(reviews or [])
    completed = [r for r in matches if r.get('status') in ('Approved', 'Modified', 'Rejected')]
    if 'reviews' in errors:
        coach_status, coach_text = 'Temporarily unavailable', 'We could not load coach review status. Please try again.'
    elif completed:
        r = completed[0]
        coach_status = {'Approved':'Approved', 'Modified':'Revised by coach', 'Rejected':'Not approved'}[r['status']]
        coach_text = {'Approved':'Your coach has approved the recommendation for this activity.',
                      'Modified':'Your coach has revised your recommendation. Read their changes.',
                      'Rejected':'Your coach did not approve this draft. Read their feedback.'}[r['status']]
        if len(matches)>1: coach_text += ' Open to see all coach reviews.'
    elif matches:
        coach_status, coach_text = 'Awaiting review', 'Your AI draft is ready for your coach.'
    elif latest.get('has_draft'):
        coach_status, coach_text = 'Draft ready', 'Your AI draft is saved. No coach review is recorded yet.'
    elif latest.get('ai_status')=='generating':
        coach_status, coach_text = 'Preparing draft', 'Your recommendation is being prepared. Check your insights shortly.'
    elif latest:
        coach_status, coach_text = 'No draft yet', 'Your activity is saved. Open insights to check your recommendation.'
    else:
        coach_status, coach_text = 'Your coach, connected', 'Add an activity to begin. Connect with your coach to share insights.'
    sleep_missing = number(snap.get('sleep_hours')) is None
    note = 'Sleep wasn’t included in this upload.' if latest and sleep_missing else 'Your measurements stay linked to their original upload.' if latest else 'Add a training export to bring your studio to life.'
    if 'uploads' in errors:
        note = 'Your saved activities could not be loaded. Please refresh your studio.'
        status = 'Connection interrupted'
        assessment = 'Try loading again'
    attention = []
    def card(tone, label, title, message, action='insights', cta='View assessment'):
        attention.append(dict(tone=tone, label=label, title=title, message=message,
                              action=action, cta=cta, upload_id=str(latest['id']) if latest else None))
    if 'uploads' in errors or 'reviews' in errors:
        card('amber', 'Unable to check', 'Updates could not be loaded',
             'Refresh to check your latest assessment and coach feedback.', 'refresh', 'Refresh updates')
    elif not latest:
        card('blue', 'Get started', 'Add your first activity',
             'Upload a session to see its assessment and coach review status.', 'upload', 'Add activity')
    else:
        # Review decisions are factual workflow states, not medical urgency.
        statuses = {item.get('status') for item in matches}
        if 'Rejected' in statuses:
            card('red', 'Coach decision', 'A coach declined this draft',
                 'Read the coach feedback before relying on this recommendation.', 'coach', 'Read coach feedback')
        elif 'Modified' in statuses:
            card('amber', 'Coach update', 'Your recommendation was revised',
                 'Open the saved review to read your coach’s changes.', 'coach', 'Read revised advice')
        elif 'Approved' in statuses:
            card('green', 'Coach decision', 'Coach approval recorded',
                 'Read the approved recommendation and any other coach reviews. This is not medical clearance.', 'coach', 'Read recommendation')
        elif matches:
            card('blue', 'Coach review', 'Waiting for coach feedback',
                 'A review is pending for this upload. No coach decision is available yet.', 'coach', 'View draft')
        else:
            card('blue', 'Coach review', 'No coach decision yet',
                 'Open your recommendation to check its draft and review status.', 'coach', 'View recommendation')
        risk = str(snap.get('injury_risk') or '').strip()
        if risk.lower() in ('low', 'moderate', 'medium', 'high', 'very high'):
            card('amber', 'Experimental estimate', f'Research risk category: {risk}',
                 'This is an unvalidated model category, not an injury probability or a medical alert. Review the evidence with your coach.')
        else:
            card('amber', 'Assessment limited', 'Risk has not been established',
                 'This upload does not provide a supported risk category. Open the assessment to see what is available.')
        missing = []
        if not date_label(snap.get('timestamp')): missing.append('session date')
        if number(snap.get('sleep_hours')) is None: missing.append('sleep duration')
        if missing:
            card('amber', 'Missing information', 'Complete your activity context',
                 'Not provided: ' + ' and '.join(missing) + '. Add these only if you know them; leave unknown values blank.', 'upload', 'Review upload details')
        else:
            card('blue', 'Latest upload', 'Review your recorded session',
                 'Your session date and sleep duration are recorded. Open the assessment for other data limitations.')
    return dict(attention=attention, name=name, initials=''.join(p[0].upper() for p in name.split())[:2] or 'A',
                unread=max(0,int(unread or 0)), uploads=trail, latest_id=str(latest['id']) if latest else None,
                events=events, measurements=measurements, coach_status=coach_status, coach_text=coach_text,
                coach_action='Read feedback' if completed else 'Read draft' if latest.get('has_draft') else 'View insights' if latest else 'Connect with a coach',
                coach_route='coach' if latest else 'requests',
                assessment=assessment, status=status, note=note, errors=list(errors),
                activity_date_known=bool(date_label(snap.get('timestamp'))),
                upload_date=date_label(latest.get('uploaded_at')),
                has_data=bool(latest))


def resolve_action(event, allowed_upload_ids):
    """Reject unknown commands and upload IDs outside this athlete's loaded records."""
    if not isinstance(event, dict) or not isinstance(event.get('nonce'), str): return None
    action = event.get('action')
    if action not in ROUTES and action != 'refresh': return None
    upload_id = event.get('upload_id')
    if upload_id is not None and str(upload_id) not in {str(x) for x in allowed_upload_ids}: return None
    return {'page': ROUTES.get(action), 'action': action, 'upload_id': upload_id}
