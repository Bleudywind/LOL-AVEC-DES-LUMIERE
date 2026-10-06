"""
Animations VALORANT (événements envoyés par client/watchers/valorant.py).

Couleurs : ton équipe en turquoise (comme dans le HUD), l'ennemi en rouge Valorant.
"""

import math

from engine import animation
from animations._fx import Sparkles, angle, lerp, scale

APP = "valorant"

IDLE_BRIGHTNESS = 0.4
ALLY  = (20, 230, 190)
ENEMY = (255, 70, 85)
WHITE = (255, 255, 255)
GOLD  = (255, 190, 60)

# Palette de chaque carte (nom de code interne → couleurs qui défilent en ambiance)
MAP_PALETTES = {
    "Ascent":   [(255, 140, 60), (90, 170, 255), (240, 210, 170)],    # Venise : terre cuite, ciel
    "Duality":  [(255, 150, 40), (0, 200, 190), (200, 90, 30)],       # Bind : sable, téléporteurs
    "Triad":    [(40, 170, 60), (255, 190, 40), (200, 30, 40)],       # Haven : jardins, or, temple
    "Bonsai":   [(255, 40, 160), (120, 60, 255), (30, 200, 120)],     # Split : néons de Tokyo
    "Port":     [(120, 220, 255), (255, 255, 255), (255, 200, 0)],    # Icebox : glace, grue jaune
    "Foxtrot":  [(0, 220, 200), (255, 220, 150), (60, 140, 255)],     # Breeze : lagon, sable
    "Canyon":   [(255, 110, 20), (0, 190, 200), (150, 60, 200)],      # Fracture : deux moitiés
    "Pitt":     [(0, 60, 200), (255, 120, 90), (0, 200, 220)],        # Pearl : sous-marin, corail
    "Jam":      [(20, 200, 120), (230, 40, 180), (255, 190, 60)],     # Lotus : jade, lotus, or
    "Juliett":  [(255, 120, 30), (255, 60, 120), (120, 40, 200)],     # Sunset : coucher de soleil
    "Infinity": [(20, 30, 140), (120, 40, 255), (0, 180, 255)],       # Abyss : abîme violet
    "Range":    [ENEMY, (255, 255, 255)],                             # Champ de tir
}
DEFAULT_PALETTE = [ENEMY, ALLY]


def _palette_at(palette, u):
    """Couleur à la position u (0..1, cyclique) dans une palette."""
    u = (u % 1.0) * len(palette)
    k = int(u)
    return lerp(palette[k], palette[(k + 1) % len(palette)], u - k)


def _scoreboard(ctx, ally, enemy, target):
    """
    Score sur le bord haut : ton équipe se remplit depuis la gauche, l'ennemi depuis
    la droite, vers le centre (proportionnellement aux manches à gagner).
    """
    top = ctx.layout.side("top") or list(range(ctx.num_leds))
    half = len(top) // 2
    lit_ally = min(half, round(ally / target * half))
    lit_enemy = min(half, round(enemy / target * half))
    colors = [(0, 0, 0)] * ctx.num_leds
    for k in range(half):
        colors[top[k]] = ALLY if k < lit_ally else scale(ALLY, 0.08)
        colors[top[-1 - k]] = ENEMY if k < lit_enemy else scale(ENEMY, 0.08)
    return colors


def _fade(ctx, colors, duration, fade_in=False):
    steps = max(1, int(duration * 30))
    for k in range(steps + 1):
        f = k / steps if fade_in else 1 - k / steps
        ctx.show_colors([scale(c, f) for c in colors])
        if not ctx.sleep(1 / 30):
            return False
    return True


MATCH_POINT_COLORS = {"ally": ALLY, "enemy": ENEMY, "both": WHITE}


def _match_point_pulses(ctx, side):
    color = MATCH_POINT_COLORS.get(side, WHITE)
    for _ in range(3):
        if not _fade(ctx, [color] * ctx.num_leds, 0.25, fade_in=True):
            return False
        if not _fade(ctx, [color] * ctx.num_leds, 0.35):
            return False
    return True


# ── Ambiances ──────────────────────────────────────────────────────────────────

@animation(APP, "theme_menu", idle=True)
def theme_menu(ctx, data):
    """Menus : rouge Valorant qui respire, traversé de temps en temps par un trait blanc."""
    angles = [angle(p) for p in ctx.positions]
    for t in ctx.loop(30):
        breath = 0.6 + 0.4 * math.sin(t * 0.8)
        head = (t / 6) % 1.0                                   # un tour toutes les 6 s
        colors = []
        for a in angles:
            d = min(abs(a - head), 1 - abs(a - head))
            colors.append(lerp(scale(ENEMY, breath), WHITE, math.exp(-(d / 0.03) ** 2)))
        ctx.show_colors([scale(c, IDLE_BRIGHTNESS) for c in colors])


