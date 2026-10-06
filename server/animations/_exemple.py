"""
Modèle pour ajouter les animations d'une nouvelle application.

1. Copie ce fichier en animations/<mon_app>.py (sans le _ devant, sinon il est ignoré)
2. Mets APP = le même `name` que le watcher côté PC (client/watchers/<mon_app>.py)
3. Une fonction par événement, décorée avec @animation(APP, "<event>")
4. Redémarre led_server.py

Outils disponibles dans `ctx` :
    ctx.num_leds                 nombre de LEDs
    ctx.fill(r, g, b)            couleur unie, envoyée tout de suite
    ctx.set_pixel(i, r, g, b)    modifie une LED (envoyée au prochain ctx.show())
    ctx.set_all(r, g, b)         modifie toutes les LEDs (sans envoyer)
    ctx.show()                   envoie le buffer au ruban
    ctx.off()                    éteint tout
    ctx.sleep(s)                 attend s secondes ; renvoie False si un autre
                                 événement est arrivé → il faut alors s'arrêter
    ctx.layout.side("top")       indices des LEDs du haut (gauche → droite),
                                 "left" (bas → haut), "right" (haut → bas),
                                 "bottom" (droite → gauche). [] si non calibré.
    ctx.layout.position(i)       (x, y) de la LED i, 0..1, (0,0) = haut-gauche
    ctx.positions                (x, y) de chaque LED (estimées si pas calibré)
    ctx.show_colors(colors)      affiche une liste de (r, g, b), une par LED
    ctx.loop(fps)                `for t in ctx.loop(30):` boucle jusqu'à interruption,
                                 t = secondes écoulées
    ctx.flash(color, hold, fade) flash qui redescend en douceur (False si interrompu)
    ctx.fade_out(duration)       fondu de l'image affichée vers le noir
    ctx.end()                    à appeler à la fin d'une animation d'événement : laisse
                                 l'ambiance reprendre en fondu enchaîné, ou fondu au noir

Animation d'ambiance : @animation(APP, "theme", idle=True) — elle boucle en fond et
reprend après chaque animation d'événement (voir theme ci-dessous).
Outils de couleur : animations/_fx.py (lerp, scale, Sparkles…).
"""

import math

from engine import animation

APP = "mon_app"


@animation(APP, "hello")
def hello(ctx, data):
    """Allume le haut de l'écran dans la couleur reçue pendant 1 seconde."""
    r, g, b = data.get("color", (0, 255, 0))
    top = ctx.layout.side("top") or range(ctx.num_leds)   # tout le ruban si pas calibré

    ctx.set_all(0, 0, 0)
    for i in top:
        ctx.set_pixel(i, r, g, b)
    ctx.show()

    if ctx.sleep(1.0):
        ctx.end()


@animation(APP, "theme", idle=True)
def theme(ctx, data):
    """Ambiance : vague bleue qui fait le tour de l'écran."""
    for t in ctx.loop(30):
        colors = []
        for x, y in ctx.positions:
            k = 0.5 + 0.5 * math.sin(t * 2 + (x + y) * 6)
            colors.append((0, 40 * k, 120 * k))
        ctx.show_colors(colors)
