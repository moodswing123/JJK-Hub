"""
Jujutsu Kaisen Telegram Game Bot — Updated
"""

from commands.item_aliases import resolve_numbered_item
from gemini_debugger import analyze_diagnostic, apply_review_to_diagnostic
import logging
import asyncio
import random
import json
import os
import signal
import sys
from datetime import datetime
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from config import BOT_TOKEN, OWNER_ID, ADMIN_IDS, MAX_LEVEL
from database import Database
from game_engine import GameEngine
from image_generator import ImageGenerator
from utils import is_owner, is_admin, format_yen
from expansion_system import ExpansionSystem
from web_auth import build_web_conversation, build_web_reset_handler
from commands.wallet import build_wallet_command
from commands.battle import build_battle_commands

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()
game = GameEngine(db)
image_gen = ImageGenerator()
expansion = ExpansionSystem(db)
battle_command, flee_command = build_battle_commands(db, game, format_yen)

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _energy_bar(current: int, maximum: int, length: int = 15) -> str:
    """Return a visual energy bar that exactly reflects current/max."""
    if maximum <= 0:
        return "░" * length
    filled = max(0, min(length, int(round(current / maximum * length))))
    return "█" * filled + "░" * (length - filled)

def _resolve_move(player: dict, move_input: str):
    """
    Resolve a move string (name or number) to a (tech_or_attack_dict, label, ce_cost, dmg_mult).
    Returns (None, error_msg) on failure.
    """
    move_lower = move_input.strip().lower()

    # Basic free attack
    if move_lower in ('attack', 'a', 'basic attack', 'basic'):
        return {'name': 'Basic Attack', 'ce_cost': 0, 'damage_multiplier': 1.0,
                'description': 'A standard physical strike'}, None

    # Expansion moves are checked before legacy learned techniques so an
    # awakened player can use the new skill tree through the existing /a flow.
    expansion_move = expansion.resolve_move(player['user_id'], move_input)
    if expansion_move:
        if expansion_move.get('locked'):
            if expansion_move.get('cooldown_until'):
                return None, f"❌ **{expansion_move['name']}** is on cooldown."
            return None, (
                f"❌ **{expansion_move['name']}** unlocks at "
                f"{expansion_move['unlock_mastery']} technique mastery."
            )
        return expansion_move, None
    if move_lower in ('domain', 'domain expansion'):
        domain_ok, domain_move = expansion.domain_move(player['user_id'])
        if not domain_ok:
            return None, f"❌ {domain_move}"
        return domain_move, None

    # Character numbered attacks (1, 2, 3)
    char = db.get_character(player.get('character_id')) if player.get('character_id') else None
    char_attacks = char.get('attacks', []) if char else []

    if move_lower.isdigit():
        num = int(move_lower)

        # 0 = basic attack
        if num == 0:
            return {'name': 'Basic Attack', 'ce_cost': 0, 'damage_multiplier': 1.0,
                    'description': 'A standard physical strike'}, None

        # 1-3 = character attacks
        for atk in char_attacks:
            if atk.get('num') == num:
                return {
                    'name': atk['name'],
                    'ce_cost': atk['ce_cost'],
                    'damage_multiplier': atk['dmg_mult'],
                    'description': atk['description'],
                    'effect': atk.get('effect', '')
                }, None

        # 4-7 = learned techniques (offset by number of char attacks)
        techs = player.get('techniques') or []
        tech_index = num - len(char_attacks) - 1
        if 0 <= tech_index < len(techs):
            t_name = techs[tech_index]
            tech = db.get_technique(t_name)
            if tech:
                return tech, None
            return {'name': t_name, 'ce_cost': 20, 'damage_multiplier': 1.5,
                    'description': 'Learned technique'}, None

        return None, f"❌ No move #{num}. Use `/a` to see your numbered moves."

    # Character named attacks
    for atk in char_attacks:
        if atk['name'].lower() == move_lower:
            return {
                'name': atk['name'],
                'ce_cost': atk['ce_cost'],
                'damage_multiplier': atk['dmg_mult'],
                'description': atk['description'],
                'effect': atk.get('effect', '')
            }, None

    # Learned techniques
    for t_name in (player.get('techniques') or []):
        if t_name.lower() == move_lower:
            tech = db.get_technique(t_name)
            if tech:
                return tech, None

    # Partial match for techniques
    for t_name in (player.get('techniques') or []):
        if move_lower in t_name.lower():
            tech = db.get_technique(t_name)
            if tech:
                return tech, None

    return None, f"❌ Unknown move: *{move_input}*\nUse `/a` to see your moves."


def _paginate(lines: list, page: int, per_page: int, header: str, footer: str = "") -> tuple:
    """Return (text, total_pages) for paginated content."""
    total = max(1, (len(lines) + per_page - 1) // per_page)
    page = max(0, min(page, total - 1))
    chunk = lines[page * per_page:(page + 1) * per_page]
    text = header + "\n".join(chunk)
    if footer:
        text += "\n" + footer
    text += f"\n\n📄 Page {page + 1}/{total}"
    return text, total, page


def _page_keyboard(cb_prefix: str, page: int, total: int) -> InlineKeyboardMarkup:
    """Build pagination keyboard."""
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{cb_prefix}_{page - 1}"))
    btns.append(InlineKeyboardButton(f"{page + 1}/{total}", callback_data="noop"))
    if page < total - 1:
        btns.append(InlineKeyboardButton("Next ▶️", callback_data=f"{cb_prefix}_{page + 1}"))
    return InlineKeyboardMarkup([btns]) if btns else None


# ═══════════════════════════════════════════════════════════════
# EXPANSION COMMANDS
# ═══════════════════════════════════════════════════════════════

async def _expansion_reply(update: Update, text: str):
    await update.effective_message.reply_text(text, parse_mode='Markdown')


async def technique_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    expansion.ensure_player(user.id)
    if not context.args:
        catalog = []
        for row in TECHNIQUE_DISPLAY:
            catalog.append(f"• **{row[0]}** — {row[1]}")
        await _expansion_reply(
            update,
            "🧬 **Innate Technique Registry**\n\n"
            "Choose an origin with `/origin sorcerer` or `/origin curse`.\n"
            "Awaken with `/technique awaken <name>`.\n\n" + "\n".join(catalog)
        )
        return
    action = context.args[0].lower()
    if action == "awaken":
        if len(context.args) < 2:
            await _expansion_reply(update, "Usage: `/technique awaken Limitless`")
            return
        ok, text = expansion.awaken(user.id, " ".join(context.args[1:]))
        await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)
        return
    t = expansion.technique(user.id)
    if not t:
        await _expansion_reply(update, "No innate technique awakened. Use `/technique awaken <name>`.")
        return
    await _expansion_reply(
        update,
        f"🧬 **{t['name']}**\n"
        f"Passive: {t['passive']}\n"
        f"Active: {', '.join(t['active_skills'])}\n"
        f"Ultimate: {t['ultimate']}\n"
        f"Maximum: {t['maximum']}\n"
        f"Affinity: {t['affinity']}\n"
        f"Mastery: {t['progress'].get('mastery', 0)}/100 "
        f"({t['progress'].get('mastery_exp', 0)}/100 EXP)"
    )


# Kept as a local presentation list so the command remains useful even if the
# catalog grows beyond the seeded set.
TECHNIQUE_DISPLAY = [
    ("Limitless", "Infinity and spatial control"), ("Ten Shadows", "Independent shikigami progression"),
    ("Blood Manipulation", "Bleeding and precision damage"), ("Cursed Speech", "Commands and control"),
    ("Boogie Woogie", "Position swaps and evasion"), ("Projection Sorcery", "Frame-based speed"),
    ("Idle Transfiguration", "Soul shaping and regeneration"), ("Ratio Technique", "Weak-point criticals"),
    ("Copy", "Borrow techniques and Rika"), ("Construction", "Create tools from CE"),
    ("Ice Formation", "Slow and freeze targets"), ("Straw Doll", "Marks and resonance"),
    ("Disaster Flames", "Burn and meteor damage"), ("Disaster Plants", "Roots and poison"),
    ("Disaster Water", "Floods and swarm attacks"), ("Shrine", "Cleave and dismantle"),
    ("Star Rage", "Virtual mass"), ("Heavenly Restriction", "Physical body awakening"),
]


async def domain_expansion_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    action = context.args[0].lower() if context.args else "status"
    if action in ("unlock", "awaken", "expand"):
        ok, text = expansion.unlock_domain(user.id)
    elif action == "clash" and len(context.args) > 1:
        opponent = db.get_user_by_username(context.args[1].lstrip("@"))
        if not opponent:
            ok, text = False, "Opponent not found."
        else:
            clash = expansion.domain_clash(user.id, opponent["user_id"])
            ok, text = True, f"Domain clash winner: {'you' if clash['winner'] == user.id else opponent['display_name']}.\nScores: {clash['score']}"
    else:
        p = expansion.progress(user.id)
        ok, text = True, (
            f"🌀 **Domain Status**\nDomain: {p['domain_name'] or 'Not unlocked'}\n"
            f"Refinement: {p['domain_refinement']}\nMastery: {p['domain_mastery']}/100\n"
            "Use `/domain unlock` when your technique is refined.\n"
            "Use `/domain clash @player` to resolve a clash."
        )
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def maximum_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, text = expansion.maximum(update.effective_user.id)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def rct_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.args[0].lower() if context.args else "heal"
    ok, text = expansion.rct(update.effective_user.id, mode)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def black_flash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timing = context.args[0] if context.args else "normal"
    ok, text, _ = expansion.black_flash(update.effective_user.id, timing)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def vow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await _expansion_reply(update, "Usage: `/vow create Last Stand permanent`")
        return
    action = context.args[0].lower()
    if action == "create":
        permanent = "permanent" in [arg.lower() for arg in context.args]
        words = [arg for arg in context.args[1:] if arg.lower() != "permanent"]
        ok, text = expansion.create_vow(update.effective_user.id, " ".join(words), permanent)
    else:
        ok, text = True, "Vows: Last Stand, Binding Blade, Black Flash Oath, Iron Body. Use `/vow create <name> [permanent]`."
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def origin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await _expansion_reply(update, "Usage: `/origin sorcerer` or `/origin curse`")
        return
    ok, text = expansion.awaken_origin(update.effective_user.id, context.args[0])
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def restriction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    variant = context.args[0] if context.args else "toji"
    ok, text = expansion.awaken_restriction(update.effective_user.id, variant)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def evolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, text = expansion.evolve(update.effective_user.id)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def school_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await _expansion_reply(update, "Schools: Tokyo, Kyoto, curse, independent. Usage: `/school Tokyo`")
        return
    ok, text = expansion.set_school(update.effective_user.id, " ".join(context.args))
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def reputation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rep = expansion.reputation(update.effective_user.id, " ".join(context.args))
    await _expansion_reply(update, "📈 **Reputation**\n" + "\n".join(f"• {k}: {v}" for k, v in rep.items()) if rep else "No reputation recorded.")


async def gear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        catalog = WEAPON_DISPLAY + ARMOR_DISPLAY
        owned = expansion.gear(user_id)
        await _expansion_reply(
            update,
            "🗡️ **Cursed Gear Catalog**\n" + "\n".join(
                f"#{index} • {name} — {desc} | ¥{expansion.GEAR_PRICES.get(name.lower(), 0):,}"
                for index, (name, desc) in enumerate(catalog, start=1)
            ) +
            "\n\nOwned:\n" + ("\n".join(f"• {g['gear_name']} Lv.{g['level']} {'[equipped]' if g['equipped'] else ''}" for g in owned) or "None") +
            "\nBuy with `/gear acquire <name>`; equip with `/gear equip <name>` or `/equip <inventory number>`."
        )
        return
    action = context.args[0].lower()
    name = " ".join(context.args[1:])
    catalog = WEAPON_DISPLAY + ARMOR_DISPLAY
    if action in ("acquire", "equip", "upgrade") and name.isdigit():
        gear_index = int(name) - 1
        if 0 <= gear_index < len(catalog):
            name = catalog[gear_index][0]
    if action == "acquire":
        ok, text = expansion.acquire_gear(user_id, name)
    elif action == "equip":
        ok, text = expansion.equip_gear(user_id, name)
    elif action == "upgrade":
        ok, text = expansion.upgrade_gear(user_id, name)
    else:
        ok, text = False, "Usage: `/gear acquire <name>`, `/gear equip <name>`, or `/gear upgrade <name>`"
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


WEAPON_DISPLAY = [(row[0], row[2]) for row in [
    ("Playful Cloud", "", "Defense scaling"), ("Split Soul Katana", "", "20% defense penetration"),
    ("Inverted Spear of Heaven", "", "Technique dispel"), ("Dragon Bone", "", "Critical CE release"),
    ("Chain of a Thousand Miles", "", "Ranged accuracy"), ("Black Rope", "", "Domain disruption"),
]]
ARMOR_DISPLAY = [(row[0], row[2]) for row in [
    ("Tokyo Jujutsu Robes", "", "Balanced protection"), ("Simple Domain Vestments", "", "Refinement +8"),
    ("Disaster Curse Mantle", "", "Elemental affinity"), ("Heavenly Body Wraps", "", "Speed and durability"),
]]


async def shikigami_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        rows = expansion.shikigami(update.effective_user.id)
        await _expansion_reply(update, "🐺 **Shikigami Registry**\n" + "\n".join(
            f"• {r['name']} — Lv.{r['level']} | Mastery {r['mastery']} | Adaptation {r['adaptation']}" for r in rows
        ) + "\n\nSummon with `/shikigami summon <name>`.")
        return
    if context.args[0].lower() != "summon":
        await _expansion_reply(update, "Usage: `/shikigami summon Nue`")
        return
    ok, text = expansion.summon(update.effective_user.id, " ".join(context.args[1:]))
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def raid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        raids = [r for r in expansion.get_raids() if r.get('status') == 'open']
        await _expansion_reply(update, "👹 **World Boss Raids**\n" + ("\n".join(
            f"#{r['id']} {r['boss']} ({r['grade']}) — {r['hp']}/{r['max_hp']} HP" for r in raids
        ) or "No open raids.") + "\n\nUse `/raid attack <id> <damage>`.")
        return
    if context.args[0].lower() == "attack" and len(context.args) > 2:
        try:
            raid_id, damage = int(context.args[1]), int(context.args[2])
        except ValueError:
            await _expansion_reply(update, "Raid id and damage must be numbers.")
            return
        ok, text = expansion.raid_attack(update.effective_user.id, raid_id, damage)
        if ok:
            expansion.unlock_achievement(update.effective_user.id, "first_raid")
    else:
        ok, text = False, "Usage: `/raid attack <id> <damage>`"
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def event_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        events = expansion.list_events()
        await _expansion_reply(update, "🌍 **Dynamic World Events**\n" + ("\n".join(
            f"#{e['id']} {e['name']} — {e['description']}" for e in events
        ) or "No active events.") + "\n\nJoin with `/event join <id>`.")
        return
    if context.args[0].lower() == "join" and len(context.args) > 1:
        try:
            event_id = int(context.args[1])
        except ValueError:
            await _expansion_reply(update, "Event id must be a number.")
            return
        ok, text = expansion.join_event(update.effective_user.id, event_id)
    elif context.args[0].lower() == "claim" and len(context.args) > 1:
        try:
            event_id = int(context.args[1])
        except ValueError:
            await _expansion_reply(update, "Event id must be a number.")
            return
        ok, text = expansion.claim_event(update.effective_user.id, event_id)
    else:
        ok, text = False, "Usage: `/event join <id>` or `/event claim <id>`"
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def story_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = " ".join(context.args) if context.args else None
    state = expansion.story(update.effective_user.id, choice)
    await _expansion_reply(update, f"📖 **Story Mode — Chapter {state['chapter']}, Scene {state['scene']}**\n"
                         "A veil trembles over the city. Your next choice will shape the route.\n"
                         "Choose with `/story investigate`, `/story protect`, or `/story pursue`.")


async def npc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    npcs = expansion.npcs()
    if context.args:
        wanted = " ".join(context.args).lower()
        npcs = [npc for npc in npcs if wanted in npc["name"].lower()]
    if not npcs:
        await _expansion_reply(update, "That NPC is not available in the current chapter.")
        return
    await _expansion_reply(
        update,
        "🧑‍🏫 **Jujutsu NPCs**\n" + "\n".join(
            f"• **{npc['name']}** ({npc['kind']}) — {npc['description']}" for npc in npcs
        ) + "\n\nNPC training and reputation are persistent parts of your progression."
    )


async def extended_missions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    missions = expansion.extended_missions(update.effective_user.id)
    await _expansion_reply(
        update,
        "📜 **Long-Form Missions**\n" + "\n\n".join(
            f"{'✅' if m['completed'] else '⬜'} **{m['name']}** — "
            f"{m['progress']}/{m['target']} | ¥{m['reward_yen']:,} + {m['reward_xp']} XP "
            f"({m['period']})" for m in missions
        )
    )


