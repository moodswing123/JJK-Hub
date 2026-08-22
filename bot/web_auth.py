"""Secure dashboard credential registration for the JJK Telegram bot."""
import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes, CommandHandler, MessageHandler, filters

USERNAME, PASSWORD, CONFIRM_PASSWORD = range(3)
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=64)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"scrypt${n}${r}${p}${encode(salt)}${encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, raw_n, raw_r, raw_p, raw_salt, raw_digest = stored.split("$", 5)
        if algorithm != "scrypt":
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        digest = hashlib.scrypt(password.encode("utf-8"), salt=decode(raw_salt), n=int(raw_n), r=int(raw_r), p=int(raw_p), dklen=len(decode(raw_digest)))
        return hmac.compare_digest(digest, decode(raw_digest))
    except (ValueError, TypeError):
        return False


def hash_reset_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def generate_reset_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "A").replace("_", "B").upper()[:8]


# Public JJK RPG dashboard URL used when DASHBOARD_URL is not supplied by the host.
_DEFAULT_DASHBOARD_URL = "https://jjk-hub-api-server.vercel.app"
_RETIRED_DASHBOARD_URL = "https://jjk-hub-api-server-5qop-ten.vercel.app"


def _dashboard_url() -> str:
    configured = (os.getenv("DASHBOARD_URL") or _DEFAULT_DASHBOARD_URL).strip().rstrip("/")
    # Prevent an old bot deployment variable from sending players to the crashed alias.
    if configured == _RETIRED_DASHBOARD_URL:
        return _DEFAULT_DASHBOARD_URL
    return configured or _DEFAULT_DASHBOARD_URL


def build_web_reset_handler(db):
    async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        credentials = db.get_dashboard_credentials(user.id)
        if not credentials:
            await update.effective_message.reply_text("No dashboard account is linked to this Telegram account. Use /web to create one first.")
            return
        code = generate_reset_code()
        expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        db.create_dashboard_reset_token(user.id, hash_reset_code(code), expires_at)
        await update.effective_message.reply_text(
            f"🔑 *JJK RPG password reset*\n\nYour one-time reset code is `{code}`. It expires in 15 minutes. Enter it on the dashboard with your username and new password.\n\nIf you did not request this, you can ignore this message.",
            parse_mode="Markdown",
        )

    return CommandHandler("webreset", reset)


def build_web_conversation(db) -> ConversationHandler:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.pop("web_username", None)
        context.user_data.pop("web_password", None)
        await update.effective_message.reply_text(
            "🔐 *JJK RPG dashboard access*\n\nChoose a username for the dashboard. Use 3–32 lowercase characters, numbers, dots, hyphens, or underscores.\n\nSend /cancel to stop.",
            parse_mode="Markdown",
        )
        return USERNAME

    async def username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = (update.effective_message.text or "").strip().lower()
        if not _USERNAME_RE.fullmatch(value):
            await update.effective_message.reply_text("That username is not valid. Use 3–32 lowercase letters, numbers, dots, hyphens, or underscores.")
            return USERNAME
        existing = db.get_player_by_dashboard_username(value)
        if existing and int(existing.get("user_id", 0)) != update.effective_user.id:
            await update.effective_message.reply_text("That dashboard username is already taken. Choose another one.")
            return USERNAME
        context.user_data["web_username"] = value
        await update.effective_message.reply_text("Username saved. Now send your dashboard password. It must be at least 10 characters.")
        return PASSWORD

    async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        message = update.effective_message
        value = message.text or ""
        try:
            await message.delete()
        except Exception:
            pass
        if len(value) < 10 or len(value) > 128:
            await message.reply_text("Password length must be between 10 and 128 characters. Please send it again.")
            return PASSWORD
        context.user_data["web_password"] = value
        await message.reply_text("Password received. Send it one more time to confirm.")
        return CONFIRM_PASSWORD

    async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        message = update.effective_message
        value = message.text or ""
        try:
            await message.delete()
        except Exception:
            pass
        password_value: Optional[str] = context.user_data.get("web_password")
        if not password_value or value != password_value:
            context.user_data.pop("web_password", None)
            await message.reply_text("The passwords did not match. Please send a new password.")
            return PASSWORD
        user = update.effective_user
        db.get_or_create_player(user.id, user.username or "", user.full_name or f"Player {user.id}")
        username_value = context.user_data["web_username"]
        try:
            db.save_dashboard_credentials(user.id, username_value, _hash_password(password_value))
        except Exception:
            context.user_data.clear()
            await message.reply_text("I could not save your dashboard access right now. Please try /web again later.")
            return ConversationHandler.END
        context.user_data.clear()
        # Send the login link immediately after the credentials are persisted.
        await message.reply_text(
            f"✅ Dashboard access created for *{username_value}*.\n\nOpen your dashboard now: {_dashboard_url()}",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.pop("web_username", None)
        context.user_data.pop("web_password", None)
        await update.effective_message.reply_text("Dashboard registration cancelled.")
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[CommandHandler("web", start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
            CONFIRM_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        conversation_timeout=300,
    )
