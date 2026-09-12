"""Compatibility entry points. Each page is imported on demand."""

def coach_dashboard(*args, **kwargs):
    from views.coach.dashboard import coach_dashboard as page
    return page(*args, **kwargs)

def assign_athlete(*args, **kwargs):
    from views.coach.assign_athlete import assign_athlete as page
    return page(*args, **kwargs)

def assigned_athletes(*args, **kwargs):
    from views.coach.assigned_athletes import assigned_athletes as page
    return page(*args, **kwargs)

def coach_intelligence_dashboard(*args, **kwargs):
    from views.coach.intelligence_dashboard import coach_intelligence_dashboard as page
    return page(*args, **kwargs)

def selected_athlete_twin_summary(*args, **kwargs):
    from views.coach.selected_athlete_twin_summary import selected_athlete_twin_summary as page
    return page(*args, **kwargs)

def coach_history(*args, **kwargs):
    from views.coach.history import coach_history as page
    return page(*args, **kwargs)

def coach_timeline(*args, **kwargs):
    from views.coach.timeline import coach_timeline as page
    return page(*args, **kwargs)

def coach_visualisations(*args, **kwargs):
    from views.coach.visualisations import coach_visualisations as page
    return page(*args, **kwargs)

def coach_notifications(*args, **kwargs):
    from views.coach.notifications import coach_notifications as page
    return page(*args, **kwargs)

def coach_portal(*args, **kwargs):
    from views.coach.portal import coach_portal as page
    return page(*args, **kwargs)


def __getattr__(name):
    from importlib import import_module
    shared = import_module("views.coach.shared")
    return getattr(shared, name)
