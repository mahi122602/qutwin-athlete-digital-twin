"""Gemini native REST transport helpers. Never place credentials in URLs."""
import json
import re
from urllib.request import Request

def make_request(key, model, system, user, json_output=False):
    if not isinstance(key,str) or not key.strip():
        raise ValueError("Set GEMINI_API_KEY.")
    key=key.strip()
    if not key.isascii() or any(c.isspace() for c in key):
        raise ValueError("The Gemini key contains invalid whitespace or characters.")
    model=str(model).strip().removeprefix("models/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+",model):
        raise ValueError("Use an exact Gemini model ID without spaces.")
    body={"systemInstruction":{"parts":[{"text":system}]},
          "contents":[{"role":"user","parts":[{"text":user}]}]}
    if json_output:
        body["generationConfig"]={"responseMimeType":"application/json"}
    return Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent",
        data=json.dumps(body,allow_nan=False).encode(),
        headers={"x-goog-api-key":key,"Content-Type":"application/json"})

def response_text(result):
    feedback=result.get("promptFeedback",{})
    if feedback.get("blockReason"):
        raise ValueError("Gemini declined the prompt. No recommendation was generated.")
    candidates=result.get("candidates",[])
    if not candidates:
        raise ValueError("Gemini returned no response candidate.")
    candidate=candidates[0]
    reason=candidate.get("finishReason")
    if reason not in (None,"STOP"):
        raise ValueError("Gemini did not finish a complete response. No partial recommendation was saved.")
    parts=candidate.get("content",{}).get("parts",[])
    text="".join(p["text"] for p in parts if isinstance(p,dict)
                 and isinstance(p.get("text"),str) and not p.get("thought"))
    if not text.strip():
        raise ValueError("Gemini returned no usable text.")
    return text.strip()

def http_error(exc,key,model):
    """Keep Google's explanation but redact credentials, URLs and control characters."""
    message=""
    try:
        data=json.loads(exc.read(32768))
        error=data.get("error",{})
        if isinstance(error,dict):
            message=str(error.get("message",""))
    except (ValueError,TypeError,AttributeError,OSError):
        pass
    if key:
        message=message.replace(key,"[KEY REDACTED]")
    message=re.sub(r"(?:AIza|AQ\.)[A-Za-z0-9_.-]+","[KEY REDACTED]",message)
    message=re.sub(r"https?://\S+","[URL REDACTED]",message)
    message="".join(c if c.isprintable() else " " for c in message)[:1000]
    detail=message or "Google returned no readable explanation."
    return f"Gemini native API returned HTTP {exc.code}. {detail} Your upload remains saved."
