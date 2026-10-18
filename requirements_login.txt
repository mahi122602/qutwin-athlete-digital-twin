"""Authentication bridge for the cinematic UI.

Uses the project's existing password hashing and PostgreSQL connection. Signup
and its extra onboarding fields commit together. This module never logs inputs.
"""
from __future__ import annotations

from datetime import date
import json
import math
import re
from typing import Any


class AuthInputError(ValueError):
    pass


class AccountExists(AuthInputError):
    pass


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS qutwin_auth_profiles (
    role TEXT NOT NULL CHECK (role IN ('Athlete', 'Coach')),
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role, user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS qutwin_auth_profiles_role_email
    ON qutwin_auth_profiles (role, lower(email));
"""


def _text(data: dict, key: str, limit: int, *, required: bool = False) -> str:
    value = data.get(key, '')
    if not isinstance(value, str):
        raise AuthInputError(f'Check the {key.replace("_", " ")} field.')
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise AuthInputError(f'Check the {key.replace("_", " ")} field.')
    return value


def _number(data: dict, key: str, low: float, high: float, *, integer=False):
    raw = data.get(key)
    if isinstance(raw, bool):
        raise AuthInputError(f'Check the {key.replace("_", " ")} field.')
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise AuthInputError(f'Check the {key.replace("_", " ")} field.') from None
    if not math.isfinite(value) or not low <= value <= high or (integer and value != int(value)):
        raise AuthInputError(f'Check the {key.replace("_", " ")} field.')
    return int(value) if integer else value


def validate_signup(data: Any, *, today: date | None = None) -> dict:
    if not isinstance(data, dict):
        raise AuthInputError('Check your account details and try again.')
    role = data.get('role')
    if role not in ('Athlete', 'Coach'):
        raise AuthInputError('Choose Athlete or Coach.')
    user_id = _text(data, 'user_id', 64, required=True)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', user_id):
        raise AuthInputError('Use 3–64 letters, numbers, dots, underscores or hyphens for your User ID.')
    name = _text(data, 'name', 120, required=True)
    email = _text(data, 'email', 254, required=True).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise AuthInputError('Enter a valid email address.')
    password = data.get('password')
    if not isinstance(password, str) or len(password) < 8 or len(password.encode('utf-8')) > 72:
        raise AuthInputError('Use a password with at least 8 characters and at most 72 UTF-8 bytes.')
    if password != data.get('confirm'):
        raise AuthInputError('Passwords do not match.')
    if data.get('terms_accepted') is not True:
        raise AuthInputError('Please acknowledge the account and data notice.')
    clean = {'role':role, 'user_id':user_id, 'name':name, 'email':email, 'password':password}
    profile = {'notice_version':'2026-10-18', 'terms_accepted':True}
    if role == 'Athlete':
        try:
            birth = date.fromisoformat(_text(data, 'date_of_birth', 10, required=True))
        except ValueError:
            raise AuthInputError('Enter a valid date of birth.') from None
        current = today or date.today()
        age = current.year - birth.year - ((current.month, current.day) < (birth.month, birth.day))
        if not 10 <= age <= 80:
            raise AuthInputError('Athlete accounts currently support ages 10–80.')
        gender = _text(data, 'gender', 40, required=True)
        if gender not in ('Female', 'Male', 'Non-binary', 'Prefer not to say'):
            raise AuthInputError('Choose an option for gender.')
        profile.update(date_of_birth=birth.isoformat(), gender=gender,
            sport=_text(data, 'sport', 100, required=True),
            event_type=_text(data, 'event_type', 100),
            injury_history=_text(data, 'injury_history', 2500))
        clean.update(age=age, height=_number(data, 'height', 100, 250),
                     weight=_number(data, 'weight', 30, 250),
                     previous_injury=_number(data, 'previous_injury', 0, 30, integer=True))
        if data.get('health_consent') is not True:
            raise AuthInputError('Please acknowledge storage of the health details you provide.')
        profile['health_consent'] = True
    else:
        profile['specialisation'] = _text(data, 'specialisation', 150)
    clean['profile'] = profile
    return clean


def register_account(data: dict, *, connect=None, hasher=None) -> dict:
    clean = validate_signup(data)
    if connect is None:
        from database.connection import get_connection
        connect = get_connection
    if hasher is None:
        from authentication.password_utils import hash_password
        hasher = hash_password
    conn = connect()
    cur = None
    try:
        cur = conn.cursor()
        # Serializes first-use schema setup across simultaneous registrations.
        cur.execute('SELECT pg_advisory_xact_lock(%s)', (736202610,))
        cur.execute(SCHEMA_SQL)
        role, uid = clean['role'], clean['user_id']
        # A new email must also be distinct from profiles created by older UI.
        table, id_col = ('athletes', 'athlete_id') if role == 'Athlete' else ('coaches', 'coach_id')
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s", (table,))
        columns = {row[0] for row in cur.fetchall()}
        if not columns:
            raise RuntimeError('The existing QUTwin account tables are not configured.')
        if 'email' in columns:
            cur.execute(f'SELECT 1 FROM {table} WHERE lower(email) = %s LIMIT 1', (clean['email'],))
            if cur.fetchone():
                raise AccountExists('That email is already registered for this account type. Please sign in.')
        values = {id_col:uid, 'name':clean['name'], 'password':hasher(clean['password'])}
        if role == 'Athlete':
            values.update({k:clean[k] for k in ('age', 'height', 'weight', 'previous_injury')})
        for key in ('email', 'gender', 'injury_history'):
            value = clean.get(key, clean['profile'].get(key))
            if key in columns and value is not None:
                values[key] = value
        fields = list(values)
        cur.execute(f'INSERT INTO {table} ({", ".join(fields)}) VALUES ({", ".join(["%s"]*len(fields))}) '
                    f'ON CONFLICT ({id_col}) DO NOTHING RETURNING {id_col}', tuple(values[k] for k in fields))
        if cur.fetchone() is None:
            raise AccountExists('That User ID is already registered. Please choose another or sign in.')
        cur.execute('INSERT INTO qutwin_auth_profiles (role, user_id, email, profile) VALUES (%s, %s, %s, %s::jsonb)',
                    (role, uid, clean['email'], json.dumps(clean['profile'])))
        conn.commit()
        return {'role':role, 'user_id':uid, 'name':clean['name']}
    except Exception as exc:
        conn.rollback()
        if getattr(exc, 'pgcode', None) == '23505':
            raise AccountExists('That User ID or email is already registered for this account type.') from None
        raise
    finally:
        if cur is not None: cur.close()
        conn.close()


def authenticate(data: Any, *, connect=None, checker=None) -> dict | None:
    if not isinstance(data, dict) or data.get('role') not in ('Athlete', 'Coach'):
        raise AuthInputError('Choose Athlete or Coach.')
    role = data['role']
    uid = _text(data, 'user_id', 254, required=True)
    password = data.get('password')
    if not isinstance(password, str) or not password or len(password.encode('utf-8')) > 72:
        raise AuthInputError('Enter your User ID and password.')
    if connect is None:
        from database.connection import get_connection
        connect = get_connection
    if checker is None:
        from authentication.password_utils import check_password
        checker = check_password
    table, id_col = ('athletes', 'athlete_id') if role == 'Athlete' else ('coaches', 'coach_id')
    conn = connect()
    cur = None
    try:
        cur = conn.cursor()
        # Existing IDs are matched exactly, preserving the existing contract.
        cur.execute(f'SELECT {id_col}, password, name FROM {table} WHERE {id_col} = %s', (uid,))
        row = cur.fetchone()
        if row is None and '@' in uid:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s AND column_name = 'email'", (table,))
            if cur.fetchone():
                cur.execute(f'SELECT {id_col}, password, name FROM {table} WHERE lower(email) = %s LIMIT 2', (uid.lower(),))
                candidates = cur.fetchall()
                if len(candidates) == 1: row = candidates[0]
            if row is None:
                cur.execute("SELECT to_regclass('qutwin_auth_profiles')")
                if cur.fetchone()[0] is not None:
                    cur.execute(f'SELECT a.{id_col}, a.password, a.name FROM {table} a '
                                f'JOIN qutwin_auth_profiles p ON p.user_id = a.{id_col}::text '
                                'WHERE p.role = %s AND lower(p.email) = %s LIMIT 2', (role, uid.lower()))
                    candidates = cur.fetchall()
                    if len(candidates) == 1: row = candidates[0]
        if row is not None and checker(password, row[1]):
            return {'role':role, 'user_id':str(row[0]), 'name':row[2]}
        return None
    finally:
        # End a read transaction before returning a pooled connection.
        conn.rollback()
        if cur is not None: cur.close()
        conn.close()

