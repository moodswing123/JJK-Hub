import os
import gemini_debugger

class TimeoutResponse:
    def raise_for_status(self):
        raise TimeoutError('simulated timeout')

def fail_post(*args, **kwargs):
    raise TimeoutError('simulated provider timeout')

os.environ['GEMINI_API_KEY'] = 'test-only'
original_post = gemini_debugger.requests.post
gemini_debugger.requests.post = fail_post
assert gemini_debugger.analyze_diagnostic('deterministic diagnostics') is None

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
assert gemini_debugger._redact({'password': 'secret'})['password'] == '[REDACTED]'
gemini_debugger.requests.post = original_post
print('Gemini fallback and truncation behavior passed')
