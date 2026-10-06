"""
Classe de base des watchers. Chaque fichier de watchers/ en définit une sous-classe,
que hub.py démarre quand le jeu est détecté et arrête quand il se ferme.
"""

from __future__ import annotations

import threading
import traceback

from core.layout import LedLayout
from core.led_client import LedClient


class Watcher:
    name: str = ""                       # identifiant de l'app = APP côté serveur
    processes: tuple[str, ...] = ()      # noms d'exécutables qui déclenchent le watcher
    poll_interval: float = 0.5           # secondes entre deux appels à poll()
    fallback: bool = False               # True = watcher par défaut, actif seulement
                                         # quand aucun autre watcher ne tourne

    def __init__(self, leds: LedClient, layout: LedLayout | None):
        self.leds = leds
        self.layout = layout
        self._stop = threading.Event()
        self._thread = None

    # ── À surcharger ──────────────────────────────────────────────────────────

    @classmethod
    def detect(cls, running: set[str]) -> bool:
        """`running` = noms des processus lancés, en minuscules."""
        return any(p.lower() in running for p in cls.processes)

    def on_start(self):
        """Appelé une fois au lancement du jeu."""

    def poll(self):
        """Appelé toutes les `poll_interval` secondes tant que le jeu tourne."""
        raise NotImplementedError

    def on_stop(self):
        """Appelé une fois à la fermeture du jeu."""

    # ── Utilitaires ───────────────────────────────────────────────────────────

    def send(self, event, data=None, quiet=False):
        """Déclenche l'animation `event` de cette app sur le serveur."""
        self.leds.send(self.name, event, data, quiet=quiet)

    @property
    def stopping(self):
        return self._stop.is_set()

    # ── Cycle de vie (géré par hub.py) ───────────────────────────────────────

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self, timeout=3.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self):
        if not self._call(self.on_start):
            return
        while not self._stop.is_set():
            self._call(self.poll)
            self._stop.wait(self.poll_interval)
        self._call(self.on_stop)

    def _call(self, fn):
        try:
            fn()
            return True
        except Exception:
            print(f"[{self.name}] erreur dans {fn.__name__} :")
            traceback.print_exc()
            return False
