"""Stable coach entry point with the approved Dawn/Dusk studio."""
def coach_portal():
    from views.coach.studio import render
    return render()
