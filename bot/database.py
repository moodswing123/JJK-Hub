"""
Database Manager for JJK Bot — PostgreSQL (Neon) backend
"""

import json
import random
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from config import (
    POSTGRES_URL, LEVEL_GAIN_ATK, LEVEL_GAIN_DEF,
    LEVEL_GAIN_SPD, LEVEL_GAIN_HP, LEVEL_GAIN_CE, MAX_LEVEL
)


class _Cur:
    """Thin wrapper so caller can do conn.execute(...).fetchone() like sqlite3."""

    def __init__(self, cursor):
        self._c = cursor

    def execute(self, sql: str, params=None):
        self._c.execute(sql, params)
        return self

    def executemany(self, sql: str, seq):
        self._c.executemany(sql, seq)
        return self

    def fetchone(self):
        return self._c.fetchone()  # RealDictCursor → dict or None

    def fetchall(self):
        return self._c.fetchall()  # RealDictCursor → list[dict]


class Database:
    def __init__(self):
        self._init_db()
        self.seed_data()

    @contextmanager
    def _conn(self):
        conn = psycopg2.connect(POSTGRES_URL)
        try:
            cur = _Cur(conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    user_id     BIGINT PRIMARY KEY,
                    username    TEXT,
                    display_name TEXT,
                    character_id INTEGER,
                    level       INTEGER DEFAULT 1,
                    xp          INTEGER DEFAULT 0,
                    xp_needed   INTEGER DEFAULT 100,
                    rank        TEXT DEFAULT 'Grade 4',
                    yen         INTEGER DEFAULT 5000,
                    hp          INTEGER DEFAULT 100,
                    max_hp      INTEGER DEFAULT 100,
                    cursed_energy INTEGER DEFAULT 50,
                    max_cursed_energy INTEGER DEFAULT 50,
                    attack      INTEGER DEFAULT 10,
                    defense     INTEGER DEFAULT 5,
                    speed       INTEGER DEFAULT 10,
                    wins        INTEGER DEFAULT 0,
                    losses      INTEGER DEFAULT 0,
                    techniques  TEXT DEFAULT '[]',
                    artifacts   TEXT DEFAULT '[]',
                    inventory   TEXT DEFAULT '[]',
                    last_daily  TEXT,
                    created_at  TEXT,
                    faction     TEXT,
                    last_active_at TEXT,
                    clan_key    TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_credentials (
                    user_id       BIGINT PRIMARY KEY REFERENCES players(user_id) ON DELETE CASCADE,
                    web_username  TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_reset_tokens (
                    id            BIGSERIAL PRIMARY KEY,
                    user_id       BIGINT NOT NULL REFERENCES players(user_id) ON DELETE CASCADE,
                    token_hash    TEXT NOT NULL,
                    expires_at    TEXT NOT NULL,
                    used_at       TEXT,
                    created_at    TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT,
                    grade       TEXT,
                    quote       TEXT,
                    technique   TEXT,
                    attack      INTEGER,
                    defense     INTEGER,
                    speed       INTEGER,
                    max_hp      INTEGER,
                    max_ce      INTEGER,
                    cost        INTEGER DEFAULT 0,
                    image_url   TEXT,
                    attacks     TEXT DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT,
                    description TEXT,
                    price       INTEGER,
                    type        TEXT,
                    effect      TEXT,
                    image_url   TEXT,
                    use_description TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS techniques (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT,
                    description TEXT,
                    energy_cost INTEGER,
                    damage_multiplier DOUBLE PRECISION,
                    character_id INTEGER DEFAULT 1,
                    level_required INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pvp_battles (
                    battle_id   SERIAL PRIMARY KEY,
                    chat_id     BIGINT,
                    player1_id  BIGINT,
                    player2_id  BIGINT,
                    player1_hp  INTEGER,
                    player2_hp  INTEGER,
                    player1_max_hp INTEGER,
                    player2_max_hp INTEGER,
                    player1_ce  INTEGER,
                    player2_ce  INTEGER,
                    player1_max_ce INTEGER,
                    player2_max_ce INTEGER,
                    round       INTEGER DEFAULT 1,
                    p1_move     TEXT,
                    p2_move     TEXT,
                    status      TEXT DEFAULT 'active',
                    first_attacker BIGINT,
                    created_at  TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT,
                    name        TEXT,
                    description TEXT,
                    mission_type TEXT,
                    target_value INTEGER,
                    current_value INTEGER DEFAULT 0,
                    reward_yen  INTEGER,
                    reward_xp   INTEGER,
                    completed   INTEGER DEFAULT 0,
                    date        TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_domains (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT,
                    domain_name TEXT,
                    power       INTEGER,
                    equipped    INTEGER DEFAULT 0,
                    created_at  TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pvp_chat_status ON pvp_battles(chat_id, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pvp_p1 ON pvp_battles(player1_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pvp_p2 ON pvp_battles(player2_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_missions_user_date ON missions(user_id, date)"
            )
            # Additive migrations preserve existing player, economy, and battle data.
            conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS faction TEXT")
            conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS last_active_at TEXT")
            conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS clan_key TEXT")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_characters (
                    user_id BIGINT NOT NULL,
                    character_id INTEGER NOT NULL,
                    purchased_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, character_id)
                )
            """)
            conn.execute("""
                INSERT INTO player_characters (user_id, character_id, purchased_at)
                SELECT user_id, character_id, COALESCE(created_at, NOW()::text)
                FROM players
                WHERE character_id IS NOT NULL
                ON CONFLICT DO NOTHING
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clans (
                    clan_key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    leader BIGINT NOT NULL,
                    leader_name TEXT,
                    members JSONB NOT NULL DEFAULT '[]'::jsonb,
                    treasury BIGINT NOT NULL DEFAULT 0,
                    inventory JSONB NOT NULL DEFAULT '{}'::jsonb,
                    level INTEGER NOT NULL DEFAULT 1,
                    upgrades JSONB NOT NULL DEFAULT '[]'::jsonb,
                    statistics JSONB NOT NULL DEFAULT '{}'::jsonb,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clan_transactions (
                    id BIGSERIAL PRIMARY KEY,
                    clan_key TEXT NOT NULL,
                    actor_id BIGINT NOT NULL,
                    recipient_id BIGINT,
                    amount BIGINT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clans_leader ON clans(leader)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clan_transactions_clan ON clan_transactions(clan_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_players_active ON players(last_active_at DESC)")

    # ───────────────────────────────────────────────
    # SEED DATA
    # ───────────────────────────────────────────────

    def seed_data(self):
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM characters").fetchone()
            if row['cnt'] > 0:
                return

        characters = [
            # (id, name, grade, quote, technique, atk, def, spd, max_hp, max_ce, cost, attacks_json)
            (1, 'Yuji Itadori', 'Grade 2',
             "I don't know how I'll feel when I'm dead, but I don't want to regret the way I lived!",
             'Divergent Fist', 85, 70, 95, 120, 80, 0,
             json.dumps([
                 {"num": 1, "name": "Divergent Fist", "ce_cost": 15, "dmg_mult": 2.1,
                  "description": "Delayed CE burst hits twice — 2.1x damage", "effect": "Double-strike with delayed cursed energy"},
                 {"num": 2, "name": "Black Flash", "ce_cost": 25, "dmg_mult": 2.8,
                  "description": "Perfect sync between physical and CE — 2.8x damage", "effect": "Critical sync attack, ignores 20% defense"},
                 {"num": 3, "name": "Mahoraga's Adaptation", "ce_cost": 35, "dmg_mult": 3.2,
                  "description": "Channels Mahoraga's wheel — 3.2x damage", "effect": "Adapts to opponent's last attack for bonus damage"},
             ])),
            (2, 'Megumi Fushiguro', 'Grade 2',
             "I'll save people unequally.",
             'Ten Shadows Technique', 75, 80, 70, 100, 100, 500000,
             json.dumps([
                 {"num": 1, "name": "Divine Dog: Totality", "ce_cost": 18, "dmg_mult": 2.1,
                  "description": "Merged Divine Dogs unleashed — 2.1x damage", "effect": "Tracking attack, cannot miss"},
                 {"num": 2, "name": "Chimera Shadow Garden", "ce_cost": 30, "dmg_mult": 2.8,
                  "description": "Incomplete domain of shadows — 2.8x damage", "effect": "Summons shikigami from shadows"},
                 {"num": 3, "name": "Mahoraga Summon", "ce_cost": 40, "dmg_mult": 3.5,
                  "description": "Unleash the Eight-Handled Wheel — 3.5x damage", "effect": "Devastating summon, costs HP if opponent adapts"},
             ])),
            (3, 'Nobara Kugisaki', 'Grade 3',
             "What makes us obligated to meet such perfection or such absurd standards?",
             'Straw Doll Technique', 80, 60, 75, 90, 70, 400000,
             json.dumps([
                 {"num": 1, "name": "Hairpin", "ce_cost": 15, "dmg_mult": 1.9,
                  "description": "Detonate nails with CE — 1.9x damage", "effect": "Piercing damage, ignores low defense"},
                 {"num": 2, "name": "Resonance", "ce_cost": 25, "dmg_mult": 2.5,
                  "description": "Shared pain curse technique — 2.5x damage", "effect": "Reflects 30% of next hit back to attacker"},
                 {"num": 3, "name": "Straw Doll: Maximum", "ce_cost": 35, "dmg_mult": 3.0,
                  "description": "Curse doll with maximum CE output — 3.0x damage", "effect": "Haunts opponent, dealing damage over next 2 turns"},
             ])),
            (4, 'Satoru Gojo', 'Special Grade',
             "Nah, I'd win.",
             'Limitless / Six Eyes', 150, 120, 130, 200, 200, 10000000,
             json.dumps([
                 {"num": 1, "name": "Hollow Purple", "ce_cost": 30, "dmg_mult": 3.0,
                  "description": "Merges Red and Blue into devastating orb — 3.0x damage", "effect": "Erases everything in its path"},
                 {"num": 2, "name": "Domain Expansion: Unlimited Void", "ce_cost": 40, "dmg_mult": 3.5,
                  "description": "Traps opponents in infinite information — 3.5x damage", "effect": "Opponent skips next turn, overwhelmed by infinity"},
                 {"num": 3, "name": "Limitless: Blue", "ce_cost": 20, "dmg_mult": 2.0,
                  "description": "Gravitational attraction force — 2.0x damage", "effect": "Pulls opponent in, guaranteed hit"},
             ])),
            (5, 'Ryomen Sukuna', 'Special Grade',
             "I'm the king of curses!",
             'Dismantle / Cleave', 155, 125, 135, 210, 210, 10000000,
             json.dumps([
                 {"num": 1, "name": "Dismantle", "ce_cost": 20, "dmg_mult": 2.5,
                  "description": "Omnidirectional slashing — 2.5x damage", "effect": "Cuts through any defense"},
                 {"num": 2, "name": "Cleave", "ce_cost": 25, "dmg_mult": 2.8,
                  "description": "Scales to target's durability — 2.8x damage", "effect": "Bonus damage against high-defense targets"},
                 {"num": 3, "name": "Domain Expansion: Malevolent Shrine", "ce_cost": 40, "dmg_mult": 3.5,
                  "description": "Open-air domain with guaranteed kill zone — 3.5x damage", "effect": "Continuously deals damage each round while active"},
             ])),
            (6, 'Yuta Okkotsu', 'Special Grade',
             "I'm not a monster anymore. I have people who care about me.",
             'Copy / Rika', 140, 110, 120, 180, 180, 5000000,
             json.dumps([
                 {"num": 1, "name": "Rika Manifestation", "ce_cost": 25, "dmg_mult": 2.6,
                  "description": "Summons Rika's overwhelming curse — 2.6x damage", "effect": "Increases all stats by 20% for this attack"},
                 {"num": 2, "name": "Copy: Inumaki's Cursed Speech", "ce_cost": 30, "dmg_mult": 2.4,
                  "description": "Copies Cursed Speech — 2.4x damage", "effect": "Silences opponent, they can only use basic attack next turn"},
                 {"num": 3, "name": "True Mutual Love: Maximum", "ce_cost": 45, "dmg_mult": 3.8,
                  "description": "Yuta and Rika's full power unleashed — 3.8x damage", "effect": "Ultimate form, massively boosts damage"},
             ])),
            (7, 'Kinji Hakari', 'Grade 1',
             "I'm always on a roll!",
             'Private Pure Love Train', 100, 90, 95, 140, 120, 2000000,
             json.dumps([
                 {"num": 1, "name": "Jackpot Roller", "ce_cost": 20, "dmg_mult": 2.2,
                  "description": "Gambling-based CE surge — 2.2x damage", "effect": "30% chance to trigger jackpot for double damage"},
                 {"num": 2, "name": "Idle Death Gamble", "ce_cost": 30, "dmg_mult": 2.7,
                  "description": "Death defying CE release — 2.7x damage", "effect": "If HP below 50%, restores 30 HP on hit"},
                 {"num": 3, "name": "Domain: Restless Gambler", "ce_cost": 40, "dmg_mult": 3.3,
                  "description": "Hakari's domain of infinite luck — 3.3x damage", "effect": "Jackpot: grants full CE restoration on win"},
             ])),
            (8, 'Aoi Todo', 'Grade 1',
             "What is your type of woman?",
             'Boogie Woogie', 110, 100, 85, 150, 100, 1500000,
             json.dumps([
                 {"num": 1, "name": "Boogie Woogie", "ce_cost": 18, "dmg_mult": 2.0,
                  "description": "Position swap technique — 2.0x damage", "effect": "Swaps position to dodge opponent's next attack"},
                 {"num": 2, "name": "Divergent Fist Copy", "ce_cost": 28, "dmg_mult": 2.6,
                  "description": "Imitates Yuji's divergent fist — 2.6x damage", "effect": "Synergy bonus if Yuji Itadori is equipped"},
                 {"num": 3, "name": "Besto Friendo Power", "ce_cost": 38, "dmg_mult": 3.1,
                  "description": "Peak brotherly power — 3.1x damage", "effect": "Massive CE surge, temporarily boosts attack by 50%"},
             ])),
            (9, 'Choso', 'Grade 1',
             "Brothers fight for brothers.",
             'Blood Manipulation', 95, 85, 75, 130, 110, 1800000,
             json.dumps([
                 {"num": 1, "name": "Piercing Blood", "ce_cost": 20, "dmg_mult": 2.3,
                  "description": "Needle-thin blood projectile — 2.3x damage", "effect": "Piercing attack, ignores 25% defense"},
                 {"num": 2, "name": "Supernova", "ce_cost": 30, "dmg_mult": 2.7,
                  "description": "Explosive blood burst — 2.7x damage", "effect": "Area blast, deals splash damage"},
                 {"num": 3, "name": "Blood Edge", "ce_cost": 35, "dmg_mult": 3.0,
                  "description": "Bladed blood projectiles at max density — 3.0x damage", "effect": "Bleeding effect: opponent loses HP next turn"},
             ])),
            (10, 'Hiromi Higuruma', 'Grade 1',
             "Justice will prevail.",
             'Cursed Judgment', 105, 95, 80, 145, 105, 1700000,
             json.dumps([
                 {"num": 1, "name": "Deadly Sentencing", "ce_cost": 22, "dmg_mult": 2.4,
                  "description": "Legal judgment strike — 2.4x damage", "effect": "Disables one opponent technique for 2 turns"},
                 {"num": 2, "name": "Confiscation", "ce_cost": 28, "dmg_mult": 2.5,
                  "description": "Strips opponent's technique — 2.5x damage", "effect": "Reduces opponent attack by 30% for 1 turn"},
                 {"num": 3, "name": "Domain: Deadly Sentencing", "ce_cost": 40, "dmg_mult": 3.2,
                  "description": "Domain of absolute judgment — 3.2x damage", "effect": "Condemns opponent, preventing healing"},
             ])),
            (11, 'Maki Zenin', 'Grade 2',
             "I don't need cursed energy to exorcise cursed spirits.",
             'Heavenly Restriction', 90, 70, 85, 110, 60, 500000,
             json.dumps([
                 {"num": 1, "name": "Playful Cloud Strike", "ce_cost": 10, "dmg_mult": 2.0,
                  "description": "Three-section staff mastery — 2.0x damage", "effect": "No CE wasted, highly efficient attack"},
                 {"num": 2, "name": "Heavenly Restriction Burst", "ce_cost": 15, "dmg_mult": 2.5,
                  "description": "Pure physical strength — 2.5x damage", "effect": "Ignores cursed energy defenses entirely"},
                 {"num": 3, "name": "Zenin Supremacy", "ce_cost": 25, "dmg_mult": 3.0,
                  "description": "Peak Heavenly Restriction output — 3.0x damage", "effect": "Speed doubles for this attack, strikes twice"},
             ])),
            (12, 'Toge Inumaki', 'Grade 2',
             "Salmon.",
             'Cursed Speech', 70, 65, 80, 85, 90, 400000,
             json.dumps([
                 {"num": 1, "name": "Don't Move", "ce_cost": 20, "dmg_mult": 1.8,
                  "description": "Voice command to freeze — 1.8x damage", "effect": "Opponent cannot attack next turn"},
                 {"num": 2, "name": "Blast Away", "ce_cost": 25, "dmg_mult": 2.3,
                  "description": "Explosive verbal command — 2.3x damage", "effect": "Pushback effect, reduces enemy speed"},
                 {"num": 3, "name": "Die", "ce_cost": 40, "dmg_mult": 3.5,
                  "description": "Ultimate cursed speech — 3.5x damage (injures user)", "effect": "Extreme damage but user loses 20 HP"},
             ])),
            (13, 'Panda', 'Grade 2',
             "I'm not a panda, I'm Panda!",
             'Panda Core', 85, 85, 70, 130, 70, 450000,
             json.dumps([
                 {"num": 1, "name": "Crashing Attack", "ce_cost": 15, "dmg_mult": 2.0,
                  "description": "Gorilla core strike — 2.0x damage", "effect": "Knockback, opponent loses 10 speed next turn"},
                 {"num": 2, "name": "Gorilla Mode", "ce_cost": 25, "dmg_mult": 2.5,
                  "description": "Switches to Gorilla core — 2.5x damage", "effect": "Gains 30% attack boost for next 2 turns"},
                 {"num": 3, "name": "Triune Assault", "ce_cost": 35, "dmg_mult": 3.0,
                  "description": "All three cores activated — 3.0x damage", "effect": "Hits three times with split damage"},
             ])),
            (14, 'Jogo', 'Grade 1 (Curse)',
             "Humans are weak.",
             'Cursed Fire', 120, 100, 75, 160, 130, 2500000,
             json.dumps([
                 {"num": 1, "name": "Ember Insects", "ce_cost": 20, "dmg_mult": 2.2,
                  "description": "Fire insect swarm — 2.2x damage", "effect": "Burn effect: 15 damage next turn"},
                 {"num": 2, "name": "Maximum: Meteor", "ce_cost": 35, "dmg_mult": 3.0,
                  "description": "Calls down a meteor — 3.0x damage", "effect": "Massive area damage, cannot be blocked"},
                 {"num": 3, "name": "Domain: Coffin of the Iron Mountain", "ce_cost": 45, "dmg_mult": 3.6,
                  "description": "Volcanic domain — 3.6x damage", "effect": "Extreme heat damages opponent every round"},
             ])),
            (15, 'Mahito', 'Grade 1 (Curse)',
             "Humans are so fascinating.",
             'Idle Transfiguration', 115, 95, 90, 150, 120, 2300000,
             json.dumps([
                 {"num": 1, "name": "Soul Transfiguration", "ce_cost": 22, "dmg_mult": 2.4,
                  "description": "Reshapes opponent's soul — 2.4x damage", "effect": "Reduces opponent's max HP by 20 permanently"},
                 {"num": 2, "name": "Self-Embodiment of Perfection", "ce_cost": 30, "dmg_mult": 2.8,
                  "description": "Optimizes own body shape — 2.8x damage", "effect": "Heals 30 HP while attacking"},
                 {"num": 3, "name": "Domain: Self-Embodiment of Perfection", "ce_cost": 42, "dmg_mult": 3.4,
                  "description": "Perfect form domain — 3.4x damage", "effect": "Touches opponent's soul, bypasses all defense"},
             ])),
            (16, 'Dagon', 'Grade 1 (Curse)',
             "My domain is supreme.",
             'Aquatic Manipulation', 110, 105, 70, 155, 140, 2200000,
             json.dumps([
                 {"num": 1, "name": "Tidal Wave", "ce_cost": 20, "dmg_mult": 2.1,
                  "description": "Crushing water assault — 2.1x damage", "effect": "Reduces opponent speed by 15"},
                 {"num": 2, "name": "Death Swarm", "ce_cost": 30, "dmg_mult": 2.7,
                  "description": "Sea creature attack swarm — 2.7x damage", "effect": "Multiple hits, each can critically strike"},
                 {"num": 3, "name": "Domain: Horizon of the Captivating Skandha", "ce_cost": 45, "dmg_mult": 3.5,
                  "description": "Perfect aquatic domain — 3.5x damage", "effect": "All attacks guaranteed to hit inside domain"},
             ])),
            (17, 'Hanami', 'Grade 1 (Curse)',
             "Protect nature.",
             'Plant Manipulation', 100, 110, 65, 150, 135, 2100000,
             json.dumps([
                 {"num": 1, "name": "Flower Field", "ce_cost": 18, "dmg_mult": 2.0,
                  "description": "Cursed plant growth — 2.0x damage", "effect": "Roots opponent, they lose 10 speed next turn"},
                 {"num": 2, "name": "Root Bind", "ce_cost": 28, "dmg_mult": 2.5,
                  "description": "Entangle with cursed roots — 2.5x damage", "effect": "Opponent cannot flee battle"},
                 {"num": 3, "name": "Disaster Plants: Full Bloom", "ce_cost": 40, "dmg_mult": 3.2,
                  "description": "Nature's full destructive power — 3.2x damage", "effect": "Drain: opponent loses CE each turn"},
             ])),
            (18, 'Junpei Yoshino', 'Grade 3',
             "Strength comes from bonds.",
             'Shikigami: Moon Dregs', 60, 50, 70, 80, 50, 100000,
             json.dumps([
                 {"num": 1, "name": "Moon Dregs Strike", "ce_cost": 12, "dmg_mult": 1.8,
                  "description": "Shikigami venom attack — 1.8x damage", "effect": "Poison: deals 10 damage next turn"},
                 {"num": 2, "name": "Jellyfish Surge", "ce_cost": 20, "dmg_mult": 2.1,
                  "description": "Jellyfish swarm release — 2.1x damage", "effect": "Multiple stings, stacks poison"},
                 {"num": 3, "name": "Moon Dregs: Maximum", "ce_cost": 30, "dmg_mult": 2.6,
                  "description": "Full shikigami manifestation — 2.6x damage", "effect": "Massive venom burst"},
             ])),
            (19, 'Arata Nitta', 'Grade 4',
             "I'm doing my best!",
             'Wound Stabilization', 45, 55, 65, 70, 60, 50000,
             json.dumps([
                 {"num": 1, "name": "Stabilize Wound", "ce_cost": 15, "dmg_mult": 1.5,
                  "description": "Seals wounds to deal damage — 1.5x damage", "effect": "Restores 25 HP to self"},
                 {"num": 2, "name": "Pressure Strike", "ce_cost": 20, "dmg_mult": 1.8,
                  "description": "Concentrated CE strike — 1.8x damage", "effect": "Steady, reliable damage"},
                 {"num": 3, "name": "Desperate Surge", "ce_cost": 28, "dmg_mult": 2.2,
                  "description": "Full CE release — 2.2x damage", "effect": "Goes all-out, risks self with high reward"},
             ])),
            (20, 'Kento Nanami', 'Grade 1',
             "Work smarter, not harder.",
             'Overtime / Ratio Technique', 105, 100, 85, 145, 110, 1900000,
             json.dumps([
                 {"num": 1, "name": "Ratio Technique: Collapse", "ce_cost": 20, "dmg_mult": 2.3,
                  "description": "7:3 weak point strike — 2.3x damage", "effect": "Always hits the weak point, ignores 20% defense"},
                 {"num": 2, "name": "Overtime: Power Surge", "ce_cost": 28, "dmg_mult": 2.8,
                  "description": "After-hours amplification — 2.8x damage", "effect": "Attack power boosted by 50% when HP below 60%"},
                 {"num": 3, "name": "Blade: Thousand Slashes", "ce_cost": 38, "dmg_mult": 3.2,
                  "description": "Methodical overwhelming barrage — 3.2x damage", "effect": "Ten precise strikes on critical weak points"},
             ])),
            (21, 'Shoko Ieiri', 'Grade 1',
             "I'll heal you right up.",
             'Reverse Cursed Technique', 65, 70, 75, 95, 100, 1000000,
             json.dumps([
                 {"num": 1, "name": "Cursed Energy Heal-Strike", "ce_cost": 20, "dmg_mult": 1.6,
                  "description": "Reverse CE turned offensive — 1.6x damage", "effect": "Heals self for 40 HP while attacking"},
                 {"num": 2, "name": "Inverted CE Burst", "ce_cost": 28, "dmg_mult": 2.0,
                  "description": "Concentrated reverse CE — 2.0x damage", "effect": "Disrupts opponent's CE flow, reduces their max CE by 10"},
                 {"num": 3, "name": "Maximum Reversal", "ce_cost": 40, "dmg_mult": 2.8,
                  "description": "Full reverse CE detonation — 2.8x damage", "effect": "Full HP restore while dealing massive damage"},
             ])),
            (22, 'Mitsuki Bakugo Parallel', 'Grade 2',
             "I will surpass everyone!",
             'Explosion Style', 95, 75, 100, 120, 95, 700000,
             json.dumps([
                 {"num": 1, "name": "AP Shot", "ce_cost": 18, "dmg_mult": 2.1,
                  "description": "Focused CE explosion — 2.1x damage", "effect": "Precise strike, ignores 15% defense"},
                 {"num": 2, "name": "Explosion Surge", "ce_cost": 28, "dmg_mult": 2.6,
                  "description": "CE-fueled explosion burst — 2.6x damage", "effect": "Blasts opponent, reducing their defense"},
                 {"num": 3, "name": "Howitzer Impact", "ce_cost": 38, "dmg_mult": 3.2,
                  "description": "Maximum explosion output — 3.2x damage", "effect": "Devastating area explosion, cannot be blocked"},
             ])),
            (23, "Sukuna's Vessel (Ancient)", 'Special Grade',
             "King of Curses reborn!",
             'Heian Era Techniques', 160, 130, 140, 220, 220, 12000000,
             json.dumps([
                 {"num": 1, "name": "Malevolent Shrine Slash", "ce_cost": 30, "dmg_mult": 3.0,
                  "description": "Ancient Sukuna slash — 3.0x damage", "effect": "Destroys terrain, no defense possible"},
                 {"num": 2, "name": "Fire Arrow", "ce_cost": 35, "dmg_mult": 3.2,
                  "description": "Heian-era fire technique — 3.2x damage", "effect": "Burn: 25 damage next 2 turns"},
                 {"num": 3, "name": "World Cutting Slash", "ce_cost": 50, "dmg_mult": 4.0,
                  "description": "The most powerful slash in existence — 4.0x damage", "effect": "Cleaves through all defenses and domains"},
             ])),
            (24, 'Geto (Cursed)', 'Special Grade',
             "Thousand Curses Army",
             'Cursed Spirit Manipulation', 135, 115, 110, 185, 175, 9000000,
             json.dumps([
                 {"num": 1, "name": "Maximum: Uzumaki", "ce_cost": 30, "dmg_mult": 2.9,
                  "description": "Absorbs all curses into one devastating beam — 2.9x damage", "effect": "Cannot be dodged, goes through all barriers"},
                 {"num": 2, "name": "Spirit Army Release", "ce_cost": 38, "dmg_mult": 3.2,
                  "description": "Releases thousands of curses — 3.2x damage", "effect": "Multiple curses attack simultaneously"},
                 {"num": 3, "name": "Infinite Void Mirror", "ce_cost": 48, "dmg_mult": 3.8,
                  "description": "Geto's ultimate technique — 3.8x damage", "effect": "Mirrors opponent's most powerful technique against them"},
             ])),
        ]

        techniques = [
            (1, 'Limitless', 'Control infinite space. 2.5x', 20, 2.5, 1, 1),
            (2, 'Six Eyes', 'See all cursed energy. 2.0x', 20, 2.0, 1, 50),
            (3, 'Domain Expansion: Infinite Void', 'Trap opponents in infinity. 3.0x', 30, 3.0, 1, 100),
            (4, 'Dismantle', 'Overwhelming slash. 2.8x', 25, 2.8, 1, 1),
            (5, 'Cleave', 'Cut through anything. 2.6x', 25, 2.6, 1, 1),
            (6, 'Domain Expansion: Malevolent Shrine', "Sukuna's domain. 3.2x", 35, 3.2, 1, 120),
            (7, 'Black Flash', 'Perfect strike. 2.2x', 20, 2.2, 1, 30),
            (8, 'Reverse Cursed Technique', 'Heal and support. 1.5x', 15, 1.5, 1, 50),
            (9, 'Cursed Energy Surge', 'Amplify power. 2.0x', 18, 2.0, 1, 20),
            (10, 'Divine Punishment', 'Heavenly strike. 2.4x', 22, 2.4, 1, 60),
            (11, 'Divergent Fist', 'Unpredictable punch. 2.1x', 18, 2.1, 1, 5),
            (12, 'Ten Shadows Technique', 'Summon shikigami. 2.3x', 22, 2.3, 1, 10),
            (13, 'Straw Doll Technique', 'Hammer from distance. 1.8x', 16, 1.8, 1, 15),
            (14, 'Cursed Spirit Manipulation', 'Command curses. 2.4x', 24, 2.4, 1, 80),
            (15, 'Boogie Woogie', 'Spatial swap. 2.2x', 20, 2.2, 1, 45),
            (16, 'Cursed Fire', 'Inferno. 2.6x', 24, 2.6, 1, 65),
            (17, 'Water Manipulation', 'Control water. 2.0x', 18, 2.0, 1, 35),
            (18, 'Electric Surge', 'Lightning strikes. 2.3x', 21, 2.3, 1, 55),
            (19, 'Barrier Technique', 'Defensive shield. 1.4x', 12, 1.4, 1, 20),
            (20, 'Shadow Clone', 'Create decoys. 1.7x', 15, 1.7, 1, 40),
        ]

        shop_items = [
            (1, 'Cursed Tool: Slaughter Demon', 'A blade imbued with cursed energy. +20 ATK',
             500000, 'weapon', '{"attack": 20}', None,
             'Equip to permanently gain +20 ATK. Use /equip to apply.'),
            (2, 'Cursed Tool: Chain of a Thousand Miles', 'A chain that extends infinitely. +15 ATK, +10 DEF',
             800000, 'weapon', '{"attack": 15, "defense": 10}', None,
             'Equip to permanently gain +15 ATK and +10 DEF. Use /equip to apply.'),
            (3, 'Reverse Cursed Technique Scroll', 'Learn to heal yourself. Unlocks Reverse Cursed Technique.',
             1500000, 'technique', '{"technique": "Reverse Cursed Technique"}', None,
             'Use /learn Reverse Cursed Technique to unlock this battle technique.'),
            (4, 'Cursed Energy Potion', 'Restores 50 CE instantly',
             100000, 'consumable', '{"ce": 50}', None,
             'Use /use Cursed Energy Potion to instantly restore 50 Cursed Energy.'),
            (5, 'Health Potion', 'Restores 50 HP instantly',
             100000, 'consumable', '{"hp": 50}', None,
             'Use /use Health Potion to instantly restore 50 HP.'),
            (6, 'Domain Expansion Blueprint', 'Blueprint to create your own domain expansion.',
             5000000, 'special', '{"special": "domain_creation"}', None,
             'Use /use Domain Expansion Blueprint [your domain name] to create your own domain. Your domain will have power 30% higher than your attack. Equip your domain for ¥1,500,000 to use it in battle.'),
            (7, 'Black Flash Training Manual', 'Master the perfect strike. Unlocks Black Flash technique.',
             2000000, 'technique', '{"technique": "Black Flash"}', None,
             'Use /learn Black Flash to add this devastating technique to your arsenal.'),
            (8, 'Grade Upgrade Token', 'Instantly upgrade your grade by one level.',
             2500000, 'upgrade', '{"grade_up": 1}', None,
             'Use /use Grade Upgrade Token to instantly advance to the next grade rank.'),
            (9, 'Cursed Spirit Binding Rope', 'Ancient rope that weakens spirits. +10 ATK, +15 DEF',
             600000, 'weapon', '{"attack": 10, "defense": 15}', None,
             'Equip to permanently gain +10 ATK and +15 DEF. Use /equip to apply.'),
            (10, 'Ancient Scroll Collection', 'Collection of lost techniques. Unlocks multiple powers.',
             3000000, 'technique', '{"technique": "Cursed Spirit Manipulation"}', None,
             'Use /learn Cursed Spirit Manipulation to control cursed spirits in battle.'),
            (11, 'Cursed Energy Elixir', 'JJK elixir brewed from minor curse remnants. +500 XP',
             50000, 'elixir', '{"xp": 500}', None,
             'Use /use Cursed Energy Elixir to absorb 500 XP of cursed knowledge.'),
            (12, "Sukuna's Blood Elixir", "A drop of the King's cursed blood. +2000 XP",
             300000, 'elixir', '{"xp": 2000}', None,
             "Use /use Sukuna's Blood Elixir to absorb 2000 XP from the King of Curses' power."),
            (13, "Heaven's Nectar", 'Sacred elixir from the heavens. +5000 XP',
             750000, 'elixir', '{"xp": 5000}', None,
             "Use /use Heaven's Nectar to absorb 5000 XP of divine cursed knowledge."),
            (14, 'Soul Elixir', 'Refined cursed soul essence. +1000 XP',
             100000, 'elixir', '{"xp": 1000}', None,
             'Use /use Soul Elixir to absorb 1000 XP from a purified cursed soul.'),
            (15, "Mahoraga's Essence", "Essence of the Eight-Handled Wheel. +10000 XP",
             2000000, 'elixir', '{"xp": 10000}', None,
             "Use /use Mahoraga's Essence to absorb 10000 XP by adapting to Mahoraga's power."),
            (16, 'Reverse Cursed Elixir', 'Elixir of reversed cursed technique. +3000 XP + 50 HP',
             500000, 'elixir', '{"xp": 3000, "hp": 50}', None,
             'Use /use Reverse Cursed Elixir to gain 3000 XP and restore 50 HP.'),
            (17, 'Limitless Shard', 'A fragment of infinity. +8000 XP + 100 CE',
             1500000, 'elixir', '{"xp": 8000, "ce": 100}', None,
             'Use /use Limitless Shard to gain 8000 XP and +100 permanent max CE.'),
        ]

        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO characters (id,name,grade,quote,technique,attack,defense,speed,max_hp,max_ce,cost,image_url,attacks) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                [(c[0],c[1],c[2],c[3],c[4],c[5],c[6],c[7],c[8],c[9],c[10],None,c[11]) for c in characters]
            )
            conn.executemany(
                "INSERT INTO techniques (id,name,description,energy_cost,damage_multiplier,character_id,level_required) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                techniques
            )
            conn.executemany(
                "INSERT INTO shop_items (id,name,description,price,type,effect,image_url,use_description) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                shop_items
            )

    # ───────────────────────────────────────────────
    # PLAYER METHODS
    # ───────────────────────────────────────────────

    def _parse_player(self, row: dict) -> Optional[Dict]:
        if row is None:
            return None
        p = dict(row)
        for field in ('techniques', 'artifacts', 'inventory'):
            try:
                p[field] = json.loads(p[field]) if p[field] else []
            except Exception:
                p[field] = []
        total = p.get('wins', 0) + p.get('losses', 0)
        p['win_rate'] = round(p['wins'] * 100.0 / total, 1) if total > 0 else 0
        return p

    def get_or_create_player(self, user_id: int, username: str, display_name: str) -> Dict:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM players WHERE user_id=%s", (user_id,)).fetchone()
            if not row:
                conn.execute(
                    """INSERT INTO players (user_id,username,display_name,character_id,level,xp,xp_needed,
                       rank,yen,hp,max_hp,cursed_energy,max_cursed_energy,attack,defense,speed,
                       wins,losses,techniques,artifacts,inventory,created_at,faction,last_active_at)
                       VALUES (%s,%s,%s,NULL,1,0,100,'Grade 4',5000,100,100,50,50,10,5,10,0,0,'[]','[]','[]',%s,%s,%s)""",
                    (user_id, username, display_name, now,
                     random.choice(('Sorcerer', 'Curse')), now)
                )
            else:
                conn.execute(
                    """UPDATE players SET username=%s, display_name=%s,
                       faction=COALESCE(faction,%s), last_active_at=%s WHERE user_id=%s""",
                    (username, display_name, random.choice(('Sorcerer', 'Curse')), now, user_id)
                )
        return self.get_player(user_id)

    def get_player(self, user_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM players WHERE user_id=%s", (user_id,)).fetchone()
            if row is None:
                return None
            return self._parse_player(row)

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE LOWER(username)=LOWER(%s) OR LOWER(display_name)=LOWER(%s)",
                (username, username)
            ).fetchone()
            return self._parse_player(row) if row else None

    def get_dashboard_credentials(self, user_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id, web_username, password_hash, created_at, updated_at FROM dashboard_credentials WHERE user_id=%s",
                (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_player_by_dashboard_username(self, web_username: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT p.*, c.web_username, c.password_hash
                   FROM dashboard_credentials c
                   JOIN players p ON p.user_id=c.user_id
                   WHERE LOWER(c.web_username)=LOWER(%s)""",
                (web_username,)
            ).fetchone()
            return dict(row) if row else None

    def save_dashboard_credentials(self, user_id: int, web_username: str, password_hash: str) -> bool:
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO dashboard_credentials (user_id, web_username, password_hash, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET web_username=%s, password_hash=%s, updated_at=%s""",
                (user_id, web_username, password_hash, now, now, web_username, password_hash, now)
            )
            return True

    def create_dashboard_reset_token(self, user_id: int, token_hash: str, expires_at: str) -> bool:
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute("UPDATE dashboard_reset_tokens SET used_at=%s WHERE user_id=%s AND used_at IS NULL", (now, user_id))
            conn.execute(
                "INSERT INTO dashboard_reset_tokens (user_id, token_hash, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                (user_id, token_hash, expires_at, now),
            )
            return True

    def consume_dashboard_reset_token(self, user_id: int, token_hash: str) -> bool:
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """UPDATE dashboard_reset_tokens SET used_at=%s
                   WHERE id=(SELECT id FROM dashboard_reset_tokens WHERE user_id=%s AND token_hash=%s AND used_at IS NULL AND expires_at > %s ORDER BY id DESC LIMIT 1)
                   RETURNING id""",
                (now, user_id, token_hash, now),
            ).fetchone()
            return bool(row)

    def get_all_players(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM players ORDER BY last_active_at DESC NULLS LAST, user_id"
            ).fetchall()
            return [self._parse_player(r) for r in rows]

    def set_faction(self, user_id: int, faction: str) -> bool:
        if faction not in ('Sorcerer', 'Curse'):
            return False
        with self._conn() as conn:
            cur = conn.execute("UPDATE players SET faction=%s WHERE user_id=%s", (faction, user_id))
            return cur._c.rowcount == 1

    def set_player_clan(self, user_id: int, clan_key: Optional[str]) -> bool:
        with self._conn() as conn:
            cur = conn.execute("UPDATE players SET clan_key=%s WHERE user_id=%s", (clan_key, user_id))
            return cur._c.rowcount == 1

    def get_player_listing(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT user_id, username, display_name, level, faction, last_active_at
                   FROM players ORDER BY last_active_at DESC NULLS LAST, display_name"""
            ).fetchall()
            return [dict(row) for row in rows]

    def add_yen(self, user_id: int, amount: int) -> int:
        with self._conn() as conn:
            conn.execute("UPDATE players SET yen=yen+%s WHERE user_id=%s", (amount, user_id))
            row = conn.execute("SELECT yen FROM players WHERE user_id=%s", (user_id,)).fetchone()
            return row['yen']

    def deduct_yen(self, user_id: int, amount: int) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT yen FROM players WHERE user_id=%s", (user_id,)).fetchone()
            if not row or row['yen'] < amount:
                return False
            conn.execute("UPDATE players SET yen=yen-%s WHERE user_id=%s", (amount, user_id))
            return True

    def remove_yen(self, user_id: int, amount: int) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT yen FROM players WHERE user_id=%s", (user_id,)).fetchone()
            current = row['yen'] if row else 0
            new_val = max(0, current - amount)
            conn.execute("UPDATE players SET yen=%s WHERE user_id=%s", (new_val, user_id))
            return new_val

    def set_player_character(self, user_id: int, character_id: int):
        with self._conn() as conn:
            char = conn.execute("SELECT * FROM characters WHERE id=%s", (character_id,)).fetchone()
            if char:
                conn.execute(
                    """UPDATE players SET character_id=%s,attack=%s,defense=%s,speed=%s,
                       max_hp=%s,hp=%s,max_cursed_energy=%s,cursed_energy=%s WHERE user_id=%s""",
                    (character_id, char['attack'], char['defense'], char['speed'],
                     char['max_hp'], char['max_hp'], char['max_ce'], char['max_ce'], user_id)
                )

    def get_owned_character_ids(self, user_id: int) -> List[int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT character_id FROM player_characters WHERE user_id=%s ORDER BY purchased_at, character_id",
                (user_id,)
            ).fetchall()
            return [int(row['character_id']) for row in rows]

    def get_owned_characters(self, user_id: int) -> List[Dict]:
        return [c for c in (self.get_character(cid) for cid in self.get_owned_character_ids(user_id)) if c]

    def player_owns_character(self, user_id: int, character_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM player_characters WHERE user_id=%s AND character_id=%s",
                (user_id, character_id)
            ).fetchone()
            return bool(row)

    def purchase_character(self, user_id: int, character_id: int) -> Dict:
        """Buy once, or equip an already-owned character, atomically."""
        with self._conn() as conn:
            character = conn.execute("SELECT * FROM characters WHERE id=%s", (character_id,)).fetchone()
            player = conn.execute("SELECT yen FROM players WHERE user_id=%s FOR UPDATE", (user_id,)).fetchone()
            if not character or not player:
                return {'ok': False, 'reason': 'not_found'}
            owned = conn.execute(
                "SELECT 1 FROM player_characters WHERE user_id=%s AND character_id=%s",
                (user_id, character_id)
            ).fetchone()
            if owned:
                conn.execute("UPDATE players SET character_id=%s WHERE user_id=%s", (character_id, user_id))
                return {'ok': True, 'owned': True, 'character': dict(character), 'remaining': int(player['yen'])}
            price = int(character['cost'] or 0)
            if int(player['yen']) < price:
                return {'ok': False, 'reason': 'funds', 'price': price, 'balance': int(player['yen'])}
            conn.execute(
                "UPDATE players SET yen=yen-%s, character_id=%s WHERE user_id=%s",
                (price, character_id, user_id)
            )
            conn.execute(
                "INSERT INTO player_characters (user_id,character_id,purchased_at) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (user_id, character_id, datetime.now().isoformat())
            )
            return {'ok': True, 'owned': False, 'character': dict(character),
                    'remaining': int(player['yen']) - price}

    def equip_owned_character(self, user_id: int, character_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM player_characters WHERE user_id=%s AND character_id=%s",
                (user_id, character_id)
            ).fetchone()
            if not row:
                return False
            conn.execute("UPDATE players SET character_id=%s WHERE user_id=%s", (character_id, user_id))
        self.recalc_player(user_id)
        return True

    def add_xp(self, user_id: int, amount: int):
        player = self.get_player(user_id)
        if not player:
            return
        xp = player['xp'] + amount
        xp_needed = player['xp_needed']
        level = player['level']
        atk = player['attack']
        def_ = player['defense']
        spd = player['speed']
        max_hp = player['max_hp']
        hp = player['hp']
        max_ce = player['max_cursed_energy']

        while xp >= xp_needed and level < MAX_LEVEL:
            xp -= xp_needed
            level += 1
            xp_needed = int(xp_needed * 1.5)
            atk += LEVEL_GAIN_ATK
            def_ += LEVEL_GAIN_DEF
            spd += LEVEL_GAIN_SPD
            hp_gain = min(LEVEL_GAIN_HP, max(0, 2000 - max_hp))
            max_hp = min(2000, max_hp + hp_gain)
            hp = min(max_hp, hp + hp_gain)
            max_ce += LEVEL_GAIN_CE

        if level >= MAX_LEVEL:
            xp = min(xp, xp_needed - 1)

        with self._conn() as conn:
            conn.execute(
                """UPDATE players SET xp=%s,xp_needed=%s,level=%s,attack=%s,defense=%s,speed=%s,
                   max_hp=%s,hp=%s,max_cursed_energy=%s WHERE user_id=%s""",
                (xp, xp_needed, level, atk, def_, spd, max_hp, hp, max_ce, user_id)
            )

    def update_cursed_energy(self, user_id: int, amount: int) -> int:
        player = self.get_player(user_id)
        if not player:
            return 0
        new_ce = max(0, min(player['max_cursed_energy'], player['cursed_energy'] + amount))
        with self._conn() as conn:
            conn.execute("UPDATE players SET cursed_energy=%s WHERE user_id=%s", (new_ce, user_id))
        return new_ce

    def update_hp(self, user_id: int, hp: int):
        with self._conn() as conn:
            conn.execute("UPDATE players SET hp=%s WHERE user_id=%s", (hp, user_id))

    def update_player_stat(self, user_id: int, stat: str, value: int):
        allowed = {'attack', 'defense', 'speed', 'hp', 'max_hp', 'cursed_energy', 'max_cursed_energy'}
        if stat not in allowed:
            return
        with self._conn() as conn:
            conn.execute(f"UPDATE players SET {stat}=%s WHERE user_id=%s", (value, user_id))

    def heal_player(self, user_id: int) -> Optional[int]:
        player = self.get_player(user_id)
        if not player or player['yen'] < 500:
            return None
        with self._conn() as conn:
            conn.execute("UPDATE players SET yen=yen-500, hp=max_hp WHERE user_id=%s", (user_id,))
        return 500

    def set_rank(self, user_id: int, rank: str):
        with self._conn() as conn:
            conn.execute("UPDATE players SET rank=%s WHERE user_id=%s", (rank, user_id))

    def add_win(self, user_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE players SET wins=wins+1 WHERE user_id=%s", (user_id,))

    def add_loss(self, user_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE players SET losses=losses+1 WHERE user_id=%s", (user_id,))

    def add_to_inventory(self, user_id: int, item_id: int):
        player = self.get_player(user_id)
        if not player:
            return
        inv = player['inventory']
        inv.append(item_id)
        with self._conn() as conn:
            conn.execute("UPDATE players SET inventory=%s WHERE user_id=%s", (json.dumps(inv), user_id))

    def remove_from_inventory(self, user_id: int, item_id: int):
        player = self.get_player(user_id)
        if not player:
            return
        inv = player['inventory']
        if item_id in inv:
            inv.remove(item_id)
        with self._conn() as conn:
            conn.execute("UPDATE players SET inventory=%s WHERE user_id=%s", (json.dumps(inv), user_id))

    def get_inventory(self, user_id: int) -> List[Dict]:
        player = self.get_player(user_id)
        if not player:
            return []
        items = []
        for item_id in player['inventory']:
            item = self.get_shop_item(item_id)
            if item:
                items.append(item)
        return items

    def learn_technique(self, user_id: int, technique_name: str):
        player = self.get_player(user_id)
        if not player:
            return
        techs = player['techniques']
        if technique_name not in techs:
            techs.append(technique_name)
            with self._conn() as conn:
                conn.execute("UPDATE players SET techniques=%s WHERE user_id=%s", (json.dumps(techs), user_id))

    def equip_artifact(self, user_id: int, artifact_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM shop_items WHERE id=%s", (artifact_id,)).fetchone()
            if not row:
                return False
        return True

    def add_level(self, user_id: int, amount: int) -> int:
        player = self.get_player(user_id)
        if not player:
            return None
        new_level = min(MAX_LEVEL, player['level'] + amount)
        levels_gained = new_level - player['level']
        if levels_gained <= 0:
            return new_level
        with self._conn() as conn:
            conn.execute(
                """UPDATE players SET level=%s,
                   attack=attack+%s,
                   defense=defense+%s,
                   speed=speed+%s,
                   max_hp=LEAST(2000, max_hp+%s),
                   hp=LEAST(max_hp+%s, hp+%s),
                   max_cursed_energy=max_cursed_energy+%s
                   WHERE user_id=%s""",
                (new_level,
                 levels_gained * LEVEL_GAIN_ATK,
                 levels_gained * LEVEL_GAIN_DEF,
                 levels_gained * LEVEL_GAIN_SPD,
                 levels_gained * LEVEL_GAIN_HP,
                 levels_gained * LEVEL_GAIN_HP,
                 levels_gained * LEVEL_GAIN_HP,
                 levels_gained * LEVEL_GAIN_CE,
                 user_id)
            )
        return new_level

    def remove_level(self, user_id: int, amount: int) -> int:
        player = self.get_player(user_id)
        if not player:
            return None
        new_level = max(1, player['level'] - amount)
        levels_lost = player['level'] - new_level
        if levels_lost <= 0:
            return new_level
        with self._conn() as conn:
            conn.execute(
                """UPDATE players SET level=%s,
                   attack=GREATEST(10, attack-%s),
                   defense=GREATEST(5, defense-%s),
                   speed=GREATEST(10, speed-%s),
                   max_hp=GREATEST(100, max_hp-%s),
                   max_cursed_energy=GREATEST(50, max_cursed_energy-%s)
                   WHERE user_id=%s""",
                (new_level,
                 levels_lost * LEVEL_GAIN_ATK,
                 levels_lost * LEVEL_GAIN_DEF,
                 levels_lost * LEVEL_GAIN_SPD,
                 levels_lost * LEVEL_GAIN_HP,
                 levels_lost * LEVEL_GAIN_CE,
                 user_id)
            )
        return new_level

    def recalc_player(self, user_id: int) -> bool:
        player = self.get_player(user_id)
        if not player:
            return False
        if player.get('character_id'):
            char = self.get_character(player['character_id'])
        else:
            char = None

        if char:
            base_atk = char['attack']
            base_def = char['defense']
            base_spd = char['speed']
            base_hp = char['max_hp']
            base_ce = char['max_ce']
        else:
            base_atk, base_def, base_spd, base_hp, base_ce = 10, 5, 10, 100, 50

        levels = max(0, player['level'] - 1)
        atk = base_atk + levels * LEVEL_GAIN_ATK
        def_ = base_def + levels * LEVEL_GAIN_DEF
        spd = base_spd + levels * LEVEL_GAIN_SPD
        max_hp = min(2000, base_hp + levels * LEVEL_GAIN_HP)
        max_ce = base_ce + levels * LEVEL_GAIN_CE

        hp_ratio = player['hp'] / max(1, player['max_hp'])
        ce_ratio = player['cursed_energy'] / max(1, player['max_cursed_energy'])

        with self._conn() as conn:
            conn.execute(
                """UPDATE players SET attack=%s,defense=%s,speed=%s,max_hp=%s,hp=%s,
                   max_cursed_energy=%s,cursed_energy=%s WHERE user_id=%s""",
                (atk, def_, spd, max_hp, max(1, int(max_hp * hp_ratio)),
                 max_ce, max(0, int(max_ce * ce_ratio)), user_id)
            )
        return True

    def claim_daily(self, user_id: int) -> Optional[Dict]:
        player = self.get_player(user_id)
        if not player:
            return None
        last = player.get('last_daily')
        now = datetime.now()
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if now - last_dt < timedelta(hours=24):
                    return None
            except Exception:
                pass
        with self._conn() as conn:
            conn.execute(
                "UPDATE players SET yen=yen+1000, xp=xp+100, last_daily=%s WHERE user_id=%s",
                (now.isoformat(), user_id)
            )
        self.add_xp(user_id, 0)  # trigger level-up check
        return {'yen': 1000, 'xp': 100}

    # ───────────────────────────────────────────────
    # DOMAIN METHODS
    # ───────────────────────────────────────────────

    def create_domain(self, user_id: int, domain_name: str, power: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "INSERT INTO user_domains (user_id, domain_name, power, equipped, created_at) VALUES (%s,%s,%s,0,%s) RETURNING id",
                (user_id, domain_name, power, datetime.now().isoformat())
            ).fetchone()
            return row['id']

    def get_user_domain(self, user_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_domains WHERE user_id=%s ORDER BY id DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def equip_domain(self, user_id: int) -> bool:
        player = self.get_player(user_id)
        if not player or player['yen'] < 1500000:
            return False
        domain = self.get_user_domain(user_id)
        if not domain:
            return False
        with self._conn() as conn:
            conn.execute("UPDATE players SET yen=yen-1500000 WHERE user_id=%s", (user_id,))
            conn.execute("UPDATE user_domains SET equipped=1 WHERE user_id=%s", (user_id,))
        return True

    # ───────────────────────────────────────────────
    # CHARACTER METHODS
    # ───────────────────────────────────────────────

    def get_all_characters(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM characters ORDER BY id").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d['attacks'] = json.loads(d['attacks']) if d.get('attacks') else []
                except Exception:
                    d['attacks'] = []
                result.append(d)
            return result

    def get_character(self, char_id: int) -> Optional[Dict]:
        if char_id is None:
            return None
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM characters WHERE id=%s", (char_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d['attacks'] = json.loads(d['attacks']) if d.get('attacks') else []
            except Exception:
                d['attacks'] = []
            return d

    def get_equipped_character(self, user_id: int) -> Optional[Dict]:
        """Return the character currently equipped by the given player, or None."""
        player = self.get_player(user_id)
        if not player or not player.get('character_id'):
            return None
        return self.get_character(player['character_id'])

    # ───────────────────────────────────────────────
    # SHOP METHODS
    # ───────────────────────────────────────────────

    def get_shop_items(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM shop_items
                   WHERE LOWER(name) <> LOWER('Domain Expansion Blueprint')
                   ORDER BY type,price"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_shop_item(self, item_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM shop_items WHERE id=%s", (item_id,)).fetchone()
            return dict(row) if row else None

    def purchase_shop_item(self, user_id: int, item_id: int) -> Dict:
        """Purchase an item atomically; the removed blueprint can never be bought."""
        with self._conn() as conn:
            item = conn.execute("SELECT * FROM shop_items WHERE id=%s", (item_id,)).fetchone()
            player = conn.execute(
                "SELECT yen,inventory FROM players WHERE user_id=%s FOR UPDATE",
                (user_id,)
            ).fetchone()
            if not item or not player:
                return {'ok': False, 'reason': 'not_found'}
            if str(item['name']).lower() == 'domain expansion blueprint':
                return {'ok': False, 'reason': 'removed'}
            price = int(item['price'] or 0)
            if int(player['yen']) < price:
                return {'ok': False, 'reason': 'funds', 'price': price, 'balance': int(player['yen'])}
            inventory = json.loads(player['inventory']) if player['inventory'] else []
            inventory.append(item_id)
            conn.execute(
                "UPDATE players SET yen=yen-%s, inventory=%s WHERE user_id=%s",
                (price, json.dumps(inventory), user_id)
            )
            return {'ok': True, 'item': dict(item), 'remaining': int(player['yen']) - price}

    def get_clans(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM clans ORDER BY name").fetchall()
            result = []
            for row in rows:
                value = dict(row)
                for field, default in (('members', []), ('inventory', {}), ('upgrades', []), ('statistics', {})):
                    if isinstance(value.get(field), str):
                        value[field] = json.loads(value[field] or json.dumps(default))
                result.append(value)
            return result

    def upsert_clan(self, clan: Dict) -> bool:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO clans
                   (clan_key,name,leader,leader_name,members,treasury,inventory,level,upgrades,statistics,description,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                   ON CONFLICT (clan_key) DO UPDATE SET
                   name=EXCLUDED.name, leader=EXCLUDED.leader, leader_name=EXCLUDED.leader_name,
                   members=EXCLUDED.members, treasury=EXCLUDED.treasury, inventory=EXCLUDED.inventory,
                   level=EXCLUDED.level, upgrades=EXCLUDED.upgrades, statistics=EXCLUDED.statistics,
                   description=EXCLUDED.description, updated_at=EXCLUDED.updated_at""",
                (clan['key'], clan['name'], clan['leader'], clan.get('leader_name', ''),
                 json.dumps(clan.get('members', [])), int(clan.get('treasury', 0)),
                 json.dumps(clan.get('inventory', {})), int(clan.get('level', 1)),
                 json.dumps(clan.get('upgrades', [])), json.dumps(clan.get('statistics', {})),
                 clan.get('description', ''), clan.get('created_at', now), now)
            )
        return True

    def clan_donate(self, clan_key: str, leader_id: int, recipient_id: int, amount: int) -> Dict:
        if amount <= 0:
            return {'ok': False, 'reason': 'amount'}
        with self._conn() as conn:
            clan = conn.execute("SELECT * FROM clans WHERE clan_key=%s FOR UPDATE", (clan_key,)).fetchone()
            if not clan:
                return {'ok': False, 'reason': 'clan'}
            members = clan['members'] if isinstance(clan['members'], list) else json.loads(clan['members'] or '[]')
            if int(clan['leader']) != leader_id:
                return {'ok': False, 'reason': 'leader'}
            if recipient_id not in [int(member) for member in members]:
                return {'ok': False, 'reason': 'member'}
            if int(clan['treasury']) < amount:
                return {'ok': False, 'reason': 'treasury', 'balance': int(clan['treasury'])}
            if not conn.execute("SELECT 1 FROM players WHERE user_id=%s", (recipient_id,)).fetchone():
                return {'ok': False, 'reason': 'recipient'}
            now = datetime.now().isoformat()
            conn.execute("UPDATE clans SET treasury=treasury-%s, updated_at=%s WHERE clan_key=%s",
                         (amount, now, clan_key))
            conn.execute("UPDATE players SET yen=yen+%s WHERE user_id=%s", (amount, recipient_id))
            conn.execute(
                """INSERT INTO clan_transactions
                   (clan_key,actor_id,recipient_id,amount,transaction_type,created_at)
                   VALUES (%s,%s,%s,%s,'donation',%s)""",
                (clan_key, leader_id, recipient_id, amount, now)
            )
            return {'ok': True, 'balance': int(clan['treasury']) - amount}

    def get_shop_item_by_name(self, name: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM shop_items WHERE LOWER(name)=LOWER(%s)",
                (name,)
            ).fetchone()
            return dict(row) if row else None

    def get_technique(self, tech_name: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM techniques WHERE LOWER(name)=LOWER(%s)",
                (tech_name,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_techniques(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM techniques ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    # ───────────────────────────────────────────────
    # PVP BATTLE METHODS
    # ───────────────────────────────────────────────

    def create_pvp_battle(self, chat_id: int, player1_id: int, player2_id: int,
                          p1_hp: int, p2_hp: int, p1_max_hp: int, p2_max_hp: int,
                          p1_ce: int, p2_ce: int, p1_max_ce: int, p2_max_ce: int,
                          first_attacker: int) -> int:
        with self._conn() as conn:
            # FIX: clear ALL active battles for both players across ALL chats,
            # not just the current chat. This prevents stale Domain Expansion
            # locks and pending moves from carrying over into new battles.
            conn.execute(
                """UPDATE pvp_battles
                   SET status='finished', p1_move=NULL, p2_move=NULL
                   WHERE status='active'
                   AND (player1_id IN (%s,%s) OR player2_id IN (%s,%s))""",
                (player1_id, player2_id, player1_id, player2_id)
            )
            row = conn.execute(
                """INSERT INTO pvp_battles
                   (chat_id,player1_id,player2_id,player1_hp,player2_hp,player1_max_hp,player2_max_hp,
                    player1_ce,player2_ce,player1_max_ce,player2_max_ce,round,p1_move,p2_move,
                    status,first_attacker,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,NULL,NULL,'active',%s,%s)
                   RETURNING battle_id""",
                (chat_id, player1_id, player2_id, p1_hp, p2_hp, p1_max_hp, p2_max_hp,
                 p1_ce, p2_ce, p1_max_ce, p2_max_ce, first_attacker, datetime.now().isoformat())
            ).fetchone()
            return row['battle_id']

    def get_active_pvp_battle(self, user_id: int, chat_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT * FROM pvp_battles WHERE chat_id=%s AND status='active'
                   AND (player1_id=%s OR player2_id=%s) ORDER BY battle_id DESC LIMIT 1""",
                (chat_id, user_id, user_id)
            ).fetchone()
            return dict(row) if row else None

    def get_battle_by_id(self, battle_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pvp_battles WHERE battle_id=%s",
                (battle_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_pvp_move(self, battle_id: int, user_id: int, move: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM pvp_battles WHERE battle_id=%s", (battle_id,)).fetchone()
            if not row or row['status'] != 'active':
                return None
            if row['player1_id'] == user_id:
                conn.execute("UPDATE pvp_battles SET p1_move=%s WHERE battle_id=%s", (move, battle_id))
            elif row['player2_id'] == user_id:
                conn.execute("UPDATE pvp_battles SET p2_move=%s WHERE battle_id=%s", (move, battle_id))
            else:
                return None
        return self.get_battle_by_id(battle_id)

    def advance_pvp_round(self, battle_id: int, p1_hp: int, p2_hp: int,
                          p1_ce: int, p2_ce: int) -> Optional[Dict]:
        with self._conn() as conn:
            # Always clear both moves when advancing to the next round so
            # neither player is permanently locked if they used Domain Expansion.
            conn.execute(
                """UPDATE pvp_battles SET player1_hp=%s,player2_hp=%s,player1_ce=%s,player2_ce=%s,
                   p1_move=NULL,p2_move=NULL,round=round+1 WHERE battle_id=%s""",
                (p1_hp, p2_hp, p1_ce, p2_ce, battle_id)
            )
        return self.get_battle_by_id(battle_id)

    def finish_pvp_battle(self, battle_id: int):
        """Mark a battle finished and clear any pending moves so no stale lock survives."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE pvp_battles SET status='finished', p1_move=NULL, p2_move=NULL WHERE battle_id=%s",
                (battle_id,)
            )

    def clear_player_battles(self, user_id: int) -> int:
        """
        Mark ALL active PvP battles involving this player as finished and clear
        pending moves.  Returns the number of battles cleared.
        This is called by /flee so no stale Domain Expansion lock survives into
        future battles.
        """
        with self._conn() as conn:
            conn.execute(
                """UPDATE pvp_battles
                   SET status='finished', p1_move=NULL, p2_move=NULL
                   WHERE status='active'
                   AND (player1_id=%s OR player2_id=%s)""",
                (user_id, user_id)
            )
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM pvp_battles WHERE status='finished' AND (player1_id=%s OR player2_id=%s)",
                (user_id, user_id)
            ).fetchone()
            return row['cnt'] if row else 0

    def get_all_active_pvp_battles(self) -> List[Dict]:
        """Return every active PvP battle — used by /debug."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pvp_battles WHERE status='active' ORDER BY battle_id"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_pvp_battles(self, limit: int = 500) -> List[Dict]:
        """Return recent PvP battles for validation — used by /debug."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pvp_battles ORDER BY battle_id DESC LIMIT %s", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ───────────────────────────────────────────────
    # MISSION METHODS
    # ───────────────────────────────────────────────

    def get_daily_missions(self, user_id: int) -> List[Dict]:
        today = datetime.now().strftime('%Y-%m-%d')
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM missions WHERE user_id=%s AND date=%s",
                (user_id, today)
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]

            defaults = [
                ('Spirit Exorcist', 'Defeat 3 cursed spirits', 'battle_wins', 3, 2000, 150),
                ('Rich Sorcerer', 'Earn 5000 yen from battles', 'yen_earned', 5000, 1000, 100),
                ('PvP Master', 'Win 2 PvP battles', 'pvp_wins', 2, 3000, 200),
                ('Technique User', 'Use techniques 5 times', 'technique_uses', 5, 1500, 100),
            ]
            for name, desc, mtype, target, r_yen, r_xp in defaults:
                conn.execute(
                    """INSERT INTO missions (user_id,name,description,mission_type,target_value,
                       current_value,reward_yen,reward_xp,completed,date)
                       VALUES (%s,%s,%s,%s,%s,0,%s,%s,0,%s)""",
                    (user_id, name, desc, mtype, target, r_yen, r_xp, today)
                )
            rows = conn.execute(
                "SELECT * FROM missions WHERE user_id=%s AND date=%s",
                (user_id, today)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_mission_progress(self, user_id: int, mission_type: str, amount: int = 1):
        today = datetime.now().strftime('%Y-%m-%d')
        with self._conn() as conn:
            conn.execute(
                """UPDATE missions SET current_value=current_value+%s
                   WHERE user_id=%s AND mission_type=%s AND date=%s AND completed=0""",
                (amount, user_id, mission_type, today)
            )
            conn.execute(
                """UPDATE missions SET completed=1
                   WHERE user_id=%s AND date=%s AND completed=0 AND current_value>=target_value""",
                (user_id, today)
            )

    # ───────────────────────────────────────────────
    # LEADERBOARD METHODS
    # ───────────────────────────────────────────────

    def get_global_leaderboard(self, limit: int = 10) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM players ORDER BY level DESC, yen DESC LIMIT %s",
                (limit,)
            ).fetchall()
            return [self._parse_player(r) for r in rows]

    def get_group_leaderboard(self, group_id: int, limit: int = 10) -> List[Dict]:
        return self.get_global_leaderboard(limit)

    # ───────────────────────────────────────────────
    # DEBUG / VALIDATION METHODS
    # ───────────────────────────────────────────────

    def validate_and_repair_player(self, player: Dict) -> Dict:
        """
        Inspect a parsed player record for missing / invalid fields.
        Returns a report dict:
          {fixed: bool, issues: [str], repaired: [str]}
        Automatically applies safe repairs to the database.
        """
        uid = player['user_id']
        issues = []
        repaired = []
        updates = {}

        # Required integer fields with their floor values
        int_fields = {
            'level': (1, MAX_LEVEL),
            'xp': (0, None),
            'xp_needed': (100, None),
            'hp': (1, None),
            'max_hp': (1, 2000),
            'cursed_energy': (0, None),
            'max_cursed_energy': (1, None),
            'attack': (1, None),
            'defense': (1, None),
            'speed': (1, None),
            'wins': (0, None),
            'losses': (0, None),
            'yen': (0, None),
        }
        for field, (lo, hi) in int_fields.items():
            val = player.get(field)
            if val is None:
                issues.append(f"Missing field: {field}")
                updates[field] = lo
                repaired.append(f"Set {field}={lo}")
            elif not isinstance(val, int):
                issues.append(f"Non-integer {field}: {val!r}")
                updates[field] = lo
                repaired.append(f"Reset {field}={lo}")
            else:
                if val < lo:
                    issues.append(f"{field}={val} below minimum {lo}")
                    updates[field] = lo
                    repaired.append(f"Clamped {field} to {lo}")
                if hi is not None and val > hi:
                    issues.append(f"{field}={val} above maximum {hi}")
                    updates[field] = hi
                    repaired.append(f"Clamped {field} to {hi}")

        # hp must not exceed max_hp
        eff_hp = updates.get('hp', player.get('hp', 1))
        eff_max_hp = updates.get('max_hp', player.get('max_hp', 100))
        if eff_hp > eff_max_hp:
            issues.append(f"hp ({eff_hp}) > max_hp ({eff_max_hp})")
            updates['hp'] = eff_max_hp
            repaired.append(f"Capped hp to max_hp ({eff_max_hp})")

        # cursed_energy must not exceed max_cursed_energy
        eff_ce = updates.get('cursed_energy', player.get('cursed_energy', 0))
        eff_max_ce = updates.get('max_cursed_energy', player.get('max_cursed_energy', 50))
        if eff_ce > eff_max_ce:
            issues.append(f"cursed_energy ({eff_ce}) > max_cursed_energy ({eff_max_ce})")
            updates['cursed_energy'] = eff_max_ce
            repaired.append(f"Capped cursed_energy to {eff_max_ce}")

        # rank must be valid
        valid_ranks = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']
        if player.get('rank') not in valid_ranks:
            issues.append(f"Invalid rank: {player.get('rank')!r}")
            updates['rank'] = 'Grade 4'
            repaired.append("Reset rank to 'Grade 4'")

        # JSON array fields
        for field in ('techniques', 'artifacts', 'inventory'):
            val = player.get(field)
            if not isinstance(val, list):
                issues.append(f"Invalid {field} (not a list): {val!r}")
                updates[field] = json.dumps([])
                repaired.append(f"Reset {field} to []")

        # display_name must not be empty
        if not player.get('display_name'):
            dn = player.get('username') or f"Player_{uid}"
            issues.append("Missing display_name")
            updates['display_name'] = dn
            repaired.append(f"Set display_name='{dn}'")

        # Apply repairs
        if updates:
            try:
                set_parts = []
                vals = []
                for k, v in updates.items():
                    set_parts.append(f"{k}=%s")
                    vals.append(v)
                vals.append(uid)
                sql = f"UPDATE players SET {', '.join(set_parts)} WHERE user_id=%s"
                with self._conn() as conn:
                    conn.execute(sql, vals)
            except Exception as e:
                repaired.append(f"REPAIR FAILED: {e}")

        return {'fixed': bool(updates), 'issues': issues, 'repaired': repaired}

    def get_db_table_counts(self) -> Dict[str, int]:
        """Return row counts for every game table — used by /debug."""
        tables = ['players', 'characters', 'shop_items', 'techniques',
                  'pvp_battles', 'missions', 'user_domains']
        result = {}
        with self._conn() as conn:
            for table in tables:
                try:
                    row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
                    result[table] = row['cnt'] if row else -1
                except Exception as e:
                    result[table] = f"ERROR: {e}"
        return result

    def verify_db_connection(self) -> bool:
        """Return True if the database is reachable."""
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def cleanup_stale_battles(self) -> int:
        """
        Mark as 'finished' any PvP battles older than 2 hours that are still
        'active'.  Returns the number of battles cleaned up.
        """
        cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
        with self._conn() as conn:
            conn.execute(
                """UPDATE pvp_battles
                   SET status='finished', p1_move=NULL, p2_move=NULL
                   WHERE status='active' AND created_at < %s""",
                (cutoff,)
            )
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM pvp_battles WHERE status='finished' AND created_at < %s",
                (cutoff,)
            ).fetchone()
            return row['cnt'] if row else 0
