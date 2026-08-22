"""Optional Gemini analysis for the owner-only bot diagnostic command."""
import json
import os
import re
from typing import Any

import requests

_SENSITIVE = re.compile(r"(?i)(password|token|secret|api[_-]?key|postgres|database[_-]?url|bot[_-]?token|authorization)")

def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if _SENSITIVE.search(str(k)) else _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    text = str(value)
    return "[REDACTED]" if _SENSITIVE.search(text) else text

def analyze_diagnostic(report: str) -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = os.getenv("GEMINI_API_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/models")
    prompt = (
        "You are a cautious production-game diagnostic assistant. Analyze only the supplied bot diagnostic report. "
        "Return at most 6 concise Telegram-safe lines with: severity, likely root causes, and concrete next checks. "
        "Do not invent database facts, do not expose secrets or personal data, and say when evidence is insufficient.\n\n"
        + json.dumps(_redact(report[-12000:]))
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 700}}
    try:
        response = requests.post(f"{endpoint.rstrip('/')}/{model}:generateContent", params={"key": key}, json=payload, timeout=12)
        response.raise_for_status()
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "\n".join(str(p.get("text", "")).strip() for p in parts if p.get("text"))
        return text[:3500] if text else None
    except Exception:
        return None
