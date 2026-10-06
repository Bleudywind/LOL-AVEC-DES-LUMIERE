"""
Animations Teamfight Tactics (événements envoyés par client/watchers/tft.py).
"""

import math
import random

from engine import animation
from animations._fx import Sparkles, angle, lerp, scale

APP = "tft"

IDLE_BRIGHTNESS = 0.4
PURPLE = (130, 40, 255)
BLUE   = (0, 140, 255)
GOLD   = (255, 180, 30)
RED    = (255, 15, 20)


def _gauge_leds(ctx):
    """LEDs du bas de l'écran de gauche à droite (tout le ruban si pas calibré)."""
    return ctx.layout.side("bottom")[::-1] or list(range(ctx.num_leds))


# ── Ambiance ───────────────────────────────────────────────────────────────────

@animation(APP, "theme", idle=True)
def theme(ctx, data):
    """
    Convergence : tourbillon violet / bleu avec des étincelles dorées.
    Vie basse (data["danger"]) : pulsation rouge comme un battement de cœur.
    """
    angles = [angle(p) for p in ctx.positions]
    sparks = Sparkles(ctx.num_leds, rate=0.25, decay=0.88)

    if data.get("danger"):
        for t in ctx.loop(30):
            beat = t % 1.0                                   # 60 bpm : double battement
            pulse = math.exp(-((beat - 0.1) / 0.05) ** 2) + 0.6 * math.exp(-((beat - 0.3) / 0.05) ** 2)
            c = lerp(lerp(PURPLE, RED, 0.6), RED, pulse)     # rouge violacé → rouge vif
            ctx.show_colors([scale(c, IDLE_BRIGHTNESS * (0.6 + 0.9 * pulse))] * ctx.num_leds)
        return

    for t in ctx.loop(30):
        glints = sparks.step()
        colors = []
        for i, a in enumerate(angles):
            swirl = 0.5 + 0.5 * math.sin(2 * math.pi * (a * 2 - t * 0.15))
            c = lerp(PURPLE, BLUE, swirl)
            c = lerp(c, GOLD, glints[i])
            colors.append(scale(c, IDLE_BRIGHTNESS))
        ctx.show_colors(colors)


# ── Événements ─────────────────────────────────────────────────────────────────

@animation(APP, "game_start")
def game_start(ctx, data):
    """Le tourbillon se remplit autour de l'écran, puis l'ambiance démarre."""
    order = sorted(range(ctx.num_leds), key=lambda i: angle(ctx.positions[i]))
    colors = [(0, 0, 0)] * ctx.num_leds
    for k, i in enumerate(order):
        colors[i] = lerp(PURPLE, GOLD, k / len(order))
        ctx.show_colors(colors)
        if not ctx.sleep(0.02):
            return
    if ctx.sleep(0.4):
        ctx.end()


@animation(APP, "damage")
def damage(ctx, data):
    """
    Round perdu : flash rouge d'autant plus fort que les dégâts sont gros,
    puis jauge de vie restante en bas de l'écran.
    """
    dmg = data.get("damage", 5)
    hp = max(0, min(100, data.get("hp", 100)))
    strength = min(1.0, 0.35 + dmg / 20)

    for _ in range(2 if dmg >= 10 else 1):
        if not ctx.flash(scale(RED, strength), hold=0.06, fade=0.22):
            return

    gauge = _gauge_leds(ctx)
    lit = round(len(gauge) * hp / 100)
    hp_color = lerp(RED, (0, 255, 60), hp / 100)
    colors = [(0, 0, 0)] * ctx.num_leds
    for k, i in enumerate(gauge):
        colors[i] = hp_color if k < lit else (25, 0, 0)
    for k in range(1, 11):                          # apparition
        ctx.show_colors([scale(c, k / 10) for c in colors])
        if not ctx.sleep(0.03):
            return
    if ctx.sleep(1.5):
        ctx.end()


@animation(APP, "level_up")
def level_up(ctx, data):
    """Montée de niveau : vague dorée qui monte du bas vers le haut, puis un éclat."""
    heights = [1 - y for _, y in ctx.positions]     # 0 = bas, 1 = haut
    for k in range(31):
        front = k / 30 * 1.1
        # derrière le front : or tamisé ; sur le front : or vif
        colors = [scale(GOLD, 0.3 + 0.7 * math.exp(-((front - h) / 0.08) ** 2)) if h <= front
                  else (0, 0, 0) for h in heights]
        ctx.show_colors(colors)
        if not ctx.sleep(1 / 30):
            return
    ctx.fill(*GOLD)
    if ctx.sleep(0.15):
        ctx.end()


@animation(APP, "eliminated")
def eliminated(ctx, data):
    """Éliminé : violet qui se brise, les LEDs s'éteignent une à une."""
    colors = [PURPLE] * ctx.num_leds
    ctx.show_colors(colors)
    if not ctx.sleep(0.4):
        return
    order = list(range(ctx.num_leds))
    random.shuffle(order)
    for i in order:
        colors[i] = (0, 0, 0)
        ctx.show_colors([lerp(c, (60, 0, 20), 0.5) if c != (0, 0, 0) else c for c in colors])
        if not ctx.sleep(0.04):
            return
    ctx.end()


@animation(APP, "game_end")
def game_end(ctx, data):
    """Victoire : tourbillon or et violet rapide. Sinon : même chose qu'une élimination."""
    if data.get("result") != "Win":
        eliminated(ctx, data)
        return
    angles = [angle(p) for p in ctx.positions]
    for t in ctx.loop(30):
        if t > 8:
            break
        colors = [lerp(PURPLE, GOLD, 0.5 + 0.5 * math.sin(2 * math.pi * (a * 3 - t))) for a in angles]
        ctx.show_colors(colors)
    ctx.fade_out(1.0)
