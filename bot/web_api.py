"""HTTP API for the JJK RPG dashboard credential login."""
import base64
import hashlib
import hmac
import json
import os
import time
from functools import wraps

from flask import Flask, jsonify, request

from database import Database
from web_auth import hash_reset_code, verify_password, _hash_password

app = Flask(__name__)
db = Database()
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
    }


def require_user(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        user_id = _user_id_from_token(header.removeprefix("Bearer ").strip()) if header else None
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        return handler(user_id, *args, **kwargs)
    return wrapped


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
    record = db.get_player_by_dashboard_username(username)
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
    record = db.get_player_by_dashboard_username(username)
    if not record or not db.consume_dashboard_reset_token(int(record["user_id"]), hash_reset_code(code)):
        return jsonify({"error": "The reset code is invalid or expired. Request a new one from Telegram."}), 400
    db.save_dashboard_credentials(int(record["user_id"]), username, _hash_password(new_password))
    return jsonify({"success": True})


@app.route("/api/auth/me", methods=["GET"])
@require_user
def auth_me(user_id):
    player = _player_payload(db.get_player(user_id))
    return jsonify(player) if player else (jsonify({"error": "Player not found"}), 404)


@app.route("/api/inventory", methods=["GET"])
@require_user
def inventory(user_id):
    items = []
    for item in db.get_inventory(user_id):
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
    player = db.get_player(user_id)
    item = next((candidate for candidate in db.get_inventory(user_id) if int(candidate["id"]) == item_id), None)
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
            db.update_player_stat(user_id, stat, int(player[stat]) + int(effect[stat]))
    db.remove_from_inventory(user_id, item_id)
    return jsonify({"success": True, "item": item})


@app.route("/api/dashboard/summary", methods=["GET"])

@require_user
def dashboard_summary(user_id):
    player = _player_payload(db.get_player(user_id))
    if not player:
        return jsonify({"error": "Player not found"}), 404
    return jsonify({"player": player, "online_count": 0, "recent_activity": [], "announcements": [], "daily_status": {"streak": 0, "can_claim": False}})


@app.route("/api/healthz", methods=["GET"])
def healthz():
    return jsonify({"ok": True, "service": "jjk-rpg-web-api"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("WEB_API_PORT", "8080")))
