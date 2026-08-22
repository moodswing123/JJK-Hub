import os
import gemini_debugger
from gemini_debugger import apply_review_to_diagnostic, format_review_lines

class TimeoutResponse:
    def raise_for_status(self):
        raise TimeoutError('simulated timeout')

def fail_post(*args, **kwargs):
    raise TimeoutError('simulated provider timeout')

os.environ['GEMINI_API_KEY'] = 'test-only'
original_post = gemini_debugger.requests.post
gemini_debugger.requests.post = fail_post
assert gemini_debugger.analyze_diagnostic('deterministic diagnostics') is None
assert format_review_lines(None) == ['Gemini AI review unavailable; deterministic diagnostics were retained.']
deterministic = ['DB: OK', 'BATTLES: 0 active']
apply_review_to_diagnostic(deterministic, None)
assert deterministic[:2] == ['DB: OK', 'BATTLES: 0 active']
assert deterministic[-1].startswith('Gemini AI review unavailable')

def long_post(*args, **kwargs):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': 'x' * 5000}]}}]}
    return Response()

gemini_debugger.requests.post = long_post
result = gemini_debugger.analyze_diagnostic('safe report')
assert result is not None and len(result) == 3500
formatted = format_review_lines(result)
assert len(formatted) == 1 and formatted[0].startswith('🤖 ')
assert len(formatted[0]) <= 3502
assembled = ['DB: OK', 'BATTLES: 0 active']
apply_review_to_diagnostic(assembled, result)
assert assembled[:2] == ['DB: OK', 'BATTLES: 0 active']
assert assembled[2] == '\n━━ GEMINI AI REVIEW ━━'
assert assembled[3].startswith('🤖 ') and len(assembled[3]) <= 3502
assert gemini_debugger._redact({'password': 'secret'})['password'] == '[REDACTED]'
gemini_debugger.requests.post = original_post
print('Gemini fallback and truncation behavior passed')
