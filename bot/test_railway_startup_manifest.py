from pathlib import Path
import importlib.util

ROOT = Path(__file__).parent
requirements = (ROOT / 'requirements.txt').read_text().splitlines()
assert any(line.strip().lower().startswith('requests') for line in requirements)
assert importlib.util.find_spec('requests') is not None
import gemini_debugger  # noqa: F401
compile((ROOT / 'bot.py').read_text(), str(ROOT / 'bot.py'), 'exec')
print('Railway requirements and bot startup dependency validation passed')
