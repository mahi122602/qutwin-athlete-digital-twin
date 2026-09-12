"""Compatibility entry points. Each page is imported on demand."""

def login_page(*args, **kwargs):
    from views.auth.login import login_page as page
    return page(*args, **kwargs)

def signup_page(*args, **kwargs):
    from views.auth.signup import signup_page as page
    return page(*args, **kwargs)

def forgot_password_page(*args, **kwargs):
    from views.auth.forgot_password import forgot_password_page as page
    return page(*args, **kwargs)


def __getattr__(name):
    from importlib import import_module
    shared = import_module("views.auth.shared")
    return getattr(shared, name)
