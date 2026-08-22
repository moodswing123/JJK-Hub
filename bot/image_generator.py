"""
Image Generator for JJK Bot
Generates stylized character cards, battle scenes, and animated battle GIFs
using PIL with JJK-themed dark cursed energy aesthetic.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import math
import random
from typing import Dict, Tuple, Optional, List


# ─── Character visual themes ────────────────────────────────────────────────
CHARACTER_THEMES = {
    'Yuji Itadori':   {'primary': (220, 40, 40),   'secondary': (180, 20, 20),  'accent': (255, 120, 80)},
    'Megumi Fushiguro':{'primary': (40, 60, 160),  'secondary': (20, 40, 120),  'accent': (100, 140, 255)},
    'Nobara Kugisaki': {'primary': (200, 80, 200), 'secondary': (160, 40, 160), 'accent': (255, 140, 255)},
    'Satoru Gojo':    {'primary': (30, 180, 255),  'secondary': (10, 120, 200), 'accent': (180, 240, 255)},
    'Ryomen Sukuna':  {'primary': (180, 0, 0),     'secondary': (100, 0, 0),    'accent': (255, 80, 30)},
    'Yuta Okkotsu':   {'primary': (80, 200, 120),  'secondary': (40, 140, 80),  'accent': (140, 255, 180)},
    'Kinji Hakari':   {'primary': (220, 160, 30),  'secondary': (160, 100, 10), 'accent': (255, 220, 80)},
    'Aoi Todo':       {'primary': (160, 60, 200),  'secondary': (100, 20, 140), 'accent': (200, 100, 255)},
    'Choso':          {'primary': (180, 30, 60),   'secondary': (120, 10, 30),  'accent': (255, 80, 100)},
    'Kento Nanami':   {'primary': (180, 150, 60),  'secondary': (120, 100, 20), 'accent': (240, 210, 120)},
    'Maki Zenin':     {'primary': (60, 180, 80),   'secondary': (20, 120, 40),  'accent': (100, 240, 120)},
    'Toge Inumaki':   {'primary': (80, 120, 200),  'secondary': (40, 80, 150),  'accent': (140, 180, 255)},
    'Jogo':           {'primary': (220, 80, 10),   'secondary': (160, 40, 0),   'accent': (255, 160, 60)},
    'Mahito':         {'primary': (100, 100, 200), 'secondary': (60, 60, 140),  'accent': (180, 160, 255)},
    'Panda':          {'primary': (200, 200, 200), 'secondary': (140, 140, 140),'accent': (255, 255, 255)},
    'default':        {'primary': (100, 80, 200),  'secondary': (60, 40, 140),  'accent': (160, 140, 255)},
}


def _theme(character: Dict) -> Dict:
    name = character.get('name', '')
    for key in CHARACTER_THEMES:
        if key in name:
            return CHARACTER_THEMES[key]
    return CHARACTER_THEMES['default']


class ImageGenerator:
    def __init__(self):
        self.char_width = 500
        self.char_height = 600
        self.battle_width = 860
        self.battle_height = 480
        self.gif_width = 820
        self.gif_height = 460

        self.colors = {
            'bg':         (8,  8,  22),
            'bg2':        (16, 16, 40),
            'card':       (22, 22, 50),
            'text_white': (240, 240, 255),
            'text_gold':  (255, 210, 50),
            'text_green': (50,  220, 110),
            'text_red':   (255, 70,  70),
            'text_blue':  (100, 170, 255),
            'text_purple':(200, 120, 255),
            'hp_bar':     (50,  210, 80),
            'hp_low':     (255, 70,  70),
            'hp_bg':      (50,  50,  70),
            'ce_bar':     (70,  130, 255),
            'ce_bg':      (50,  50,  70),
            'xp_bar':     (200, 120, 255),
            'xp_bg':      (50,  50,  70),
        }

        self.grade_colors = {
            'Grade 4':          (140, 200, 255),
            'Grade 3':          (160, 160, 255),
            'Grade 2':          (200, 100, 255),
            'Grade 1':          (255, 130, 80),
            'Special Grade':    (255, 215, 0),
            'Grade 1 (Curse)':  (255, 100, 60),
        }

    # ─── Fonts ──────────────────────────────────────────────────────────────

    def _get_font(self, size: int = 12, bold: bool = False) -> ImageFont.FreeTypeFont:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
        return ImageFont.load_default()

    # ─── Drawing primitives ─────────────────────────────────────────────────

    def _draw_rounded_rect(self, draw, x1, y1, x2, y2, fill, outline=None,
                           radius=8, width=2):
        draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill,
                                outline=outline, width=width)

    def _draw_bar(self, draw, x, y, w, h, current, maximum, fg, bg, label=""):
        draw.rounded_rectangle([x, y, x+w, y+h], radius=4, fill=bg)
        if maximum > 0:
            ratio = max(0.0, min(1.0, current / maximum))
            bw = int(w * ratio)
            if bw > 0:
                draw.rounded_rectangle([x, y, x+bw, y+h], radius=4, fill=fg)
        if label:
            draw.text((x + w//2, y + h//2), label,
                      fill=self.colors['text_white'], anchor='mm',
                      font=self._get_font(8))

    def _glow_circle(self, draw, cx, cy, r, color, alpha_factor=0.6):
        """Draw a glowing circle outline."""
        for dr in range(4, 0, -1):
            faded = tuple(int(c * alpha_factor * (dr / 4)) for c in color)
            draw.ellipse([cx-r-dr, cy-r-dr, cx+r+dr, cy+r+dr],
                         outline=faded, width=2)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color, width=2)

    def _draw_energy_aura(self, draw, cx, cy, theme, intensity=1.0):
        """Draw layered cursed energy aura rings."""
        primary = theme['primary']
        accent = theme['accent']
        radii = [90, 70, 55, 40, 28]
        for i, r in enumerate(radii):
            alpha = intensity * (0.15 + i * 0.12)
            col = tuple(int(c * alpha) for c in (accent if i % 2 == 0 else primary))
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=col, width=2)

    def _draw_character_figure(self, draw, cx, cy, w, h, theme):
        """Draw an anime-style stylized character silhouette."""
        primary = theme['primary']
        secondary = theme['secondary']
        accent = theme['accent']

        scale = h / 200.0

        # Body glow aura
        for r, alpha in [(int(70*scale), 0.15), (int(55*scale), 0.25), (int(42*scale), 0.35)]:
            glow = tuple(int(c * alpha) for c in accent)
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=glow)

        # Legs
        leg_w = int(10*scale)
        leg_h = int(60*scale)
        leg_y = cy + int(20*scale)
        draw.rounded_rectangle([cx - int(18*scale), leg_y,
                                 cx - int(8*scale),  leg_y + leg_h],
                                radius=4, fill=secondary)
        draw.rounded_rectangle([cx + int(8*scale),  leg_y,
                                 cx + int(18*scale), leg_y + leg_h],
                                radius=4, fill=secondary)

        # Torso
        torso_w = int(38*scale)
        torso_h = int(55*scale)
        torso_y = cy - int(30*scale)
        self._draw_rounded_rect(draw,
                                 cx - torso_w//2, torso_y,
                                 cx + torso_w//2, torso_y + torso_h,
                                 fill=primary, outline=accent, radius=8, width=2)

        # Arms
        arm_w = int(10*scale)
        arm_h = int(48*scale)
        arm_y = torso_y + int(6*scale)
        draw.rounded_rectangle([cx - torso_w//2 - arm_w - 2, arm_y,
                                 cx - torso_w//2 - 2, arm_y + arm_h],
                                radius=4, fill=secondary)
        draw.rounded_rectangle([cx + torso_w//2 + 2, arm_y,
                                 cx + torso_w//2 + arm_w + 2, arm_y + arm_h],
                                radius=4, fill=secondary)

        # Head
        head_r = int(22*scale)
        head_cy = torso_y - head_r - int(4*scale)
        draw.ellipse([cx-head_r, head_cy-head_r, cx+head_r, head_cy+head_r],
                     fill=secondary, outline=accent, width=2)

        # Eyes (glowing)
        ey = head_cy - int(3*scale)
        er = max(2, int(4*scale))
        draw.ellipse([cx-int(8*scale)-er, ey-er, cx-int(8*scale)+er, ey+er],
                     fill=accent)
        draw.ellipse([cx+int(8*scale)-er, ey-er, cx+int(8*scale)+er, ey+er],
                     fill=accent)

        # Cursed energy tendrils
        for angle_deg in range(0, 360, 45):
            angle = math.radians(angle_deg)
            t_start = int(50*scale)
            t_end = int(75*scale) + random.randint(-5, 5)
            x1 = cx + int(math.cos(angle) * t_start)
            y1 = cy + int(math.sin(angle) * t_start)
            x2 = cx + int(math.cos(angle + 0.3) * t_end)
            y2 = cy + int(math.sin(angle + 0.3) * t_end)
            draw.line([x1, y1, x2, y2], fill=accent, width=2)

    def _draw_hex_pattern(self, draw, x, y, w, h, color, alpha=0.05):
        """Draw a subtle hex grid pattern in the background."""
        faded = tuple(int(c * alpha) for c in color)
        size = 20
        for gy in range(y, y+h, size):
            for gx in range(x, x+w, size * 2):
                offset = size if ((gy - y) // size) % 2 else 0
                pts = [
                    (gx+offset+size//2, gy),
                    (gx+offset+size, gy+size//2),
                    (gx+offset+size//2, gy+size),
                    (gx+offset-size//2+size, gy+size),
                    (gx+offset-size//2, gy+size//2),
                ]
                try:
                    draw.polygon(pts, outline=faded)
                except Exception:
                    pass

    # ─── Character portrait (panel) ─────────────────────────────────────────

    def _character_portrait(self, draw, x, y, w, h, character):
        theme = _theme(character)
        grade = character.get('grade', 'Grade 4')
        gc = self.grade_colors.get(grade, self.colors['text_white'])
        primary = theme['primary']
        accent = theme['accent']

        # Panel bg
        self._draw_rounded_rect(draw, x, y, x+w, y+h,
                                 fill=(12, 12, 30), outline=gc, radius=10, width=3)

        # Hex pattern bg
        self._draw_hex_pattern(draw, x, y, w, h, primary, alpha=0.06)

        # Aura background glow
        cx, cy = x + w//2, y + h//2
        for r, a in [(min(w,h)//2-5, 0.12), (min(w,h)//3, 0.20), (min(w,h)//4, 0.28)]:
            glow = tuple(int(c * a) for c in primary)
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=glow)

        # Cursed energy rings
        self._draw_energy_aura(draw, cx, cy, theme, intensity=0.9)

        # Character figure
        fig_h = min(h - 30, 160)
        self._draw_character_figure(draw, cx, cy - 5, w - 20, fig_h, theme)

        # Grade badge at bottom
        grade_short = grade.replace('Grade ', 'G').replace('Special Grade', 'SG')
        badge_w = max(40, len(grade_short) * 9 + 16)
        bx = x + (w - badge_w) // 2
        self._draw_rounded_rect(draw, bx, y+h-26, bx+badge_w, y+h-8,
                                 fill=gc, outline=None, radius=5)
        draw.text((bx + badge_w//2, y+h-17), grade_short,
                  fill=self.colors['bg'], anchor='mm',
                  font=self._get_font(9, bold=True))

    # ─── Public generators ──────────────────────────────────────────────────

    def generate_faction_awakening(self, player: Dict) -> io.BytesIO:
        """Themed faction assignment card shown when a player first starts."""
        faction = player.get('faction') or 'Sorcerer'
        primary = (35, 150, 255) if faction == 'Sorcerer' else (190, 45, 80)
        accent = (150, 235, 255) if faction == 'Sorcerer' else (255, 150, 90)
        W, H = 700, 360
        img = Image.new('RGB', (W, H), self.colors['bg'])
        draw = ImageDraw.Draw(img)
        self._draw_hex_pattern(draw, 0, 0, W, H, primary, 0.10)
        for r, alpha in [(155, .08), (125, .14), (95, .22)]:
            col = tuple(int(c * alpha) for c in primary)
            draw.ellipse([W // 2 - r, 145 - r, W // 2 + r, 145 + r], fill=col)
        draw.rounded_rectangle([12, 12, W - 12, H - 12], radius=18,
                               fill=self.colors['card'], outline=accent, width=3)
        draw.text((W // 2, 62), "CURSED ENERGY AWAKENING",
                  fill=accent, anchor='mm', font=self._get_font(20, bold=True))
        draw.text((W // 2, 145), faction.upper(),
                  fill=self.colors['text_gold'], anchor='mm', font=self._get_font(42, bold=True))
        draw.text((W // 2, 205), player.get('display_name', 'Player')[:28],
                  fill=self.colors['text_white'], anchor='mm', font=self._get_font(18))
        draw.text((W // 2, 270),
                  "Your faction is permanent unless changed by an administrator.",
                  fill=(190, 190, 215), anchor='mm', font=self._get_font(12))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def generate_wallet_image(self, player: Dict) -> io.BytesIO:
        """Wallet card with current balance and progression."""
        W, H = 600, 300
        img = Image.new('RGB', (W, H), self.colors['bg'])
        draw = ImageDraw.Draw(img)
        primary = (35, 150, 255) if player.get('faction') == 'Sorcerer' else (190, 45, 80)
        self._draw_hex_pattern(draw, 0, 0, W, H, primary, 0.08)
        draw.rounded_rectangle([10, 10, W - 10, H - 10], radius=16,
                               fill=self.colors['card'], outline=primary, width=3)
        draw.text((30, 48), f"{player.get('display_name', 'Player')}'s WALLET",
                  fill=self.colors['text_white'], font=self._get_font(20, bold=True))
        draw.text((30, 122), f"¥{int(player.get('yen', 0)):,}",
                  fill=self.colors['text_gold'], font=self._get_font(40, bold=True))
        draw.text((30, 185), f"Level {player.get('level', 1)}  •  {player.get('faction') or 'Unassigned'}",
                  fill=self.colors['text_blue'], font=self._get_font(15))
        draw.text((30, 230), "Use /shop to spend your yen",
                  fill=(190, 190, 215), font=self._get_font(13))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def generate_character_skin(self, character: Dict, player: Dict) -> io.BytesIO:
        """Character card shown on /profile."""
        img = Image.new('RGB', (self.char_width, self.char_height), self.colors['bg'])
        draw = ImageDraw.Draw(img)
        theme = _theme(character)
        grade = character.get('grade', 'Grade 4')
        gc = self.grade_colors.get(grade, self.colors['text_white'])
        primary = theme['primary']
        accent = theme['accent']

        # Background hex pattern
        self._draw_hex_pattern(draw, 0, 0, self.char_width, self.char_height, primary, 0.04)

        # Outer glow border
        for offset, alpha in [(0, 0.6), (3, 0.3), (6, 0.1)]:
            col = tuple(int(c * alpha) for c in primary)
            draw.rounded_rectangle([offset, offset, self.char_width-offset, self.char_height-offset],
                                   radius=14, outline=col, width=2)

        # Main card
        self._draw_rounded_rect(draw, 4, 4, self.char_width-4, self.char_height-4,
                                 fill=self.colors['card'], outline=gc, radius=14, width=2)

        # Portrait area
        self._character_portrait(draw, 18, 14, self.char_width-36, 200, character)

        # Name banner
        name_y = 226
        self._draw_rounded_rect(draw, 18, name_y-2, self.char_width-18, name_y+28,
                                 fill=tuple(int(c*0.3) for c in primary), outline=None, radius=6)
        draw.text((self.char_width//2, name_y+12), character['name'],
                  fill=self.colors['text_gold'], anchor='mm',
                  font=self._get_font(20, bold=True))

        # Technique
        draw.text((self.char_width//2, name_y+42), f"✦ {character['technique']} ✦",
                  fill=accent, anchor='mm', font=self._get_font(11))

        # Divider
        draw.line([(28, name_y+58), (self.char_width-28, name_y+58)], fill=gc, width=1)

        # Stats row
        sy = name_y + 70
        stats = [
            ("ATK", player.get('attack', character['attack'])),
            ("DEF", player.get('defense', character['defense'])),
            ("SPD", player.get('speed', character['speed'])),
        ]
        col_w = (self.char_width - 36) // 3
        for i, (label, val) in enumerate(stats):
            cx = 18 + col_w * i + col_w // 2
            # Stat box
            self._draw_rounded_rect(draw, cx-28, sy-4, cx+28, sy+32,
                                     fill=self.colors['bg2'], outline=None, radius=6)
            draw.text((cx, sy+10), str(val), fill=self.colors['text_white'],
                      anchor='mm', font=self._get_font(18, bold=True))
            draw.text((cx, sy+28), label, fill=gc, anchor='mm', font=self._get_font(9))

        # HP bar
        hp  = player.get('hp', character['max_hp'])
        mhp = player.get('max_hp', character['max_hp'])
        hp_color = self.colors['hp_low'] if hp < mhp * 0.3 else self.colors['hp_bar']
        draw.text((28, sy+48), "❤️ HP", fill=self.colors['text_white'], font=self._get_font(10))
        self._draw_bar(draw, 28, sy+64, self.char_width-56, 14, hp, mhp,
                       hp_color, self.colors['hp_bg'], f"{hp}/{mhp}")

        # CE bar
        ce  = player.get('cursed_energy', character['max_ce'])
        mce = player.get('max_cursed_energy', character['max_ce'])
        draw.text((28, sy+86), "⚡ CE", fill=self.colors['text_white'], font=self._get_font(10))
        self._draw_bar(draw, 28, sy+102, self.char_width-56, 14, ce, mce,
                       self.colors['ce_bar'], self.colors['ce_bg'], f"{ce}/{mce}")

        # XP bar
        if player.get('level'):
            xp  = player.get('xp', 0)
            xpn = player.get('xp_needed', 100)
            draw.text((28, sy+124), f"⭐ Level {player['level']} XP",
                      fill=self.colors['text_white'], font=self._get_font(10))
            self._draw_bar(draw, 28, sy+140, self.char_width-56, 14, xp, xpn,
                           self.colors['xp_bar'], self.colors['xp_bg'], f"{xp}/{xpn}")

        # Attacks preview
        attacks = character.get('attacks', [])
        ay = sy + 165
        draw.text((28, ay), "⚔️ Attacks:", fill=self.colors['text_gold'],
                  font=self._get_font(10, bold=True))
        for atk in attacks[:3]:
            ay += 18
            draw.text((28, ay), f"  {atk['num']}. {atk['name']} — {atk['dmg_mult']}x",
                      fill=self.colors['text_white'], font=self._get_font(9))

        # Cost
        cost = character.get('cost', 0)
        cost_str = "FREE 🎁" if cost == 0 else f"¥{cost:,}"
        draw.text((self.char_width//2, self.char_height-16), f"Cost: {cost_str}",
                  fill=self.colors['text_green'], anchor='mm', font=self._get_font(11, bold=True))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def generate_character_shop_display(self, character: Dict, player: Dict) -> io.BytesIO:
        """Character card for /characters browser."""
        h = self.char_height + 80
        img = Image.new('RGB', (self.char_width, h), self.colors['bg'])
        draw = ImageDraw.Draw(img)
        theme = _theme(character)
        grade = character.get('grade', 'Grade 4')
        gc = self.grade_colors.get(grade, self.colors['text_white'])
        primary = theme['primary']
        accent = theme['accent']

        self._draw_hex_pattern(draw, 0, 0, self.char_width, h, primary, 0.04)

        # Glow border
        for offset, alpha in [(0, 0.5), (3, 0.25), (6, 0.08)]:
            col = tuple(int(c * alpha) for c in primary)
            draw.rounded_rectangle([offset, offset, self.char_width-offset, h-offset],
                                   radius=14, outline=col, width=2)

        self._draw_rounded_rect(draw, 4, 4, self.char_width-4, h-4,
                                 fill=self.colors['card'], outline=gc, radius=14, width=2)

        # Portrait
        self._character_portrait(draw, 18, 14, self.char_width-36, 210, character)

        # Name + grade
        draw.text((self.char_width//2, 238), character['name'],
                  fill=self.colors['text_gold'], anchor='mm',
                  font=self._get_font(22, bold=True))
        draw.text((self.char_width//2, 262), f"[ {grade} ]",
                  fill=gc, anchor='mm', font=self._get_font(12, bold=True))

        draw.line([(28, 278), (self.char_width-28, 278)], fill=gc, width=1)

        # Stats row
        col_w = (self.char_width - 36) // 3
        for i, (label, val) in enumerate([("ATK", character['attack']),
                                           ("DEF", character['defense']),
                                           ("SPD", character['speed'])]):
            cx = 18 + col_w*i + col_w//2
            self._draw_rounded_rect(draw, cx-26, 286, cx+26, 318,
                                     fill=self.colors['bg2'], outline=None, radius=6)
            draw.text((cx, 298), str(val), fill=self.colors['text_white'],
                      anchor='mm', font=self._get_font(16, bold=True))
            draw.text((cx, 314), label, fill=gc, anchor='mm', font=self._get_font(8))

        # HP/CE
        draw.text((self.char_width//2, 332),
                  f"❤️ {character['max_hp']}  ⚡ {character['max_ce']}",
                  fill=self.colors['text_white'], anchor='mm', font=self._get_font(11))

        # Technique
        draw.text((self.char_width//2, 352), f"✦ {character['technique']}",
                  fill=accent, anchor='mm', font=self._get_font(11, bold=True))

        draw.line([(28, 368), (self.char_width-28, 368)], fill=gc, width=1)

        # Attacks
        attacks = character.get('attacks', [])
        ay = 376
        draw.text((28, ay), "⚔️ Character Attacks:",
                  fill=self.colors['text_gold'], font=self._get_font(10, bold=True))
        for atk in attacks[:3]:
            ay += 20
            draw.text((28, ay), f"  {atk['num']}. {atk['name']}",
                      fill=self.colors['text_white'], font=self._get_font(10, bold=True))
            draw.text((280, ay), f"CE:{atk['ce_cost']} | {atk['dmg_mult']}x",
                      fill=self.colors['text_blue'], font=self._get_font(9))

        # Quote
        ay += 26
        quote = character.get('quote', '')
        if len(quote) > 55:
            quote = quote[:52] + "..."
        draw.text((self.char_width//2, ay), f'"{quote}"',
                  fill=(180, 180, 200), anchor='mm', font=self._get_font(9))

        # Cost badge
        cost = character.get('cost', 0)
        cost_str = "FREE 🎁" if cost == 0 else f"¥{cost:,}"
        cost_color = self.colors['text_green'] if cost == 0 else self.colors['text_gold']
        draw.text((self.char_width//2, h-22), f"💰 {cost_str}",
                  fill=cost_color, anchor='mm', font=self._get_font(13, bold=True))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def generate_pvp_battle_display(self, player1: Dict, player2: Dict,
                                    char1: Optional[Dict], char2: Optional[Dict],
                                    turn: int = 1) -> io.BytesIO:
        """Battle card showing both fighters."""
        img = Image.new('RGB', (self.battle_width, self.battle_height), self.colors['bg'])
        draw = ImageDraw.Draw(img)
        w, h = self.battle_width, self.battle_height

        # Background
        theme1 = _theme(char1) if char1 else CHARACTER_THEMES['default']
        theme2 = _theme(char2) if char2 else CHARACTER_THEMES['default']
        self._draw_hex_pattern(draw, 0, 0, w//2, h, theme1['primary'], 0.05)
        self._draw_hex_pattern(draw, w//2, 0, w//2, h, theme2['primary'], 0.05)

        # Title bar
        self._draw_rounded_rect(draw, 4, 4, w-4, 46,
                                 fill=self.colors['card'],
                                 outline=self.colors['text_gold'], radius=10, width=2)
        draw.text((w//2, 25), f"⚔️  ROUND {turn}  ⚔️",
                  fill=self.colors['text_gold'], anchor='mm',
                  font=self._get_font(20, bold=True))

        # P1 card (left)
        self._draw_battle_card(draw, 8, 54, w//2 - 12, h - 10, player1, char1, theme1)

        # VS
        draw.text((w//2, h//2), "VS", fill=self.colors['text_gold'],
                  anchor='mm', font=self._get_font(32, bold=True))
        draw.line([(w//2, 54), (w//2, h-10)],
                  fill=self.colors['text_gold'], width=1)

        # P2 card (right)
        self._draw_battle_card(draw, w//2 + 4, 54, w - 8, h - 10, player2, char2, theme2)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def _draw_battle_card(self, draw, x1, y1, x2, y2, player, char, theme):
        gc = self.grade_colors.get(player.get('rank', 'Grade 4'),
                                   self.colors['text_white'])
        primary = theme['primary']
        accent  = theme['accent']

        self._draw_rounded_rect(draw, x1+3, y1+3, x2-3, y2-3,
                                 fill=self.colors['card'], outline=gc, radius=10, width=2)

        cx = (x1+x2)//2
        cw = x2 - x1 - 8

        # Portrait
        ph = 140
        self._character_portrait(draw, x1+6, y1+6, cw-2, ph, char if char else {'name': '?', 'grade': player.get('rank', 'Grade 4')})

        ty = y1 + ph + 16

        # Name
        name = player.get('display_name', 'Player')[:16]
        draw.text((cx, ty), name, fill=self.colors['text_gold'],
                  anchor='mm', font=self._get_font(13, bold=True))

        if char:
            draw.text((cx, ty+17), char.get('name', ''), fill=self.colors['text_white'],
                      anchor='mm', font=self._get_font(9))

        draw.text((cx, ty+32), f"Lv.{player.get('level', 1)} | {player.get('rank', '?')}",
                  fill=gc, anchor='mm', font=self._get_font(9))

        # HP
        hp  = player.get('hp', 100)
        mhp = player.get('max_hp', 100)
        hp_col = self.colors['hp_low'] if hp < mhp * 0.3 else self.colors['hp_bar']
        draw.text((x1+10, ty+48), "HP", fill=self.colors['text_white'], font=self._get_font(8))
        self._draw_bar(draw, x1+10, ty+60, cw-10, 11, hp, mhp, hp_col,
                       self.colors['hp_bg'], f"{hp}/{mhp}")

        # CE
        ce  = player.get('cursed_energy', 50)
        mce = player.get('max_cursed_energy', 50)
        draw.text((x1+10, ty+78), "CE", fill=self.colors['text_white'], font=self._get_font(8))
        self._draw_bar(draw, x1+10, ty+90, cw-10, 11, ce, mce,
                       self.colors['ce_bar'], self.colors['ce_bg'], f"{ce}/{mce}")

        # Stats
        draw.text((x1+10, ty+110), f"ATK:{player.get('attack',0)}",
                  fill=self.colors['text_white'], font=self._get_font(9))
        draw.text((cx+4,  ty+110), f"DEF:{player.get('defense',0)}",
                  fill=self.colors['text_white'], font=self._get_font(9))
        draw.text((x1+10, ty+124), f"SPD:{player.get('speed',0)}",
                  fill=self.colors['text_white'], font=self._get_font(9))
        draw.text((cx+4,  ty+124), f"🏆{player.get('wins',0)}W",
                  fill=self.colors['text_green'], font=self._get_font(9))

    def generate_battle_result(self, winner: Dict, loser: Dict,
                               winner_char: Dict, reward: int) -> io.BytesIO:
        """Victory screen image."""
        img = Image.new('RGB', (self.battle_width, 400), self.colors['bg'])
        draw = ImageDraw.Draw(img)
        w = self.battle_width
        theme = _theme(winner_char) if winner_char else CHARACTER_THEMES['default']
        primary = theme['primary']

        self._draw_hex_pattern(draw, 0, 0, w, 400, primary, 0.06)

        for off, alpha in [(0, 0.7), (3, 0.3), (7, 0.1)]:
            col = tuple(int(c*alpha) for c in primary)
            draw.rounded_rectangle([off, off, w-off, 400-off], radius=14, outline=col, width=2)

        self._draw_rounded_rect(draw, 4, 4, w-4, 396,
                                 fill=self.colors['card'],
                                 outline=self.colors['text_gold'], radius=14, width=3)

        draw.text((w//2, 55), "🎉  VICTORY!  🎉",
                  fill=self.colors['text_gold'], anchor='mm',
                  font=self._get_font(32, bold=True))

        draw.text((w//2, 110), f"{winner['display_name']} WINS!",
                  fill=self.colors['text_green'], anchor='mm',
                  font=self._get_font(22, bold=True))

        if winner_char:
            draw.text((w//2, 148), f"Character: {winner_char['name']}",
                      fill=self.colors['text_white'], anchor='mm', font=self._get_font(14))

        draw.line([(80, 175), (w-80, 175)], fill=self.colors['text_gold'], width=2)

        draw.text((w//2, 210), "REWARDS",
                  fill=self.colors['text_gold'], anchor='mm',
                  font=self._get_font(18, bold=True))
        draw.text((w//2, 256), f"💰 Yen: +{reward:,}",
                  fill=self.colors['text_green'], anchor='mm', font=self._get_font(16))
        draw.text((w//2, 296), f"⭐ XP: +{int(reward * 0.5):,}",
                  fill=self.colors['text_green'], anchor='mm', font=self._get_font(16))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    # ─── Animated Battle GIF ─────────────────────────────────────────────────

    def generate_battle_gif(self,
                            attacker: Dict, defender: Dict,
                            attacker_char: Optional[Dict],
                            defender_char: Optional[Dict],
                            attack_name: str,
                            damage: int,
                            defender_hp_before: int,
                            defender_max_hp: int,
                            attacker_hp: int,
                            attacker_max_hp: int) -> io.BytesIO:
        """
        Generate a ~10-second animated battle GIF showing the attack sequence.
        20 frames × 500 ms = 10 seconds.
        """
        W, H = self.gif_width, self.gif_height
        theme_a = _theme(attacker_char) if attacker_char else CHARACTER_THEMES['default']
        theme_d = _theme(defender_char) if defender_char else CHARACTER_THEMES['default']

        frames = []
        n_frames = 20

        for fi in range(n_frames):
            frame = Image.new('RGB', (W, H), self.colors['bg'])
            draw  = ImageDraw.Draw(frame)

            # Background split
            self._draw_hex_pattern(draw, 0,   0, W//2, H, theme_a['primary'], 0.05)
            self._draw_hex_pattern(draw, W//2, 0, W//2, H, theme_d['primary'], 0.05)

            # Draw attacker (left side)
            self._draw_gif_fighter(draw, W//4, H//2 - 20, theme_a,
                                   attacker, attacker_char, facing_right=True,
                                   is_attacking=(4 <= fi <= 9))

            # Draw defender (right side)
            # Flash white on impact frames 10-13
            hit_flash = (10 <= fi <= 13)
            self._draw_gif_fighter(draw, 3*W//4, H//2 - 20, theme_d,
                                   defender, defender_char, facing_right=False,
                                   is_hit=hit_flash)

            # Attack projectile (frames 5-11)
            if 5 <= fi <= 11:
                progress = (fi - 5) / 6.0  # 0.0 → 1.0
                proj_x = int(W//4 + 80 + (W//2 - 80) * progress)
                proj_y = H//2 - 10
                self._draw_projectile(draw, proj_x, proj_y, theme_a, progress)

            # Impact explosion (frames 10-14)
            if 10 <= fi <= 14:
                intensity = 1.0 - (fi - 10) / 5.0
                self._draw_impact(draw, 3*W//4, H//2 - 20, theme_a, intensity)

            # HP bars at bottom
            self._draw_gif_hp_bars(draw, W, H,
                                   attacker, defender,
                                   attacker_hp, attacker_max_hp,
                                   defender_hp_before - (damage if fi >= 12 else 0),
                                   defender_max_hp,
                                   attack_name, damage, fi)

            # Round label
            draw.text((W//2, 18), f"⚔️ {attack_name}",
                      fill=self.colors['text_gold'], anchor='mm',
                      font=self._get_font(16, bold=True))

            frames.append(frame)

        # Save as GIF
        buf = io.BytesIO()
        frames[0].save(
            buf, format='GIF', save_all=True,
            append_images=frames[1:], optimize=False,
            duration=500, loop=0
        )
        buf.seek(0)
        return buf

    def _draw_gif_fighter(self, draw, cx, cy, theme, player, char, *,
                          facing_right=True, is_attacking=False, is_hit=False):
        """Draw a single fighter in the GIF frame."""
        primary = theme['primary']
        accent  = theme['accent']

        if is_hit:
            # Flash white
            for r in [50, 38, 28]:
                draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                             fill=(255, 255, 255, 60))
            return

        # Aura
        intensity = 1.3 if is_attacking else 0.8
        for r, a in [(55, 0.15*intensity), (42, 0.25*intensity), (30, 0.38*intensity)]:
            glow = tuple(min(255, int(c * a)) for c in primary)
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=glow)

        # Simple figure
        scale = 0.9 if not is_attacking else 1.1
        s = scale

        # Legs
        leg_offset = int(15*s)
        if is_attacking:
            # Lunge pose: legs spread
            draw.rounded_rectangle([cx-int(22*s), cy+int(18*s), cx-int(8*s), cy+int(62*s)],
                                   radius=4, fill=theme['secondary'])
            draw.rounded_rectangle([cx+int(4*s), cy+int(10*s), cx+int(18*s), cy+int(58*s)],
                                   radius=4, fill=theme['secondary'])
        else:
            draw.rounded_rectangle([cx-int(18*s), cy+int(20*s), cx-int(8*s), cy+int(60*s)],
                                   radius=4, fill=theme['secondary'])
            draw.rounded_rectangle([cx+int(8*s), cy+int(20*s), cx+int(18*s), cy+int(60*s)],
                                   radius=4, fill=theme['secondary'])

        # Torso
        tw = int(38*s)
        th = int(50*s)
        self._draw_rounded_rect(draw, cx-tw//2, cy-int(28*s),
                                 cx+tw//2, cy-int(28*s)+th,
                                 fill=primary, outline=accent, radius=8, width=2)

        # Attack arm extension
        arm_end_x = cx + (int(60*s) if (facing_right and is_attacking) else int(28*s))
        draw.rounded_rectangle([cx+tw//2, cy-int(22*s),
                                 arm_end_x, cy-int(12*s)],
                                radius=4, fill=theme['secondary'])
        # Back arm
        draw.rounded_rectangle([cx-tw//2-int(10*s), cy-int(22*s),
                                 cx-tw//2, cy-int(10*s)],
                                radius=4, fill=theme['secondary'])

        # Head
        hr = int(22*s)
        hcy = cy - int(28*s) - hr - 2
        draw.ellipse([cx-hr, hcy-hr, cx+hr, hcy+hr],
                     fill=theme['secondary'], outline=accent, width=2)

        # Glowing eyes
        ey = hcy - int(3*s)
        er = max(2, int(4*s))
        draw.ellipse([cx-int(8*s)-er, ey-er, cx-int(8*s)+er, ey+er], fill=accent)
        draw.ellipse([cx+int(8*s)-er, ey-er, cx+int(8*s)+er, ey+er], fill=accent)

        # Attacking energy in hand
        if is_attacking:
            ex = arm_end_x
            ey2 = cy - int(17*s)
            for r2 in [16, 12, 8]:
                a2 = 0.9 - r2/20
                gc = tuple(min(255, int(c*a2)) for c in accent)
                draw.ellipse([ex-r2, ey2-r2, ex+r2, ey2+r2], fill=gc)

        # Name tag
        name = (player.get('display_name') or 'Fighter')[:12]
        draw.text((cx, cy + int(70*s)), name,
                  fill=self.colors['text_gold'], anchor='mm',
                  font=self._get_font(10, bold=True))

    def _draw_projectile(self, draw, x, y, theme, progress):
        """Draw a cursed energy projectile."""
        primary = theme['primary']
        accent  = theme['accent']
        size = int(8 + 12 * math.sin(progress * math.pi))

        # Trail
        trail_len = int(60 * (1 - progress * 0.5))
        for t in range(trail_len, 0, -8):
            alpha = 0.6 * (1 - t / trail_len)
            tc = tuple(int(c * alpha) for c in primary)
            ts = max(2, int(size * (1 - t / trail_len * 0.6)))
            draw.ellipse([x-t-ts, y-ts, x-t+ts, y+ts], fill=tc)

        # Projectile
        for r, a in [(size+6, 0.2), (size+3, 0.4), (size, 1.0)]:
            ac = tuple(int(c * a) for c in accent)
            draw.ellipse([x-r, y-r, x+r, y+r], fill=ac)

        # Sparkles
        for ang in range(0, 360, 60):
            rad = math.radians(ang)
            sx = x + int(math.cos(rad) * (size + 10))
            sy = y + int(math.sin(rad) * (size + 10))
            draw.ellipse([sx-3, sy-3, sx+3, sy+3], fill=accent)

    def _draw_impact(self, draw, x, y, theme, intensity):
        """Draw impact explosion effect."""
        primary = theme['primary']
        accent  = theme['accent']
        max_r = int(70 * intensity)

        # Explosion rings
        for r in range(10, max_r, 12):
            alpha = intensity * (1 - r / max_r)
            col = tuple(int(c * alpha) for c in accent)
            draw.ellipse([x-r, y-r, x+r, y+r], outline=col, width=3)

        # Rays
        for ang in range(0, 360, 30):
            rad = math.radians(ang)
            length = int(max_r * 0.8)
            ex = x + int(math.cos(rad) * length)
            ey = y + int(math.sin(rad) * length)
            col = tuple(int(c * intensity * 0.8) for c in primary)
            draw.line([x, y, ex, ey], fill=col, width=2)

        # Core flash
        cr = int(20 * intensity)
        draw.ellipse([x-cr, y-cr, x+cr, y+cr],
                     fill=tuple(min(255, int(c * intensity)) for c in accent))

    def _draw_gif_hp_bars(self, draw, W, H, attacker, defender,
                          a_hp, a_max, d_hp, d_max,
                          attack_name, damage, fi):
        """Draw HP bars and info at the bottom of GIF frames."""
        bar_y = H - 80
        bar_h = 12
        bar_w = W // 2 - 40

        # Attacker HP bar (left)
        draw.text((20, bar_y - 16), attacker.get('display_name', 'P1')[:12],
                  fill=self.colors['text_gold'], font=self._get_font(10, bold=True))
        self._draw_bar(draw, 20, bar_y, bar_w, bar_h,
                       max(0, a_hp), max(1, a_max),
                       self.colors['hp_bar'], self.colors['hp_bg'],
                       f"{max(0, a_hp)}/{a_max}")

        # CE bar attacker
        a_ce  = attacker.get('cursed_energy', 0)
        a_mce = attacker.get('max_cursed_energy', 1)
        self._draw_bar(draw, 20, bar_y + 18, bar_w, 8,
                       a_ce, a_mce, self.colors['ce_bar'], self.colors['ce_bg'])

        # Defender HP bar (right)
        draw.text((W - bar_w - 20, bar_y - 16), defender.get('display_name', 'P2')[:12],
                  fill=self.colors['text_gold'], font=self._get_font(10, bold=True))
        self._draw_bar(draw, W - bar_w - 20, bar_y, bar_w, bar_h,
                       max(0, d_hp), max(1, d_max),
                       self.colors['hp_bar'] if d_hp > d_max * 0.3 else self.colors['hp_low'],
                       self.colors['hp_bg'], f"{max(0,d_hp)}/{d_max}")

        d_ce  = defender.get('cursed_energy', 0)
        d_mce = defender.get('max_cursed_energy', 1)
        self._draw_bar(draw, W - bar_w - 20, bar_y + 18, bar_w, 8,
                       d_ce, d_mce, self.colors['ce_bar'], self.colors['ce_bg'])

        # Damage text (appears on impact)
        if fi >= 12 and damage > 0:
            dmg_x = W - bar_w // 2 - 20
            draw.text((dmg_x, bar_y - 34), f"-{damage} DMG!",
                      fill=self.colors['text_red'], anchor='mm',
                      font=self._get_font(14, bold=True))

    def generate_elixir_image(self, item: Dict, player: Optional[Dict] = None,
                              quantity: int = 1) -> io.BytesIO:
        """Generate a themed purchase card for any shop item."""
        W, H = 300, 360
        img  = Image.new('RGB', (W, H), self.colors['bg'])
        draw = ImageDraw.Draw(img)

        # Pick color by item type
        itype = item.get('type', 'elixir')
        if itype == 'elixir':
            colors = [(80, 40, 180), (140, 60, 255), (200, 140, 255)]
        elif itype == 'weapon':
            colors = [(180, 60, 20), (240, 100, 40), (255, 200, 100)]
        elif itype == 'consumable':
            colors = [(20, 140, 80), (40, 200, 120), (120, 255, 180)]
        else:
            colors = [(60, 100, 200), (100, 160, 255), (200, 220, 255)]

        primary, secondary, accent = colors

        self._draw_hex_pattern(draw, 0, 0, W, H, primary, 0.08)

        # Glow background
        cx, cy = W//2, H//2 - 20
        for r, a in [(100, 0.1), (80, 0.18), (60, 0.28)]:
            glow = tuple(int(c*a) for c in secondary)
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=glow)

        # Bottle shape
        # Body
        bx, by, bw, bh = cx-35, cy-45, 70, 80
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=20,
                                fill=secondary, outline=accent, width=3)
        # Liquid fill
        liq_h = int(bh * 0.65)
        draw.rounded_rectangle([bx+4, by+bh-liq_h, bx+bw-4, by+bh-4],
                                radius=16, fill=accent)
        # Shine
        draw.ellipse([bx+10, by+8, bx+22, by+20], fill=(255, 255, 255, 180))

        # Neck
        nx, nw, nh = cx-12, 24, 20
        draw.rectangle([nx, by-nh, nx+nw, by], fill=secondary)
        draw.rectangle([nx, by-nh, nx+nw, by-nh+4], fill=accent)

        # Cork
        draw.rounded_rectangle([nx-4, by-nh-12, nx+nw+4, by-nh+2],
                                radius=4, fill=(160, 100, 40), outline=(100, 60, 10), width=2)

        # Sparkles around bottle
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            sx = cx + int(math.cos(rad) * 70)
            sy = cy + int(math.sin(rad) * 70)
            sr = random.randint(3, 6)
            draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=accent)

        # Item name, rarity, quantity, and purchase details
        name = item.get('name', 'Item')
        if len(name) > 22:
            name = name[:20] + ".."
        draw.text((W//2, H-60), name, fill=self.colors['text_gold'],
                  anchor='mm', font=self._get_font(13, bold=True))

        rarity = {
            'weapon': 'RARE', 'technique': 'EPIC', 'consumable': 'COMMON',
            'elixir': 'LEGENDARY', 'special': 'MYTHIC', 'upgrade': 'RARE'
        }.get(itype, 'COMMON')
        draw.text((W//2, H-82), f"{rarity}  •  QTY {quantity}",
                  fill=accent, anchor='mm', font=self._get_font(10, bold=True))
        price = item.get('price', 0)
        draw.text((W//2, H-38), f"¥{price:,}" +
                  (f"  •  {player.get('display_name', '')[:18]}" if player else ""),
                  fill=self.colors['text_green'], anchor='mm',
                  font=self._get_font(11))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
