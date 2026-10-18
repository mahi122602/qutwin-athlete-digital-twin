"""Compatible entry points for app.py; dashboards keep their existing routing."""

def login_page(*args, **kwargs):
    from ui.auth_studio.page import render_auth
    return render_auth('Login')

def signup_page(*args, **kwargs):
    from ui.auth_studio.page import render_auth
    return render_auth('Signup')

def forgot_password_page(*args, **kwargs):
    from ui.auth_studio.page import render_auth
    return render_auth('Forgot Password')

def __getattr__(name):
    from importlib import import_module
    return getattr(import_module('views.auth.shared'), name)