async def clan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.args[0].lower() if context.args else "status"
    if action == "donate":
        await clan_donate_command(update, context)
        return
    value = " ".join(context.args[1:])
    try:
        ok, text = expansion.clan(update.effective_user.id, action, value)
    except ValueError:
        ok, text = False, "Contribution amount must be a number."
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def buyyen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment_text = (
        "🏦 BANK DETAILS\n\n"
        "😎 PATRICK\n\n"
        "🔢 6521307860\n\n"
        "✅ OPAY\n\n"
        "SEND SCREENSHOT AFTER PAYMENT\n\n"
        "Yen will be credited after payment verification."
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Contact owner", url=f"tg://user?id={OWNER_ID}")
    ]])
    await update.effective_message.reply_text(payment_text, reply_markup=keyboard)


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Owner access required.")
        return
    await update.effective_message.reply_text(
        "♻️ The bot is restarting safely. All committed data has been saved. "
        "It will come back online automatically."
    )

    async def _restart():
        await asyncio.sleep(1.5)
        os.execv(sys.executable, [sys.executable, *sys.argv])

    context.application.create_task(_restart())


async def clan_donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /clan donate <amount> @member")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Donation amount must be a positive number.")
        return
    recipient = db.get_user_by_username(context.args[1].lstrip("@"))
    if not recipient:
        await update.effective_message.reply_text("❌ Recipient player not found.")
        return
    player = db.get_player(user_id)
    clan_key = player.get("clan_key") if player else None
    if not clan_key:
        await update.effective_message.reply_text("❌ You are not in a clan.")
        return
    result = db.clan_donate(clan_key, user_id, recipient["user_id"], amount)
    if not result.get("ok"):
        messages = {
            "amount": "Amount must be positive.",
            "clan": "Clan not found.",
            "leader": "Only the clan leader may donate from the treasury.",
            "member": "That player is not a member of your clan.",
            "treasury": f"Insufficient treasury balance: ¥{result.get('balance', 0):,}.",
            "recipient": "Recipient player not found.",
        }
        await update.effective_message.reply_text("❌ " + messages.get(result.get("reason"), "Donation failed."))
        return
    text = (
        f"✅ Treasury donation complete.\n"
        f"¥{amount:,} sent to {recipient.get('display_name') or recipient.get('username')}.\n"
        f"Remaining treasury: ¥{result['balance']:,}"
    )
    await update.effective_message.reply_text(text)
    try:
        await context.bot.send_message(
            chat_id=recipient["user_id"],
            text=f"🏯 Your clan treasury sent you ¥{amount:,}.",
        )
    except Exception as exc:
        logger.warning("Could not notify donation recipient: %s", exc)


async def craft_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        recipes = expansion.recipes()
        await _expansion_reply(update, "🛠️ **Crafting Recipes**\n" + "\n".join(
            f"• {r['name']}: {r['requirements']}" for r in recipes
        ) + "\nUse `/craft <recipe name>`.")
        return
    ok, text = expansion.craft(update.effective_user.id, " ".join(context.args))
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def materials_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _expansion_reply(
        update,
        "🧱 **Crafting Materials**\n" + expansion.material_summary(update.effective_user.id)
    )


async def enchant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await _expansion_reply(update, "Usage: `/enchant <gear> <Fire|Ice|Lightning|Poison|Soul Damage|Bleeding>`")
        return
    ok, text = expansion.enchant(update.effective_user.id, context.args[0], " ".join(context.args[1:]))
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        ok, text = expansion.market(user_id, "listings")
    elif context.args[0].lower() == "list" and len(context.args) >= 3:
        try:
            price = int(context.args[-1])
        except ValueError:
            price = 0
        ok, text = expansion.market(user_id, "list", " ".join(context.args[1:-1]), price)
    elif context.args[0].lower() == "buy" and len(context.args) > 1:
        try:
            listing_id = int(context.args[1])
        except ValueError:
            listing_id = 0
        ok, text = expansion.market(user_id, "buy", listing_id=listing_id)
    else:
        ok, text = False, "Usage: `/market`, `/market list <item> <price>`, `/market buy <listing id>`"
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def culling_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.args[0].lower() if context.args else "leaderboard"
    colony = " ".join(context.args[1:])
    ok, text = expansion.culling(update.effective_user.id, action, colony)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def prestige_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, text = expansion.prestige(update.effective_user.id)
    if ok:
        expansion.unlock_achievement(update.effective_user.id, "first_prestige")
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def collection_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    achievements = expansion.achievements(user_id)
    titles = expansion.titles(user_id)
    a_text = "\n".join(f"{'✅' if a['unlocked_at'] else '⬜'} {a['name']} — {a['description']}" for a in achievements)
    t_text = "\n".join(f"{'✅' if t['unlocked_at'] else '⬜'} {t['name']}" for t in titles)
    await _expansion_reply(update, f"🏆 **Achievements**\n{a_text}\n\n🎖️ **Titles**\n{t_text}")


async def cosmetics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        rows = expansion.cosmetics(user_id)
        text = "\n".join(
            f"{'✅' if row['unlocked_at'] else '⬜'} {row['name']} "
            f"({row['kind']}) — {row['description']}"
            for row in rows
        )
        await _expansion_reply(
            update,
            "🎨 **Cosmetics Collection**\n" + text
            + "\n\nUnlock with `/cosmetics unlock <name>` and equip with "
            "`/cosmetics equip <name>`."
        )
        return
    action = context.args[0].lower()
    name = " ".join(context.args[1:])
    if action == "unlock":
        ok, text = expansion.unlock_cosmetic(user_id, name)
    elif action == "equip":
        ok, text = expansion.equip_cosmetic(user_id, name)
    else:
        ok, text = False, (
            "Usage: `/cosmetics`, `/cosmetics unlock <name>`, "
            "or `/cosmetics equip <name>`"
        )
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = expansion.weather()
    await _expansion_reply(update, f"🌦️ **World Weather: {current['name']}**\n{current['effect']}\nWeather changes daily and affects combat.")


async def endgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.args[0].lower() if context.args else "status"
    p = expansion.progress(update.effective_user.id)
    floor = p.get("prestige", 0) + 1
    if action == "advance":
        # Use prestige level as a proxy for current floor when no DB query available
        floor = p.get("prestige", 0) + 1
    ok, text = expansion.endless(update.effective_user.id, action if action in ("dungeon", "tower", "survival") else "tower", floor)
    await _expansion_reply(update, ("✅ " if ok else "❌ ") + text)


