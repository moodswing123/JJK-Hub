from expansion_system import ExpansionSystem

class FakeDB:
    def __init__(self):
        self.deductions = []
    def get_player(self, user_id):
        return {"user_id": user_id, "yen": 100000}
    def deduct_yen(self, user_id, amount):
        self.deductions.append((user_id, amount))

fake = FakeDB()
expansion = ExpansionSystem(db=fake)
expansion.players[7] = {"gear": [{"gear_name": "Playful Cloud", "level": 1, "equipped": False}]}
ok, message = expansion.acquire_gear(7, "Playful Cloud")
assert not ok
assert "already own" in message.lower()
assert fake.deductions == []
print("duplicate gear purchase does not deduct yen")
