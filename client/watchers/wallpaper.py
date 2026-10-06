"""
Watcher "wallpaper" : ambiance par défaut quand aucun jeu n'est lancé.
Les LEDs reprennent les couleurs des bords du fond d'écran (y compris un fond animé
Wallpaper Engine), même s'il est caché par des fenêtres. Nécessite la calibration.

Dépendances : pip install windows-capture opencv-python numpy
"""

import time

import numpy as np

from core.capture import EdgeSampler, WallpaperCapture, pick_monitor
from core.watcher import Watcher

# ── Réglages ───────────────────────────────────────────────────────────────────
MONITOR    = None    # écran entouré par les LEDs : None = principal, sinon 0, 1… (ordre Windows)
FPS        = 20      # images envoyées au ruban par seconde
DEPTH      = 0.08    # profondeur de la bande analysée le long du bord (fraction de l'écran)
BRIGHTNESS = 0.6     # luminosité max (0..1) — limite aussi la consommation du ruban
SATURATION = 1.3     # > 1 : couleurs plus vives (les LEDs ont tendance à délaver)
GAMMA      = 2.2     # correction gamma : les couleurs sombres restent sombres sur les LEDs
SMOOTHING  = 0.25    # 0..1 : vitesse de transition (1 = instantané, plus bas = plus doux)
# ───────────────────────────────────────────────────────────────────────────────


class WallpaperWatcher(Watcher):
    name = "wallpaper"
    fallback = True          # lancé uniquement quand aucun jeu n'est actif
    poll_interval = 1 / FPS

    @classmethod
    def detect(cls, running):
        return True          # toujours disponible

    def on_start(self):
        self.capture = None
        if self.layout is None or not self.layout.sides:
            print("[wallpaper] pas de calibration : lance calibrate.py d'abord")
            return

        monitor = pick_monitor(MONITOR)
        self.capture = WallpaperCapture(monitor, self._on_image, fps=FPS)
        self.sampler = EdgeSampler(self.layout, self.capture.width, self.capture.height, DEPTH)
        self.target = None
        self.current = np.zeros((self.layout.num_leds, 3), dtype=np.float32)
        self.last_restart = 0.0
        self.capture.start()
        print(f"[wallpaper] capture de l'écran {monitor[2] - monitor[0]}×{monitor[3] - monitor[1]}"
              f"{' (principal)' if monitor[4] else ''}")

    def _on_image(self, image_bgr):
        # thread de capture : on ne fait que calculer la cible, l'envoi se fait dans poll()
        self.target = self.sampler.sample(image_bgr)

    def poll(self):
        if self.capture is None:
            return

        # La capture s'arrête si l'explorateur Windows redémarre → on la relance
        if not self.capture.alive and time.time() - self.last_restart > 5:
            self.last_restart = time.time()
            print("[wallpaper] capture interrompue, redémarrage")
            self.capture.stop()
            self.capture.start()

        if self.target is None:
            return
        self.current += (self.target - self.current) * SMOOTHING
        self.leds.frame(self._to_led_colors(self.current))

    @staticmethod
    def _to_led_colors(rgb):
        luma = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        rgb = luma[:, None] + (rgb - luma[:, None]) * SATURATION
        rgb = np.clip(rgb / 255.0, 0.0, 1.0) ** GAMMA * (255 * BRIGHTNESS)
        return [tuple(int(c) for c in px) for px in rgb.round()]

    def on_stop(self):
        if self.capture is not None:
            self.capture.stop()
        self.leds.off()
