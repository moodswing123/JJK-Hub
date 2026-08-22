"""
Utility functions for JJK Bot
"""

from config import OWNER_ID, ADMIN_IDS

def is_owner(user_id: int) -> bool:
    """Check if user is bot owner."""
    return user_id == OWNER_ID

def is_admin(user_id: int) -> bool:
    """Check if user is an admin (owner is always admin)."""
    return user_id in ADMIN_IDS

def format_yen(amount: int) -> str:
    """Format yen with commas."""
    return f"{amount:,}"

def get_rank_emoji(rank: str) -> str:
    """Get emoji for rank."""
    rank_emojis = {
        'Grade 4': '🔰',
        'Grade 3': '⚔️',
        'Grade 2': '💠',
        'Grade 1': '👑',
        'Special Grade': '✨'
    }
    return rank_emojis.get(rank, '❓')

def get_grade_color(grade: str) -> str:
    """Get color hex for grade."""
    colors = {
        'Grade 4': '#95a5a6',
        'Grade 3': '#3498db',
        'Grade 2': '#9b59b6',
        'Grade 1': '#f39c12',
        'Special Grade': '#e74c3c'
    }
    return colors.get(grade, '#ffffff')
