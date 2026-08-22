"""Core PvE battle entry and battle-state reset commands.

Combat move resolution remains in the existing battle engine for compatibility;
this module owns the user-facing battle start and flee command handlers.
"""
from telegram import Update
from telegram.ext import ContextTypes


def build_battle_commands(db, game, format_yen):
    async def battle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        player = db.get_player(user.id)
        if not player or not player["character_id"]:
            await update.effective_message.reply_text("❌ Choose a character first! Use /characters")
            return
        if context.user_data.get("pve_battle"):
            await update.effective_message.reply_text("❌ You're already in a PvE battle! Use /flee to escape.")
            return
        if context.user_data.get("bot_battle"):
            await update.effective_message.reply_text("❌ You're already in a bot battle! Use /flee to escape.")
            return

        spirit = game.generate_cursed_spirit(player["level"])
        context.user_data["pve_battle"] = {
            "spirit": spirit,
            "turn": 1,
            "player_hp": player["hp"],
            "spirit_hp": spirit["hp"],
        }
        char = db.get_character(player["character_id"])
        attacks = char.get("attacks", []) if char else []
        atk_hint = "\n".join(f"  /a {a['num']} — {a['name']}" for a in attacks)
        text = (
            "👹 **CURSED SPIRIT APPEARS!**\n\n"
            f"*{spirit['name']}* (Grade {spirit['grade']})\n"
            f"❤️ HP: {spirit['hp']}\n"
            f"⚔️ ATK: {spirit['attack']}\n"
            f"🛡️ DEF: {spirit['defense']}\n\n"
            f"💰 *Reward:* ¥{format_yen(spirit['reward'])}\n"
            f"⭐ *XP:* {spirit['xp']}\n\n"
            f"{'━' * 22}\n"
            "**Your Attacks:**\n"
            "  /a attack — Basic strike (free)\n"
            f"{atk_hint}\n\n"
            "📋 /a — See all moves | 💨 /flee — Escape"
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def flee_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat = update.effective_chat
        popped = False
        for key in ("pve_battle", "bot_battle"):
            if context.user_data.pop(key, None):
                popped = True
        if chat:
            pvp = db.get_active_pvp_battle(user.id, chat.id)
            if pvp:
                db.finish_pvp_battle(pvp["battle_id"])
                popped = True
        cleared = db.clear_player_battles(user.id)
        if cleared and not popped:
            popped = True
        if popped:
            await update.effective_message.reply_text(
                "💨 **You fled the battle!**\n\n"
                "Sometimes retreat is the best strategy...\n"
                "_All battle state has been fully reset._",
                parse_mode="Markdown",
            )
        else:
            await update.effective_message.reply_text("❌ You're not in a battle!")

    return battle_command, flee_command
