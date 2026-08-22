from gemini_debugger import _redact

redacted = _redact({"password": "hidden", "nested": {"api_key": "hidden"}, "status": "ok"})
assert redacted["password"] == "[REDACTED]"
assert redacted["nested"]["api_key"] == "[REDACTED]"
assert redacted["status"] == "ok"
print("Gemini diagnostic redaction passed")
