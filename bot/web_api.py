"""HTTP API for the JJK RPG dashboard credential login."""
import base64
import hashlib
import hmac
import json
import os
import time
import requests
from functools import wraps

from flask import Flask, jsonify, request

from database import Database
from web_auth import hash_reset_code, verify_password, _hash_password

app = Flask(__name__)
_db = None


def get_db():
    """Initialize the database only when an endpoint needs player data."""
    global _db
    if _db is None:
        _db = Database()
    return _db


TOKEN_TTL = 60 * 60 * 24 * 7


def _secret() -> bytes:
    value = os.getenv("WEB_AUTH_SECRET") or os.getenv("JWT_SECRET")
    if not value:
        raise RuntimeError("WEB_AUTH_SECRET or JWT_SECRET must be configured")
    return value.encode("utf-8")


def _token(user_id: int) -> str:
    payload = json.dumps({"user_id": user_id, "exp": int(time.time()) + TOKEN_TTL}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def _user_id_from_token(value: str):
    try:
        body, encoded_signature = value.split(".", 1)
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(time.time()):
            return None
        return int(payload["user_id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _player_payload(player):
    if not player:
        return None
    wins, losses = int(player.get("wins", 0) or 0), int(player.get("losses", 0) or 0)
    total = wins + losses
    return {
        "user_id": int(player["user_id"]), "username": player.get("username"), "display_name": player.get("display_name") or "Player",
        "level": int(player.get("level", 1) or 1), "rank": player.get("rank") or "Grade 4", "xp": int(player.get("xp", 0) or 0), "xp_needed": int(player.get("xp_needed", 100) or 100),
        "yen": int(player.get("yen", 0) or 0), "hp": int(player.get("hp", 0) or 0), "max_hp": int(player.get("max_hp", 0) or 0),
        "cursed_energy": int(player.get("cursed_energy", 0) or 0), "max_cursed_energy": int(player.get("max_cursed_energy", 0) or 0),
        "attack": int(player.get("attack", 0) or 0), "defense": int(player.get("defense", 0) or 0), "speed": int(player.get("speed", 0) or 0),
        "wins": wins, "losses": losses, "win_rate": round(wins / total * 100, 1) if total else 0,
        "is_admin": _is_admin(int(player["user_id"])),
    }


def _is_admin(user_id: int) -> bool:
    owner = os.getenv("OWNER_ID", "0")
    admins = {int(owner)} if owner.isdigit() and int(owner) > 0 else set()
    admins.update(int(value.strip()) for value in os.getenv("ADMIN_IDS", "").split(",") if value.strip().isdigit())
    return user_id in admins


def require_user(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        user_id = _user_id_from_token(header.removeprefix("Bearer ").strip()) if header else None
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        return handler(user_id, *args, **kwargs)
    return wrapped


def require_admin(handler):
    @wraps(handler)
    @require_user
    def wrapped(user_id, *args, **kwargs):
        if not _is_admin(user_id):
            return jsonify({"error": "Owner access required"}), 403
        return handler(user_id, *args, **kwargs)
    return wrapped


def _forward_receipt_to_owner(user_id: int, amount: int, reference: str, topup_id: int, receipt_name: str, receipt_mimetype: str, receipt_bytes: bytes):
    bot_token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    owner_raw = os.getenv("OWNER_ID") or os.getenv("TELEGRAM_OWNER_ID") or ""
    if not bot_token or not owner_raw.isdigit() or int(owner_raw) <= 0:
        return False, "Telegram forwarding is not configured: BOT_TOKEN/TELEGRAM_BOT_TOKEN and OWNER_ID are required."
    caption = f"Yen top-up pending\nPlayer ID: {user_id}\nYen: ¥{amount:,}\nNaira due: ₦{(amount + 999) // 1000:,}\nReference: {reference}\nTop-up ID: {topup_id}"
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    last_error = "Telegram did not accept the receipt."
    for attempt in range(3):
        try:
            response = requests.post(endpoint, data={"chat_id": owner_raw, "caption": caption}, files={"document": (receipt_name, receipt_bytes, receipt_mimetype)}, timeout=20)
            payload = response.json() if response.content else {}
            if response.ok and payload.get("ok") is True:
                return True, ""
            last_error = str(payload.get("description") or f"Telegram HTTP {response.status_code}")
        except (requests.RequestException, ValueError) as exc:
            last_error = str(exc)
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    return False, last_error


@app.after_request
def add_headers(response):
    origin = os.getenv("DASHBOARD_ORIGIN", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/auth/password", methods=["POST"])
def password_login():
    data = request.get_json(silent=True) or {}
    username, password = str(data.get("username", "")).strip().lower(), str(data.get("password", ""))
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    record = get_db().get_player_by_dashboard_username(username)
    if not record or not verify_password(password, str(record.get("password_hash", ""))):
        return jsonify({"error": "Invalid username or password"}), 401
    return jsonify({"token": _token(int(record["user_id"])), "player": _player_payload(record)})


@app.route("/api/auth/password-reset", methods=["POST"])
def password_reset():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    code = str(data.get("code", "")).strip().upper()
    new_password = str(data.get("new_password", ""))
    if not username or not code or len(new_password) < 10 or len(new_password) > 128:
        return jsonify({"error": "Username, reset code, and a 10–128 character new password are required"}), 400
    record = get_db().get_player_by_dashboard_username(username)
    if not record or not get_db().consume_dashboard_reset_token(int(record["user_id"]), hash_reset_code(code)):
        return jsonify({"error": "The reset code is invalid or expired. Request a new one from Telegram."}), 400
    get_db().save_dashboard_credentials(int(record["user_id"]), username, _hash_password(new_password))
    return jsonify({"success": True})


@app.route("/api/auth/me", methods=["GET"])
@require_user
def auth_me(user_id):
    player = _player_payload(get_db().get_player(user_id))
    return jsonify(player) if player else (jsonify({"error": "Player not found"}), 404)


@app.route("/api/inventory", methods=["GET"])
@require_user
def inventory(user_id):
    items = []
    for item in get_db().get_inventory(user_id):
        payload = dict(item)
        try:
            payload["effect"] = json.loads(payload["effect"]) if payload.get("effect") else {}
        except Exception:
            payload["effect"] = {}
        items.append(payload)
    return jsonify({"items": items})


@app.route("/api/inventory/equip", methods=["POST"])
@require_user
def equip_inventory_item(user_id):
    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid item_id is required"}), 400
    player = get_db().get_player(user_id)
    item = next((candidate for candidate in get_db().get_inventory(user_id) if int(candidate["id"]) == item_id), None)
    if not player or not item:
        return jsonify({"error": "Cursed tool not found in your inventory"}), 404
    if item.get("type") != "weapon":
        return jsonify({"error": "Only weapon-type cursed tools can be equipped from the dashboard"}), 400
    try:
        effect = json.loads(item.get("effect") or "{}") if isinstance(item.get("effect"), str) else (item.get("effect") or {})
    except Exception:
        effect = {}
    for stat in ("attack", "defense"):
        if effect.get(stat):
            get_db().update_player_stat(user_id, stat, int(player[stat]) + int(effect[stat]))
    get_db().remove_from_inventory(user_id, item_id)
    return jsonify({"success": True, "item": item})


@app.route("/api/market", methods=["GET"])
@require_user
def market_snapshot(user_id):
    return jsonify(get_db().get_market_snapshot(user_id))


@app.route("/api/market/trade", methods=["POST"])
@require_user
def market_trade(user_id):
    data = request.get_json(silent=True) or {}
    try:
        asset_id = str(data.get("asset_id", "")).strip().lower()
        side = str(data.get("side", "")).strip().lower()
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid asset, side, and quantity are required"}), 400
    result = get_db().execute_market_trade(user_id, asset_id, side, quantity)
    if result.get("ok"):
        return jsonify(result)
    status = 400 if result.get("reason") in {"invalid", "funds", "holdings"} else 404
    messages = {"invalid": "Invalid market order", "funds": "Insufficient yen", "holdings": "Insufficient holdings", "not_found": "Market asset or player not found"}
    return jsonify({"error": messages.get(result.get("reason"), "Market order failed"), **result}), status


@app.route("/api/arcade/play", methods=["POST"])
@require_user
def arcade_play(user_id):
    data = request.get_json(silent=True) or {}
    result = get_db().play_arcade_game(user_id, str(data.get("game_id", "")).strip().lower())
    if result.get("ok"):
        return jsonify(result)
    status = 429 if result.get("reason") == "cooldown" else 400
    messages = {"invalid": "Unknown arcade game", "cooldown": "That game is cooling down"}
    return jsonify({"error": messages.get(result.get("reason"), "Arcade run failed"), **result}), status


@app.route("/api/arcade/skill", methods=["POST"])
@require_user
def arcade_skill(user_id):
    data = request.get_json(silent=True) or {}
    result = get_db().play_skill_game(user_id, str(data.get("game_id", "")).strip().lower(), data.get("action") or {})
    if result.get("ok"):
        return jsonify(result)
    status = 429 if result.get("reason") == "cooldown" else 400
    messages = {"invalid": "Unknown game", "invalid_action": "That play did not include valid controls", "cooldown": "The arena is cooling down"}
    return jsonify({"error": messages.get(result.get("reason"), "Game could not be settled"), **result}), status


@app.route("/api/topups/info", methods=["GET"])
@require_user
def topup_info(_user_id):
    return jsonify({
        "provider": os.getenv("OPAY_PROVIDER", "OPay"),
        "account_name": os.getenv("OPAY_ACCOUNT_NAME", "Patrick"),
        "account_number": os.getenv("OPAY_ACCOUNT_NUMBER", "6521307860"),
        "rate_yen_per_naira": 1000,
        "packages": [
            {"yen": 100000, "naira": 100},
            {"yen": 250000, "naira": 250},
            {"yen": 500000, "naira": 500},
            {"yen": 750000, "naira": 750},
            {"yen": 1000000, "naira": 1000},
        ],
        "notice": "Send the exact naira amount first, then upload the receipt. Yen is credited automatically when the owner approves the receipt.",
    })


@app.route("/api/topups/request", methods=["POST"])
@require_user
def create_topup(user_id):
    try:
        amount = int(request.form.get("amount", "0"))
    except ValueError:
        amount = 0
    reference = str(request.form.get("reference", "")).strip()
    naira_amount = (amount + 999) // 1000
    submitted_naira = str(request.form.get("naira_amount", "")).strip()
    if submitted_naira and (not submitted_naira.isdigit() or int(submitted_naira) != naira_amount):
        return jsonify({"error": "The naira amount does not match the yen conversion."}), 400
    receipt = request.files.get("receipt")
    if not receipt or not receipt.filename or (receipt.mimetype or "").lower() not in {"image/jpeg", "image/png", "image/webp", "application/pdf"}:
        return jsonify({"error": "Upload a JPG, PNG, WEBP, or PDF receipt."}), 400
    receipt_bytes = receipt.read(5 * 1024 * 1024 + 1)
    if len(receipt_bytes) > 5 * 1024 * 1024:
        return jsonify({"error": "Receipt must be 5 MB or smaller."}), 400
    result = get_db().create_topup_request(user_id, amount, reference, naira_amount)
    if not result.get("ok"):
        return jsonify({"error": "Enter a valid yen amount and payment reference."}), 400
    forwarded, delivery_error = _forward_receipt_to_owner(user_id, amount, reference, result['topup_id'], receipt.filename, receipt.mimetype, receipt_bytes)
    get_db().update_topup_delivery(result['topup_id'], 'sent' if forwarded else 'failed', delivery_error)
    if not forwarded:
        return jsonify({"success": False, "topup_id": result["topup_id"], "forwarded_to_owner": False, "delivery_error": delivery_error, "error": "Receipt was saved but could not be sent to the owner. Please retry or contact the owner."}), 502
    return jsonify({"success": True, "topup_id": result["topup_id"], "forwarded_to_owner": True, "naira_amount": naira_amount, "message": f"Receipt sent. Send ₦{naira_amount:,}; yen will be credited automatically after approval."})


@app.route("/api/admin/overview", methods=["GET"])
@require_admin
def admin_overview(_user_id):
    payload = get_db().get_admin_overview()
    payload['prices'] = get_db().get_admin_prices()
    payload['receipt_forwarding_configured'] = bool((os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')) and (os.getenv('OWNER_ID') or os.getenv('TELEGRAM_OWNER_ID')))
    return jsonify(payload)


@app.route("/api/admin/prices/<source>/<int:item_id>", methods=["POST"])
@require_admin
def admin_update_price(_user_id, source, item_id):
    try:
        price = int((request.get_json(silent=True) or {}).get("price", 0))
    except (TypeError, ValueError):
        price = 0
    result = get_db().update_admin_price(source, item_id, price)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/admin/topups/<int:topup_id>", methods=["POST"])
@require_admin
def admin_review_topup(_user_id, topup_id):
    status = str((request.get_json(silent=True) or {}).get("status", "")).strip().lower()
    result = get_db().review_topup(topup_id, status)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/admin/players/<int:target_id>/yen", methods=["POST"])
@require_admin
def admin_adjust_player_yen(_user_id, target_id):
    try:
        amount = int((request.get_json(silent=True) or {}).get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    result = get_db().admin_adjust_yen(target_id, amount)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/dashboard/summary", methods=["GET"])

@require_user
def dashboard_summary(user_id):
    player = _player_payload(get_db().get_player(user_id))
    if not player:
        return jsonify({"error": "Player not found"}), 404
    return jsonify({"player": player, "online_count": 0, "recent_activity": [], "announcements": [], "daily_status": {"streak": 0, "can_claim": False}})


@app.route("/api/healthz", methods=["GET"])
def healthz():
    return jsonify({"ok": True, "service": "jjk-rpg-web-api"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("WEB_API_PORT", "8080")))
