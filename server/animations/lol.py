"""
Animations League of Legends (événements envoyés par client/watchers/lol.py).
"""

import math

from engine import animation
from animations._fx import Sparkles, angle, lerp, scale, smoothstep

APP = "lol"


@animation(APP, "kill")
def kill(ctx, data):
    """Flash rouge vif × 3, chaque flash redescend en douceur."""
    for _ in range(3):
        if not ctx.flash((255, 0, 0), hold=0.06, fade=0.18):
            return
    ctx.end()


@animation(APP, "death")
def death(ctx, data):
    """Bleu qui s'éteint progressivement."""
    ctx.fill(0, 0, 255)
    if ctx.sleep(0.1):
        ctx.fade_out(1.2)
    ctx.end()


@animation(APP, "assist")
def assist(ctx, data):
    """Assist : deux vagues dorées partent des bords gauche et droit et se rejoignent au centre."""
    gold = (255, 170, 30)
    xs = [x for x, _ in ctx.positions]
    for k in range(19):
        front = k / 18 * 0.5                                  # 0 → 0.5 (centre)
        colors = []
        for x in xs:
            d = abs(min(x, 1 - x) - front)                    # distance au front de chaque vague
            colors.append(scale(gold, max(0.0, 1 - d / 0.12)))
        ctx.show_colors(colors)
        if not ctx.sleep(1 / 30):
            return
    # éclat au centre qui s'éteint
    ctx.show_colors([scale(gold, math.exp(-((x - 0.5) / 0.15) ** 2)) for x in xs])
    if ctx.fade_out(0.4):
        ctx.end()


@animation(APP, "multikill")
def multikill(ctx, data):
    """Flashs orange de plus en plus rapides selon le streak."""
    streak  = data.get("streak", 2)
    flashes = min(streak, 6)
    fade    = max(0.08, 0.22 - streak * 0.025)
    for _ in range(flashes):
        if not ctx.flash((255, 50, 0), hold=0.04, fade=fade):
            return
    ctx.end()


