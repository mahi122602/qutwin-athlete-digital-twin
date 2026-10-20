"""Presentation and validation for the athlete profile; no database side effects."""
from __future__ import annotations

import base64
from io import BytesIO
import math
import re

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 20_000_000


def positive_number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def valid_photo(data):
    """Validate bytes, file format and decoded dimensions before display or saving."""
    from PIL import Image, UnidentifiedImageError

    if not isinstance(data, (bytes, bytearray, memoryview)) or not data:
        raise ValueError("Choose a PNG or JPEG photo.")
    data = bytes(data)
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Choose a photo no larger than 5 MB.")
    try:
        with Image.open(BytesIO(data)) as image:
            kind = image.format
            if kind not in ("PNG", "JPEG"):
                raise ValueError("Choose a PNG or JPEG photo.")
            if image.width * image.height > MAX_PHOTO_PIXELS:
                raise ValueError("Choose a photo smaller than 20 megapixels.")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("This image could not be opened. Choose another PNG or JPEG.") from exc
    mime = "image/png" if kind == "PNG" else "image/jpeg"
    return data, "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")


def build_profile_model(profile, athlete_id, history=None, history_available=True, theme="dawn", notice=None):
    import pandas as pd

    profile = profile or {}
    photo, photo_unavailable = None, False
    if profile.get("profile_photo"):
        try:
            _, photo = valid_photo(profile["profile_photo"])
        except (ValueError, TypeError):
            photo_unavailable = True
    portrait = {"cutout": False, "layout": {"x": 0.0, "y": 0.0, "scale": 1.0}}
    avatar = photo
    if photo:
        from services.profile_portrait import portrait_info, avatar_uri
        portrait = portrait_info(profile["profile_photo"])
        avatar = avatar_uri(profile["profile_photo"])
    fields = {
        "name": str(profile.get("name") or ""),
        "email": str(profile.get("email") or ""),
        "phone": str(profile.get("contact_number") or ""),
        "height": positive_number(profile.get("height")),
        "weight": positive_number(profile.get("weight")),
        "injury": str(profile.get("injury_history") or ""),
    }
    has_history = history is not None and not history.empty
    latest = None
    if history_available and has_history and "timestamp" in history.columns:
        dates = pd.to_datetime(history["timestamp"], errors="coerce", utc=True).dropna()
        if not dates.empty:
            latest = dates.max().strftime("%d %b %Y · %H:%M UTC")
    checks = [
        {"label": "Full name", "field": "name", "done": bool(fields["name"].strip())},
        {"label": "Age", "field": None, "done": positive_number(profile.get("age")) is not None},
        {"label": "Height", "field": "height", "done": fields["height"] is not None},
        {"label": "Weight", "field": "weight", "done": fields["weight"] is not None},
        {"label": "Email address", "field": "email", "done": bool(fields["email"].strip())},
        {"label": "Contact number", "field": "phone", "done": bool(fields["phone"].strip())},
        {"label": "Profile photo", "field": "photo", "done": bool(photo)},
    ]
    completed = sum(item["done"] for item in checks)
    return {
        "athlete_id": str(athlete_id), "fields": fields,
        "display_name": fields["name"].strip() or str(athlete_id),
        "initials": "".join(part[:1] for part in (fields["name"].strip() or str(athlete_id)).split())[:2].upper(),
        "age": positive_number(profile.get("age")),
        "previous_injury": None if profile.get("previous_injury") is None else bool(profile["previous_injury"]),
        "photo": photo, "avatar": avatar, "portrait": portrait, "photo_unavailable": photo_unavailable,
        "completion": round(completed / len(checks) * 100),
        "completed": completed, "checks": checks,
        "history_available": bool(history_available),
        "record_count": len(history) if history_available and has_history else (0 if history_available else None),
        "latest_activity": latest,
        "theme": "dusk" if theme == "dusk" else "dawn", "notice": notice,
    }


def validate_changes(payload):
    """Allow only existing editable fields; user identity never comes from the client."""
    if not isinstance(payload, dict) or not {"name", "email", "phone", "height", "weight", "injury"} <= payload.keys():
        raise ValueError("Your changes could not be read. Please try again.")

    def text(key, maximum):
        value = payload.get(key, "")
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError("Check the " + key.replace("_", " ") + " field.")
        return value.strip()

    name = text("name", 200)
    email = text("email", 254)
    phone = text("phone", 80)
    injury = text("injury", 10000)
    if not name:
        raise ValueError("Enter your full name.")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address, or leave it empty.")
    numbers = {}
    for key, maximum, unit in [("height", 300, "cm"), ("weight", 500, "kg")]:
        value = payload.get(key)
        if value is None or value == "":
            numbers[key] = None
            continue
        number = positive_number(value)
        if isinstance(value, bool) or number is None or number > maximum:
            raise ValueError(f"Enter a {key} greater than zero and no more than {maximum} {unit}, or leave it empty.")
        numbers[key] = number
    photo = None
    uploaded = payload.get("photo")
    if uploaded is not None:
        if not isinstance(uploaded, str) or len(uploaded) > (MAX_PHOTO_BYTES * 4 // 3 + 200):
            raise ValueError("Choose a PNG or JPEG photo no larger than 5 MB.")
        try:
            header, encoded = uploaded.split(",", 1)
            if header not in ("data:image/png;base64", "data:image/jpeg;base64"):
                raise ValueError("Choose a PNG or JPEG photo.")
            photo = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("This photo could not be read. Choose another PNG or JPEG.") from exc
        photo, _ = valid_photo(photo)
    return dict(name=name, email=email, contact_number=phone, height=numbers["height"],
                weight=numbers["weight"], injury_history=injury, profile_photo=photo)