@animation(APP, "theme_pregame", idle=True)
def theme_pregame(ctx, data):
    """Sélection d'agent : turquoise qui pulse, avec un point blanc qui tourne comme un compte à rebours."""
    angles = [angle(p) for p in ctx.positions]
    for t in ctx.loop(30):
        pulse = 0.55 + 0.45 * math.sin(t * 2 * math.pi * 0.8)
        head = (t / 3) % 1.0
        colors = []
        for a in angles:
            d = min(abs(a - head), 1 - abs(a - head))
            colors.append(lerp(scale(ALLY, pulse), WHITE, math.exp(-(d / 0.025) ** 2)))
        ctx.show_colors([scale(c, IDLE_BRIGHTNESS) for c in colors])


@animation(APP, "theme_map", idle=True)
def theme_map(ctx, data):
    """
    En jeu : les couleurs de la carte défilent doucement autour de l'écran.
    Balle de match : pulsation turquoise (pour toi), rouge (pour l'ennemi) ou blanche
    (manche décisive) toutes les 2 s.
    """
    palette = MAP_PALETTES.get(data.get("map"), DEFAULT_PALETTE)
    mp = data.get("match_point")
    mp_color = MATCH_POINT_COLORS.get(mp, WHITE)
    angles = [angle(p) for p in ctx.positions]

    for t in ctx.loop(30):
        pulse = math.exp(-(((t % 2.0) - 0.3) / 0.15) ** 2) if mp else 0.0
        colors = []
        for i, a in enumerate(angles):
            c = _palette_at(palette, a + t * 0.03)
            shimmer = 0.85 + 0.15 * math.sin(t * 1.3 + i * 0.4)
            c = lerp(scale(c, shimmer), mp_color, 0.7 * pulse)
            colors.append(scale(c, IDLE_BRIGHTNESS * (1 + pulse)))
        ctx.show_colors(colors)


# ── Événements ─────────────────────────────────────────────────────────────────

@animation(APP, "agent_select")
def agent_select(ctx, data):
    """Entrée en sélection d'agent : éclair blanc qui retombe en turquoise, trois « ticks »."""
    for k in range(20):
        ctx.show_colors([lerp(WHITE, ALLY, k / 19)] * ctx.num_leds)
        if not ctx.sleep(1 / 30):
            return
    for _ in range(3):
        if not ctx.flash(ALLY, hold=0.05, fade=0.3):
            return
    ctx.fill(*ALLY)
    if ctx.sleep(0.1):
        ctx.end()


@animation(APP, "match_start")
def match_start(ctx, data):
    """Début du match : ton équipe arrive par la gauche, l'ennemi par la droite, choc au centre."""
    xs = [x for x, _ in ctx.positions]
    for k in range(31):
        front = k / 30 * 0.5
        colors = [ALLY if x <= front else ENEMY if x >= 1 - front else (0, 0, 0) for x in xs]
        ctx.show_colors(colors)
        if not ctx.sleep(1 / 30):
            return
    ctx.fill(*WHITE)
    if ctx.sleep(0.12):
        ctx.end(fade=0.6)


@animation(APP, "round_won")
def round_won(ctx, data):
    """Manche gagnée : double flash turquoise, puis le score sur le bord haut."""
    for _ in range(2):
        if not ctx.flash(ALLY, hold=0.06, fade=0.2):
            return
    _show_score(ctx, data)


@animation(APP, "round_lost")
def round_lost(ctx, data):
    """Manche perdue : rouge qui tombe du haut vers le bas, puis le score."""
    ys = [y for _, y in ctx.positions]
    for k in range(21):
        front = k / 20
        ctx.show_colors([scale(ENEMY, 0.8) if y <= front else (0, 0, 0) for y in ys])
        if not ctx.sleep(1 / 30):
            return
    if not _fade(ctx, [scale(ENEMY, 0.8)] * ctx.num_leds, 0.4):
        return
    _show_score(ctx, data)


def _show_score(ctx, data):
    board = _scoreboard(ctx, data.get("ally", 0), data.get("enemy", 0), data.get("target") or 13)
    if not _fade(ctx, board, 0.3, fade_in=True) or not ctx.sleep(2.0):
        return
    if data.get("match_point"):
        if not _fade(ctx, board, 0.4) or not _match_point_pulses(ctx, data["match_point"]):
            return
    ctx.end()


@animation(APP, "match_end")
def match_end(ctx, data):
    """Victoire : vagues turquoise et blanches, étincelles. Défaite : rouge qui s'éteint lentement."""
    result = data.get("result")
    if result == "win":
        sparks = Sparkles(ctx.num_leds, rate=1.5, decay=0.85)
        angles = [angle(p) for p in ctx.positions]
        for t in ctx.loop(30):
            if t > 7:
                break
            glints = sparks.step()
            colors = [lerp(scale(ALLY, 0.6 + 0.4 * math.sin(2 * math.pi * (a * 2 - t))), WHITE, glints[i])
                      for i, a in enumerate(angles)]
            ctx.show_colors(colors)
    elif result == "loss":
        ctx.fill(*ENEMY)
        if ctx.sleep(0.6):
            _fade(ctx, [ENEMY] * ctx.num_leds, 3.0)
    else:
        if _fade(ctx, [WHITE] * ctx.num_leds, 0.3, fade_in=True):
            _fade(ctx, [WHITE] * ctx.num_leds, 1.5)
    ctx.end()
