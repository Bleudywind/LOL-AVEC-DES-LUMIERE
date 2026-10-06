"""
calibrate.py — repère la position des LEDs autour de l'écran.

Tu indiques la LED de chacun des 4 coins de l'écran en déplaçant la LED allumée
(en blanc sur le ruban). Les côtés sont déduits des coins, quel que soit le sens
de câblage. Le résultat est enregistré dans led_layout.json (utilisable par les
watchers via self.layout) et envoyé au Pi (utilisable par les animations via ctx.layout).

Le serveur doit tourner sur le Pi.
Usage : python calibrate.py

Touches :  ← / →      LED précédente / suivante
           ↑ / ↓      ±10 LEDs
           Entrée     valider le coin
           S          pas de LED à ce coin
           G H D B    (à la fin) activer / désactiver le côté gauche, haut, droit, bas
           Retour ←   annuler la dernière étape
           Échap      quitter
"""

import tkinter as tk
from tkinter import messagebox, simpledialog

import config
from core.layout import (CLOCKWISE, CORNERS, SIDE_ENDS, LedLayout,
                         crosses_strip_ends, sides_from_corners)
from core.led_client import LedClient

SIDE_FR   = {"left": "gauche", "top": "haut", "right": "droit", "bottom": "bas"}
SIDE_KEY  = {"left": "g", "top": "h", "right": "d", "bottom": "b"}
CORNER_FR = {"top_left": "haut-gauche", "top_right": "haut-droit",
             "bottom_right": "bas-droit", "bottom_left": "bas-gauche"}
SIDE_RGB  = {"left": (255, 0, 0), "top": (0, 255, 0),
             "right": (0, 80, 255), "bottom": (255, 160, 0)}
CORNER_RGB = (255, 255, 0)

W, H, MARGIN = 720, 460, 70
RESEND_MS = 500   # renvoi périodique de l'image (l'UDP peut perdre des paquets)


def hex_color(rgb):
    return "#%02x%02x%02x" % rgb


def dim(rgb, factor):
    return tuple(int(c * factor) for c in rgb)