@animation(APP, "ace")
def ace(ctx, data):
    """Vague dorée de gauche à droite."""
    for _ in range(2):
        for i in range(ctx.num_leds):
            ctx.set_all(0, 0, 0)
            for j in range(max(0, i - 4), i + 1):
                intensity = 255 - (i - j) * 50
                ctx.set_pixel(j, intensity, intensity // 2, 0)
            ctx.show()
            if not ctx.sleep(0.03):
                return
    if ctx.fade_out(0.3):
        ctx.end()


def _steal_flash(ctx, data):
    """Objectif volé : stroboscope blanc avant l'animation. Renvoie False si interrompu."""
    if not data.get("stolen"):
        return True
    for _ in range(4):
        if not ctx.flash((255, 255, 255), hold=0.04, fade=0.1):
            return False
    return True


DRAGON_COLORS = {
    "Fire":     (255, 60,  0),
    "Infernal": (255, 60,  0),
    "Water":    (0,   150, 255),
    "Ocean":    (0,   150, 255),
    "Air":      (180, 240, 255),
    "Mountain": (120, 80,  40),
    "Earth":    (120, 80,  40),
    "Elder":    (255, 200, 0),
    "Hextech":  (100, 0,   255),
    "Chemtech": (50,  200, 50),
}


@animation(APP, "dragon")
def dragon(ctx, data):
    """Couleur selon le type de dragon, pulse 2×."""
    if not _steal_flash(ctx, data):
        return
    color = DRAGON_COLORS.get(data.get("type", ""), (255, 255, 255))
    for _ in range(2):
        if not ctx.flash(color, hold=0.3, fade=0.35):
            return
    ctx.end()


@animation(APP, "baron")
def baron(ctx, data):
    """Pulse violet lent × 3."""
    if not _steal_flash(ctx, data):
        return
    steps = list(range(0, 200, 8)) + list(range(200, 0, -8))
    for _ in range(3):
        for brightness in steps:
            ctx.fill(brightness, 0, brightness)
            if not ctx.sleep(0.02):
                return
    ctx.end()


@animation(APP, "herald")
def herald(ctx, data):
    """Pulse violet clair × 2."""
    if not _steal_flash(ctx, data):
        return
    for _ in range(2):
        if not ctx.flash((100, 0, 200), hold=0.3, fade=0.35):
            return
    ctx.end()


@animation(APP, "turret")
def turret(ctx, data):
    """Flash cyan."""
    if ctx.flash((0, 200, 200), hold=0.15, fade=0.4):
        ctx.end()


@animation(APP, "inhibitor")
def inhibitor(ctx, data):
    """Flash orange × 2."""
    for _ in range(2):
        if not ctx.flash((255, 100, 0), hold=0.15, fade=0.3):
            return
    ctx.end()


def _rainbow(pos):
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def _win(ctx):
    """Vague arc-en-ciel qui parcourt le ruban 3×."""
    n = ctx.num_leds
    for _ in range(3):
        for offset in range(256):
            for i in range(n):
                ctx.set_pixel(i, *_rainbow((i * 256 // n + offset) % 256))
            ctx.show()
            if not ctx.sleep(0.015):
                return
    ctx.fade_out(1.0)


def _lose(ctx):
    """Extinction rouge progressive."""
    ctx.fill(200, 0, 0)
    if ctx.sleep(0.5):
        ctx.fade_out(2.5)


@animation(APP, "game_end")
def game_end(ctx, data):
    if data.get("result") == "Win":
        _win(ctx)
    else:
        _lose(ctx)


@animation(APP, "game_start")
def game_start(ctx, data):
    """Balayage blanc au démarrage de la partie."""
    for i in range(ctx.num_leds):
        ctx.set_pixel(i, 200, 200, 200)
        ctx.show()
        if not ctx.sleep(0.03):
            return
    if ctx.sleep(0.3):
        ctx.end()


# ── Ambiances (tournent en fond pendant la partie) ─────────────────────────────

IDLE_BRIGHTNESS = 0.4    # les ambiances restent discrètes

TERRAIN_COLORS = {       # couleur de la rivière une fois l'âme du dragon révélée
    "Infernal": (255, 70,  0),
    "Ocean":    (0,   110, 255),
    "Mountain": (150, 90,  40),
    "Cloud":    (170, 230, 255),
    "Hextech":  (90,  40,  255),
    "Chemtech": (60,  220, 40),
}


@animation(APP, "theme_rift", idle=True)
def theme_rift(ctx, data):
    """
    Faille de l'invocateur, vue comme la minimap : base bleue en bas à gauche, base
    rouge en haut à droite, jungle verte entre les deux et rivière scintillante sur
    la diagonale. La rivière prend la couleur du terrain élémentaire.
    """
    blue, jungle, red = (20, 60, 255), (10, 130, 25), (255, 25, 15)
    river = TERRAIN_COLORS.get(data.get("terrain"), (0, 160, 170))
    # 0 = base bleue (bas-gauche), 1 = base rouge (haut-droite), 0.5 = rivière
    diag = [(x + (1 - y)) / 2 for x, y in ctx.positions]

    for t in ctx.loop(30):
        colors = []
        for i, d in enumerate(diag):
            if d < 0.5:
                c = lerp(blue, jungle, smoothstep(0.08, 0.38, d))
            else:
                c = lerp(jungle, red, smoothstep(0.62, 0.92, d))
            water = math.exp(-((d - 0.5) / 0.08) ** 2) * (0.75 + 0.25 * math.sin(t * 2.5 + i * 0.7))
            c = lerp(c, river, water)
            breath = 0.85 + 0.15 * math.sin(t * 0.7 + d * 5)
            colors.append(scale(c, IDLE_BRIGHTNESS * breath))
        ctx.show_colors(colors)


@animation(APP, "theme_aram", idle=True)
def theme_aram(ctx, data):
    """Abîme hurlant : bleu glacier qui ondule doucement, avec des flocons qui scintillent."""
    deep, frost, snow = (40, 90, 255), (150, 200, 255), (255, 255, 255)
    snowflakes = Sparkles(ctx.num_leds, rate=0.3, decay=0.92)

    for t in ctx.loop(30):
        flakes = snowflakes.step()
        colors = []
        for i, (x, y) in enumerate(ctx.positions):
            wave = 0.5 + 0.5 * math.sin(t * 0.6 + x * 4 - y * 2)
            c = lerp(deep, frost, wave)
            c = lerp(c, snow, flakes[i])
            colors.append(scale(c, IDLE_BRIGHTNESS))
        ctx.show_colors(colors)


@animation(APP, "theme_arena", idle=True)
def theme_arena(ctx, data):
    """Arena : braises orangées et un éclat doré qui tourne autour de l'écran comme dans l'arène."""
    ember, gold = (255, 60, 0), (255, 190, 50)
    angles = [angle(p) for p in ctx.positions]

    for t in ctx.loop(30):
        head = (t * 0.2) % 1.0
        colors = []
        for i, a in enumerate(angles):
            dist = min(abs(a - head), 1 - abs(a - head))      # distance angulaire, en tours
            glow = math.exp(-(dist / 0.06) ** 2)
            flicker = 0.7 + 0.3 * math.sin(t * 3.1 + i * 1.7) * math.sin(t * 1.3 + i)
            c = lerp(scale(ember, flicker), gold, glow)
            colors.append(scale(c, IDLE_BRIGHTNESS * (0.6 + 0.4 * glow)))
        ctx.show_colors(colors)