# ═══════════════════════════════════════════════════════════════
# GENERAL COMMANDS
# ═══════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_or_create_player(user.id, user.username, user.first_name)

    welcome_text = (
        f"🌀 **Welcome to Jujutsu Kaisen, {user.first_name}!**\n\n"
        f"Rank: {player['rank']}\n"
        f"💴 Yen: ¥{format_yen(player['yen'])}\n"
        f"⚡ Cursed Energy: {player['cursed_energy']}/{player['max_cursed_energy']}\n\n"
        f"🎮 **Quick Commands:**\n"
        f"• `/p` — View your profile\n"
        f"• `/characters` — Choose your fighter\n"
        f"• `/battle` — Fight cursed spirits\n"
        f"• `/ch @user` — Challenge a sorcerer\n"
        f"• `/shop` — Buy items & techniques\n"
        f"• `/help` — Full command list\n\n"
        f"🔥 *Become the strongest sorcerer!*"
    )

    keyboard = [
        [InlineKeyboardButton("🎭 Choose Character", callback_data='choose_char')],
        [InlineKeyboardButton("⚔️ Start Battle", callback_data='start_battle')],
        [InlineKeyboardButton("📜 Missions", callback_data='missions')]
    ]
    try:
        awakening_image = image_gen.generate_faction_awakening(player)
        await update.effective_message.reply_photo(
            photo=awakening_image,
            caption=welcome_text + f"\n\n✨ Your assigned faction: **{player.get('faction', 'Sorcerer')}**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as exc:
        logger.error("Faction awakening image failed: %s", exc)
        await update.effective_message.reply_text(
            welcome_text + f"\n\n✨ Your assigned faction: **{player.get('faction', 'Sorcerer')}**",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )


async def listplayers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List registered players with simple command pagination."""
    page = int(context.args[0]) - 1 if context.args and context.args[0].isdigit() else 0
    players = db.get_player_listing()
    per_page = 8
    total_pages = max(1, (len(players) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    rows = players[page * per_page:(page + 1) * per_page]
    lines = [f"👥 **Registered Players** — Page {page + 1}/{total_pages}", "━" * 26]
    for index, p in enumerate(rows, start=page * per_page + 1):
        last_active = p.get('last_active_at') or "Unknown"
        try:
            last_active = datetime.fromisoformat(str(last_active)).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
        lines.append(
            f"{index}. **{p.get('display_name') or 'Unknown'}** "
            f"(@{p.get('username') or 'no_username'})\n"
            f"   ID: `{p['user_id']}` | Lv.{p.get('level', 1)} | "
            f"{p.get('faction') or 'Unassigned'} | Active: {last_active}"
        )
    if not rows:
        lines.append("No registered players yet.")
    lines.append(f"\nUse `/listplayers {page + 2}` for the next page." if page + 1 < total_pages else "")
    await update.effective_message.reply_text("\n".join(lines), parse_mode='Markdown')


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ You haven't started yet! Use /start")
        return

    character = db.get_character(player['character_id']) if player['character_id'] else None
    char_attacks = character.get('attacks', []) if character else []
    domain = db.get_user_domain(user.id)

    # Techniques the player can still learn (all techniques - already learned)
    all_techs = db.get_all_techniques()
    learned = set(player.get('techniques') or [])
    available_to_learn = [t for t in all_techs if t['name'] not in learned]

    # Build equipped techniques display
    if player['techniques']:
        equip_lines = []
        for tname in player['techniques']:
            t = db.get_technique(tname)
            if t:
                equip_lines.append(f"  🌀 {t['name']} (CE:{t['energy_cost']}, {t['damage_multiplier']}x)")
            else:
                equip_lines.append(f"  🌀 {tname}")
        equipped_techs_str = "\n".join(equip_lines)
    else:
        equipped_techs_str = "  None — buy from /shop then /learn"

    # Character attacks available
    if char_attacks:
        char_atk_lines = []
        for atk in char_attacks:
            char_atk_lines.append(f"  {atk['num']}. {atk['name']} (CE:{atk['ce_cost']}, {atk['dmg_mult']}x)")
        char_atk_str = "\n".join(char_atk_lines)
    else:
        char_atk_str = "  None (choose a character first)"

    # Available to learn (first 5)
    if available_to_learn:
        learn_preview = ", ".join(t['name'] for t in available_to_learn[:5])
        if len(available_to_learn) > 5:
            learn_preview += f" +{len(available_to_learn)-5} more"
        learn_str = f"  {learn_preview}"
    else:
        learn_str = "  All techniques learned! 🏆"

    domain_str = ""
    if domain:
        status = "✅ Equipped" if domain['equipped'] else f"🔒 Not equipped (¥1,500,000 to equip)"
        domain_str = f"\n🌀 *Domain:* {domain['domain_name']} (Power: {domain['power']}) — {status}"

    profile_text = (
        f"🌀 **{player['display_name']}**\n"
        f"{'━' * 20}\n"
        f"🏅 *Rank:* {player['rank']}\n"
        f"⭐ *Level:* {player['level']}/{MAX_LEVEL} ({player['xp']}/{player['xp_needed']} XP)\n"
        f"🎭 *Character:* {character['name'] if character else 'None'}\n"
        f"{'━' * 20}\n"
        f"💴 *Yen:* ¥{format_yen(player['yen'])}\n"
        f"❤️ HP:  {player['hp']}/{player['max_hp']} [{_energy_bar(player['hp'], player['max_hp'])}]\n"
        f"⚡ CE:  {player['cursed_energy']}/{player['max_cursed_energy']} [{_energy_bar(player['cursed_energy'], player['max_cursed_energy'])}]\n"
        f"{'━' * 20}\n"
        f"⚔️ *Attack:* {player['attack']}\n"
        f"🛡️ *Defense:* {player['defense']}\n"
        f"💨 *Speed:* {player['speed']}\n"
        f"{'━' * 20}\n"
        f"🏆 *Wins:* {player['wins']} | 💀 *Losses:* {player['losses']} | 📊 {player['win_rate']}% WR\n"
        f"{'━' * 20}\n"
        f"🔮 **Equipped Techniques:**\n{equipped_techs_str}\n"
        f"{'━' * 20}\n"
        f"⚔️ **Character Attacks** (use /a 1, /a 2, /a 3):\n{char_atk_str}\n"
        f"{'━' * 20}\n"
        f"📚 **Available to Learn:** /learn [name]\n{learn_str}"
        f"{domain_str}"
    )

    # Expansion data is additive: existing profile fields and commands remain
    # unchanged, while awakened players get their deeper progression at a glance.
    try:
        xp = expansion.profile(user.id)
        technique = xp.get('technique') or {}
        gear = xp.get('gear') or []
        profile_text += (
            f"\n{'━' * 20}\n"
            f"🌌 **Awakening Layer**\n"
            f"🧬 Innate: {xp.get('innate_technique') or 'Not awakened'}"
            f" | Mastery: {xp.get('technique_mastery', 0)}/100\n"
            f"🌀 Domain: {xp.get('domain_name') or 'Not unlocked'}"
            f" | Refinement: {xp.get('domain_refinement', 0)}\n"
            f"✨ Awakening: {xp.get('awakening') or 'Dormant'}"
            f" | Prestige: {xp.get('prestige', 0)}\n"
            f"🏫 School: {xp.get('school') or 'Unaffiliated'}"
            f" | Clan: {xp.get('clan') or 'None'}\n"
            f"⚡ Black Flash: {xp.get('black_flash_record', 0)} record"
            f" | {xp.get('black_flash_total', 0)} total\n"
            f"🗡️ Equipped: {', '.join(g['gear_name'] for g in gear) if gear else 'None'}\n"
            f"🎨 Cosmetics: {', '.join(c['cosmetic_name'] for c in xp.get('cosmetics', [])) or 'None'}\n"
            f"🏆 Collections: {xp.get('title_count', 0)} titles | "
            f"{xp.get('achievement_count', 0)} achievements"
        )
    except Exception as exc:
        logger.warning("Expansion profile unavailable: %s", exc)

    if character:
        try:
            char_image = image_gen.generate_character_skin(character, player)
            await update.effective_message.reply_photo(
                photo=char_image, caption=profile_text, parse_mode='Markdown'
            )
            return
        except Exception as e:
            logger.error(f"Error generating character image: {e}")
    await update.effective_message.reply_text(profile_text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# CHARACTERS — PAGINATED
# ═══════════════════════════════════════════════════════════════

def _build_char_page(characters, page: int, player=None):
    char = characters[page]
    total = len(characters)
    attacks = char.get('attacks', [])

    atk_lines = "\n".join(
        f"  {a['num']}. **{a['name']}** — CE:{a['ce_cost']} | {a['dmg_mult']}x\n     _{a['description']}_"
        for a in attacks
    ) if attacks else "  No special attacks"

    is_free = char['cost'] == 0
    cost_str = "**FREE** 🎁" if is_free else f"¥{format_yen(char['cost'])}"
    owned = bool(player and db.player_owns_character(player['user_id'], char['id']))
    ownership = "✅ Owned — tap to equip" if owned else "🛒 Purchase to unlock permanently"

    text = (
        f"🎭 **{char['name']}**\n"
        f"{'━' * 22}\n"
        f"🏅 *Grade:* {char['grade']}\n"
        f"💬 *\"{char['quote']}\"*\n"
        f"{'━' * 22}\n"
        f"⚔️ ATK: {char['attack']}  |  🛡️ DEF: {char['defense']}  |  💨 SPD: {char['speed']}\n"
        f"❤️ Max HP: {char['max_hp']}  |  ⚡ Max CE: {char['max_ce']}\n"
        f"🔮 *Signature:* {char['technique']}\n"
        f"💰 *Cost:* {cost_str}\n"
        f"{ownership}\n"
        f"{'━' * 22}\n"
        f"⚔️ **Attacks:**\n{atk_lines}\n"
        f"{'━' * 22}\n"
        f"Page {page + 1}/{total}"
    )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"chars_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total}", callback_data="chars_noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"chars_page_{page + 1}"))

    button_label = "⚡ Equip " if owned else "🛒 Buy "
    select_btn = [InlineKeyboardButton(f"{button_label}{char['name']}", callback_data=f"select_char_{char['id']}")]
    keyboard = InlineKeyboardMarkup([nav, select_btn])
    return text, keyboard, char


async def characters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        player = db.get_or_create_player(user.id, user.username, user.first_name)

    characters = db.get_all_characters()
    if context.args and context.args[0].lower() in ("owned", "inventory", "mine"):
        characters = [c for c in characters if db.player_owns_character(user.id, c['id'])]
    if not characters:
        await update.effective_message.reply_text(
            "❌ You do not own any characters yet. Use /characters to browse the roster."
        )
        return

    text, keyboard, char = _build_char_page(characters, 0, player)

    try:
        img = image_gen.generate_character_shop_display(char, player or {})
        await update.effective_message.reply_photo(
            photo=img, caption=text, reply_markup=keyboard, parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Character image error: {e}")
        await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')


async def characters_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split('_')[2])
    user = query.from_user
    player = db.get_player(user.id)
    characters = db.get_all_characters()

    if page < 0 or page >= len(characters):
        return

    text, keyboard, char = _build_char_page(characters, page, player)

    try:
        img = image_gen.generate_character_shop_display(char, player or {})
        await query.edit_message_media(
            media=InputMediaPhoto(media=img, caption=text, parse_mode='Markdown'),
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Character page image error: {e}")
        try:
            await query.edit_message_caption(caption=text, reply_markup=keyboard, parse_mode='Markdown')
        except Exception:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# PVE BATTLE COMMANDS
# ═══════════════════════════════════════════════════════════════
# `/battle` and `/flee` live in commands/battle.py. `/a` remains here for now
# because it also resolves legacy techniques, expansions, and PvP state.

# ═══════════════════════════════════════════════════════════════
# /a  ATTACK COMMAND  (PvE + Bot + PvP)
# ═══════════════════════════════════════════════════════════════

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return

    # No arguments — show move list
    if not context.args:
        char = db.get_character(player['character_id']) if player['character_id'] else None
        char_attacks = char.get('attacks', []) if char else []
        techs = player.get('techniques') or []

        MAX_MOVES = 7
        slots_used = len(char_attacks) + len(techs)

        text = "🔮 **Your Moves**\n" + "━" * 24 + "\n\n"
        text += "⚔️ **0. Basic Attack** — Free strike, no CE\n\n"

        if char_attacks:
            text += f"🎭 **{char['name']} Attacks:**\n"
            for atk in char_attacks:
                text += (f"  **{atk['num']}. {atk['name']}**"
                         f"  |  CE: {atk['ce_cost']}  |  DMG: {atk['dmg_mult']}x\n"
                         f"     _{atk['description']}_\n\n")

        if techs:
            text += "🌀 **Learned Techniques:**\n"
            start_num = len(char_attacks) + 1
            for idx, t_name in enumerate(techs):
                move_num = start_num + idx
                tech = db.get_technique(t_name)
                if tech:
                    text += (f"  **{move_num}. {tech['name']}**"
                             f"  |  CE: {tech['energy_cost']}  |  DMG: {tech['damage_multiplier']}x\n"
                             f"     _{tech['description']}_\n\n")
                else:
                    text += f"  **{move_num}. {t_name}**\n\n"
        else:
            text += "_No techniques learned yet. Buy from /shop then use /learn_\n\n"

        remaining = MAX_MOVES - slots_used
        if remaining > 0:
            text += f"📥 **Slots:** {slots_used}/{MAX_MOVES} — {remaining} slot(s) open\n"
        else:
            text += f"🔒 **Move slots full** ({MAX_MOVES}/{MAX_MOVES})\n"

        text += f"\n⚡ CE: {player['cursed_energy']}/{player['max_cursed_energy']} [{_energy_bar(player['cursed_energy'], player['max_cursed_energy'])}]"
        text += "\n\n💡 Use `/a <number>` in battle to attack"
        await update.effective_message.reply_text(text, parse_mode='Markdown')
        return

    move_input = ' '.join(context.args).strip()
    chat = update.effective_chat

    # Determine battle context
    bot_battle = context.user_data.get('bot_battle')
    pve = context.user_data.get('pve_battle')
    pvp = db.get_active_pvp_battle(user.id, chat.id) if chat else None

    if pvp:
        await _handle_pvp_move(update, context, player, pvp, move_input)
    elif bot_battle:
        await _handle_bot_battle_move(update, context, player, bot_battle, move_input)
    elif pve:
        await _handle_pve_move(update, context, player, pve, move_input)
    else:
        await update.effective_message.reply_text(
            "❌ You're not in a battle!\nUse /battle for PvE or /ch @user / /ch bot for PvP."
        )


# ── PvE move handler ──────────────────────────────────────────

async def _handle_pve_move(update, context, player, battle, move_input: str):
    user = update.effective_user
    spirit = battle['spirit']

    move, err = _resolve_move(player, move_input)
    if err:
        await update.effective_message.reply_text(err, parse_mode='Markdown')
        return

    ce_cost = move.get('ce_cost', move.get('energy_cost', 0))
    if ce_cost > 0 and player['cursed_energy'] < ce_cost:
        await update.effective_message.reply_text(
            f"❌ Not enough cursed energy!\n"
            f"⚡ Need: {ce_cost} | Have: {player['cursed_energy']}"
        )
        return

    dmg_mult = move.get('damage_multiplier', move.get('dmg_mult', 1.0))
    damage = game.calculate_damage(int(player['attack'] * dmg_mult), spirit['defense'],
                                   target_max_hp=spirit['hp'])
    damage, expansion_text = expansion.combat_effect(user.id, move['name'], damage)
    action_text = f"🌀 **{move['name']}** — {damage} damage!"
    if expansion_text:
        action_text += f"\n✨ {expansion_text}"

    if ce_cost > 0:
        new_ce = db.update_cursed_energy(user.id, -ce_cost)
        player['cursed_energy'] = new_ce

    battle['spirit_hp'] -= damage

    # Send battle GIF
    try:
        player_char = db.get_equipped_character(user.id)
        gif_bytes = image_gen.generate_battle_gif(
            attacker_name=player.get('username') or player.get('name', 'You'),
            attacker_char=player_char,
            defender_name=spirit['name'],
            defender_char=None,
            move_name=move['name'],
            attacker_hp=battle['player_hp'],
            attacker_max_hp=player['max_hp'],
            defender_hp=max(0, battle['spirit_hp']),
            defender_max_hp=spirit['hp'],
        )
        if gif_bytes:
            import io
            await update.effective_message.reply_animation(
                animation=io.BytesIO(gif_bytes),
                filename="battle.gif",
            )
    except Exception:
        pass

    # Spirit defeated
    if battle['spirit_hp'] <= 0:
        db.add_yen(user.id, spirit['reward'])
        db.add_xp(user.id, spirit['xp'])
        db.update_mission_progress(user.id, 'battle_wins')
        db.update_mission_progress(user.id, 'yen_earned', spirit['reward'])
        material, material_amount = expansion.award_battle_loot(user.id, spirit['grade'])
        awakening = expansion.awaken_from_trigger(
            user.id, "boss_defeat" if "Special" in spirit["grade"] else "quest"
        )
        if ce_cost > 0:
            db.update_mission_progress(user.id, 'technique_uses')
        context.user_data.pop('pve_battle', None)

        updated = db.get_player(user.id)
        level_up = f"\n🆙 **LEVEL UP! Now Level {updated['level']}!**" if updated['level'] > player['level'] else ""
        awakening_text = f"✨ {awakening}\n" if awakening else ""

        await update.effective_message.reply_text(
            f"🎉 **VICTORY!**\n\n"
            f"{action_text}\n\n"
            f"👹 *{spirit['name']}* has been exorcised!\n\n"
            f"💰 **Reward:** ¥{format_yen(spirit['reward'])}\n"
            f"⭐ **XP:** +{spirit['xp']}{level_up}\n"
            f"🧱 **Material:** {material} ×{material_amount}\n"
            f"{awakening_text}\n"
            f"⚡ CE: {updated['cursed_energy']}/{updated['max_cursed_energy']} "
            f"[{_energy_bar(updated['cursed_energy'], updated['max_cursed_energy'])}]\n"
            f"🔥 *Domain Expansion... of your wallet!*",
            parse_mode='Markdown'
        )
        return

    # Spirit counterattacks
    spirit_damage = game.calculate_damage(spirit['attack'], player['defense'],
                                          target_max_hp=player['max_hp'])
    battle['player_hp'] -= spirit_damage
    battle['turn'] += 1

    if battle['player_hp'] <= 0:
        db.update_hp(user.id, 0)
        awakening = expansion.awaken_from_trigger(user.id, "near_death")
        awakening_text = f"✨ {awakening}\n" if awakening else ""
        context.user_data.pop('pve_battle', None)
        await update.effective_message.reply_text(
            f"💀 **DEFEAT...**\n\n"
            f"{action_text}\n"
            f"👹 *{spirit['name']}* struck back for {spirit_damage} damage — you fell!\n\n"
            f"{awakening_text}"
            f"🔄 Use /heal to recover.",
            parse_mode='Markdown'
        )
        return

    refreshed = db.get_player(user.id)
    await update.effective_message.reply_text(
        f"⚔️ **TURN {battle['turn']}**\n\n"
        f"{action_text}\n"
        f"👹 *{spirit['name']}* counterattacks for {spirit_damage} damage!\n\n"
        f"❤️ Your HP: {battle['player_hp']}/{player['max_hp']} [{_energy_bar(battle['player_hp'], player['max_hp'])}]\n"
        f"⚡ CE: {refreshed['cursed_energy']}/{player['max_cursed_energy']} [{_energy_bar(refreshed['cursed_energy'], player['max_cursed_energy'])}]\n"
        f"👹 Spirit HP: {battle['spirit_hp']}/{spirit['hp']} [{_energy_bar(battle['spirit_hp'], spirit['hp'])}]\n\n"
        f"Use `/a <move or number>` to continue | `/a` to see moves | `/flee` to run",
        parse_mode='Markdown'
    )


# ── Bot battle move handler ───────────────────────────────────

async def _handle_bot_battle_move(update, context, player, battle, move_input: str):
    user = update.effective_user
    bot_player = battle['bot_player']

    move, err = _resolve_move(player, move_input)
    if err:
        await update.effective_message.reply_text(err, parse_mode='Markdown')
        return

    ce_cost = move.get('ce_cost', move.get('energy_cost', 0))
    if ce_cost > 0 and player['cursed_energy'] < ce_cost:
        await update.effective_message.reply_text(
            f"❌ Not enough cursed energy! Need: {ce_cost} | Have: {player['cursed_energy']}"
        )
        return

    dmg_mult = move.get('damage_multiplier', move.get('dmg_mult', 1.0))
    damage = game.calculate_damage(int(player['attack'] * dmg_mult), bot_player['defense'],
                                   target_max_hp=bot_player['hp'])
    damage, expansion_text = expansion.combat_effect(user.id, move['name'], damage)
    action_text = f"🌀 **{move['name']}** — {damage} damage!"
    if expansion_text:
        action_text += f"\n✨ {expansion_text}"

    if ce_cost > 0:
        new_ce = db.update_cursed_energy(user.id, -ce_cost)
        player['cursed_energy'] = new_ce

    battle['bot_hp'] -= damage

    # Send battle GIF
    try:
        player_char = db.get_equipped_character(user.id)
        bot_char = db.get_equipped_character(bot_player.get('user_id', 0))
        gif_bytes = image_gen.generate_battle_gif(
            attacker_name=player.get('username') or player.get('name', 'You'),
            attacker_char=player_char,
            defender_name=bot_player.get('username') or bot_player.get('name', 'Bot'),
            defender_char=bot_char,
            move_name=move['name'],
            attacker_hp=battle['player_hp'],
            attacker_max_hp=player['max_hp'],
            defender_hp=max(0, battle['bot_hp']),
            defender_max_hp=bot_player['hp'],
        )
        if gif_bytes:
            import io
            await update.effective_message.reply_animation(
                animation=io.BytesIO(gif_bytes),
                filename="battle.gif",
            )
    except Exception:
        pass

    if battle['bot_hp'] <= 0:
        reward = max(2000, int(4000 * (player['level'] / 10)))
        xp_gain = int(reward * 0.5)
        db.add_yen(user.id, reward)
        db.add_xp(user.id, xp_gain)
        db.add_win(user.id)
        db.update_mission_progress(user.id, 'pvp_wins')
        context.user_data.pop('bot_battle', None)
        updated = db.get_player(user.id)
        level_up = f"\n🆙 **LEVEL UP! Now Level {updated['level']}!**" if updated['level'] > player['level'] else ""
        await update.effective_message.reply_text(
            f"🎉 **VICTORY AGAINST THE BOT!**\n\n"
            f"{action_text}\n"
            f"🤖 Bot defeated!\n\n"
            f"💰 Reward: ¥{format_yen(reward)}\n"
            f"⭐ XP: +{xp_gain}{level_up}",
            parse_mode='Markdown'
        )
        return

    # Bot attacks back
    bot_actions = ['attack', 'attack', 'attack', 'defend']
    bot_choice = random.choice(bot_actions)
    if bot_choice == 'attack':
        bot_dmg = game.calculate_damage(bot_player['attack'], player['defense'],
                                        target_max_hp=player['max_hp'])
        bot_text = f"🤖 Bot used **Basic Attack** for {bot_dmg} damage!"
    else:
        bot_dmg = 0
        bot_text = "🤖 Bot defended — no damage!"

    battle['player_hp'] -= bot_dmg
    battle['turn'] += 1

    if battle['player_hp'] <= 0:
        db.update_hp(user.id, 0)
        db.add_loss(user.id)
        context.user_data.pop('bot_battle', None)
        await update.effective_message.reply_text(
            f"💀 **DEFEAT BY THE BOT!**\n\n"
            f"{action_text}\n{bot_text}\n\n"
            f"🔄 Use /heal and try again!",
            parse_mode='Markdown'
        )
        return

    refreshed = db.get_player(user.id)
    await update.effective_message.reply_text(
        f"⚔️ **BOT BATTLE — Turn {battle['turn']}**\n\n"
        f"{action_text}\n{bot_text}\n\n"
        f"❤️ Your HP: {battle['player_hp']}/{player['max_hp']} [{_energy_bar(battle['player_hp'], player['max_hp'])}]\n"
        f"⚡ CE: {refreshed['cursed_energy']}/{player['max_cursed_energy']} [{_energy_bar(refreshed['cursed_energy'], player['max_cursed_energy'])}]\n"
        f"🤖 Bot HP: {battle['bot_hp']}/{bot_player['hp']} [{_energy_bar(battle['bot_hp'], bot_player['hp'])}]\n\n"
        f"Use `/a <move or number>` to continue | `/a` to see moves | `/flee` to run",
        parse_mode='Markdown'
    )


# ── PvP move handler ──────────────────────────────────────────

async def _handle_pvp_move(update, context, player, battle, move_input: str):
    user = update.effective_user
    battle_id = battle['battle_id']

    if user.id not in (battle['player1_id'], battle['player2_id']):
        return

    is_p1 = (user.id == battle['player1_id'])
    existing = battle['p1_move'] if is_p1 else battle['p2_move']
    if existing:
        await update.effective_message.reply_text(
            f"⏳ You've already locked in **{existing}**. Waiting for your opponent...",
            parse_mode='Markdown'
        )
        return

    move, err = _resolve_move(player, move_input)
    if err:
        await update.effective_message.reply_text(err, parse_mode='Markdown')
        return

    valid_move = move['name']
    updated_battle = db.set_pvp_move(battle_id, user.id, valid_move)
    if not updated_battle:
        await update.effective_message.reply_text("❌ Battle error. Try again.")
        return

    p1 = db.get_player(updated_battle['player1_id'])
    p2 = db.get_player(updated_battle['player2_id'])
    p1_tag = f"@{p1['username']}" if p1.get('username') else p1['display_name']
    p2_tag = f"@{p2['username']}" if p2.get('username') else p2['display_name']

    p1_locked = updated_battle['p1_move'] is not None
    p2_locked = updated_battle['p2_move'] is not None

    if not (p1_locked and p2_locked):
        waiting_tag = p2_tag if is_p1 else p1_tag
        await update.effective_message.reply_text(
            f"✅ **Move locked!** *{valid_move}*\n\n"
            f"⏳ Waiting for {waiting_tag} to use `/a <move or number>`...",
            parse_mode='Markdown'
        )
        return

    await _resolve_pvp_round(update, context, updated_battle, p1, p2, p1_tag, p2_tag)


async def _resolve_pvp_round(update, context, battle, p1, p2, p1_tag, p2_tag):
    battle_id = battle['battle_id']
    rnd = battle['round']
    p1_move = battle['p1_move']
    p2_move = battle['p2_move']
    p1_hp = battle['player1_hp']
    p2_hp = battle['player2_hp']
    p1_ce = battle['player1_ce']
    p2_ce = battle['player2_ce']

    def _calc(attacker, defender, move_name, ce):
        defender_max_hp = battle['player2_max_hp'] if attacker is p1 else battle['player1_max_hp']
        move, _ = _resolve_move(attacker, move_name)
        if not move:
            dmg = game.calculate_damage(attacker['attack'], defender['defense'],
                                        target_max_hp=defender_max_hp)
            return dmg, 0, "⚔️ Basic Attack"
        ce_cost = move.get('ce_cost', move.get('energy_cost', 0))
        if ce_cost > ce:
            dmg = game.calculate_damage(attacker['attack'], defender['defense'],
                                        target_max_hp=defender_max_hp)
            return dmg, 0, "⚔️ Basic Attack *(no CE — fell back)*"
        dmg_mult = move.get('damage_multiplier', move.get('dmg_mult', 1.0))
        dmg = game.calculate_damage(int(attacker['attack'] * dmg_mult), defender['defense'],
                                    target_max_hp=defender_max_hp)
        dmg, expansion_text = expansion.combat_effect(attacker['user_id'], move['name'], dmg)
        label = f"🌀 {move['name']}"
        if expansion_text:
            label += f" — {expansion_text}"
        return dmg, ce_cost, label

    p1_dmg, p1_ce_used, p1_label = _calc(p1, p2, p1_move, p1_ce)
    p2_dmg, p2_ce_used, p2_label = _calc(p2, p1, p2_move, p2_ce)

    p1_hp = max(0, p1_hp - p2_dmg)
    p2_hp = max(0, p2_hp - p1_dmg)
    p1_ce = max(0, p1_ce - p1_ce_used)
    p2_ce = max(0, p2_ce - p2_ce_used)

    result_text = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ **ROUND {rnd} RESULTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{p1_tag}** used {p1_label}\n"
        f"  → Dealt **{p1_dmg}** damage to {p2_tag}\n\n"
        f"**{p2_tag}** used {p2_label}\n"
        f"  → Dealt **{p2_dmg}** damage to {p1_tag}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"❤️ {p1_tag}: {p1_hp}/{battle['player1_max_hp']} [{_energy_bar(p1_hp, battle['player1_max_hp'])}]\n"
        f"❤️ {p2_tag}: {p2_hp}/{battle['player2_max_hp']} [{_energy_bar(p2_hp, battle['player2_max_hp'])}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.effective_message.reply_text(result_text, parse_mode='Markdown')

    p1_dead = p1_hp <= 0
    p2_dead = p2_hp <= 0

    if p1_dead or p2_dead:
        db.finish_pvp_battle(battle_id)

        if p1_dead and p2_dead:
            winner_tag = "— Draw —"
            winner_id = None
        elif p2_dead:
            winner_tag = p1_tag
            winner_id = battle['player1_id']
        else:
            winner_tag = p2_tag
            winner_id = battle['player2_id']

        loser_id = (battle['player2_id'] if winner_id == battle['player1_id']
                    else battle['player1_id'])

        xp_gain = max(50, int((p1['level'] + p2['level']) * 15))
        yen_gain = max(500, int((p1['level'] + p2['level']) * 50))

        if winner_id:
            db.add_yen(winner_id, yen_gain)
            db.add_xp(winner_id, xp_gain)
            db.add_win(winner_id)
            db.add_loss(loser_id)
            db.update_mission_progress(winner_id, 'pvp_wins')

            updated_winner = db.get_player(winner_id)
            level_up = (
                f"\n🆙 **{winner_tag} LEVELED UP! Now Level {updated_winner['level']}!**"
                if updated_winner['level'] > (p1['level'] if winner_id == battle['player1_id'] else p2['level'])
                else ""
            )
            final_text = (
                f"🏆 **BATTLE OVER!**\n\n"
                f"🎉 **Winner: {winner_tag}**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Yen earned: ¥{format_yen(yen_gain)}\n"
                f"⭐ XP earned: +{xp_gain}{level_up}\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
        else:
            final_text = (
                f"🤝 **DRAW!**\n\n"
                f"Both sorcerers fell at the same time!\n"
                f"No rewards — but respect earned."
            )

        await update.effective_message.reply_text(final_text, parse_mode='Markdown')
        return

    # Next round
    next_battle = db.advance_pvp_round(battle_id, p1_hp, p2_hp, p1_ce, p2_ce)
    next_rnd = next_battle['round'] if next_battle else rnd + 1
    p1_spd = p1.get('speed', 10)
    p2_spd = p2.get('speed', 10)
    first_tag = p1_tag if p1_spd >= p2_spd else p2_tag
    second_tag = p2_tag if p1_spd >= p2_spd else p1_tag

    await update.effective_message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌀 **ROUND {next_rnd}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ {first_tag}, lock in your attack!\n"
        f"⚡ {second_tag}, lock in your attack!\n\n"
        f"📋 Use `/a` to see your moves\n"
        f"⚔️ Use `/a <move or number>` to attack",
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
# /ch — CHALLENGE (PvP or Bot)
# ═══════════════════════════════════════════════════════════════

async def ch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Challenge another player: /ch @user  or  /ch bot  (works in groups)

    ROOT CAUSE FIX for Owner Challenge Bug:
    Two issues prevented the bot owner from challenging:

    1. Hard private-chat block:  `if chat.type == 'private': return` fired for
       *everyone* — including the owner — with no bypass.  The owner is now
       allowed to bypass this guard so they can test challenges from PM or
       arrange test fights without being locked to a group.

    2. Missing player record:  the owner may not have run /start before trying
       /ch.  The original code called db.get_player() (which returns None for
       new users) and then immediately bailed with "Both players must /start".
       The fix auto-creates the owner's player record via get_or_create_player
       so they are never blocked by this check.
    """
    user = update.effective_user
    chat = update.effective_chat
    owner = is_owner(user.id)

    if len(context.args) < 1:
        await update.effective_message.reply_text(
            "⚠️ Usage: `/ch @username` or `/ch bot`\n"
            "Note: PvP vs real players requires a group chat.",
            parse_mode='Markdown'
        )
        return

    target_arg = context.args[0].lower()

    if target_arg == 'bot':
        return await pvp_bot_command(update, context)

    # PvP requires groups — owner bypasses this restriction (for testing / admin use)
    if chat.type == 'private' and not owner:
        await update.effective_message.reply_text(
            "❌ PvP against real players only works in groups!\n"
            "Use `/ch bot` to fight the AI instead.",
            parse_mode='Markdown'
        )
        return

    # Resolve target — try text_mention entity first, then username lookup
    target = None
    message = update.effective_message
    if message and message.entities:
        for entity in message.entities:
            if entity.type == 'text_mention' and entity.user:
                target = db.get_player(entity.user.id)
                break

    if not target:
        target_username = context.args[0].replace('@', '')
        target = db.get_user_by_username(target_username)

    if not target:
        await update.effective_message.reply_text(
            "❌ User not found! Make sure they've used /start first."
        )
        return

    if target['user_id'] == user.id:
        await update.effective_message.reply_text("❌ You can't fight yourself, Gojo!")
        return

    # Auto-create player record for the owner if they haven't used /start yet
    if owner:
        challenger = db.get_or_create_player(user.id, user.username or '', user.first_name)
    else:
        challenger = db.get_player(user.id)

    opponent = db.get_player(target['user_id'])

    if not challenger or not opponent:
        await update.effective_message.reply_text("❌ Both players must /start the game first!")
        return

    challenger_char = db.get_character(challenger['character_id']) if challenger['character_id'] else None
    opponent_char = db.get_character(opponent['character_id']) if opponent['character_id'] else None

    # Owner without a character gets a helpful nudge rather than a hard block
    if not challenger_char and owner:
        await update.effective_message.reply_text(
            "⚠️ You haven't chosen a character yet!\n"
            "Use /characters to pick one first, then challenge again.",
            parse_mode='Markdown'
        )
        return

    if not challenger_char or not opponent_char:
        await update.effective_message.reply_text("❌ Both players must choose a character first!")
        return

    c_tag = f"@{user.username}" if user.username else user.first_name
    o_tag = f"@{target.get('username') or target['display_name']}"

    text = (
        f"⚔️ **PVP CHALLENGE!**\n\n"
        f"👤 {challenger['display_name']} ({challenger_char['name']})\n"
        f"  ❤️ {challenger['hp']} | ⚔️ {challenger['attack']} | 🛡️ {challenger['defense']}\n\n"
        f"⚔️ **VS** ⚔️\n\n"
        f"👤 {opponent['display_name']} ({opponent_char['name']})\n"
        f"  ❤️ {opponent['hp']} | ⚔️ {opponent['attack']} | 🛡️ {opponent['defense']}\n\n"
        f"{o_tag}, do you accept the challenge?"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"pvp_accept_{user.id}_{target['user_id']}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"pvp_decline_{user.id}"),
    ]])

    try:
        battle_image = image_gen.generate_pvp_battle_display(
            challenger, opponent, challenger_char, opponent_char, turn=1
        )
        await update.effective_message.reply_photo(
            photo=battle_image, caption=text, reply_markup=keyboard, parse_mode='Markdown'
        )
        try:
            challenge_gif = image_gen.generate_battle_gif(
                attacker_name=challenger.get('display_name') or 'Challenger',
                attacker_char=challenger_char,
                defender_name=opponent.get('display_name') or 'Opponent',
                defender_char=opponent_char,
                move_name='Cursed Energy Clash',
                attacker_hp=challenger['hp'],
                attacker_max_hp=challenger['max_hp'],
                defender_hp=opponent['hp'],
                defender_max_hp=opponent['max_hp'],
            )
            if challenge_gif:
                import io
                await update.effective_message.reply_animation(animation=io.BytesIO(challenge_gif), filename='pvp_challenge.gif')
        except Exception:
            logger.debug('Could not render challenge animation', exc_info=True)
    except Exception as e:
        logger.error(f"Battle image error: {e}")
        await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')


