"""
Modèle pour ajouter un watcher.

1. Copie ce fichier en watchers/<mon_app>.py (sans le _ devant, sinon il est ignoré)
2. Renseigne `name` (= APP dans server/animations/<mon_app>.py) et `processes`
   (nom de l'exe, visible dans le Gestionnaire des tâches → onglet Détails)
3. Écris poll() : lis l'état du jeu, et appelle self.send("<event>", {...})
   quand quelque chose se passe
4. Relance hub.py — teste sans lancer le jeu avec : python hub.py --force mon_app

Disponible dans le watcher :
    self.send(event, data)    déclenche l'animation <name>/<event> sur le Pi
    self.leds.frame(pixels)   envoie directement une image [(r, g, b), ...] au ruban
    self.leds.fill(r, g, b)   / self.leds.off()
    self.layout               calibration (None si calibrate.py n'a pas été lancé) :
        self.layout.side("top")             indices des LEDs du haut
        self.layout.position(i)             (x, y) de la LED i, 0..1
        self.layout.leds_with_position()    [(i, (x, y)), ...]
"""

import time

from core.watcher import Watcher


class ExempleWatcher(Watcher):
    name = "mon_app"
    processes = ("MonJeu.exe",)
    poll_interval = 1.0

    # Pour une détection plus fine que le nom du processus :
    # @classmethod
    # def detect(cls, running):
    #     return "monjeu.exe" in running and "monlauncher.exe" not in running

    def on_start(self):
        print("[mon_app] jeu détecté")
        self.last_hello = 0.0

    def poll(self):
        if time.time() - self.last_hello > 10:
            self.last_hello = time.time()
            self.send("hello", {"color": [0, 255, 0]})

    def on_stop(self):
        self.leds.off()
