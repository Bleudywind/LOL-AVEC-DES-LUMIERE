"""
Disposition des LEDs autour de l'écran (produite par calibrate.py).

Coordonnées normalisées : (0, 0) = coin haut-gauche de l'écran, (1, 1) = bas-droit.
Les côtés sont ordonnés dans le sens des aiguilles d'une montre vu de face :
    left   : du coin bas-gauche  vers le haut-gauche
    top    : du coin haut-gauche vers le haut-droit
    right  : du coin haut-droit  vers le bas-droit
    bottom : du coin bas-droit   vers le bas-gauche
La LED d'un coin appartient aux deux côtés qui s'y rejoignent.
Les indices peuvent être croissants ou décroissants (selon le câblage).
"""

from __future__ import annotations

import json
from pathlib import Path

SIDES = ("left", "top", "right", "bottom")

CORNERS = {
    "top_left":     (0.0, 0.0),
    "top_right":    (1.0, 0.0),
    "bottom_right": (1.0, 1.0),
    "bottom_left":  (0.0, 1.0),
}

# côté → (coin de la première LED, coin de la dernière LED)
SIDE_ENDS = {
    "left":   ("bottom_left",  "top_left"),
    "top":    ("top_left",     "top_right"),
    "right":  ("top_right",    "bottom_right"),
    "bottom": ("bottom_right", "bottom_left"),
}


# Ordre des coins en tournant dans le sens des aiguilles d'une montre
CLOCKWISE = ("bottom_left", "top_left", "top_right", "bottom_right")


def sides_from_corners(num_leds: int, corners: dict[str, int]) -> dict[str, list[int]]:
    """
    Déduit les LEDs de chaque côté à partir des LEDs des coins.
    corners = {"top_left": 12, ...} — un coin sans LED est simplement absent.

    Le sens du ruban est celui qui passe le moins souvent de la dernière LED à la
    première (un vrai ruban le fait au plus une fois), puis, à égalité, celui qui
    relie les coins avec le moins de LEDs.
    """
    pairs = [(side, a, b) for side, (a, b) in SIDE_ENDS.items() if a in corners and b in corners]
    if not pairs:
        return {}

    def dist(a, b, d):
        return ((corners[b] - corners[a]) * d) % num_leds

    def crossings(d):
        return sum(1 for _, a, b in pairs if (corners[b] - corners[a]) * d < 0)

    d = min((1, -1), key=lambda d: (crossings(d), sum(dist(a, b, d) for _, a, b in pairs)))
    return {side: [(corners[a] + k * d) % num_leds for k in range(dist(a, b, d) + 1)]
            for side, a, b in pairs}


def crosses_strip_ends(indices: list[int]) -> bool:
    """Vrai si ces LEDs passent par la fin puis le début du ruban (ex: [57, 58, 0, 1])."""
    return any(abs(b - a) != 1 for a, b in zip(indices, indices[1:]))


class LedLayout:
    def __init__(self, num_leds: int, sides: dict[str, list[int]]):
        self.num_leds = num_leds
        self.sides = {s: list(sides[s]) for s in SIDES if sides.get(s)}
        self.positions: list[tuple[float, float] | None] = [None] * num_leds
        for side, indices in self.sides.items():
            (x0, y0), (x1, y1) = (CORNERS[c] for c in SIDE_ENDS[side])
            n = len(indices)
            for k, i in enumerate(indices):
                t = k / (n - 1) if n > 1 else 0.5
                if 0 <= i < num_leds:
                    self.positions[i] = (x0 + t * (x1 - x0), y0 + t * (y1 - y0))

    @classmethod
    def from_corners(cls, num_leds: int, corners: dict[str, int], disabled=()):
        """corners = {"top_left": 12, ...} ; disabled = côtés sans LED à ignorer."""
        sides = sides_from_corners(num_leds, corners)
        return cls(num_leds, {s: i for s, i in sides.items() if s not in disabled})

    # ── Lecture ───────────────────────────────────────────────────────────────

    def side(self, name) -> list[int]:
        return list(self.sides.get(name, []))

    def position(self, index) -> tuple[float, float] | None:
        return self.positions[index] if 0 <= index < self.num_leds else None

    def leds_with_position(self):
        """[(index, (x, y)), ...] pour toutes les LEDs calibrées."""
        return [(i, p) for i, p in enumerate(self.positions) if p is not None]

    # ── Sauvegarde ────────────────────────────────────────────────────────────

    def to_dict(self):
        return {
            "num_leds": self.num_leds,
            "sides": self.sides,
            "positions": [list(p) if p else None for p in self.positions],
        }

    def save(self, path: Path):
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> LedLayout | None:
        """Renvoie None si la calibration n'a pas encore été faite."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        return cls(data["num_leds"], data.get("sides", {}))
