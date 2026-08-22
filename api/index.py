"""Vercel entrypoint for the JJK RPG Flask API.

The existing bot API lives in bot/web_api.py. This adapter adds the bot directory
 to Python's import path and exposes its Flask WSGI application to Vercel.
"""
from pathlib import Path
import sys

BOT_DIR = Path(__file__).resolve().parents[1] / "bot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from web_api import app  # noqa: E402,F401
