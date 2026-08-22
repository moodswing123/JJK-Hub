"""
Game Engine for JJK Bot
Handles combat calculations, cursed spirit generation, etc.
Battle balance ensures minimum 3+ rounds by capping damage per hit.
"""

import random
from typing import Dict, List
from config import MAX_LEVEL


class GameEngine:
    def __init__(self, db):
        self.db = db

        self.spirit_names = {
            'Grade 4': ['Fly Head', 'Demon Dog', 'Cursed Corpse', 'Worm Curse', 'Shadow Slug'],
            'Grade 3': ['Cursed Womb', 'Rainbow Dragon', 'Mirrored Curse', 'Stone Snake Curse'],
            'Grade 2': ['Special Grade Cursed Womb', 'Finger Bearer', 'Spiked Curse', 'Armored Spirit'],
            'Grade 1': ['Hanami Clone', 'Jogo Fragment', 'Dagon Shell', 'Mahito Echo'],
            'Special Grade': ["Sukuna's Finger", "Geto's Uzumaki Remnant", 'Special Grade Vengeful Spirit']
        }

    def generate_cursed_spirit(self, player_level: int) -> Dict:
        """Generate a cursed spirit scaled to the player.
        HP is large enough to ensure at least 3 rounds of combat."""
        if player_level < 5:
            grade = 'Grade 4'
        elif player_level < 10:
            grade = random.choice(['Grade 4', 'Grade 3'])
        elif player_level < 20:
            grade = random.choice(['Grade 3', 'Grade 2'])
        elif player_level < 35:
            grade = random.choice(['Grade 2', 'Grade 1'])
        elif player_level < MAX_LEVEL:
            grade = random.choice(['Grade 1', 'Special Grade'])
        else:
            grade = 'Special Grade'

        # HP is intentionally high — guarantees 3+ rounds even with strong attacks.
        # Rule of thumb: spirit HP >= 4 × max player single-hit damage at this level.
        base_stats = {
            'Grade 4':       {'hp': 240,  'atk': 12, 'def': 8,  'reward': 500,   'xp': 50},
            'Grade 3':       {'hp': 400,  'atk': 25, 'def': 15, 'reward': 1000,  'xp': 100},
            'Grade 2':       {'hp': 700,  'atk': 45, 'def': 28, 'reward': 2500,  'xp': 250},
            'Grade 1':       {'hp': 1100, 'atk': 70, 'def': 50, 'reward': 5000,  'xp': 500},
            'Special Grade': {'hp': 1800, 'atk': 100,'def': 75, 'reward': 10000, 'xp': 1000}
        }

        stats = base_stats[grade]
        scale = 1 + (player_level * 0.07)

        spirit_atk = int(stats['atk'] * scale)
        spirit_hp  = int(stats['hp']  * scale)

        return {
            'id':      random.randint(1000, 9999),
            'name':    random.choice(self.spirit_names[grade]),
            'grade':   grade,
            'hp':      spirit_hp,
            'attack':  spirit_atk,
            'defense': int(stats['def'] * scale),
            'reward':  int(stats['reward'] * scale),
            'xp':      int(stats['xp']    * scale)
        }

    def calculate_damage(self, attacker_atk: int, defender_def: int,
                         target_max_hp: int = None) -> int:
        """
        Resolve damage symmetrically for PvE and PvP.

        Attackers and defenders use the same mitigation model. Variance is
        deliberately narrow and critical hits are modest, so a fight is not
        decided by a single lucky roll. The 30% max-HP cap remains in place
        to prevent instant defeats and preserve meaningful counterplay.
        """
        attacker_atk = max(1, int(attacker_atk))
        defender_def = max(0, int(defender_def))
        # Defense mitigates consistently but cannot reduce a comparable attack
        # below the guaranteed minimum or erase the effect of equipment.
        mitigation = min(int(defender_def * 0.60), int(attacker_atk * 0.45))
        base_damage = max(8, attacker_atk - mitigation)
        variance = random.uniform(0.92, 1.08)
        is_critical = random.random() < 0.05
        dmg = max(1, int(base_damage * variance * (1.5 if is_critical else 1.0)))

        if target_max_hp and target_max_hp > 0:
            cap = max(15, int(target_max_hp * 0.30))
            dmg = min(dmg, cap)
        return dmg

    def calculate_pvp_damage(self, attacker: Dict, defender: Dict, move: str) -> Dict:
        """Resolve a named PvP move into damage + CE cost."""
        if move == 'attack':
            damage  = self.calculate_damage(attacker['attack'], defender['defense'],
                                            defender.get('max_hp'))
            ce_cost = 0
        elif move == 'technique':
            damage  = self.calculate_damage(int(attacker['attack'] * 1.8), defender['defense'],
                                            defender.get('max_hp'))
            ce_cost = 20
        elif move == 'defend':
            damage  = 0
            ce_cost = 0
        else:
            damage  = 0
            ce_cost = 0

        return {
            'damage':  damage,
            'ce_cost': ce_cost,
            'is_crit': damage > attacker['attack'] * 1.5
        }

    def get_rank_up_requirements(self, current_rank: str) -> Dict:
        ranks = ['Grade 4', 'Grade 3', 'Grade 2', 'Grade 1', 'Special Grade']
        try:
            current_idx = ranks.index(current_rank)
            if current_idx >= len(ranks) - 1:
                return None
            next_rank = ranks[current_idx + 1]
            requirements = {
                'Grade 3':       {'level': 5,  'wins': 10,  'yen': 10000},
                'Grade 2':       {'level': 15, 'wins': 30,  'yen': 30000},
                'Grade 1':       {'level': 30, 'wins': 60,  'yen': 80000},
                'Special Grade': {'level': 50, 'wins': 100, 'yen': 200000},
            }
            return {'next_rank': next_rank, 'requirements': requirements.get(next_rank, {})}
        except ValueError:
            return None
