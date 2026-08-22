"""Stable one-based item aliases shared by shop and inventory commands."""

def resolve_numbered_item(items, raw_value):
    value = str(raw_value).strip()
    if value.isdigit():
        index = int(value) - 1
        return items[index] if 0 <= index < len(items) else None
    return next((item for item in items if str(item.get("name", "")).casefold() == value.casefold()), None)