async def pvp_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fight the bot AI — works in private AND group chats."""
    user = update.effective_user
    player = db.get_player(user.id)

    if not player or not player['character_id']:
        await update.effective_message.reply_text("❌ Choose a character first! Use /characters")
        return

    if context.user_data.get('bot_battle'):
        await update.effective_message.reply_text("❌ You're already in a bot battle! Use /flee to escape.")
        return
    if context.user_data.get('pve_battle'):
        await update.effective_message.reply_text("❌ Finish your PvE battle first! Use /flee to escape.")
        return

    # Bot is NEVER stronger than the player
    bot_player = {
        'user_id': 0,
        'display_name': '🤖 Bot Opponent',
        'username': 'bot',
        'character_id': 1,
        'level': player['level'],
        'rank': player['rank'],
        'hp': player['max_hp'],
        'max_hp': player['max_hp'],
        'cursed_energy': player['max_cursed_energy'],
        'max_cursed_energy': player['max_cursed_energy'],
        'attack': player['attack'],          # same as player
        'defense': player['defense'],        # same as player
        'speed': max(1, player['speed'] - 1),  # slightly slower
        'wins': 50, 'losses': 10, 'win_rate': 83.3,
        'techniques': [],
    }

    bot_starts = random.choice([True, False])
    opening_text = ""
    opening_player_hp = player['hp']
    if bot_starts:
        opening_damage = game.calculate_damage(bot_player['attack'], player['defense'], target_max_hp=player['max_hp'])
        opening_player_hp = max(0, player['hp'] - opening_damage)
        db.update_hp(user.id, opening_player_hp)
        opening_text = (
            f"\n⚡ Initiative: **Bot**\n"
            f"🤖 The bot opens with a basic attack for **{opening_damage}** damage.\n"
        )
    else:
        opening_text = "\n⚡ Initiative: **You**\nYou have the opening move.\n"
    context.user_data['bot_battle'] = {
        'bot_player': bot_player,
        'bot_char': db.get_character(bot_player['character_id']),
        'turn': 1,
        'player_hp': opening_player_hp,
        'bot_hp': bot_player['hp'],
        'initiative': 'bot' if bot_starts else 'player',
    }
    player_char = db.get_character(player['character_id'])
    bot_char = context.user_data['bot_battle']['bot_char']
    char_attacks = player_char.get('attacks', []) if player_char else []
    atk_hint = "\n".join(f"  /a {a['num']} — {a['name']}" for a in char_attacks)

    text = (
        f"⚔️ **BOT BATTLE!**\n\n"
        f"👤 {player['display_name']} ({player_char['name'] if player_char else 'Unknown'})\n"
        f"  ❤️ {opening_player_hp}/{player['max_hp']} | ⚔️ {player['attack']}\n\n"
        f"🤖 Bot Opponent ({bot_char['name'] if bot_char else 'Unknown'})\n"
        f"  ❤️ {bot_player['hp']}/{bot_player['max_hp']} | ⚔️ {bot_player['attack']}\n\n"
        f"{'━' * 22}\n"
        f"{opening_text}\n"
        f"**Your Attacks:**\n"
        f"  /a attack — Basic strike (free)\n"
        f"{atk_hint}\n\n"
        f"📋 /a — See all moves | 💨 /flee — Escape"
    )

    try:
        img = image_gen.generate_pvp_battle_display(player, bot_player, player_char, bot_char, turn=1)
        await update.effective_message.reply_photo(photo=img, caption=text, parse_mode='Markdown')
        try:
            intro_gif = image_gen.generate_battle_gif(
                attacker_name=player.get('display_name') or 'You',
                attacker_char=player_char,
                defender_name=bot_player.get('display_name') or 'Bot Opponent',
                defender_char=bot_char,
                move_name='Cursed Energy Clash',
                attacker_hp=context.user_data['bot_battle']['player_hp'],
                attacker_max_hp=player['max_hp'],
                defender_hp=bot_player['hp'],
                defender_max_hp=bot_player['max_hp'],
            )
            if intro_gif:
                import io
                await update.effective_message.reply_animation(animation=io.BytesIO(intro_gif), filename='bot_battle.gif')
        except Exception:
            logger.debug('Could not render bot battle animation', exc_info=True)
    except Exception as e:
        logger.error(f"Bot battle image error: {e}")
        await update.effective_message.reply_text(text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# SHOP / ECONOMY
# ═══════════════════════════════════════════════════════════════

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy a shop item by its stable one-based number or exact name."""
    user = update.effective_user
    items = db.get_shop_items()
    if not context.args:
        await update.effective_message.reply_text("Usage: /buy <item number or exact item name>")
        return
    raw = " ".join(context.args).strip()
    item = resolve_numbered_item(items, raw)
    if not item:
        await update.effective_message.reply_text("❌ Shop item not found. Use /shop to see numbered items.")
        return
    result = db.purchase_shop_item(user.id, item["id"])
    if not result.get("ok"):
        reason = result.get("reason")
        if reason == "funds":
            await update.effective_message.reply_text(f"❌ Not enough yen. Need ¥{format_yen(result['price'])}; you have ¥{format_yen(result.get('balance', 0))}.")
        elif reason == "removed":
            await update.effective_message.reply_text("❌ That item is no longer available.")
        else:
            await update.effective_message.reply_text("❌ Purchase failed. Try again.")
        return
    await update.effective_message.reply_text(
        f"✅ Purchased **{item['name']}** for ¥{format_yen(item['price'])}.\n"
        f"💰 Remaining balance: ¥{format_yen(result['remaining'])}",
        parse_mode='Markdown'
    )

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show shop with pagination."""
    page = int(context.args[0]) - 1 if context.args and context.args[0].isdigit() else 0
    items = db.get_shop_items()

    type_icons = {
        'weapon': '⚔️', 'technique': '🔮', 'consumable': '🧪',
        'elixir': '🌟', 'upgrade': '⬆️', 'special': '🌀'
    }

    lines = []
    for item_number, item in enumerate(items, start=1):
        icon = type_icons.get(item['type'], '📦')
        lines.append(
            f"#{item_number} {icon} **{item['name']}**\n"
            f"   📖 {item['description']}\n"
            f"   💰 ¥{format_yen(item['price'])} | Type: {item['type']}\n"
            f"   💡 _{item.get('use_description', 'Check /help for usage')}_"
        )

    per_page = 4
    total_pages = max(1, (len(lines) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = lines[page * per_page:(page + 1) * per_page]
    page_items = items[page * per_page:(page + 1) * per_page]

    text = f"🏪 **Jujutsu Shop** (Page {page+1}/{total_pages})\n{'━'*24}\n\n"
    text += "\n\n".join(chunk)
    text += f"\n\n📄 Page {page+1}/{total_pages} — Use /shop [page number]"

    buy_btns = [[InlineKeyboardButton(
        f"Buy #{items.index(i) + 1} {i['name'][:16]} - ¥{format_yen(i['price'])}",
        callback_data=f"buy_{i['id']}"
    )] for i in page_items]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"shop_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"shop_page_{page + 1}"))

    keyboard = buy_btns + ([nav] if nav else [])
    await update.effective_message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reward = db.claim_daily(user.id)
    if reward:
        await update.effective_message.reply_text(
            f"🎁 **Daily Reward Claimed!**\n\n"
            f"💰 ¥{format_yen(reward['yen'])} Yen\n"
            f"⭐ {reward['xp']} XP\n\n"
            f"🔥 Come back tomorrow for more!",
            parse_mode='Markdown'
        )
    else:
        await update.effective_message.reply_text(
            "⏰ **Already claimed!**\n\nCome back in 24 hours...",
            parse_mode='Markdown'
        )


async def heal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    if player['hp'] >= player['max_hp']:
        await update.effective_message.reply_text(
            f"❤️ You're already at full HP! ({player['hp']}/{player['max_hp']})"
        )
        return
    cost = db.heal_player(user.id)
    if cost is not None:
        refreshed = db.get_player(user.id)
        await update.effective_message.reply_text(
            f"❤️ **Healed!**\n\n"
            f"💰 Cost: ¥{format_yen(cost)}\n"
            f"❤️ HP: {refreshed['hp']}/{refreshed['max_hp']} [{_energy_bar(refreshed['hp'], refreshed['max_hp'])}]",
            parse_mode='Markdown'
        )
    else:
        await update.effective_message.reply_text("❌ Not enough yen to heal! (Cost: ¥500)")


async def energy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    if player['cursed_energy'] >= player['max_cursed_energy']:
        await update.effective_message.reply_text(
            f"⚡ Cursed energy is already full!\n"
            f"⚡ {player['cursed_energy']}/{player['max_cursed_energy']} "
            f"[{_energy_bar(player['cursed_energy'], player['max_cursed_energy'])}]"
        )
        return
    if player['yen'] < 300:
        await update.effective_message.reply_text(f"❌ Need ¥300. You have ¥{format_yen(player['yen'])}")
        return

    before = player['cursed_energy']
    db.deduct_yen(user.id, 300)
    actual_gain = min(50, player['max_cursed_energy'] - before)
    new_ce = db.update_cursed_energy(user.id, 50)
    refreshed = db.get_player(user.id)

    await update.effective_message.reply_text(
        f"⚡ **Cursed Energy Restored!**\n\n"
        f"✅ +{actual_gain} CE\n"
        f"⚡ Energy: {refreshed['cursed_energy']}/{refreshed['max_cursed_energy']} "
        f"[{_energy_bar(refreshed['cursed_energy'], refreshed['max_cursed_energy'])}]\n"
        f"💰 Cost: ¥300 | 💴 Remaining: ¥{format_yen(refreshed['yen'])}",
        parse_mode='Markdown'
    )


async def giveyen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sender = db.get_player(user.id)
    if not sender:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "⚠️ **Usage:** `/giveyen @username <amount>`", parse_mode='Markdown'
        )
        return

    target = None
    message = update.effective_message
    if message and message.entities:
        for entity in message.entities:
            if entity.type == 'text_mention' and entity.user:
                target = db.get_player(entity.user.id)
                break
    if not target:
        target = db.get_user_by_username(context.args[0].replace('@', ''))
    if not target:
        await update.effective_message.reply_text("❌ User not found!")
        return
    if target['user_id'] == user.id:
        await update.effective_message.reply_text("❌ Can't send yen to yourself!")
        return
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("❌ Amount must be a number!")
        return
    if amount <= 0:
        await update.effective_message.reply_text("❌ Amount must be positive!")
        return
    if sender['yen'] < amount:
        await update.effective_message.reply_text(
            f"❌ Not enough yen! You have: ¥{format_yen(sender['yen'])}"
        )
        return

    db.deduct_yen(user.id, amount)
    new_bal = db.add_yen(target['user_id'], amount)
    await update.effective_message.reply_text(
        f"💸 **Yen Transferred!**\n\n"
        f"👤 From: {sender['display_name']}\n"
        f"👤 To: {target['display_name']}\n"
        f"💴 Amount: ¥{format_yen(amount)}\n\n"
        f"💰 Your balance: ¥{format_yen(sender['yen'] - amount)}\n"
        f"💰 Their balance: ¥{format_yen(new_bal)}",
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
# INVENTORY / BAG / TECHNIQUES
# ═══════════════════════════════════════════════════════════════

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show inventory — paginated."""
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return

    items = db.get_inventory(user.id)
    if not items:
        await update.effective_message.reply_text(
            "🎒 **Your Bag is Empty!**\n\nVisit /shop to buy items.",
            parse_mode='Markdown'
        )
        return

    type_icons = {'weapon': '⚔️', 'technique': '🔮', 'consumable': '🧪',
                  'elixir': '🌟', 'upgrade': '⬆️', 'special': '🌀'}
    lines = []
    for i, item in enumerate(items, 1):
        icon = type_icons.get(item['type'], '📦')
        lines.append(
            f"{i}. {icon} **{item['name']}**\n"
            f"   💰 ¥{format_yen(item['price'])} | {item['type']}\n"
            f"   💡 _{item.get('use_description', item['description'])}_"
        )

    page = int(context.args[0]) - 1 if context.args and context.args[0].isdigit() else 0
    per_page = 5
    total_pages = max(1, (len(lines) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = lines[page * per_page:(page + 1) * per_page]

    header = f"🎒 **Your Bag** ({len(items)} items) — Page {page+1}/{total_pages}\n{'━'*28}\n\n"
    text = header + "\n\n".join(chunk)
    text += f"\n\n{'━'*28}\n💡 Use `/use [item name]` to use an item\n📄 Page {page+1}/{total_pages}"

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"inv_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"inv_page_{page + 1}"))

    keyboard = InlineKeyboardMarkup([nav]) if nav else None
    await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')


async def equip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "⚠️ **Usage:** `/equip [item name]`", parse_mode='Markdown'
        )
        return

    item_name = ' '.join(context.args)
    owned_characters = db.get_owned_characters(user.id)
    owned_character = next(
        (char for char in owned_characters if char['name'].lower() == item_name.lower()),
        None
    )
    if owned_character:
        if db.equip_owned_character(user.id, owned_character['id']):
            await update.effective_message.reply_text(
                f"⚡ **{owned_character['name']} equipped!**\n\n"
                "Your profile, battle stats, skills, and character image now use this character.",
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text("❌ Could not equip that owned character.")
        return

    items = db.get_inventory(user.id)
    resolved_item = resolve_numbered_item(items, item_name)
    item = resolved_item
    if not item:
        await update.effective_message.reply_text(f"❌ Item '{item_name}' not found in inventory!")
        return
    if item['type'] not in ('weapon',):
        await update.effective_message.reply_text(
            f"❌ *{item['name']}* cannot be equipped this way.\n"
            f"💡 {item.get('use_description', 'Use /use for consumables and special items.')}",
            parse_mode='Markdown'
        )
        return

    effect = {}
    try:
        effect = json.loads(item['effect']) if item['effect'] else {}
    except Exception:
        pass

    stat_changes = []
    if 'attack' in effect:
        db.update_player_stat(user.id, 'attack', player['attack'] + effect['attack'])
        stat_changes.append(f"+{effect['attack']} ATK")
    if 'defense' in effect:
        db.update_player_stat(user.id, 'defense', player['defense'] + effect.get('defense', 0))
        stat_changes.append(f"+{effect['defense']} DEF")

    db.remove_from_inventory(user.id, item['id'])
    await update.effective_message.reply_text(
        f"✅ **Item Equipped!**\n\n"
        f"⚔️ *{item['name']}* equipped!\n"
        f"📈 Gained: {', '.join(stat_changes) if stat_changes else 'No stat changes'}",
        parse_mode='Markdown'
    )


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "⚠️ **Usage:** `/learn [skill name]`\n\n"
            "Buy technique scrolls from /shop first, then learn them here.",
            parse_mode='Markdown'
        )
        return

    skill_name = ' '.join(context.args)
    items = db.get_inventory(user.id)

    # Match by item name first, then by technique name stored inside effect JSON
    skill_item = next(
        (i for i in items if i['type'] == 'technique' and i['name'].lower() == skill_name.lower()),
        None
    )
    if not skill_item:
        for i in items:
            if i['type'] == 'technique' and i.get('effect'):
                try:
                    eff = json.loads(i['effect'])
                    if eff.get('technique', '').lower() == skill_name.lower():
                        skill_item = i
                        break
                except Exception:
                    pass

    if not skill_item:
        # Build a helpful hint showing what they actually have in their bag
        tech_items = [i for i in items if i['type'] == 'technique']
        if tech_items:
            hints = []
            for i in tech_items:
                try:
                    eff = json.loads(i['effect']) if i.get('effect') else {}
                    tname = eff.get('technique', i['name'])
                except Exception:
                    tname = i['name']
                hints.append(f"• `/learn {tname}` _(from {i['name']})_")
            hint_str = "\n".join(hints)
            await update.effective_message.reply_text(
                f"❌ No technique *'{skill_name}'* found in your bag.\n\n"
                f"📚 **Technique items you can learn:**\n{hint_str}",
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                f"❌ No technique scrolls in your bag!\n"
                f"Buy them from /shop first.",
                parse_mode='Markdown'
            )
        return

    # Extract actual technique name from effect
    try:
        effect = json.loads(skill_item['effect']) if skill_item['effect'] else {}
        tech_name = effect.get('technique', skill_name)
    except Exception:
        tech_name = skill_name

    if tech_name in player['techniques']:
        await update.effective_message.reply_text(
            f"❌ Already learned **{tech_name}**! It's already in your battle arsenal.",
            parse_mode='Markdown'
        )
        return

    # Enforce 7-move cap (character attacks + learned techniques)
    MAX_MOVES = 7
    char = db.get_character(player['character_id']) if player.get('character_id') else None
    char_attacks = char.get('attacks', []) if char else []
    current_techs = player.get('techniques') or []
    total_moves = len(char_attacks) + len(current_techs)
    if total_moves >= MAX_MOVES:
        await update.effective_message.reply_text(
            f"🔒 **Move slots full!** ({MAX_MOVES}/{MAX_MOVES})\n\n"
            f"You already have {len(char_attacks)} character attacks + {len(current_techs)} learned techniques.\n"
            f"Max total moves is **{MAX_MOVES}**.\n\n"
            f"Use `/a` to see your current moves.",
            parse_mode='Markdown'
        )
        return

    db.learn_technique(user.id, tech_name)
    db.remove_from_inventory(user.id, skill_item['id'])

    # Calculate the slot number this technique was assigned
    new_slot = len(char_attacks) + len(current_techs) + 1

    tech = db.get_technique(tech_name)
    if tech:
        await update.effective_message.reply_text(
            f"✅ **Technique Learned!**\n\n"
            f"🔮 **{new_slot}. {tech['name']}**\n"
            f"📖 {tech['description']}\n"
            f"⚡ CE Cost: {tech['energy_cost']} | 💥 Damage: {tech['damage_multiplier']}x\n\n"
            f"⚔️ **Assigned to slot {new_slot}** — use `/a {new_slot}` or `/a {tech['name']}` in battle!\n"
            f"📋 See all moves with `/a`",
            parse_mode='Markdown'
        )
    else:
        await update.effective_message.reply_text(
            f"✅ **Technique Learned!**\n\n"
            f"🔮 **{new_slot}. {tech_name}** added to your arsenal!\n"
            f"⚔️ Use `/a {new_slot}` or `/a {tech_name}` in battle.\n"
            f"📋 See all moves with `/a`",
            parse_mode='Markdown'
        )


async def techniques_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return

    lines = []
    if player['techniques']:
        for i, tech_name in enumerate(player['techniques'], 1):
            t = db.get_technique(tech_name)
            if t:
                lines.append(f"{i}. **{t['name']}**\n   CE:{t['energy_cost']} | {t['damage_multiplier']}x dmg\n   _{t['description']}_")
            else:
                lines.append(f"{i}. **{tech_name}**")
    else:
        await update.effective_message.reply_text(
            "🔮 **No Techniques Learned**\n\n"
            "Buy technique scrolls from /shop then use /learn to unlock them!\n"
            "Your character's numbered attacks (/a 1, /a 2, /a 3) are always available.",
            parse_mode='Markdown'
        )
        return

    page = 0
    per_page = 5
    total_pages = max(1, (len(lines) + per_page - 1) // per_page)
    chunk = lines[page * per_page:(page + 1) * per_page]
    text = f"🔮 **Your Techniques** ({len(player['techniques'])} learned)\n{'━'*24}\n\n"
    text += "\n\n".join(chunk)
    text += f"\n\n{'━'*24}\nUse `/a [name]` in battle to use these."

    await update.effective_message.reply_text(text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# /use ITEM COMMAND
# ═══════════════════════════════════════════════════════════════

async def use_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use an item from inventory."""
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "⚠️ **Usage:** `/use [item name]`\n\n"
            "Example: `/use Health Potion`\n"
            "Or: `/use Domain Expansion Blueprint My Void Domain`",
            parse_mode='Markdown'
        )
        return

    full_args = ' '.join(context.args)

    # Handle "equip domain" — route to the domain equip handler
    if full_args.lower() in ("equip domain", "equipdomain"):
        return await use_equip_domain_command(update, context)

    # Handle Domain Expansion Blueprint with domain name
    domain_prefix = "domain expansion blueprint"
    if full_args.lower().startswith(domain_prefix):
        remainder = full_args[len(domain_prefix):].strip()
        if not remainder:
            await update.effective_message.reply_text(
                "⚠️ Include a domain name!\n"
                "**Usage:** `/use Domain Expansion Blueprint [your domain name]`\n"
                "Example: `/use Domain Expansion Blueprint Void of Broken Dreams`",
                parse_mode='Markdown'
            )
            return
        return await _use_domain_blueprint(update, player, user.id, remainder)

    # Find item by name (look for longest match)
    item_name = full_args
    items = db.get_inventory(user.id)
    item = next((i for i in items if i['name'].lower() == item_name.lower()), None)

    # Partial match fallback
    if not item:
        item = next((i for i in items if i['name'].lower().startswith(item_name.lower())), None)

    if not item:
        await update.effective_message.reply_text(
            f"❌ Item '{item_name}' not found in your bag!\n"
            f"Use /bag or /inventory to see your items.",
            parse_mode='Markdown'
        )
        return

    await _apply_item_use(update, player, user.id, item)


async def _use_domain_blueprint(update, player, user_id, domain_name):
    items = db.get_inventory(user_id)
    blueprint = next((i for i in items if i['name'].lower() == 'domain expansion blueprint'), None)
    if not blueprint:
        await update.effective_message.reply_text(
            "❌ You don't have a Domain Expansion Blueprint in your bag!\n"
            "Buy one from /shop.",
            parse_mode='Markdown'
        )
        return

    # Check if domain already exists
    existing_domain = db.get_user_domain(user_id)
    if existing_domain:
        await update.effective_message.reply_text(
            f"❌ You already have a domain: **{existing_domain['domain_name']}**!\n"
            f"Only one domain per sorcerer.",
            parse_mode='Markdown'
        )
        return

    # Domain power = player attack * 1.3
    domain_power = int(player['attack'] * 1.3)
    domain_id = db.create_domain(user_id, domain_name, domain_power)
    db.remove_from_inventory(user_id, blueprint['id'])

    await update.effective_message.reply_text(
        f"🌀 **DOMAIN EXPANSION CREATED!**\n\n"
        f"✨ Domain Name: **{domain_name}**\n"
        f"💥 Power: **{domain_power}** (30% above your attack of {player['attack']})\n\n"
        f"{'━' * 22}\n"
        f"🔒 **To equip your domain for battle:**\n"
        f"Cost: ¥1,500,000\n"
        f"Use: `/use equip domain`\n\n"
        f"💡 An equipped domain will be automatically used in battle as a devastating attack!",
        parse_mode='Markdown'
    )


async def _apply_item_use(update, player, user_id, item):
    """Apply the effect of a used item."""
    effect = {}
    try:
        effect = json.loads(item['effect']) if item['effect'] else {}
    except Exception:
        pass

    item_type = item['type']
    name = item['name']

    # Consumables and elixirs
    if item_type in ('consumable', 'elixir'):
        results = []
        ce_gained = effect.get('ce', 0)
        hp_gained = effect.get('hp', 0)
        xp_gained = effect.get('xp', 0)
        ce_perm = effect.get('ce_permanent', 0)

        if hp_gained:
            new_hp = min(player['max_hp'], player['hp'] + hp_gained)
            actual = new_hp - player['hp']
            db.update_hp(user_id, new_hp)
            results.append(f"❤️ +{actual} HP")

        if ce_gained:
            actual_ce = db.update_cursed_energy(user_id, ce_gained)
            results.append(f"⚡ +{min(ce_gained, actual_ce)} CE")

        if xp_gained:
            db.add_xp(user_id, xp_gained)
            results.append(f"⭐ +{xp_gained} XP")

        if ce_perm:
            db.update_player_stat(user_id, 'max_cursed_energy', player['max_cursed_energy'] + ce_perm)
            results.append(f"⚡ +{ce_perm} Max CE (permanent)")

        db.remove_from_inventory(user_id, item['id'])
        refreshed = db.get_player(user_id)

        if 'ce' in effect and effect['ce'] > 0:
            ce_str = f"\n⚡ CE: {refreshed['cursed_energy']}/{refreshed['max_cursed_energy']} [{_energy_bar(refreshed['cursed_energy'], refreshed['max_cursed_energy'])}]"
        else:
            ce_str = ""

        if 'hp' in effect and effect['hp'] > 0:
            hp_str = f"\n❤️ HP: {refreshed['hp']}/{refreshed['max_hp']} [{_energy_bar(refreshed['hp'], refreshed['max_hp'])}]"
        else:
            hp_str = ""

        level_up = ""
        if xp_gained and refreshed['level'] > player['level']:
            level_up = f"\n🆙 **LEVEL UP! Now Level {refreshed['level']}!**"

        await update.effective_message.reply_text(
            f"✅ **Used {name}!**\n\n"
            f"{chr(10).join(results) if results else 'No effect'}"
            f"{hp_str}{ce_str}{level_up}",
            parse_mode='Markdown'
        )

    elif item_type == 'upgrade' and effect.get('grade_up'):
        ranks = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']
        try:
            idx = ranks.index(player['rank'])
        except ValueError:
            idx = 0
        if idx >= len(ranks) - 1:
            await update.effective_message.reply_text("❌ You're already at the maximum rank: Special Grade!")
            return
        new_rank = ranks[idx + 1]
        db.set_rank(user_id, new_rank)
        db.remove_from_inventory(user_id, item['id'])
        await update.effective_message.reply_text(
            f"🆙 **Grade Upgrade!**\n\n"
            f"🏅 {player['rank']} → **{new_rank}**\n\n"
            f"Your sorcerer rank has been elevated!",
            parse_mode='Markdown'
        )

    elif item_type == 'special' and effect.get('special') == 'domain_creation':
        await update.effective_message.reply_text(
            "⚠️ To create a domain, include its name:\n"
            f"`/use {name} [your domain name]`\n\n"
            "Example: `/use Domain Expansion Blueprint Boundless Void of Sorrow`",
            parse_mode='Markdown'
        )

    elif item_type == 'technique':
        await update.effective_message.reply_text(
            f"ℹ️ **{name}** is a technique scroll.\n"
            f"Use `/learn {name}` to permanently learn it for battle!",
            parse_mode='Markdown'
        )

    elif item_type == 'weapon':
        await update.effective_message.reply_text(
            f"ℹ️ **{name}** is a weapon.\n"
            f"Use `/equip {name}` to equip it and gain its stat bonuses!",
            parse_mode='Markdown'
        )

    else:
        await update.effective_message.reply_text(
            f"❌ Can't use **{name}** directly.\n"
            f"💡 {item.get('use_description', 'Check /help for guidance.')}",
            parse_mode='Markdown'
        )


async def use_equip_domain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equip a created domain — costs ¥1,500,000."""
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return

    domain = db.get_user_domain(user.id)
    if not domain:
        await update.effective_message.reply_text(
            "❌ You don't have a domain yet!\n"
            "Buy a **Domain Expansion Blueprint** from /shop and use it.",
            parse_mode='Markdown'
        )
        return
    if domain['equipped']:
        await update.effective_message.reply_text(
            f"✅ **{domain['domain_name']}** is already equipped!",
            parse_mode='Markdown'
        )
        return
    if player['yen'] < 1500000:
        await update.effective_message.reply_text(
            f"❌ Need ¥1,500,000 to equip your domain.\n"
            f"You have: ¥{format_yen(player['yen'])}",
            parse_mode='Markdown'
        )
        return

    success = db.equip_domain(user.id)
    if success:
        await update.effective_message.reply_text(
            f"🌀 **DOMAIN EXPANSION EQUIPPED!**\n\n"
            f"✨ **{domain['domain_name']}**\n"
            f"💥 Power: {domain['power']}\n\n"
            f"💰 ¥1,500,000 paid\n\n"
            f"Your domain is now ready for battle! It appears in `/a` and `/profile`.",
            parse_mode='Markdown'
        )
    else:
        await update.effective_message.reply_text("❌ Failed to equip domain. Check your yen balance.")


# ═══════════════════════════════════════════════════════════════
# STATS / RANK / LEADERBOARD / MISSIONS
# ═══════════════════════════════════════════════════════════════

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    char = db.get_character(player['character_id']) if player['character_id'] else None
    await update.effective_message.reply_text(
        f"⚔️ **Combat Stats — {player['display_name']}**\n{'━' * 24}\n"
        f"🎭 Character: {char['name'] if char else 'None'}\n"
        f"🏅 Rank: {player['rank']} | ⭐ Lv.{player['level']}/{MAX_LEVEL}\n{'━' * 24}\n"
        f"❤️ HP: {player['hp']}/{player['max_hp']} [{_energy_bar(player['hp'], player['max_hp'])}]\n"
        f"⚡ CE: {player['cursed_energy']}/{player['max_cursed_energy']} [{_energy_bar(player['cursed_energy'], player['max_cursed_energy'])}]\n"
        f"⚔️ Attack:  {player['attack']}\n"
        f"🛡️ Defense: {player['defense']}\n"
        f"💨 Speed:   {player['speed']}\n{'━' * 24}\n"
        f"🏆 Wins: {player['wins']}  💀 Losses: {player['losses']}  📊 WR: {player['win_rate']}%",
        parse_mode='Markdown'
    )


async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = db.get_player(user.id)
    if not player:
        await update.effective_message.reply_text("❌ Use /start first!")
        return
    rank_order = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']
    rank_emojis = {'Grade 4': '🔰', 'Grade 3': '⚔️', 'Grade 2': '💠', 'Grade 1': '👑', 'Special Grade': '✨'}
    requirements = {
        'Grade 3': {'level': 5, 'wins': 100, 'yen': 10000},
        'Grade 2': {'level': 15, 'wins': 300, 'yen': 3000000},
        'Grade 1': {'level': 30, 'wins': 600, 'yen': 800000000},
        'Special Grade': {'level': 50, 'wins': 1000, 'yen': 200000000000},
    }
    current = player['rank']
    emoji = rank_emojis.get(current, '❓')
    idx = rank_order.index(current) if current in rank_order else 0
    text = (f"{emoji} **Rank Status: {current}**\n{'━' * 22}\n"
            f"⭐ Level: {player['level']}/{MAX_LEVEL}\n"
            f"🏆 Wins: {player['wins']} | 💀 Losses: {player['losses']}\n"
            f"💴 Yen: ¥{format_yen(player['yen'])}\n{'━' * 22}\n")
    if idx >= len(rank_order) - 1:
        text += "\n✨ *Maximum rank achieved — Special Grade!*"
    else:
        next_rank = rank_order[idx + 1]
        req = requirements[next_rank]
        ne = rank_emojis[next_rank]
        lv_ok = "✅" if player['level'] >= req['level'] else f"❌ (need {req['level']})"
        win_ok = "✅" if player['wins'] >= req['wins'] else f"❌ (need {req['wins']})"
        yen_ok = "✅" if player['yen'] >= req['yen'] else f"❌ (need ¥{format_yen(req['yen'])})"
        text += (f"\n**Next rank:** {ne} {next_rank}\n{'━' * 22}\n"
                 f"⭐ Level {req['level']}: {lv_ok}\n"
                 f"🏆 {req['wins']} Wins: {win_ok}\n"
                 f"💴 ¥{format_yen(req['yen'])}: {yen_ok}")
    await update.effective_message.reply_text(text, parse_mode='Markdown')


async def missions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    missions = db.get_daily_missions(user.id)
    text = "📜 **Daily Missions**\n\n"
    for m in missions:
        status = "✅" if m['completed'] else f"⬜ {m.get('current_value',0)}/{m['target_value']}"
        text += (f"{status} **{m['name']}**\n"
                 f"📖 {m['description']}\n"
                 f"💰 ¥{format_yen(m['reward_yen'])} | ⭐ {m['reward_xp']} XP\n\n")
    await update.effective_message.reply_text(text, parse_mode='Markdown')


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == 'private':
        leaders = db.get_global_leaderboard(10)
        text = "🏆 **Global Sorcerer Rankings**\n\n"
    else:
        leaders = db.get_group_leaderboard(chat.id, 10)
        text = f"🏆 **{chat.title} Rankings**\n\n"
    medals = ['🥇', '🥈', '🥉']
    for i, p in enumerate(leaders):
        medal = medals[i] if i < 3 else f"{i + 1}."
        text += (f"{medal} **{p['display_name']}**\n"
                 f"   ⭐ Lv.{p['level']} | 💴 ¥{format_yen(p['yen'])} | 🏆 {p['wins']}W\n\n")
    await update.effective_message.reply_text(text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# HELP — PAGINATED
# ═══════════════════════════════════════════════════════════════

HELP_PAGES = [
    # Page 1 — General + Combat
    (
        "🌀 **JJK Bot Commands** (1/5)\n\n"
        "**🎮 General**\n"
        "`/start` — Begin your journey\n"
        "`/p` or `/profile` — View full profile\n"
        "`/s` or `/stats` — Quick combat stats\n"
        "`/wallet` — View your yen balance\n"
        "`/characters` — Browse & choose fighter\n"
        "`/rank` — Your rank & requirements\n"
        "`/leaderboard` — Top sorcerers\n"
        "`/missions` — Daily quests\n"
        "`/daily` — Claim daily reward\n\n"
        "**🌐 Web Dashboard**\n"
        "`/web` — Create your JJK RPG dashboard username and password\n"
        "`/webreset` — Generate a one-time password-reset code\n"
        "Open the dashboard link sent by the bot after registration.\n"
    ),
    # Page 2 — Combat
    (
        "🌀 **JJK Bot Commands** (2/5)\n\n"
        "**⚔️ Combat**\n"
        "`/battle` — Fight a cursed spirit (PvE)\n"
        "`/ch @user` or `/challenge @user` — Challenge a player (groups)\n"
        "`/ch bot` — Fight the bot AI (private or group)\n"
        "`/flee` — Escape from battle\n"
        "`/heal` — Restore HP (¥500)\n"
        "`/energy` — Restore cursed energy (¥300)\n\n"
        "**⚔️ Attack Format:**\n"
        "`/a` — List all your moves\n"
        "`/a attack` — Basic free strike\n"
        "`/a 1` `/a 2` `/a 3` — Character's numbered attacks\n"
        "`/a [attack name]` — Use by exact name\n"
        "`/a [learned technique]` — Use a learned technique\n"
    ),
    # Page 3 — Inventory & Items
    (
        "🌀 **JJK Bot Commands** (3/5)\n\n"
        "**🎒 Inventory & Skills**\n"
        "`/bag` or `/inventory` — View your items\n"
        "`/techniques` — View learned techniques\n"
        "`/equip [item]` — Equip a weapon/armor\n"
        "`/learn [skill]` — Learn a technique from inventory\n"
        "`/use [item name]` — Use a consumable/elixir/special item\n"
        "`/use Domain Expansion Blueprint [name]` — Create your domain\n"
        "`/use equip domain` — Equip your domain (¥1,500,000)\n\n"
        "**🏪 Shop**\n"
        "`/shop` — Browse all items (paginated)\n"
        "`/shop 2` — Jump to page 2\n"
        "`/giveyen @user <amount>` — Send yen to a player\n"
        "`/buyyen` — Payment instructions for Yen\n"
    ),
    # Page 4 — Expansion systems
    (
        "🌀 **JJK Bot Commands** (4/5)\n\n"
        "**🌀 Innate Techniques**\n"
        "`/technique` — Browse techniques and mastery\n"
        "`/technique awaken <name>` — Awaken an innate technique\n"
        "`/domain` `/domain unlock` — Domain status or unlock\n"
        "`/maximum` — Check your Maximum Technique\n"
        "`/rct [heal|limb|revive]` — Reverse Cursed Technique\n"
        "`/blackflash [normal|perfect]` — Attempt a Black Flash\n"
        "`/vow create <name> [permanent]` — Create a binding vow\n"
        "`/origin sorcerer|curse` — Choose an origin\n"
        "`/restriction toji|maki` — Attempt Heavenly Restriction\n"
        "`/evolve` — Evolve as a cursed spirit\n"
        "`/school Tokyo|Kyoto|curse|independent` — Join a faction\n\n"
        "**⚔️ Progression & Gear**\n"
        "`/gear` — Weapons, robes, relics, upgrades\n"
        "`/shikigami` — Train Ten Shadows summons\n"
        "`/materials` — View crafting materials\n"
        "`/craft` `/enchant` — Make and enchant cursed tools\n"
        "`/achievements` `/titles` — Collection rewards\n\n"
        "**🌍 World Content**\n"
        "`/raid` `/event` `/story` `/npc` `/quests`\n"
        "`/clan` `/culling` `/market` `/endgame` `/weather`\n"
        "`/clan donate <amount> @member` — Leader treasury donation\n"
    ),
    # Page 5 — Admin & Owner
    (
        "🌀 **JJK Bot Commands** (5/5)\n\n"
        "**🛡️ Admin**\n"
        "`/admin recalc all` — Recalculate all player stats\n"
        "`/admin recalc @user` — Recalculate a player\n\n"
        "**👑 Owner (dot-prefix)**\n"
        "`.addyen @user <amount>` — Add yen\n"
        "`.removeyen @user <amount>` — Remove yen\n"
        "`/adminendbattle` — End all active PvP battles (admin)\n"
        "`.setrank @user <rank>` — Set rank\n"
        "`.removerank @user` — Reduce rank\n"
        "`.addlevel @user <amount>` — Add levels\n"
        "`.removelevel @user <amount>` — Remove levels\n"
        "`/debug` — Full diagnostic (DB, players, battles, simulation)\n\n"
        "**📝 Abbreviations:**\n"
        "`/p` = `/profile` | `/s` = `/stats` | `/ch` = `/challenge`\n"
        "`/bag` = `/inventory` | `/a` = attack in battle\n\n"
        "🔥 *Become the strongest sorcerer! Max level: 100*"
    ),
]


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(context.args[0]) - 1 if context.args and context.args[0].isdigit() else 0
    page = max(0, min(page, len(HELP_PAGES) - 1))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"help_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{len(HELP_PAGES)}", callback_data="noop"))
    if page < len(HELP_PAGES) - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"help_page_{page + 1}"))

    keyboard = InlineKeyboardMarkup([nav]) if nav else None
    await update.effective_message.reply_text(
        HELP_PAGES[page], reply_markup=keyboard, parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════

async def adminendbattle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner/admin emergency command to finish every active PvP battle."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text("⛔ Admin access required.")
        return
    try:
        count = db.clear_all_active_pvp_battles()
        await update.effective_message.reply_text(f"✅ Ended {count} active battle(s). Pending moves and battle locks were cleared.")
    except Exception as exc:
        logger.exception("adminendbattle failed")
        await update.effective_message.reply_text("❌ Could not end active battles. Check /debug for database status.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text("⛔ **Admin access required.**", parse_mode='Markdown')
        return

    if not context.args:
        await update.effective_message.reply_text(
            "⚠️ **Admin Commands:**\n"
            "/admin recalc all — Recalculate all player stats\n"
            "/admin recalc @user — Recalculate a player's stats\n"
            "/admin faction @user Sorcerer|Curse — Change a player's faction",
            parse_mode='Markdown'
        )
        return

    sub = context.args[0].lower()

    if sub == "faction":
        if len(context.args) < 3:
            await update.effective_message.reply_text(
                "Usage: `/admin faction @user Sorcerer|Curse`",
                parse_mode='Markdown'
            )
            return
        target = db.get_user_by_username(context.args[1].lstrip("@"))
        faction = context.args[2].capitalize()
        if not target:
            await update.effective_message.reply_text("❌ Player not found.")
            return
        if faction not in ("Sorcerer", "Curse"):
            await update.effective_message.reply_text("❌ Faction must be Sorcerer or Curse.")
            return
        db.set_faction(target["user_id"], faction)
        await update.effective_message.reply_text(
            f"✅ {target.get('display_name') or target.get('username')} is now assigned to {faction}."
        )
        return

    if sub == 'recalc':
        if len(context.args) < 2:
            await update.effective_message.reply_text(
                "⚠️ Usage: `/admin recalc all` or `/admin recalc @user`",
                parse_mode='Markdown'
            )
            return

        target_arg = context.args[1]

        if target_arg.lower() == 'all':
            msg = await update.effective_message.reply_text("⏳ Recalculating all player stats...")
            players = db.get_all_players()
            count = sum(1 for p in players if db.recalc_player(p['user_id']))
            await msg.edit_text(
                f"✅ **Recalc complete!**\n🔄 Recalculated **{count}** player(s).",
                parse_mode='Markdown'
            )
        else:
            target_username = target_arg.replace('@', '')
            target = db.get_user_by_username(target_username)
            if not target:
                message = update.effective_message
                if message and message.entities:
                    for entity in message.entities:
                        if entity.type == 'text_mention' and entity.user:
                            target = db.get_player(entity.user.id)
                            break
            if not target:
                await update.effective_message.reply_text(f"❌ User @{target_username} not found!")
                return
            if db.recalc_player(target['user_id']):
                updated = db.get_player(target['user_id'])
                await update.effective_message.reply_text(
                    f"✅ **Recalculated @{target.get('username') or target['display_name']}**\n\n"
                    f"⚔️ ATK: {updated['attack']} | 🛡️ DEF: {updated['defense']} | 💨 SPD: {updated['speed']}\n"
                    f"❤️ HP: {updated['hp']}/{updated['max_hp']} | "
                    f"⚡ CE: {updated['cursed_energy']}/{updated['max_cursed_energy']}",
                    parse_mode='Markdown'
                )
            else:
                await update.effective_message.reply_text("❌ Recalculation failed.")


# ═══════════════════════════════════════════════════════════════
# OWNER COMMANDS  (dot prefix)
# ═══════════════════════════════════════════════════════════════

async def addyen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    parts = update.effective_message.text.split()
    if len(parts) < 3:
        await update.effective_message.reply_text("⚠️ `.addyen @user <amount>`")
        return
    username = parts[1].replace('@', '')
    try:
        amount = int(parts[2])
    except ValueError:
        await update.effective_message.reply_text("❌ Amount must be a number!")
        return
    target = db.get_user_by_username(username)
    if not target:
        await update.effective_message.reply_text(f"❌ User @{username} not found!")
        return
    new_bal = db.add_yen(target['user_id'], amount)
    await update.effective_message.reply_text(
        f"✅ Added ¥{format_yen(amount)} to @{username}\n💰 New balance: ¥{format_yen(new_bal)}"
    )


async def removeyen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    parts = update.effective_message.text.split()
    if len(parts) < 3:
        await update.effective_message.reply_text("⚠️ `.removeyen @user <amount>`")
        return
    username = parts[1].replace('@', '')
    try:
        amount = int(parts[2])
    except ValueError:
        await update.effective_message.reply_text("❌ Amount must be a number!")
        return
    target = db.get_user_by_username(username)
    if not target:
        await update.effective_message.reply_text(f"❌ User @{username} not found!")
        return
    new_bal = db.remove_yen(target['user_id'], amount)
    await update.effective_message.reply_text(
        f"✅ Removed ¥{format_yen(amount)} from @{username}\n💰 New balance: ¥{format_yen(new_bal)}"
    )


async def setrank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    parts = update.effective_message.text.split()
    if len(parts) < 3:
        await update.effective_message.reply_text("⚠️ `.setrank @user <rank>`")
        return
    username = parts[1].replace('@', '')
    rank = ' '.join(parts[2:])
    target = db.get_user_by_username(username)
    if not target:
        await update.effective_message.reply_text(f"❌ User @{username} not found!")
        return
    db.set_rank(target['user_id'], rank)
    await update.effective_message.reply_text(
        f"✅ Set @{username}'s rank to **{rank}**", parse_mode='Markdown'
    )


async def removerank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    parts = update.effective_message.text.split()
    if len(parts) < 2:
        await update.effective_message.reply_text("⚠️ `.removerank @user`")
        return
    username = parts[1].replace('@', '')
    target = db.get_user_by_username(username)
    if not target:
        await update.effective_message.reply_text(f"❌ User @{username} not found!")
        return
    rank_order = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']
    try:
        idx = rank_order.index(target['rank'])
    except ValueError:
        await update.effective_message.reply_text(f"❌ Invalid rank: {target['rank']}")
        return
    if idx == 0:
        await update.effective_message.reply_text(f"❌ @{username} is already at Grade 4!")
        return
    new_rank = rank_order[idx - 1]
    db.set_rank(target['user_id'], new_rank)
    await update.effective_message.reply_text(
        f"✅ @{username}: {target['rank']} → {new_rank}", parse_mode='Markdown'
    )


async def addlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    parts = update.effective_message.text.split()
    if len(parts) < 3:
        await update.effective_message.reply_text("⚠️ `.addlevel @user <amount>`")
        return
    username = parts[1].replace('@', '')
    try:
        amount = int(parts[2])
    except ValueError:
        await update.effective_message.reply_text("❌ Amount must be a number!")
        return
    target = db.get_user_by_username(username)
    if not target:
        await update.effective_message.reply_text(f"❌ User @{username} not found!")
        return
    old_level = target['level']
    new_level = db.add_level(target['user_id'], amount)
    await update.effective_message.reply_text(
        f"✅ **Level added to @{username}**\n⭐ Level: {old_level} → {new_level}",
        parse_mode='Markdown'
    )


async def removelevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    parts = update.effective_message.text.split()
    if len(parts) < 3:
        await update.effective_message.reply_text("⚠️ `.removelevel @user <amount>`")
        return
    username = parts[1].replace('@', '')
    try:
        amount = int(parts[2])
    except ValueError:
        await update.effective_message.reply_text("❌ Amount must be a number!")
        return
    target = db.get_user_by_username(username)
    if not target:
        await update.effective_message.reply_text(f"❌ User @{username} not found!")
        return
    old_level = target['level']
    new_level = db.remove_level(target['user_id'], amount)
    await update.effective_message.reply_text(
        f"✅ **Level removed from @{username}**\n⭐ Level: {old_level} → {new_level}",
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
# /debug — OWNER-ONLY DIAGNOSTIC COMMAND
# ═══════════════════════════════════════════════════════════════

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /debug  — Owner-only full diagnostic.

    Sections produced:
      1. Database connectivity & table row counts
      2. Player scan — validates every player record, reports / auto-repairs bad state
      3. Active battle audit — lists every live PvP battle and flags stuck ones
         (no moves submitted for 5+ minutes, or a pending move with no opponent move)
      4. Battle lock sweep — force-finishes genuinely stale battles
      5. Battle simulation — runs a headless PvP sim between two real players
         (or falls back to synthetic players) so damage / CE formulas can be spot-checked
      6. Game integrity checks — verifies character roster, technique table, shop items
      7. Summary & recommendations
    """
    if not is_owner(update.effective_user.id):
        return  # silently refuse — no leak of diagnostic info

    msg = await update.effective_message.reply_text(
        "🔍 *Running diagnostics…*\n_This may take a moment._",
        parse_mode='Markdown'
    )

    lines: list[str] = []
    separator = "─" * 28

    # ── Helper ─────────────────────────────────────────────────
    def section(title: str):
        lines.append(f"\n{separator}")
        lines.append(f"🧪 **{title}**")
        lines.append(separator)

    def ok(text: str):   lines.append(f"✅ {text}")
    def warn(text: str): lines.append(f"⚠️ {text}")
    def err(text: str):  lines.append(f"❌ {text}")
    def info(text: str): lines.append(f"ℹ️ {text}")

    # ─────────────────────────────────────────────────────────
    # 1. DATABASE CONNECTIVITY
    # ─────────────────────────────────────────────────────────
    section("DATABASE CONNECTIVITY")
    try:
        alive = db.verify_db_connection()
        if alive:
            ok("PostgreSQL connection: OK")
        else:
            err("PostgreSQL connection: FAILED")
    except Exception as exc:
        err(f"DB connection check raised: {exc}")
        alive = False

    if alive:
        try:
            counts = db.get_db_table_counts()
            for table, count in counts.items():
                if isinstance(count, str):
                    err(f"Table '{table}': {count}")
                else:
                    ok(f"Table '{table}': {count} rows")
        except Exception as exc:
            err(f"Table count query failed: {exc}")

    # ─────────────────────────────────────────────────────────
    # 2. PLAYER RECORD VALIDATION
    # ─────────────────────────────────────────────────────────
    section("PLAYER VALIDATION")
    try:
        all_players = db.get_all_players()
        info(f"Total registered players: {len(all_players)}")
        total_issues = 0
        total_repaired = 0
        bad_players: list[str] = []

        for p in all_players:
            report = db.validate_and_repair_player(p)
            if report['issues']:
                total_issues += len(report['issues'])
                pname = p.get('username') or p.get('display_name') or str(p['user_id'])
                bad_players.append(pname)
                for issue in report['issues']:
                    warn(f"  @{pname}: {issue}")
            if report['repaired']:
                total_repaired += len(report['repaired'])
                pname = p.get('username') or p.get('display_name') or str(p['user_id'])
                for fix in report['repaired']:
                    ok(f"  @{pname}: AUTO-FIXED → {fix}")

        if total_issues == 0:
            ok(f"All {len(all_players)} player records are valid.")
        else:
            warn(f"{total_issues} issue(s) found across {len(bad_players)} player(s); "
                 f"{total_repaired} auto-repaired.")
    except Exception as exc:
        err(f"Player scan failed: {exc}")
        all_players = []

    # ─────────────────────────────────────────────────────────
    # 3. ACTIVE PVP BATTLE AUDIT
    # ─────────────────────────────────────────────────────────
    section("ACTIVE PVP BATTLE AUDIT")
    try:
        active_battles = db.get_all_active_pvp_battles()
        info(f"Active PvP battles in DB: {len(active_battles)}")

        from datetime import datetime as _dt
        now_ts = _dt.now()
        stuck_ids: list[int] = []

        for battle in active_battles:
            bid    = battle['battle_id']
            p1_id  = battle['player1_id']
            p2_id  = battle['player2_id']
            p1_mv  = battle.get('p1_move')
            p2_mv  = battle.get('p2_move')
            rnd    = battle.get('round', 1)
            chat   = battle.get('chat_id')
            age_s  = None
            try:
                created = _dt.fromisoformat(str(battle['created_at']))
                age_s = (now_ts - created).total_seconds()
            except Exception:
                pass

            age_str = f"{int(age_s // 60)}m ago" if age_s is not None else "unknown age"
            info(f"  Battle #{bid} | Chat {chat} | R{rnd} | "
                 f"P1={p1_id}({p1_mv or 'pending'}) vs P2={p2_id}({p2_mv or 'pending'}) "
                 f"| {age_str}")

            # Flag as stuck if older than 2 hours
            if age_s is not None and age_s > 7200:
                warn(f"  ↳ Battle #{bid} is STALE (> 2 h old) — scheduled for cleanup")
                stuck_ids.append(bid)
            # Flag asymmetric lock: one player has a move set but the other doesn't, long wait
            elif age_s is not None and age_s > 300 and bool(p1_mv) != bool(p2_mv):
                warn(f"  ↳ Battle #{bid} has asymmetric move lock (possible Domain Expansion lock)")
                stuck_ids.append(bid)

        if not active_battles:
            ok("No active PvP battles — clean state.")
        elif not stuck_ids:
            ok(f"All {len(active_battles)} active battle(s) appear healthy.")
    except Exception as exc:
        err(f"Battle audit failed: {exc}")
        active_battles = []
        stuck_ids = []

    # ─────────────────────────────────────────────────────────
    # 4. BATTLE LOCK SWEEP (auto-repair)
    # ─────────────────────────────────────────────────────────
    section("BATTLE LOCK SWEEP")
    try:
        swept = db.cleanup_stale_battles()
        if swept > 0:
            ok(f"Force-finished {swept} stale battle(s) older than 2 h.")
        else:
            ok("No battles needed force-finishing — all are within the 2 h window.")
    except Exception as exc:
        err(f"Battle cleanup failed: {exc}")

    # ─────────────────────────────────────────────────────────
    # 5. BATTLE SIMULATION
    # ─────────────────────────────────────────────────────────
    section("BATTLE SIMULATION")
    try:
        # Pick two real players with characters if available, else synthesize
        sim_players = [p for p in all_players if p.get('character_id') and p.get('hp', 0) > 0]
        if len(sim_players) >= 2:
            import random as _rand
            a, b = _rand.sample(sim_players[:10], 2)
            info(f"Simulating: {a.get('display_name','P1')} vs {b.get('display_name','P2')}")
        else:
            a = {'user_id': 99991, 'display_name': 'SyntheticA',
                 'character_id': 1, 'hp': 120, 'max_hp': 120,
                 'cursed_energy': 80, 'max_cursed_energy': 80,
                 'attack': 85, 'defense': 70, 'speed': 95}
            b = {'user_id': 99992, 'display_name': 'SyntheticB',
                 'character_id': 5, 'hp': 210, 'max_hp': 210,
                 'cursed_energy': 210, 'max_cursed_energy': 210,
                 'attack': 155, 'defense': 125, 'speed': 135}
            info("No two real players with characters — using synthetic data.")

        char_a = db.get_character(a['character_id'])
        char_b = db.get_character(b['character_id'])

        if not char_a or not char_b:
            warn("Could not load characters for simulation — skipped.")
        else:
            # Headless simulation: pick first attack from each character
            def _sim_damage(attacker: dict, defender: dict, dmg_mult: float) -> int:
                raw = max(1, int(attacker['attack'] * dmg_mult))
                reduction = max(0, min(0.75, defender['defense'] / (defender['defense'] + 100)))
                return max(1, int(raw * (1 - reduction)))

            a_atk = char_a['attacks'][0] if char_a.get('attacks') else None
            b_atk = char_b['attacks'][0] if char_b.get('attacks') else None

            if a_atk:
                dmg_a = _sim_damage(a, b, a_atk.get('dmg_mult', 2.0))
                ok(f"  {a['display_name']} → '{a_atk['name']}' deals ~{dmg_a} dmg to {b['display_name']}")
            if b_atk:
                dmg_b = _sim_damage(b, a, b_atk.get('dmg_mult', 2.0))
                ok(f"  {b['display_name']} → '{b_atk['name']}' deals ~{dmg_b} dmg to {a['display_name']}")

            # Check domain expansion attacks specifically
            for char, player in [(char_a, a), (char_b, b)]:
                for atk in (char.get('attacks') or []):
                    if 'domain' in atk['name'].lower() or 'expansion' in atk['name'].lower():
                        de_dmg = _sim_damage(player, b if player is a else a, atk.get('dmg_mult', 3.5))
                        ok(f"  Domain: '{atk['name']}' → ~{de_dmg} dmg (CE cost {atk.get('ce_cost','?')})")

            # Multi-round simulation
            hp_a, hp_b = a['hp'], b['hp']
            ce_a, ce_b = a.get('cursed_energy', 50), b.get('cursed_energy', 50)
            attacks_a = char_a.get('attacks', []) or []
            attacks_b = char_b.get('attacks', []) or []
            if not attacks_a:
                attacks_a = [{'name': 'Basic Attack', 'ce_cost': 10, 'dmg_mult': 1.5}]
            if not attacks_b:
                attacks_b = [{'name': 'Basic Attack', 'ce_cost': 10, 'dmg_mult': 1.5}]

            sim_rounds = 0
            max_rounds = 20
            while hp_a > 0 and hp_b > 0 and sim_rounds < max_rounds:
                sim_rounds += 1
                # Pick best affordable attack for each
                def _best_atk(attacks, ce):
                    affordable = [x for x in attacks if x.get('ce_cost', 0) <= ce]
                    if not affordable:
                        return {'name': 'Exhausted Strike', 'ce_cost': 0, 'dmg_mult': 1.0}
                    return max(affordable, key=lambda x: x.get('dmg_mult', 1.0))

                atk_a = _best_atk(attacks_a, ce_a)
                atk_b = _best_atk(attacks_b, ce_b)
                d_a_to_b = _sim_damage(a, b, atk_a['dmg_mult'])
                d_b_to_a = _sim_damage(b, a, atk_b['dmg_mult'])
                hp_b = max(0, hp_b - d_a_to_b)
                hp_a = max(0, hp_a - d_b_to_a)
                ce_a = max(0, ce_a - atk_a.get('ce_cost', 0))
                ce_b = max(0, ce_b - atk_b.get('ce_cost', 0))
                # CE regen (5/round)
                ce_a = min(a.get('max_cursed_energy', 80), ce_a + 5)
                ce_b = min(b.get('max_cursed_energy', 80), ce_b + 5)

            if hp_a > 0 and hp_b <= 0:
                winner = a['display_name']
                loser  = b['display_name']
            elif hp_b > 0 and hp_a <= 0:
                winner = b['display_name']
                loser  = a['display_name']
            else:
                winner = loser = None

            if winner:
                ok(f"  Sim concluded in {sim_rounds} round(s): **{winner}** defeated {loser}")
                ok(f"  Survivor HP: {max(hp_a, hp_b)} | Damage formula: VALIDATED ✓")
            else:
                warn(f"  Sim hit {max_rounds}-round cap — draw / infinite loop possible")
                warn("  Check CE regen vs CE cost balance.")
    except Exception as exc:
        err(f"Battle simulation crashed: {exc}")

    # ─────────────────────────────────────────────────────────
    # GEMINI AI REVIEW (optional; deterministic diagnostics remain authoritative)
    # ─────────────────────────────────────────────────────────
    try:
        ai_review = analyze_diagnostic("\n".join(lines))
        if ai_review:
            apply_review_to_diagnostic(lines, ai_review)
        else:
            info(apply_review_to_diagnostic(lines, None) or lines.pop())
    except Exception:
        info("Gemini AI review failed safely; deterministic diagnostics were retained.")

    # ─────────────────────────────────────────────────────────
    # 6. GAME INTEGRITY CHECKS
    # ─────────────────────────────────────────────────────────
    section("GAME INTEGRITY")
    try:
        chars = db.get_all_characters()
        if chars:
            ok(f"Characters loaded: {len(chars)}")
            no_attacks = [c['name'] for c in chars if not c.get('attacks')]
            if no_attacks:
                warn(f"Characters with no attacks: {', '.join(no_attacks)}")
            else:
                ok("All characters have attack lists.")
        else:
            err("No characters in DB — seed data may not have run!")

        techs = db.get_all_techniques()
        ok(f"Techniques in DB: {len(techs)}")

        items = db.get_shop_items()
        ok(f"Shop items in DB: {len(items)}")

        # Verify equipped characters for all players are valid
        orphan_chars = 0
        for p in all_players:
            cid = p.get('character_id')
            if cid is not None:
                c = db.get_character(cid)
                if not c:
                    orphan_chars += 1
                    warn(f"  Player {p.get('username') or p['user_id']} has orphaned character_id={cid}")
        if orphan_chars == 0:
            ok("No orphaned character references found.")
    except Exception as exc:
        err(f"Integrity check failed: {exc}")

    # ─────────────────────────────────────────────────────────
    # 7. SUMMARY
    # ─────────────────────────────────────────────────────────
    section("SUMMARY & RECOMMENDATIONS")

    warn_lines = [l for l in lines if l.startswith("⚠️")]
    err_lines  = [l for l in lines if l.startswith("❌")]

    if not err_lines and not warn_lines:
        ok("System is healthy — no issues detected.")
    else:
        if err_lines:
            err(f"{len(err_lines)} error(s) require attention.")
        if warn_lines:
            warn(f"{len(warn_lines)} warning(s) were found (some may have been auto-repaired).")

    info("Auto-repairs applied where possible (player fields, stale battles).")
    info("Use /flee to manually reset your own battle state.")
    info("Owner dot-commands: .addyen .addlevel .setrank etc.")
    info(f"Active stale battle(s) swept: see section 4 above.")

    # ─────────────────────────────────────────────────────────
    # OUTPUT — split into chunks to stay under Telegram's 4096-char limit
    # ─────────────────────────────────────────────────────────
    full_report = "\n".join(lines)
    chunk_size = 3800
    chunks = [full_report[i:i + chunk_size] for i in range(0, len(full_report), chunk_size)]

    try:
        await msg.delete()
    except Exception:
        pass

    header = (
        "🛠️ **JJK BOT — DIAGNOSTIC REPORT**\n"
        f"_Owner-only  •  {len(all_players)} players  •  {len(active_battles)} active battles_\n"
    )
    for idx, chunk in enumerate(chunks):
        prefix = header if idx == 0 else f"_(continued {idx+1}/{len(chunks)})_\n"
        try:
            await update.effective_message.reply_text(
                prefix + chunk,
                parse_mode='Markdown'
            )
        except Exception:
            # Markdown parse error fallback — send as plain text
            await update.effective_message.reply_text(prefix + chunk)


# ═══════════════════════════════════════════════════════════════
# CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # NOTE: do NOT call query.answer() here — sub-handlers call it themselves
    # so they can pass show_alert messages. Answering upfront blocks that.

    if data == 'noop' or data == 'chars_noop':
        await query.answer()
        return
    elif data == 'choose_char':
        await query.answer()
        await characters_command(update, context)
    elif data == 'start_battle':
        await query.answer()
        await battle_command(update, context)
    elif data == 'missions':
        await query.answer()
        await missions_command(update, context)
    elif data.startswith('chars_page_'):
        # characters_page_callback calls its own query.answer()
        await characters_page_callback(update, context)
    elif data.startswith('select_char_'):
        # select_character calls its own query.answer()
        char_id = int(data.split('_')[2])
        await select_character(update, context, char_id)
    elif data.startswith('buy_'):
        # handle_purchase calls its own query.answer()
        item_id = int(data.split('_')[1])
        await handle_purchase(update, context, item_id)
    elif data.startswith('pvp_accept_'):
        parts = data.split('_')
        challenger_id = int(parts[2])
        opponent_id = int(parts[3]) if len(parts) > 3 else query.from_user.id
        await handle_pvp_accept(update, context, challenger_id, opponent_id)
    elif data.startswith('pvp_decline_'):
        await handle_pvp_decline(update, context)
    elif data.startswith('help_page_'):
        await query.answer()
        page = int(data.split('_')[2])
        page = max(0, min(page, len(HELP_PAGES) - 1))
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"help_page_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{len(HELP_PAGES)}", callback_data="noop"))
        if page < len(HELP_PAGES) - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"help_page_{page + 1}"))
        keyboard = InlineKeyboardMarkup([nav]) if nav else None
        try:
            await query.edit_message_text(HELP_PAGES[page], reply_markup=keyboard, parse_mode='Markdown')
        except Exception:
            pass
    elif data.startswith('shop_page_'):
        await query.answer()
        page = int(data.split('_')[2])
        context.args = [str(page + 1)]
        await shop_command(update, context)
    elif data.startswith('inv_page_'):
        await query.answer()
        page = int(data.split('_')[2])
        context.args = [str(page + 1)]
        await inventory_command(update, context)
    else:
        await query.answer()


async def select_character(update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int):
    query = update.callback_query
    user = query.from_user
    character = db.get_character(char_id)
    player = db.get_player(user.id)

    if not character:
        await query.answer("❌ Character not found!", show_alert=True)
        return
    if not player:
        player = db.get_or_create_player(user.id, user.username, user.first_name)

    result = db.purchase_character(user.id, char_id)
    if not result.get("ok"):
        if result.get("reason") == "funds":
            await query.answer(
                f"❌ Not enough yen! Need ¥{format_yen(result['price'])}", show_alert=True
            )
        else:
            await query.answer("❌ Character purchase failed.", show_alert=True)
        return
    await query.answer("Equipped" if result.get("owned") else "Purchased permanently")

    attacks = character.get('attacks', [])
    atk_list = "\n".join(f"  {a['num']}. {a['name']}" for a in attacks)

    caption = (
        f"{'⚡ **Character Equipped!**' if result.get('owned') else '✅ **Character Purchased Permanently!**'}\n\n"
        f"🎭 *{character['name']}*\n"
        f"💬 \"{character['quote']}\"\n\n"
        f"🔮 **Signature:** {character['technique']}\n"
        f"⚔️ ATK: {character['attack']} | 🛡️ DEF: {character['defense']} | 💨 SPD: {character['speed']}\n\n"
        f"⚔️ **Attacks:**\n{atk_list}\n\n"
        f"💰 *Remaining Yen:* ¥{format_yen(result['remaining'])}\n"
        f"🎒 It is now in your permanent Character Inventory."
    )

    try:
        await query.edit_message_caption(caption=caption, parse_mode='Markdown', reply_markup=None)
    except Exception:
        await query.edit_message_text(
            f"✅ **{character['name']}** selected! Use /p to see your stats.",
            parse_mode='Markdown'
        )


async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    query = update.callback_query
    user = query.from_user
    player = db.get_player(user.id)
    if not player:
        await query.answer("❌ Error!", show_alert=True)
        return
    result = db.purchase_shop_item(user.id, item_id)
    if not result.get("ok"):
        if result.get("reason") == "removed":
            await query.answer("This shop item has been removed.", show_alert=True)
        elif result.get("reason") == "funds":
            await query.answer(
                f"❌ Not enough yen! Need ¥{format_yen(result['price'])}", show_alert=True
            )
        else:
            await query.answer("❌ Purchase failed.", show_alert=True)
        return
    item = result["item"]
    await query.answer()
    text = (
        f"✅ **Purchased!**\n\n"
        f"🎒 *{item['name']}* added to your bag!\n"
        f"💡 {item.get('use_description', item['description'])}\n\n"
        f"💰 Remaining: ¥{format_yen(result['remaining'])}"
    )
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=image_gen.generate_elixir_image(item, player=player, quantity=1),
                caption=text, parse_mode='Markdown'
            ),
            reply_markup=None
        )
    except Exception:
        await query.edit_message_text(text, parse_mode='Markdown')


async def handle_pvp_accept(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            challenger_id: int, opponent_id: int):
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat

    if user.id != opponent_id:
        await query.answer("❌ This challenge isn't for you!", show_alert=True)
        return

    challenger = db.get_player(challenger_id)
    opponent = db.get_player(opponent_id)

    if not challenger or not opponent:
        await query.answer()
        await query.edit_message_text("❌ One of the players is not registered!")
        return

    c_char = db.get_character(challenger['character_id']) if challenger['character_id'] else None
    o_char = db.get_character(opponent['character_id']) if opponent['character_id'] else None

    if not c_char or not o_char:
        await query.answer()
        await query.edit_message_text("❌ Both players need a character!")
        return

    await query.answer()

    first = challenger if challenger['speed'] >= opponent['speed'] else opponent
    first_tag = (f"@{challenger.get('username') or challenger['display_name']}"
                 if first['user_id'] == challenger_id
                 else f"@{opponent.get('username') or opponent['display_name']}")
    second_tag = (f"@{opponent.get('username') or opponent['display_name']}"
                  if first['user_id'] == challenger_id
                  else f"@{challenger.get('username') or challenger['display_name']}")

    db.create_pvp_battle(
        chat_id=chat.id,
        player1_id=challenger_id,
        player2_id=opponent_id,
        p1_hp=challenger['hp'], p2_hp=opponent['hp'],
        p1_max_hp=challenger['max_hp'], p2_max_hp=opponent['max_hp'],
        p1_ce=challenger['cursed_energy'], p2_ce=opponent['cursed_energy'],
        p1_max_ce=challenger['max_cursed_energy'], p2_max_ce=opponent['max_cursed_energy'],
        first_attacker=first['user_id'],
    )

    c_tag = f"@{challenger.get('username') or challenger['display_name']}"
    o_tag = f"@{opponent.get('username') or opponent['display_name']}"

    battle_text = (
        f"⚔️ **BATTLE ACCEPTED!**\n\n"
        f"👤 {challenger['display_name']} ({c_char['name']})\n"
        f"❤️ {challenger['hp']}/{challenger['max_hp']} ⚔️ {challenger['attack']}\n\n"
        f"⚔️ **VS** ⚔️\n\n"
        f"👤 {opponent['display_name']} ({o_char['name']})\n"
        f"❤️ {opponent['hp']}/{opponent['max_hp']} ⚔️ {opponent['attack']}\n\n"
        f"{'━' * 22}\n"
        f"🌀 **ROUND 1 — FIGHT!**\n\n"
        f"⚡ {first_tag}, lock in your move!\n"
        f"⚡ {second_tag}, lock in your move!\n\n"
        f"📋 `/a` — see your moves\n"
        f"⚔️ `/a <move or number>` — lock in your attack"
    )

    try:
        img = image_gen.generate_pvp_battle_display(challenger, opponent, c_char, o_char, turn=1)
        await query.edit_message_media(
            media=InputMediaPhoto(media=img, caption=battle_text, parse_mode='Markdown'),
            reply_markup=None
        )
    except Exception:
        try:
            await query.edit_message_caption(caption=battle_text, parse_mode='Markdown', reply_markup=None)
        except Exception:
            await query.edit_message_text(battle_text, parse_mode='Markdown')


async def handle_pvp_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❌ **Challenge Declined**\n\nThe opponent chose not to fight...",
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════════════════════

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update caused error {context.error}", exc_info=context.error)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # ── General commands ──────────────────────────────────────
    application.add_handler(build_web_conversation(db))
    application.add_handler(build_web_reset_handler(db))
    application.add_handler(CommandHandler("start", start_command))

    # Profile aliases: /profile and /p
    application.add_handler(CommandHandler(["profile", "p"], profile_command))

    # Stats aliases: /stats and /s
    application.add_handler(CommandHandler(["stats", "s"], stats_command))

    # Characters
    application.add_handler(CommandHandler("characters", characters_command))

    # Battle
    application.add_handler(CommandHandler("battle", battle_command))
    application.add_handler(CommandHandler("flee", flee_command))
    application.add_handler(CommandHandler("a", attack_command))

    # Challenge aliases: /ch and /challenge
    application.add_handler(CommandHandler(["ch", "challenge"], ch_command))

    # Shop & Economy
    application.add_handler(CommandHandler("shop", shop_command))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("missions", missions_command))
    application.add_handler(CommandHandler(["leaderboard", "lb"], leaderboard_command))
    application.add_handler(CommandHandler("listplayers", listplayers_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("daily", daily_command))
    application.add_handler(CommandHandler("heal", heal_command))
    application.add_handler(CommandHandler("energy", energy_command))
    application.add_handler(CommandHandler("wallet", build_wallet_command(db, image_gen, format_yen)))
    application.add_handler(CommandHandler("giveyen", giveyen_command))
    application.add_handler(CommandHandler("buyyen", buyyen_command))
    application.add_handler(CommandHandler("rank", rank_command))

    # Inventory aliases: /inventory, /bag, /inv
    application.add_handler(CommandHandler(["inventory", "bag", "inv"], inventory_command))

    # Techniques and equip/learn/use
    application.add_handler(CommandHandler("techniques", techniques_command))
    application.add_handler(CommandHandler("equip", equip_command))
    application.add_handler(CommandHandler("learn", learn_command))
    application.add_handler(CommandHandler("use", use_command))

    # Deep JJK expansion systems. These are additive and do not replace the
    # existing /a, /battle, /ch, /shop, inventory, or mission handlers.
    application.add_handler(CommandHandler("technique", technique_command))
    application.add_handler(CommandHandler("domain", domain_expansion_command))
    application.add_handler(CommandHandler("maximum", maximum_command))
    application.add_handler(CommandHandler("rct", rct_command))
    application.add_handler(CommandHandler("blackflash", black_flash_command))
    application.add_handler(CommandHandler("vow", vow_command))
    application.add_handler(CommandHandler("origin", origin_command))
    application.add_handler(CommandHandler("restriction", restriction_command))
    application.add_handler(CommandHandler("evolve", evolve_command))
    application.add_handler(CommandHandler("school", school_command))
    application.add_handler(CommandHandler("reputation", reputation_command))
    application.add_handler(CommandHandler("gear", gear_command))
    application.add_handler(CommandHandler("shikigami", shikigami_command))
    application.add_handler(CommandHandler("raid", raid_command))
    application.add_handler(CommandHandler("event", event_command))
    application.add_handler(CommandHandler("story", story_command))
    application.add_handler(CommandHandler("npc", npc_command))
    application.add_handler(CommandHandler(["quests", "extendedmissions"], extended_missions_command))
    application.add_handler(CommandHandler("clan", clan_command))
    application.add_handler(CommandHandler("craft", craft_command))
    application.add_handler(CommandHandler(["materials", "mats"], materials_command))
    application.add_handler(CommandHandler("enchant", enchant_command))
    application.add_handler(CommandHandler("market", market_command))
    application.add_handler(CommandHandler("culling", culling_command))
    application.add_handler(CommandHandler("prestige", prestige_command))
    application.add_handler(CommandHandler(["achievements", "titles", "collection"], collection_command))
    application.add_handler(CommandHandler("cosmetics", cosmetics_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("endgame", endgame_command))

    # Admin
    application.add_handler(CommandHandler("adminendbattle", adminendbattle_command))
    application.add_handler(CommandHandler("admin", admin_command))

    # Debug — owner-only full diagnostic
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("restart", restart_command))

    # Owner dot-prefix commands
    for pattern, handler in [
        (r'^\.addyen', addyen_command),
        (r'^\.removeyen', removeyen_command),
        (r'^\.setrank', setrank_command),
        (r'^\.removerank', removerank_command),
        (r'^\.addlevel', addlevel_command),
        (r'^\.removelevel', removelevel_command),
    ]:
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex(pattern), handler))

    # Callbacks
    application.add_handler(CallbackQueryHandler(button_callback))

    # Error handler
    application.add_error_handler(error_handler)

    print("🌀 Jujutsu Kaisen Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
