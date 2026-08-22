from pathlib import Path

BOT = Path(__file__).with_name('bot.py').read_text()

assert 'from expansion_system import ExpansionSystem, GEAR_PRICES' in BOT
assert 'GEAR_PRICES.get(name.lower(), 0)' in BOT
assert 'expansion.GEAR_PRICES' not in BOT
assert 'if action in ("acquire", "equip", "upgrade") and name.isdigit()' in BOT
assert 'CommandHandler("gear", gear_command)' in BOT

print('/gear catalog and numeric alias regression passed')
