"""
Watcher Teamfight Tactics (animations dans server/animations/tft.py).

L'API live de Riot expose très peu de choses en TFT (ni rounds, ni adversaires, ni
synergies). On s'appuie sur ce qui reste : la vie du tacticien (dégâts reçus,
élimination, ambiance "danger" quand la vie est basse), son niveau, et les
événements de début / fin de partie.

DUMP_GAME_DATA enregistre ce que renvoie l'API dans client/debug/ au début et à la fin
de chaque partie : utile pour vérifier les champs disponibles et ajouter d'autres animations.
"""

import json
import time
from pathlib import Path

from core.watcher import Watcher
from watchers import _riot as riot

DANGER_HP = 20           # en dessous : ambiance "danger"
THEME_RESEND = 15.0
DUMP_GAME_DATA = True
DUMP_DIR = Path(__file__).resolve().parent.parent / "debug"


class TftWatcher(Watcher):
    name = "tft"
    processes = ("League of Legends.exe",)
    poll_interval = 0.5

    @classmethod
    def detect(cls, running):
        return riot.detect_mode(running) == "tft"

    def on_start(self):
        self.api = riot.LiveClient()
        self.feed = riot.EventFeed()
        self.hp = None
        self.level = None
        self.theme = None
        self.theme_at = 0.0
        self.ended = False
        self.dumped = not DUMP_GAME_DATA

    def on_stop(self):
        self.leds.clear_idle()
        self.api.close()

    def poll(self):
        if not self.dumped:
            self.dumped = self.dump("debut")

        for evt in self.feed.new_events(self.api):
            name = evt.get("EventName", "")
            if name == "GameStart":
                self.send("game_start")
            elif name == "GameEnd":
                self.end_game()
                self.send("game_end", {"result": evt.get("Result", "Unknown")})

        player = self.api.get("activeplayer")
        if player and not self.ended:
            self.track_player(player)

        if self.hp is not None and self.hp > 0 and not self.ended:
            self.update_theme()

    def track_player(self, player):
        hp = (player.get("championStats") or {}).get("currentHealth")
        level = player.get("level")

        hurt = False
        if isinstance(hp, (int, float)):
            if self.hp is not None and hp < self.hp - 0.5:
                hurt = True
                if hp <= 0:
                    self.end_game()
                    self.send("eliminated")
                else:
                    self.send("damage", {"damage": round(self.hp - hp), "hp": round(hp)})
            self.hp = hp

        if isinstance(level, int):
            # Si on vient de prendre des dégâts, on ne coupe pas leur animation
            if self.level is not None and level > self.level and not hurt:
                self.send("level_up", {"level": level})
            self.level = level

    def update_theme(self):
        theme = ("theme", {"danger": self.hp <= DANGER_HP})
        changed = theme != self.theme
        if changed or time.time() - self.theme_at > THEME_RESEND:
            self.send(*theme, quiet=not changed)
            self.theme, self.theme_at = theme, time.time()

    def end_game(self):
        self.ended = True
        self.leds.clear_idle()
        if DUMP_GAME_DATA:
            self.dump("fin")

    def dump(self, label):
        """Enregistre /allgamedata dans client/debug/. Renvoie True si réussi."""
        data = self.api.get("allgamedata")
        if not data:
            return False
        DUMP_DIR.mkdir(exist_ok=True)
        path = DUMP_DIR / f"tft_{time.strftime('%Y%m%d_%H%M%S')}_{label}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[tft] données de la partie enregistrées dans debug/{path.name}")
        return True
