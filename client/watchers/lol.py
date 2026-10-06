"""
Watcher League of Legends (Faille de l'invocateur, ARAM, Arena) : surveille la
Live Client Data API pendant une partie et envoie les événements au serveur
(animations dans server/animations/lol.py).

Seuls les événements qui te concernent sont animés : tes kills, tes morts, tes
assists, et les monstres neutres (dragon, Baron, Héraut) pris par ton équipe.
En dehors des événements, une ambiance propre au mode de jeu tourne en fond
(theme_rift / theme_aram / theme_arena).

Dépendances : pip install requests
"""

import time

from core.watcher import Watcher
from watchers import _riot as riot

THEMES = {"rift": "theme_rift", "aram": "theme_aram", "arena": "theme_arena"}
STATS_INTERVAL = 5.0     # secondes entre deux lectures de /gamestats (terrain de la Faille)
THEME_RESEND = 15.0      # renvoi régulier de l'ambiance (si le Pi a redémarré entre-temps)


class LolWatcher(Watcher):
    name = "lol"
    processes = ("League of Legends.exe",)
    poll_interval = 0.5

    @classmethod
    def detect(cls, running):
        return riot.detect_mode(running) in THEMES

    def on_start(self):
        self.api = riot.LiveClient()
        self.feed = riot.EventFeed()
        self.roster = riot.Roster()
        self.mode = None
        self.terrain = None
        self.stats_at = 0.0
        self.theme = None        # (event, data) envoyé en dernier
        self.theme_at = 0.0
        self.ended = False

    def on_stop(self):
        self.leds.clear_idle()
        self.api.close()

    def poll(self):
        now = time.time()
        if now - self.stats_at > STATS_INTERVAL:
            stats = self.api.get("gamestats")
            if stats:
                self.stats_at = now
                self.mode = riot.classify(stats)
                self.terrain = stats.get("mapTerrain", "Default")

        # Qui tu es et qui sont tes alliés (tant que c'est inconnu, les événements
        # personnels sont ignorés ; début / fin de partie passent quand même)
        if not self.roster.ready and self.roster.load(self.api):
            print(f"[lol] joueur reconnu, équipe {self.roster.my_team}")

        for evt in self.feed.new_events(self.api):
            self.handle_event(evt)

        if self.mode in THEMES and not self.ended:
            self.update_theme(now)

    def update_theme(self, now):
        theme = (THEMES[self.mode], {"terrain": self.terrain} if self.mode == "rift" else {})
        changed = theme != self.theme
        if changed or now - self.theme_at > THEME_RESEND:
            self.send(*theme, quiet=not changed)
            self.theme, self.theme_at = theme, now

    def handle_event(self, evt: dict):
        """
        Traduit un événement LoL en événement LED.
        Référence : https://developer.riotgames.com/docs/lol#game-client-api_live-client-data-api
        """
        etype = evt.get("EventName", "")

        me, ally = self.roster.is_me, self.roster.is_ally

        if etype == "ChampionKill":
            killer = evt.get("KillerName", "")
            victim = evt.get("VictimName", "")
            if me(victim):
                self.send("death", {"killer": killer})
            elif me(killer):
                self.send("kill", {"victim": victim})
            elif any(me(a) for a in evt.get("Assisters", [])):
                self.send("assist", {"killer": killer, "victim": victim})

        elif etype == "Multikill":
            if me(evt.get("KillerName", "")):
                self.send("multikill", {"streak": evt.get("KillStreak", 2)})

        elif etype == "Ace":
            if evt.get("AcingTeam") == self.roster.my_team:
                self.send("ace")

        # Monstres neutres : seulement si ton équipe les prend
        elif etype == "DragonKill":
            if ally(evt.get("KillerName", "")):
                # Air, Earth, Fire, Water, Elder, Hextech, Chemtech
                self.send("dragon", {"type": evt.get("DragonType", "Unknown"),
                                     "stolen": evt.get("Stolen") == "True"})

        elif etype == "BaronKill":
            if ally(evt.get("KillerName", "")):
                self.send("baron", {"stolen": evt.get("Stolen") == "True"})

        elif etype == "HeraldKill":
            if ally(evt.get("KillerName", "")):
                self.send("herald", {"stolen": evt.get("Stolen") == "True"})

        elif etype == "TurretKilled":
            self.send("turret")

        elif etype == "InhibKilled":
            self.send("inhibitor")

        elif etype == "GameEnd":
            # Plus d'ambiance après l'animation de victoire / défaite
            self.ended = True
            self.leds.clear_idle()
            self.send("game_end", {"result": evt.get("Result", "Unknown")})   # "Win" / "Lose"

        elif etype == "GameStart":
            self.send("game_start")
