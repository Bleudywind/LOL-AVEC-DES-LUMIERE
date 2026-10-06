"""
Petits outils de couleur partagés par les animations.
(Le _ devant le nom empêche led_server.py de le charger comme un fichier d'animations.)
"""

import math
import random


def lerp(c1, c2, t):
    """Mélange de deux couleurs : t=0 → c1, t=1 → c2."""
    t = min(max(t, 0.0), 1.0)
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


def scale(c, k):
    return tuple(v * k for v in c)


def add(c1, c2):
    return tuple(a + b for a, b in zip(c1, c2))


def smoothstep(edge0, edge1, x):
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def angle(pos):
    """Angle d'une LED autour du centre de l'écran, en tours (0..1), sens horaire depuis le haut."""
    x, y = pos
    return (math.atan2(x - 0.5, 0.5 - y) / (2 * math.pi)) % 1.0


class Sparkles:
    """Scintillements aléatoires : intensité par LED, qui retombe progressivement."""

    def __init__(self, n, rate=0.6, decay=0.9):
        self.values = [0.0] * n
        self.rate = rate      # nouveaux scintillements par image (en moyenne)
        self.decay = decay

    def step(self):
        self.values = [v * self.decay for v in self.values]
        count = int(self.rate) + (random.random() < self.rate % 1)
        for _ in range(count):
            self.values[random.randrange(len(self.values))] = 1.0
        return self.values
