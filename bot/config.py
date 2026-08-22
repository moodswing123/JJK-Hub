"""
Configuration file for JJK Bot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set. Add it as a Secret.")

OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# Admin IDs — owner is always an admin; add more comma-separated IDs if needed
_extra_admins = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = {OWNER_ID} | {int(x) for x in _extra_admins.split(',') if x.strip().isdigit()}

# PostgreSQL (Neon) connection string
POSTGRES_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL')
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL environment variable is not set. Add it as a Secret.")

# Game Settings
DAILY_REWARD_YEN = 1000
DAILY_REWARD_XP = 100
HEAL_COST = 500

# Ranks
RANKS = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']

# Cursed Spirit Grades
SPIRIT_GRADES = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']

# Max level
MAX_LEVEL = 100

# Starting stats for new players
STARTING_STATS = {
    'hp': 100,
    'max_hp': 100,
    'cursed_energy': 50,
    'max_cursed_energy': 50,
    'attack': 10,
    'defense': 5,
    'speed': 10,
    'yen': 5000,
    'level': 1,
    'xp': 0,
    'rank': 'Grade 4'
}

# Per-level stat gains (used by recalc)
LEVEL_GAIN_ATK = 5
LEVEL_GAIN_DEF = 3
LEVEL_GAIN_SPD = 2
LEVEL_GAIN_HP = 10
LEVEL_GAIN_CE = 5
