from commands.item_aliases import resolve_numbered_item

items = [{"id": 8, "name": "Split Soul Katana"}, {"id": 3, "name": "Black Rope"}]
assert resolve_numbered_item(items, "1")["id"] == 8
assert resolve_numbered_item(items, "2")["name"] == "Black Rope"
assert resolve_numbered_item(items, "black rope")["id"] == 3
assert resolve_numbered_item(items, "99") is None
print("item-number behavioral mapping passed")
