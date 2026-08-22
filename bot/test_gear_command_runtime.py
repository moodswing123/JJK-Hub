import ast
import asyncio
from pathlib import Path

source = Path(__file__).with_name('bot.py').read_text()
module = ast.parse(source)
gear_node = next(node for node in module.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'gear_command')
namespace = {
    'WEAPON_DISPLAY': [('Playful Cloud', 'Defense scaling')],
    'ARMOR_DISPLAY': [('Tokyo Jujutsu Robes', 'Balanced protection')],
    'GEAR_PRICES': {'playful cloud': 50000, 'tokyo jujutsu robes': 25000},
}
exec(compile('from __future__ import annotations\n' + ast.unparse(gear_node), '<gear_command>', 'exec'), namespace)

class FakeExpansion:
    def gear(self, user_id):
        return []

class FakeUser:
    id = 101

class FakeUpdate:
    effective_user = FakeUser()

class FakeContext:
    args = []

replies = []
async def fake_expansion_reply(update, text):
    replies.append(text)

namespace['expansion'] = FakeExpansion()
namespace['_expansion_reply'] = fake_expansion_reply
asyncio.run(namespace['gear_command'](FakeUpdate(), FakeContext()))

assert len(replies) == 1
assert 'Playful Cloud' in replies[0]
assert '¥50,000' in replies[0]
assert 'Tokyo Jujutsu Robes' in replies[0]
assert '¥25,000' in replies[0]

class LegacyExpansion:
    pass
try:
    LegacyExpansion().GEAR_PRICES
except AttributeError:
    legacy_lookup_failed = True
else:
    legacy_lookup_failed = False
assert legacy_lookup_failed
assert 'GEAR_PRICES.get(name.lower(), 0)' in source
assert 'expansion.GEAR_PRICES' not in source
print('/gear runtime catalog reproduction and repair passed')