class Calibrator:
    def __init__(self, root, leds: LedClient, num_leds: int):
        self.root = root
        self.leds = leds
        self.num_leds = num_leds
        self.current = 0
        self.step = 0            # index dans CLOCKWISE ; 4 = vérification des côtés
        self.corners = {}        # coin -> index de LED
        self.disabled = set()    # côtés sans LED
        self.history = []        # pile pour annuler

        root.title("Calibration LEDs")
        root.configure(bg="#1e1e1e")
        self.info = tk.Label(root, font=("Segoe UI", 13), fg="white", bg="#1e1e1e",
                             justify="left", anchor="w")
        self.info.pack(fill="x", padx=12, pady=(10, 0))
        self.canvas = tk.Canvas(root, width=W, height=H, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(padx=12, pady=6)

        bar = tk.Frame(root, bg="#1e1e1e")
        bar.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(bar, text="◀", width=4, command=lambda: self.move(-1)).pack(side="left")
        tk.Button(bar, text="▶", width=4, command=lambda: self.move(1)).pack(side="left", padx=4)
        self.btn_ok = tk.Button(bar, text="Valider (Entrée)", command=self.validate)
        self.btn_ok.pack(side="left", padx=8)
        self.btn_skip = tk.Button(bar, text="Pas de LED à ce coin (S)", command=self.skip)
        self.btn_skip.pack(side="left")
        tk.Button(bar, text="Annuler (⌫)", command=self.undo).pack(side="left", padx=8)
        self.btn_save = tk.Button(bar, text="Enregistrer", command=self.save, state="disabled")
        self.btn_save.pack(side="right")

        root.bind("<Left>",      lambda e: self.move(-1))
        root.bind("<Right>",     lambda e: self.move(1))
        root.bind("<Up>",        lambda e: self.move(10))
        root.bind("<Down>",      lambda e: self.move(-10))
        root.bind("<Return>",    lambda e: self.validate())
        root.bind("<s>",         lambda e: self.skip())
        root.bind("<BackSpace>", lambda e: self.undo())
        root.bind("<Escape>",    lambda e: self.quit())
        for side, key in SIDE_KEY.items():
            root.bind(f"<{key}>", lambda e, s=side: self.toggle_side(s))
        root.protocol("WM_DELETE_WINDOW", self.quit)

        self.refresh()
        self._resend_loop()

    # ── État ──────────────────────────────────────────────────────────────────

    @property
    def reviewing(self):
        return self.step >= len(CLOCKWISE)

    def candidate_sides(self):
        """Tous les côtés déduits des coins, avant désactivation manuelle."""
        return sides_from_corners(self.num_leds, self.corners)

    def layout(self):
        return LedLayout.from_corners(self.num_leds, self.corners, self.disabled)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _push(self):
        self.history.append((self.step, self.current, dict(self.corners), set(self.disabled)))

    def move(self, delta):
        if not self.reviewing:
            self.current = (self.current + delta) % self.num_leds
            self.refresh()

    def validate(self):
        if self.reviewing:
            return
        self._push()
        self.corners[CLOCKWISE[self.step]] = self.current
        self._next()

    def skip(self):
        if self.reviewing:
            return
        self._push()
        self.corners.pop(CLOCKWISE[self.step], None)
        self._next()

    def _next(self):
        self.step += 1
        if self.reviewing:
            # Un "côté" qui ne contient que les deux bouts du ruban n'existe pas
            # physiquement (ex: ruban en U sans LEDs en bas) → désactivé par défaut.
            self.disabled = {s for s, idx in self.candidate_sides().items()
                             if len(idx) <= 2 and crosses_strip_ends(idx)}
        self.refresh()

    def toggle_side(self, side):
        if self.reviewing and side in self.candidate_sides():
            self._push()
            self.disabled ^= {side}
            self.refresh()

    def undo(self):
        if self.history:
            self.step, self.current, self.corners, self.disabled = self.history.pop()
            self.refresh()

    def save(self):
        layout = self.layout()
        layout.save(config.LAYOUT_FILE)
        self.leds.send_layout(layout)
        self.leds.send("system", "test", quiet=True)
        messagebox.showinfo("Calibration", f"Enregistré dans {config.LAYOUT_FILE.name}\n"
                                           "et envoyé au Pi (animation de test en cours).")

    def quit(self):
        self.leds.off()
        self.root.destroy()

    # ── Rendu : ruban + fenêtre ───────────────────────────────────────────────

    def frame_pixels(self):
        pixels = [(0, 0, 0)] * self.num_leds
        factor = 0.5 if self.reviewing else 0.15
        for side, indices in self.layout().sides.items():
            for i in indices:
                pixels[i] = dim(SIDE_RGB[side], factor)
        if not self.reviewing:
            for i in self.corners.values():
                pixels[i] = CORNER_RGB
            pixels[self.current] = (255, 255, 255)
        return pixels

    def _resend_loop(self):
        self.leds.frame(self.frame_pixels())
        self.root.after(RESEND_MS, self._resend_loop)

    def to_canvas(self, corner_or_xy):
        x, y = CORNERS[corner_or_xy] if isinstance(corner_or_xy, str) else corner_or_xy
        return MARGIN + x * (W - 2 * MARGIN), MARGIN + y * (H - 2 * MARGIN)

    def refresh(self):
        self.leds.frame(self.frame_pixels())
        c = self.canvas
        c.delete("all")
        x0, y0 = self.to_canvas("top_left")
        x1, y1 = self.to_canvas("bottom_right")
        c.create_rectangle(x0, y0, x1, y1, outline="#666", width=2, fill="#2a2a2a")
        c.create_text((x0 + x1) / 2, y1 + 40, text="(écran vu de face)", fill="#888")

        # Côtés désactivés : pointillés gris
        for side in self.disabled:
            (ax, ay), (bx, by) = (self.to_canvas(cn) for cn in SIDE_ENDS[side])
            c.create_line(ax, ay, bx, by, fill="#555", width=3, dash=(6, 6))

        # LEDs des côtés actifs
        layout = self.layout()
        for side, indices in layout.sides.items():
            for i in indices:
                px, py = self.to_canvas(layout.position(i))
                c.create_oval(px - 4, py - 4, px + 4, py + 4,
                              fill=hex_color(SIDE_RGB[side]), outline="")
            # libellé au milieu du côté
            (ax, ay), (bx, by) = (self.to_canvas(cn) for cn in SIDE_ENDS[side])
            mx, my = (ax + bx) / 2, (ay + by) / 2
            dx = -30 if side == "left" else 30 if side == "right" else 0
            dy = -20 if side == "top" else 20 if side == "bottom" else 0
            c.create_text(mx + dx, my + dy, text=f"{len(indices)}", fill=hex_color(SIDE_RGB[side]))

        # Coins marqués
        for corner, i in self.corners.items():
            px, py = self.to_canvas(corner)
            c.create_oval(px - 7, py - 7, px + 7, py + 7, fill=hex_color(CORNER_RGB), outline="")
            c.create_text(px, py - 20 if py < H / 2 else py + 20, text=str(i), fill="white",
                          font=("Segoe UI", 11, "bold"))

        if self.reviewing:
            self._refresh_review(layout)
            return

        self.btn_save.config(state="disabled")
        self.btn_ok.config(state="normal")
        self.btn_skip.config(state="normal")

        corner = CLOCKWISE[self.step]
        tx, ty = self.to_canvas(corner)
        c.create_oval(tx - 16, ty - 16, tx + 16, ty + 16, outline="yellow", width=3)
        c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"LED n° {self.current}",
                      fill="white", font=("Segoe UI", 28, "bold"))
        self.info.config(text=f"Coin {self.step + 1}/{len(CLOCKWISE)} : {CORNER_FR[corner]}.\n"
                              "Déplace la LED blanche avec ← → (↑ ↓ : ±10) jusqu'à ce coin, "
                              "puis Entrée.")

    def _refresh_review(self, layout):
        self.btn_ok.config(state="disabled")
        self.btn_skip.config(state="disabled")
        self.btn_save.config(state="normal" if layout.sides else "disabled")
        toggles = "  ".join(
            f"[{SIDE_KEY[s].upper()}] {SIDE_FR[s]} {'✔' if s not in self.disabled else '✘'}"
            for s in self.candidate_sides())
        self.info.config(text="Vérifie les côtés (le ruban les affiche en couleur).\n"
                              f"{toggles or 'aucun côté : marque au moins 2 coins voisins'}"
                              "   → puis « Enregistrer ».")


def main():
    root = tk.Tk()
    root.withdraw()
    num_leds = simpledialog.askinteger("Calibration LEDs", "Nombre de LEDs du ruban :",
                                       initialvalue=config.NUM_LEDS, minvalue=1, maxvalue=2000)
    if not num_leds:
        return
    root.deiconify()
    leds = LedClient(config.PI_IP, config.PI_PORT)
    Calibrator(root, leds, num_leds)
    root.mainloop()
    leds.close()


if __name__ == "__main__":
    main()
