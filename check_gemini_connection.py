"""Standalone Gemini check. Python 3.11+. No app/database changes or athlete data."""
import os
import tomllib
from pathlib import Path
import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HOST = "https://generativelanguage.googleapis.com"

def redact(value, key):
    text = str(value).replace(key, "[KEY REDACTED]") if key else str(value)
    text = re.sub(r"https?://\S+", "[URL REDACTED]", text)
    text = re.sub(r"(?:AIza|AQ\.)[A-Za-z0-9_.-]+", "[KEY REDACTED]", text)
    return "".join(c if c.isprintable() else " " for c in text)[:1800]

def call(path, key, body=None, native=False):
    headers = {"Content-Type": "application/json"}
    headers.update({"x-goog-api-key": key} if native else {"Authorization": "Bearer " + key})
    request = Request(HOST + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        print("HTTP status:", exc.code)
        try:
            error = json.loads(exc.read(32768)).get("error", {})
            if not isinstance(error, dict):
                raise ValueError()
            print("Google status:", redact(error.get("status", "not supplied"), key))
            print("Google explanation:", redact(error.get("message", "not supplied"), key))
            for detail in error.get("details", []):
                if isinstance(detail, dict) and detail.get("reason"):
                    print("Google reason:", redact(detail["reason"], key))
        except (ValueError, TypeError, AttributeError):
            print("Google returned an error without a readable JSON explanation.")
    except (URLError, TimeoutError, OSError):
        print("Network/TLS/timeout error. No credentials or raw network details printed.")
    except (ValueError, TypeError):
        print("Response was not valid JSON.")
    return None

def main():
    print("Gemini diagnostic: no database access, no files modified, no athlete data sent.")
    print("Reading settings beside this script. No terminal input is required.")
    print("Browser-session settings cannot be read here.")
    path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    try:
        with path.open("rb") as handle:
            settings = tomllib.load(handle)
    except FileNotFoundError:
        settings = {}
    except (OSError, ValueError):
        print("Cannot read secrets.toml or its TOML format is invalid. No contents printed.")
        return 1
    key = os.environ.get("GEMINI_API_KEY") or settings.get("GEMINI_API_KEY", "")
    model = os.environ.get("QUTWIN_GEMINI_MODEL") or settings.get("QUTWIN_GEMINI_MODEL", "")
    if not isinstance(key, str) or not isinstance(model, str):
        print("Gemini settings must be quoted text values.")
        return 1
    key, model = key.strip(), model.strip()
    if not key or not model:
        print("Add top-level GEMINI_API_KEY and QUTWIN_GEMINI_MODEL to .streamlit/secrets.toml.")
        print("Put them before any [section] heading, preserving database settings.")
        return 1
    if any(c.isspace() for c in key) or not key.isascii():
        print("The key contains whitespace or non-ASCII characters. Copy the exact key again.")
        return 1
    print("Key loaded privately from " + ("environment" if os.environ.get("GEMINI_API_KEY") else "secrets.toml") + ".")
    print("Model setting source: " + ("environment" if os.environ.get("QUTWIN_GEMINI_MODEL") else "secrets.toml"))
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", model):
        print("Model ID must contain no spaces or slashes. Copy the exact ID from your app.")
        return 1
    print("\nSelected model:", redact(model,key))
    print("\n1. Checking Google's model list with this key...")
    result = call("/v1beta/models?pageSize=1000", key, native=True)
    if isinstance(result, dict):
        models = [m["name"].removeprefix("models/") for m in result.get("models", [])
                  if isinstance(m,dict) and isinstance(m.get("name"),str)
                  and "generateContent" in m.get("supportedGenerationMethods", [])]
        print("Model list accessible.")
        print("Selected model listed:", model in models)
        print("Listed Flash models (availability does not establish free quota):")
        for name in models:
            if "flash" in name:
                print(" -", redact(name,key))
        if result.get("nextPageToken"):
            print("More models exist beyond this page.")
    print("\n2. Testing the SAME chat endpoint used by QUTwin with a short test prompt...")
    result = call("/v1beta/openai/chat/completions", key, {
        "model": model,
        "messages": [{"role": "system", "content": "You are a connection test assistant."},
                     {"role": "user", "content": "Reply with only OK."}]
    })
    try:
        text = result["choices"][0]["message"]["content"]
        if isinstance(text,str) and text.strip():
            print("SUCCESS: Google returned a non-empty reply.")
            print("If QUTwin still fails, its active settings or recommendation request differs.")
            return 0
    except (KeyError, IndexError, TypeError):
        pass
    print("Connection test did not succeed. Share this output, never your key.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
