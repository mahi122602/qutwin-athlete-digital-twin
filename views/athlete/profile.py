import streamlit as st
import pandas as pd
from io import BytesIO
from database.twin_repository import get_athlete_twin_history
from database.athlete_repository import get_athlete_profile, update_athlete_profile

def athlete_profile():
    """Editable athlete profile using the existing repository fields only."""
    import base64
    import html
    import math
    from PIL import Image, UnidentifiedImageError

    athlete_id = str(st.session_state.user_id)
    profile = get_athlete_profile(athlete_id)
    if profile is None:
        st.error("Athlete profile not found.")
        return

    def escape(value):
        return html.escape(str(value))

    def row(label, value):
        display = "Not provided" if value is None or str(value).strip() == "" else value
        st.html(f'<div class="qp-row"><span>{escape(label)}</span><strong>{escape(display)}</strong></div>')

    def numeric(value):
        try:
            value = float(value)
            return value if math.isfinite(value) and value > 0 else None
        except (ValueError, TypeError):
            return None

    def photo_uri(data):
        if not data:
            return None
        with Image.open(BytesIO(bytes(data))) as image:
            if image.format not in ("PNG", "JPEG"):
                raise ValueError("Please choose a PNG or JPEG image.")
            mime = "image/png" if image.format == "PNG" else "image/jpeg"
            image.verify()
        return f"data:{mime};base64," + base64.b64encode(bytes(data)).decode("ascii")

    revision = st.session_state.get(f"qp_revision_{athlete_id}", 0)
    prefix = f"qp_{athlete_id}_{revision}_"
    values = {
        "name": profile.get("name") or "",
        "email": profile.get("email") or "",
        "phone": profile.get("contact_number") or "",
        "height": numeric(profile.get("height")),
        "weight": numeric(profile.get("weight")),
        "injury": profile.get("injury_history") or "",
    }
    for key, value in values.items():
        st.session_state[prefix + key] = st.session_state.get(prefix + key, value)

    if st.session_state.pop(f"qp_saved_{athlete_id}", False):
        st.success("Profile updated successfully.")

    # Data history is informative; an unavailable history must not block profile editing.
    try:
        history = get_athlete_twin_history(athlete_id)
        history_available = True
    except Exception:
        history = None
        history_available = False
    has_history = history is not None and not history.empty
    latest_date = None
    if has_history and "timestamp" in history.columns:
        dates = pd.to_datetime(history["timestamp"], errors="coerce", utc=True).dropna()
        if not dates.empty:
            latest_date = dates.max().strftime("%d %b %Y, %H:%M UTC")

    st.html('''<style>
.st-key-qp_layout {color:#e8f4ff;}
.st-key-qp_identity, .st-key-qp_personal, .st-key-qp_athlete,
.st-key-qp_health, .st-key-qp_data {
 background:linear-gradient(145deg,#071e36,#031225) !important;
 border:1px solid #28465d !important; border-radius:14px !important;
 padding:20px !important; box-shadow:none !important;
}
.st-key-qp_identity {border-color:#24cbed !important; text-align:center;}
.qp-avatar {width:160px;height:160px;border-radius:50%;object-fit:cover;
 border:3px solid #22c7ed;display:block;margin:0 auto 14px;}
.qp-initials {display:flex;align-items:center;justify-content:center;
 background:#0b425b;color:#9eefff;font-size:48px;font-weight:700;}
.qp-name {font-size:28px;font-weight:750;color:#f3f8ff;overflow-wrap:anywhere;}
.qp-role,.qp-welcome {color:#22d3ee;}
.qp-welcome {font-size:16px;margin:0 0 4px;}
.qp-title {font-size:32px;font-weight:800;color:#f3f8ff;margin:0 0 18px;}
.qp-card-title {font-size:18px;font-weight:700;color:#e8f4ff;margin:0;}
.qp-card-title span {color:#22d3ee;margin-right:8px;}
.qp-row {display:flex;justify-content:space-between;gap:16px;
 border-top:1px solid #1c3a52;padding:11px 0;font-size:14px;}
.qp-row span {color:#a2b8ce;flex:1;}
.qp-row strong {font-weight:500;color:#eef6ff;flex:1.25;overflow-wrap:anywhere;white-space:pre-wrap;}
.qp-badge {border:1px solid #166878;background:#062b35;color:#67e8f9;
 padding:7px 12px;border-radius:10px;display:inline-block;font-size:13px;margin:12px 0;}
.st-key-qp_layout button[kind="primary"] {background:#10bce8 !important;color:#031324 !important;}
.st-key-qp_layout button:focus-visible {outline:2px solid #67e8f9;outline-offset:2px;}
@media(max-width:760px){.qp-title{font-size:27px;}.qp-avatar{width:125px;height:125px;}}
</style>''')
    st.html(f'<div class="qp-welcome">Welcome, {escape(profile.get("name") or athlete_id)}</div><div class="qp-title">Athlete Profile</div>')

    existing_photo = profile.get("profile_photo")
    existing_photo = bytes(existing_photo) if existing_photo else None
    uploaded_photo = None
    new_photo = None
    photo_error = None

    with st.container(key="qp_layout"):
        identity, middle, right = st.columns([0.85, 1.2, 1.2], gap="medium")
        with identity:
            with st.container(key="qp_identity"):
                try:
                    uri = photo_uri(existing_photo)
                except (ValueError, OSError, UnidentifiedImageError):
                    uri = None
                if uri:
                    st.html(f'<img class="qp-avatar" src="{uri}" alt="Your profile photo">')
                else:
                    initials = "".join(p[0] for p in str(profile.get("name") or athlete_id).split())[:2].upper()
                    st.html(f'<div class="qp-avatar qp-initials">{escape(initials)}</div>')
                st.html(f'<div class="qp-name">{escape(profile.get("name") or athlete_id)}</div><div class="qp-role">Athlete</div>')
                fields = [profile.get(k) for k in ("name", "age", "height", "weight", "email", "contact_number")]
                completed = sum(v is not None and str(v).strip() != "" for v in fields) + bool(uri)
                completion = round(completed / 7 * 100)
                st.progress(completion, text=f"Profile completion · {completion}%")
                st.caption("Based on personal details and profile photo.")
                status = "History unavailable" if not history_available else ("Activity data available" if has_history else "No activity data yet")
                st.html(f'<div class="qp-badge">{escape(status)}</div>')
                if st.toggle("Change photo", key=prefix + "edit_photo"):
                    uploaded_photo = st.file_uploader("Choose a PNG or JPEG (up to 5 MB)", type=["png", "jpg", "jpeg"], key=prefix + "upload")
                    if uploaded_photo is not None:
                        try:
                            new_photo = uploaded_photo.getvalue()
                            if len(new_photo) > 5 * 1024 * 1024:
                                raise ValueError("Please choose a photo smaller than 5 MB.")
                            new_uri = photo_uri(new_photo)
                            if not new_uri:
                                raise ValueError("The image file is empty.")
                            st.html(f'<img class="qp-avatar" src="{new_uri}" alt="New photo preview">')
                        except (ValueError, OSError, UnidentifiedImageError) as exc:
                            photo_error = str(exc)
                            st.error("Unable to use this photo. " + photo_error)
        with middle:
            with st.container(key="qp_personal"):
                st.html('<div class="qp-card-title"><span>◉</span>Personal Information</div>')
                edit = st.toggle("Edit personal information", key=prefix + "edit_personal")
                row("User ID", athlete_id)
                if edit:
                    st.text_input("Full name", key=prefix + "name")
                    st.text_input("Email", key=prefix + "email")
                    st.text_input("Contact number", key=prefix + "phone")
                else:
                    row("Full name", st.session_state[prefix + "name"])
                    row("Email", st.session_state[prefix + "email"])
                    row("Contact number", st.session_state[prefix + "phone"])
            with st.container(key="qp_health"):
                st.html('<div class="qp-card-title"><span>♡</span>Health & Injuries</div>')
                previous = profile.get("previous_injury")
                row("Previous injury recorded", "Not provided" if previous is None else ("Yes" if previous else "No"))
                if st.toggle("Edit injury history", key=prefix + "edit_health"):
                    st.text_area("Injury history / notes", key=prefix + "injury", height=130)
                else:
                    row("Injury history / notes", st.session_state[prefix + "injury"])
        with right:
            with st.container(key="qp_athlete"):
                st.html('<div class="qp-card-title"><span>◇</span>Athlete Information</div>')
                row("Age", profile.get("age"))
                if st.toggle("Edit athlete information", key=prefix + "edit_athlete"):
                    st.number_input("Height (cm)", min_value=0.0, max_value=300.0, value=None, step=0.5, key=prefix + "height")
                    st.number_input("Weight (kg)", min_value=0.0, max_value=500.0, value=None, step=0.5, key=prefix + "weight")
                else:
                    row("Height", f'{st.session_state[prefix + "height"]:g} cm' if st.session_state[prefix + "height"] is not None else None)
                    row("Weight", f'{st.session_state[prefix + "weight"]:g} kg' if st.session_state[prefix + "weight"] is not None else None)
                st.caption("Age is shown from your registration details.")
            with st.container(key="qp_data"):
                st.html('<div class="qp-card-title"><span>↗</span>Connected Data</div>')
                row("Data access", "Uploaded activity files")
                row("Available twin records", len(history) if has_history else (0 if history_available else "Unavailable"))
                row("Latest activity record", latest_date)
                row("Live Garmin sync", "Not configured")
                st.caption("Activity history does not indicate a live device connection.")
                if st.button("Upload activity data", key=prefix + "go_upload", use_container_width=True):
                    st.session_state.current_page = "Upload Garmin Data"
                    st.rerun()
        _, save_col, _ = st.columns([1, 1, 1])
        with save_col:
            save = st.button("Save Changes", key=prefix + "save", type="primary", use_container_width=True)
        if save:
            name = st.session_state[prefix + "name"].strip()
            email = st.session_state[prefix + "email"].strip()
            height = st.session_state[prefix + "height"]
            weight = st.session_state[prefix + "weight"]
            if not name:
                st.error("Please enter your full name.")
            elif email and ("@" not in email or not all(email.split("@", 1))):
                st.error("Please enter a valid email address.")
            elif (height is not None and height <= 0) or (weight is not None and weight <= 0):
                st.error("Height and weight must be greater than zero, or left empty.")
            elif photo_error:
                st.error("Please choose a valid photo before saving.")
            else:
                try:
                    update_athlete_profile(
                        athlete_id=athlete_id, name=name, email=email,
                        contact_number=st.session_state[prefix + "phone"].strip(),
                        height=height, weight=weight,
                        injury_history=st.session_state[prefix + "injury"].strip(),
                        profile_photo=new_photo,
                    )
                except Exception:
                    st.error("Your profile could not be saved. Your edits are still here; please try again.")
                else:
                    if new_photo is not None:
                        st.session_state.profile_photo = new_photo
                    # Clear drafts only after a successful database write.
                    for key in list(st.session_state):
                        if key.startswith(prefix):
                            del st.session_state[key]
                    st.session_state[f"qp_revision_{athlete_id}"] = revision + 1
                    st.session_state[f"qp_saved_{athlete_id}"] = True
                    st.rerun()
