"""Wallet command for the JJK RPG Telegram bot.

The command is dependency-injected so it can be tested independently from the
monolithic bot entrypoint and reused by future command registration modules.
"""
from telegram import Update
from telegram.ext import ContextTypes


def build_wallet_command(db, image_gen, format_yen):
    async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the player's yen balance with an image and text fallback."""
        user = update.effective_user
        player = db.get_player(user.id)
        if not player:
            await update.effective_message.reply_text("❌ Use /start first!")
            return

        # Keep this as a string: a trailing comma would create a tuple and make
        # Telegram reject both the image caption and text fallback.
        wallet_text = (
            f"💴 **{player['display_name']}'s Wallet**\n"
            f"{'━' * 22}\n"
            f"💰 Balance: ¥{format_yen(player['yen'])}\n"
            f"⭐ Level: {player['level']} | 🏅 Rank: {player['rank']}\n"
            f"{'━' * 22}\n"
            f"💸 Use /shop to spend • /daily for free yen"
        )
        try:
            await update.effective_message.reply_photo(
                photo=image_gen.generate_wallet_image(player),
                caption=wallet_text,
                parse_mode="Markdown",
            )
        except Exception:
            await update.effective_message.reply_text(wallet_text, parse_mode="Markdown")

    return wallet_command
