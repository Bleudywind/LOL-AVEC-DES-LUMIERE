"""
Animations génériques utilisables par tous les watchers et par calibrate.py.
"""

from engine import animation


@animation("system", "off", threaded=False)
def off(ctx, data):
    """Éteint le ruban."""
    ctx.off()


@animation("system", "fill", threaded=False)
def fill(ctx, data):
    """Couleur unie. data = {"color": [r, g, b]}"""
    r, g, b = data.get("color", (0, 0, 0))
    ctx.fill(r, g, b)


@animation("system", "frame", threaded=False)
def frame(ctx, data):
    """
    Affiche une image complète du ruban.
    data = {"pixels": "ff0000 00ff00 ..."} sans espaces : 6 caractères hex par LED.
    Les LEDs non fournies sont éteintes.
    """
    pixels = bytes.fromhex(data.get("pixels", ""))
    count = min(ctx.num_leds, len(pixels) // 3)
    ctx.set_all(0, 0, 0)
    for i in range(count):
        ctx.set_pixel(i, pixels[3 * i], pixels[3 * i + 1], pixels[3 * i + 2])
    ctx.show()


@animation("system", "test")
def test(ctx, data):
    """Allume chaque côté calibré dans sa couleur, l'un après l'autre."""
    colors = {"left": (255, 0, 0), "top": (0, 255, 0),
              "right": (0, 80, 255), "bottom": (255, 160, 0)}
    if not ctx.layout.calibrated:
        print("  [test] pas de calibration, chenillard simple")
        for i in range(ctx.num_leds):
            ctx.set_all(0, 0, 0)
            ctx.set_pixel(i, 255, 255, 255)
            ctx.show()
            if not ctx.sleep(0.03):
                break
        ctx.off()
        return

    ctx.set_all(0, 0, 0)
    for side, color in colors.items():
        for i in ctx.layout.side(side):
            ctx.set_pixel(i, *color)
            ctx.show()
            if not ctx.sleep(0.03):
                ctx.off()
                return
    ctx.sleep(2)
    ctx.off()
