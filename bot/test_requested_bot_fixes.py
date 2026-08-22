from pathlib import Path

ROOT = Path(__file__).parent
BOT = (ROOT / 'bot.py').read_text()
DB = (ROOT / 'database.py').read_text()
EXPANSION = (ROOT / 'expansion_system.py').read_text()

assert 'CommandHandler("adminendbattle", adminendbattle_command)' in BOT
assert 'CommandHandler("buy", buy_command)' in BOT
assert 'if action in ("acquire", "equip", "upgrade") and name.isdigit()' in BOT
assert 'def clear_all_active_pvp_battles' in DB
assert 'self.db.deduct_yen(user_id, price)' in EXPANSION
assert 'GEAR_PRICES = {' in EXPANSION
print('requested bot-fix assertions passed')
