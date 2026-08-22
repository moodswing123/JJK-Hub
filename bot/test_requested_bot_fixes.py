from pathlib import Path

ROOT = Path(__file__).parent
BOT = (ROOT / 'bot.py').read_text()
DB = (ROOT / 'database.py').read_text()
EXPANSION = (ROOT / 'expansion_system.py').read_text()
ENGINE = (ROOT / 'game_engine.py').read_text()

assert 'CommandHandler("adminendbattle", adminendbattle_command)' in BOT
assert 'CommandHandler("buy", buy_command)' in BOT
assert 'if action in ("acquire", "equip", "upgrade") and name.isdigit()' in BOT
assert 'def clear_all_active_pvp_battles' in DB
assert 'self.db.deduct_yen(user_id, price)' in EXPANSION
assert 'GEAR_PRICES = {' in EXPANSION
assert "bot_starts = random.choice([True, False])" in BOT
assert "'initiative': 'bot' if bot_starts else 'player'" in BOT
assert "'reward': 20000" in ENGINE
assert EXPANSION.index('if any(g.get("gear_name"') < EXPANSION.index('self.db.deduct_yen(user_id, price)')
assert "opening_player_hp}/{player['max_hp']}" in BOT
assert 'ORDER BY type,price,id' in DB
assert 'challenge_gif = image_gen.generate_battle_gif' in BOT
assert 'intro_gif = image_gen.generate_battle_gif' in BOT
print('requested bot-fix assertions passed')
