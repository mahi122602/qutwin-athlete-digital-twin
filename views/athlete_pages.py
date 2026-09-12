"""Compatibility entry points. Each page is imported on demand."""

def athlete_profile(*args, **kwargs):
    from views.athlete.profile import athlete_profile as page
    return page(*args, **kwargs)

def athlete_dashboard(*args, **kwargs):
    from views.athlete.digital_twin import athlete_dashboard as page
    return page(*args, **kwargs)

def upload_garmin_data(*args, **kwargs):
    from views.athlete.upload import upload_garmin_data as page
    return page(*args, **kwargs)

def athlete_predictions(*args, **kwargs):
    from views.athlete.predictions import athlete_predictions as page
    return page(*args, **kwargs)

def athlete_history(*args, **kwargs):
    from views.athlete.history import athlete_history as page
    return page(*args, **kwargs)

def athlete_visualisations(*args, **kwargs):
    from views.athlete.visualisations import athlete_visualisations as page
    return page(*args, **kwargs)

def athlete_simulation(*args, **kwargs):
    from views.athlete.simulation import athlete_simulation as page
    return page(*args, **kwargs)


def __getattr__(name):
    from importlib import import_module
    shared = import_module("views.athlete.shared")
    return getattr(shared, name)
