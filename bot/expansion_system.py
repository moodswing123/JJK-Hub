import random
import time


class ExpansionSystem:
    """
    ExpansionSystem — in-memory world/progression/gear/technique/clan/market/raid system.
    Data is not persisted between bot restarts (use a DB-backed version for production).
    """

    def __init__(self, db=None):
        self.db = db

        self.players      = {}   # user_id -> player expansion data
        self.raids        = {}   # raid_id -> raid dict
        self.next_raid_id = 1
        self.events       = {}   # event_id -> event dict
        self.next_event_id = 1
        self._listings    = {}   # listing_id -> market listing dict (renamed to avoid shadowing method)
        self.next_listing_id = 1
        self.weather_state = {"name": "Clear", "effect": "No special effects."}
        self.clans        = {}   # clan_name (lower) -> clan dict

        self._seed_sample_world()
        self._load_persistent_clans()

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _load_persistent_clans(self):
        """Load clans from PostgreSQL; the database is the source of truth."""
        if not self.db:
            return
        try:
            self.clans = {c["clan_key"]: c for c in self.db.get_clans()}
        except Exception:
            # A database error must not silently replace durable data with a
            # destructive empty state. Keep the in-memory map unchanged.
            return

    def _persist_clan(self, clan):
        if self.db:
            self.db.upsert_clan(clan)

    def _seed_sample_world(self):
        bosses = [
            {"boss": "Giant Cursed Spirit",    "grade": "Special", "hp": 5000,  "max_hp": 5000},
            {"boss": "Corrupted Shikigami",     "grade": "Grade 1", "hp": 2500,  "max_hp": 2500},
            {"boss": "Vengeful Spirit Horde",   "grade": "Grade 2", "hp": 1200,  "max_hp": 1200},
        ]
        for b in bosses:
            b["id"]     = self.next_raid_id
            b["status"] = "open"
            b["attackers"] = {}   # user_id -> total damage dealt
            self.raids[self.next_raid_id] = b
            self.next_raid_id += 1

        e = {
            "id": self.next_event_id,
            "name": "Festival Disturbance",
            "description": "Local shrine cursed energy spike",
            "joined": []
        }
        self.events[self.next_event_id] = e
        self.next_event_id += 1

    def _ensure(self, user_id):
        if user_id in self.players:
            return self.players[user_id]
        p = {
            "user_id": user_id,
            "innate_technique": None,
            "technique_mastery": 0,
            "technique_mastery_exp": 0,
            "domain": None,
            "awakening": None,
            "prestige": 0,
            "school": None,
            "clan": None,
            "gear": [],
            "cosmetics": [],
            "titles": [],
            "achievements": [],
            "materials": {},
            "shikigami": [],
            "events_joined": set(),
            "market_listings": [],
            "story": {"chapter": 1, "scene": 1},
        }
        if self.db:
            try:
                player = self.db.get_player(user_id)
                if player:
                    p["clan"] = player.get("clan_key")
            except Exception:
                pass
        self.players[user_id] = p
        return p

    # ─── Player & profile ────────────────────────────────────────────────────

    def ensure_player(self, user_id):
        self._ensure(user_id)
        return True

    def profile(self, user_id):
        p = self._ensure(user_id)
        gear_list = p.get("gear", [])
        cosm_list = p.get("cosmetics", [])
        return {
            "innate_technique":   p["innate_technique"],
            "technique_mastery":  p["technique_mastery"],
            "domain_name":        p["domain"]["name"] if p.get("domain") else None,
            "domain_refinement":  p["domain"]["refinement"] if p.get("domain") else 0,
            "awakening":          p.get("awakening"),
            "prestige":           p.get("prestige", 0),
            "school":             p.get("school"),
            "clan":               p.get("clan"),
            "black_flash_record": 0,
            "black_flash_total":  0,
            "gear":               gear_list,
            "cosmetics":          cosm_list,
            "title_count":        len(p.get("titles", [])),
            "achievement_count":  len(p.get("achievements", [])),
            "technique":          {},
        }

    # ─── Techniques / awakening ──────────────────────────────────────────────

    def awaken(self, user_id, name):
        p = self._ensure(user_id)
        p["innate_technique"] = name
        p["technique_mastery"] = 0
        p["technique_mastery_exp"] = 0
        return True, f"Awakened innate technique: {name}"

    def technique(self, user_id):
        p = self._ensure(user_id)
        if not p["innate_technique"]:
            return None
        return {
            "name": p["innate_technique"],
            "passive": "A subtle passive benefit.",
            "active_skills": ["Pulse", "Surge"],
            "ultimate": "Awakened Domain",
            "maximum": "Maximum Technique (experimental)",
            "affinity": "Neutral",
            "progress": {"mastery": p["technique_mastery"],
                         "mastery_exp": p["technique_mastery_exp"]},
        }

    def maximum(self, user_id):
        p = self._ensure(user_id)
        if p["technique_mastery"] >= 100:
            return True, "Maximum activated!"
        return False, "Not enough mastery to achieve Maximum Technique."

    def rct(self, user_id, mode):
        return True, f"RCT ({mode}) performed."

    def black_flash(self, user_id, timing):
        success = random.random() < (0.35 if timing == "perfect" else 0.12)
        if success:
            p = self._ensure(user_id)
            p["technique_mastery_exp"] += 5
            p["technique_mastery"] = min(
                100, p["technique_mastery"] + p["technique_mastery_exp"] // 10
            )
            return True, "Perfect Black Flash! Massive damage bonus.", 1.5
        return False, "Black Flash failed.", 1.0

    def create_vow(self, user_id, name, permanent=False):
        p = self._ensure(user_id)
        p.setdefault("titles", []).append(name)
        return True, f"Vow '{name}' created{' permanently' if permanent else ''}."

    def awaken_origin(self, user_id, origin):
        p = self._ensure(user_id)
        p["origin"] = origin
        return True, f"Origin set to {origin}"

    def awaken_restriction(self, user_id, variant):
        p = self._ensure(user_id)
        p["restriction"] = variant
        return True, f"Restriction {variant} applied."

    def evolve(self, user_id):
        p = self._ensure(user_id)
        p["awakening"] = "Evolved"
        return True, "Evolved!"

    def set_school(self, user_id, school_name):
        p = self._ensure(user_id)
        p["school"] = school_name
        return True, f"School set to {school_name}"

    # ─── Domain ──────────────────────────────────────────────────────────────

    def progress(self, user_id):
        p = self._ensure(user_id)
        dom = p.get("domain")
        return {
            "domain_name":       dom["name"]      if dom else None,
            "domain_refinement": dom["refinement"] if dom else 0,
            "domain_mastery":    dom["mastery"]    if dom else 0,
            "prestige":          p.get("prestige", 0),
        }

    def unlock_domain(self, user_id):
        p = self._ensure(user_id)
        if not p.get("innate_technique"):
            return False, "You must awaken an innate technique first."
        if p["technique_mastery"] < 20:
            return False, "Technique not refined enough to unlock a domain."
        p["domain"] = {
            "name":       f"{p['innate_technique']} Domain",
            "power":      100 + p["technique_mastery"],
            "equipped":   False,
            "refinement": 1,
            "mastery":    p["technique_mastery"]
        }
        return True, f"Domain '{p['domain']['name']}' unlocked!"

    def domain_clash(self, user_id, opponent_id):
        p = self._ensure(user_id)
        o = self._ensure(opponent_id)
        p_score = p.get("domain", {}).get("mastery", 0) if p.get("domain") else 0
        o_score = o.get("domain", {}).get("mastery", 0) if o.get("domain") else 0
        winner  = user_id if p_score >= o_score else opponent_id
        return {"winner": winner, "score": f"{p_score}-{o_score}"}

    def domain_move(self, user_id):
        p = self._ensure(user_id)
        dom = p.get("domain")
        if not dom or not dom.get("equipped"):
            return False, "You don't have an equipped domain."
        return True, {
            "name": dom["name"], "ce_cost": 0,
            "damage_multiplier": 3.0, "description": "Unleash your domain!"
        }

    # ─── Gear ────────────────────────────────────────────────────────────────

    def gear(self, user_id):
        return self._ensure(user_id).get("gear", [])

    def acquire_gear(self, user_id, name):
        p = self._ensure(user_id)
        p.setdefault("gear", []).append({"gear_name": name, "level": 1, "equipped": False})
        return True, f"Acquired gear: {name}"

    def equip_gear(self, user_id, name):
        p = self._ensure(user_id)
        for g in p.setdefault("gear", []):
            if g["gear_name"].lower() == name.lower():
                g["equipped"] = True
                return True, f"Equipped {g['gear_name']}"
        return False, "Gear not found."

    def upgrade_gear(self, user_id, name):
        p = self._ensure(user_id)
        for g in p.setdefault("gear", []):
            if g["gear_name"].lower() == name.lower():
                g["level"] += 1
                return True, f"Upgraded {g['gear_name']} to Lv.{g['level']}"
        return False, "Gear not found."

    # ─── Shikigami ───────────────────────────────────────────────────────────

    def shikigami(self, user_id):
        return self._ensure(user_id).get("shikigami", [])

    def summon(self, user_id, name):
        p = self._ensure(user_id)
        p.setdefault("shikigami", []).append({"name": name, "level": 1, "mastery": 0, "adaptation": 0})
        return True, f"Summoned {name}!"

    # ─── Raids ───────────────────────────────────────────────────────────────

    def get_raids(self):
        """Return list of all raid dicts."""
        return list(self.raids.values())

    def raid_attack(self, user_id, raid_id, damage):
        raid = self.raids.get(raid_id)
        if not raid or raid.get("status") != "open":
            return False, "Raid not available or already defeated."
        raid["hp"] = max(0, raid["hp"] - damage)
        raid.setdefault("attackers", {})[user_id] = \
            raid["attackers"].get(user_id, 0) + damage
        if raid["hp"] <= 0:
            raid["status"] = "defeated"
            return True, f"You dealt {damage} damage — **{raid['boss']}** has been defeated! 🎉"
        pct = int(100 * raid["hp"] / raid["max_hp"])
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        return True, (
            f"You dealt **{damage}** damage to {raid['boss']}!\n"
            f"Boss HP: {raid['hp']}/{raid['max_hp']} [{bar}] {pct}%"
        )

    # ─── Events ──────────────────────────────────────────────────────────────

    def list_events(self):
        return list(self.events.values())

    def join_event(self, user_id, event_id):
        ev = self.events.get(event_id)
        if not ev:
            return False, "Event not found."
        ev.setdefault("joined", []).append(user_id)
        self._ensure(user_id)["events_joined"].add(event_id)
        return True, f"Joined event: {ev['name']}"

    def claim_event(self, user_id, event_id):
        ev = self.events.get(event_id)
        if not ev:
            return False, "Event not found."
        if user_id not in ev.get("joined", []):
            return False, "You didn't join this event."
        reward_yen, reward_xp = 1000, 50
        try:
            if self.db:
                self.db.add_yen(user_id, reward_yen)
                self.db.add_xp(user_id, reward_xp)
        except Exception:
            pass
        return True, f"Claimed event reward: ¥{reward_yen:,}, {reward_xp} XP"

    # ─── Clan ────────────────────────────────────────────────────────────────

    def clan(self, user_id, action: str, value: str = ""):
        """
        Full clan system.
        Actions: create <name> | join <name> | leave | status | contribute <amount> | info <name>
        """
        p = self._ensure(user_id)
        action = action.lower().strip()

        if action == "status":
            self._load_persistent_clans()
            cname = p.get("clan")
            if not cname:
                return True, (
                    "🏯 You are not in a clan.\n"
                    "• `/clan create <name>` — found a new clan\n"
                    "• `/clan join <name>` — join an existing clan\n"
                    f"• Active clans: {len(self.clans)}"
                )
            c = self.clans.get(cname)
            if not c:
                return False, "Your clan could not be loaded. No data was deleted."
            members = c.get("members", [])
            return True, (
                f"🏯 **{c['name']}**\n"
                f"👑 Leader: {c.get('leader_name', 'Unknown')}\n"
                f"👥 Members: {len(members)}\n"
                f"💰 Treasury: ¥{c.get('treasury', 0):,}\n"
                f"⭐ Level: {c.get('level', 1)}\n"
                f"📜 {c.get('description', 'A clan of powerful sorcerers.')}"
            )

        if action == "create":
            if not value:
                return False, "Usage: `/clan create <clan name>`"
            cname_key = value.lower().strip()
            if p.get("clan"):
                return False, f"You are already in clan **{p['clan']}**. Leave first with `/clan leave`."
            if cname_key in self.clans:
                return False, f"A clan named **{value}** already exists. Try `/clan join {value}`."
            clan = {
                "name":        value,
                "key":         cname_key,
                "clan_key":    cname_key,
                "leader":      user_id,
                "leader_name": "Leader",
                "members":     [user_id],
                "treasury":    0,
                "level":       1,
                "description": f"The {value} clan stands strong.",
            }
            self._persist_clan(clan)
            self.clans[cname_key] = clan
            p["clan"] = cname_key
            if self.db:
                self.db.set_player_clan(user_id, cname_key)
            return True, (
                f"🏯 Clan **{value}** has been founded!\n"
                f"Invite others with `/clan join {value}`\n"
                f"Grow your clan with `/clan contribute <yen>`"
            )

        if action == "join":
            if not value:
                return False, "Usage: `/clan join <clan name>`"
            cname_key = value.lower().strip()
            if p.get("clan"):
                return False, f"You are already in clan **{p['clan']}**. Use `/clan leave` first."
            self._load_persistent_clans()
            c = self.clans.get(cname_key)
            if not c:
                # Show available clans
                if self.clans:
                    names = ", ".join(v['name'] for v in self.clans.values())
                    return False, f"Clan **{value}** not found.\nAvailable clans: {names}"
                return False, "Clan not found. Create one with `/clan create <name>`."
            if user_id not in c.setdefault("members", []):
                c["members"].append(user_id)
            p["clan"] = cname_key
            if self.db:
                self.db.set_player_clan(user_id, cname_key)
                self._persist_clan(c)
            return True, f"🏯 You joined clan **{c['name']}**! ({len(c['members'])} members)"

        if action == "leave":
            cname_key = p.get("clan")
            if not cname_key:
                return False, "You are not in a clan."
            self._load_persistent_clans()
            c = self.clans.get(cname_key)
            if c:
                c.setdefault("members", [])
                if user_id in c["members"]:
                    c["members"].remove(user_id)
                # Never delete a clan automatically. Preserve its record even
                # when its last member leaves, so crashes/restarts cannot
                # destroy treasury, inventory, upgrades, or statistics.
                if c.get("leader") == user_id and c["members"]:
                    # Transfer leadership
                    c["leader"] = c["members"][0]
                self._persist_clan(c)
            p["clan"] = None
            if self.db:
                self.db.set_player_clan(user_id, None)
            clan_name = c['name'] if c else cname_key
            return True, f"You have left clan **{clan_name}**."

        if action == "contribute":
            try:
                amount = int(value)
            except (ValueError, TypeError):
                return False, "Usage: `/clan contribute <amount>` — amount must be a number."
            if amount <= 0:
                return False, "Contribution must be positive."
            cname_key = p.get("clan")
            if not cname_key:
                return False, "You are not in a clan. Join one first."
            # Deduct from player yen
            if self.db:
                player_data = self.db.get_player(user_id)
                if not player_data or player_data.get("yen", 0) < amount:
                    return False, f"Not enough yen. You have ¥{player_data.get('yen', 0):,}."
                self.db.deduct_yen(user_id, amount)
            self._load_persistent_clans()
            c = self.clans.get(cname_key)
            if not c:
                return False, "Your clan no longer exists."
            c["treasury"] = c.get("treasury", 0) + amount
            # Level up clan every 1,000,000 yen
            level = max(1, c["treasury"] // 1_000_000 + 1)
            c["level"] = level
            self._persist_clan(c)
            return True, (
                f"💰 Contributed ¥{amount:,} to **{c['name']}**!\n"
                f"🏯 Treasury: ¥{c['treasury']:,} | Level: {c['level']}"
            )

        if action == "info":
            self._load_persistent_clans()
            cname_key = (value or p.get("clan") or "").lower().strip()
            if not cname_key:
                return False, "Usage: `/clan info <name>` or use `/clan status` for your own clan."
            c = self.clans.get(cname_key)
            if not c:
                return False, f"Clan **{value}** not found."
            members = c.get("members", [])
            return True, (
                f"🏯 **{c['name']}** (Level {c.get('level', 1)})\n"
                f"👑 Leader ID: {c.get('leader', '?')}\n"
                f"👥 Members: {len(members)}\n"
                f"💰 Treasury: ¥{c.get('treasury', 0):,}\n"
                f"📜 {c.get('description', '')}"
            )

        if action == "list":
            self._load_persistent_clans()
            if not self.clans:
                return True, "No clans exist yet. Be the first! `/clan create <name>`"
            lines = [f"🏯 **Active Clans** ({len(self.clans)} total)\n"]
            for c in list(self.clans.values())[:10]:
                lines.append(
                    f"• **{c['name']}** — {len(c.get('members', []))} members | "
                    f"Lv.{c.get('level', 1)} | ¥{c.get('treasury', 0):,}"
                )
            return True, "\n".join(lines)

        return False, (
            "❓ Unknown action. Available:\n"
            "• `/clan status` — your clan info\n"
            "• `/clan create <name>` — found a clan\n"
            "• `/clan join <name>` — join a clan\n"
            "• `/clan leave` — leave your clan\n"
            "• `/clan contribute <yen>` — donate to treasury\n"
            "• `/clan info <name>` — inspect any clan\n"
            "• `/clan list` — all clans"
        )

    # ─── Story / NPC / missions ──────────────────────────────────────────────

    def story(self, user_id, choice=None):
        p = self._ensure(user_id)
        if not choice:
            return p["story"]
        if choice.lower().startswith("investigate"):
            p["story"]["scene"] += 1
        else:
            p["story"]["scene"] += 1
        return p["story"]

    def npcs(self):
        return [
            {"name": "Principal Yaga",  "kind": "mentor", "description": "Guides new sorcerers."},
            {"name": "Cursed Merchant", "kind": "vendor", "description": "Sells rare tools."},
        ]

    def extended_missions(self, user_id):
        return [
            {"name": "Purge the Alley", "completed": False, "progress": 0,
             "target": 10, "reward_yen": 5000, "reward_xp": 200, "period": "weekly"}
        ]

    # ─── Crafting / materials / market ───────────────────────────────────────

    def recipes(self):
        return [
            {"name": "Healing Potion",      "requirements": "3 Herbs"},
            {"name": "Cursed Energy Tonic",  "requirements": "2 Essence + 1 Scrap"},
        ]

    def material_summary(self, user_id):
        p = self._ensure(user_id)
        if not p["materials"]:
            return "No materials. Earn them by winning battles!"
        return "\n".join(f"• {k}: {v}" for k, v in p["materials"].items())

    def craft(self, user_id, recipe):
        if recipe.lower() == "healing potion":
            return True, "Crafted Healing Potion."
        if recipe.lower() == "cursed energy tonic":
            return True, "Crafted Cursed Energy Tonic."
        return False, "Recipe unknown or requirements unmet."

    def enchant(self, user_id, gear_name, effect_name):
        p = self._ensure(user_id)
        for g in p.get("gear", []):
            if g["gear_name"].lower() == gear_name.lower():
                g["enchant"] = effect_name
                return True, f"Enchanted {gear_name} with {effect_name}!"
        return False, f"Gear '{gear_name}' not found in your inventory."

    # ─── Market ──────────────────────────────────────────────────────────────

    def market(self, user_id, action, item=None, price=0, listing_id=None):
        """
        Player-to-player marketplace.
        action: 'listings' | 'list' | 'buy'
        Note: self._listings is the dict — never self.market (that's this method).
        """
        if action == "listings":
            if not self._listings:
                return True, (
                    "🛒 **Market is empty!**\n"
                    "List items with `/market list <item> <price>`"
                )
            lines = []
            for lid, lst in self._listings.items():
                lines.append(
                    f"#{lid} **{lst['item']}** — ¥{lst['price']:,} "
                    f"(seller: {lst['seller_name']})"
                )
            return True, "🛒 **Market Listings**\n" + "\n".join(lines) + "\n\nBuy with `/market buy <#id>`"

        if action == "list":
            if not item:
                return False, "Usage: `/market list <item name> <price>`"
            if price <= 0:
                return False, "Price must be greater than 0."
            lid = self.next_listing_id
            seller_name = "Sorcerer"
            if self.db:
                seller_data = self.db.get_player(user_id)
                if seller_data:
                    seller_name = seller_data.get("display_name", "Sorcerer")
            self._listings[lid] = {
                "id":          lid,
                "item":        item,
                "price":       price,
                "seller":      user_id,
                "seller_name": seller_name,
            }
            self.next_listing_id += 1
            return True, f"✅ Listed **{item}** for ¥{price:,} (listing #{lid})"

        if action == "buy":
            if listing_id is None:
                return False, "Usage: `/market buy <listing id>`"
            lst = self._listings.get(listing_id)
            if not lst:
                return False, f"Listing #{listing_id} not found."
            if lst["seller"] == user_id:
                return False, "You can't buy your own listing!"
            if self.db:
                buyer = self.db.get_player(user_id)
                if not buyer or buyer.get("yen", 0) < lst["price"]:
                    return False, f"Not enough yen. Need ¥{lst['price']:,}."
                self.db.deduct_yen(user_id, lst["price"])
                self.db.add_yen(lst["seller"], lst["price"])
            del self._listings[listing_id]
            return True, f"✅ Purchased **{lst['item']}** for ¥{lst['price']:,}!"

        return False, "Usage: `/market` | `/market list <item> <price>` | `/market buy <id>`"

    # ─── Culling / prestige / endgame ────────────────────────────────────────

    def culling(self, user_id, action, colony):
        return True, (
            "⚔️ **Culling Game** is active!\n"
            "Eliminate cursed spirits and earn colony points.\n"
            "Use `/battle` to participate and gain ranking."
        )

    def prestige(self, user_id):
        p = self._ensure(user_id)
        p["prestige"] = p.get("prestige", 0) + 1
        return True, f"⭐ Prestiged! You are now Prestige **{p['prestige']}**."

    def endless(self, user_id, action, floor):
        return True, f"Endless {action} on floor {floor} (coming soon)"

    # ─── Achievements / cosmetics ────────────────────────────────────────────

    def achievements(self, user_id):
        p = self._ensure(user_id)
        return [{"name": a, "description": "Achievement unlocked.", "unlocked_at": True}
                for a in p.get("achievements", [])]

    def titles(self, user_id):
        p = self._ensure(user_id)
        return [{"name": t, "unlocked_at": True} for t in p.get("titles", [])]

    def cosmetics(self, user_id):
        p = self._ensure(user_id)
        return [{"name": c if isinstance(c, str) else c.get("cosmetic_name", "?"),
                 "kind": "skin", "description": "Visual cosmetic.", "unlocked_at": True}
                for c in p.get("cosmetics", [])]

    def unlock_cosmetic(self, user_id, name):
        p = self._ensure(user_id)
        p.setdefault("cosmetics", []).append({"cosmetic_name": name})
        return True, f"Unlocked cosmetic: {name}"

    def equip_cosmetic(self, user_id, name):
        p = self._ensure(user_id)
        for c in p.get("cosmetics", []):
            cname = c if isinstance(c, str) else c.get("cosmetic_name", "")
            if cname == name:
                return True, f"Equipped cosmetic: {name}"
        return False, "Cosmetic not unlocked."

    def weather(self):
        return self.weather_state

    # ─── Combat integration ──────────────────────────────────────────────────

    def combat_effect(self, user_id, move_name, damage):
        """Small chance for technique synergy bonus."""
        if random.random() < 0.05:
            return int(damage * 1.1), "Technique synergy! +10% damage"
        return damage, ""

    def award_battle_loot(self, user_id, grade):
        loot_table = {
            'Grade 4':       [("Scrap", 1),       ("Herb", 2)],
            'Grade 3':       [("Scrap", 2),       ("Essence", 1)],
            'Grade 2':       [("Essence", 2),     ("Rare Core", 1)],
            'Grade 1':       [("Rare Core", 1),   ("Essence", 3)],
            'Special Grade': [("Rare Core", 2),   ("Cursed Shard", 1)],
        }
        table  = loot_table.get(grade, loot_table['Grade 4'])
        mat, amount = random.choice(table)
        p = self._ensure(user_id)
        p.setdefault("materials", {})[mat] = p["materials"].get(mat, 0) + amount
        return mat, amount

    def awaken_from_trigger(self, user_id, trigger):
        p = self._ensure(user_id)
        gained = random.randint(1, 5)
        p["technique_mastery_exp"] += gained
        p["technique_mastery"] = min(
            100, p["technique_mastery"] + p["technique_mastery_exp"] // 10
        )
        if gained:
            return f"Gained {gained} technique mastery EXP from {trigger}."
        return None

    def unlock_achievement(self, user_id, name):
        p = self._ensure(user_id)
        if name not in p.setdefault("achievements", []):
            p["achievements"].append(name)
        return True

    def resolve_move(self, user_id, move_input: str):
        """
        Hook for expansion skill-tree moves.
        Returns a move dict if the input matches a known expansion move,
        or None to fall through to the regular move resolver.
        Currently a stub — returns None so the regular flow handles everything.
        """
        return None
