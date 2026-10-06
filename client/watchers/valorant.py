"""
Watcher VALORANT (animations dans server/animations/valorant.py).

Valorant n'a pas d'API live officielle : on lit la "présence" que le jeu publie
auprès du Riot Client local (https://127.0.0.1:<port>/chat/v4/presences, identifiants
dans le lockfile du Riot Client). Lecture seule, en local : aucun accès au jeu
lui-même ni aux serveurs de Riot.

Ce qu'elle contient : l'étape (menus, sélection d'agent, en jeu), la carte, le mode
et le score des deux équipes. On en déduit les manches gagnées / perdues, la balle de
match et le résultat. Les kills, le spike ou la vie ne sont pas disponibles.

DUMP_PRESENCE enregistre ta présence décodée dans client/debug/ à chaque changement
d'étape (pour vérifier les champs et en exploiter d'autres).

Dépendances : pip install requests
"""

import base64
import json
import os
import time
from pathlib import Path

import requests
import urllib3

from core.watcher import Watcher

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCKFILE = Path(os.path.expandvars(r"%LOCALAPPDATA%\Riot Games\Riot Client\Config\lockfile"))
THEME_RESEND = 15.0
DUMP_PRESENCE = True
DUMP_DIR = Path(__file__).resolve().parent.parent / "debug"

# Manches à gagner selon le mode (None = pas de manches : deathmatch, etc.)
WIN_TARGET = {
    "competitive": 13, "unrated": 13, "premier": 13, "custom": 13, "newmap": 13,
    "swiftplay": 5, "spikerush": 4,
}
NO_ROUNDS = {"deathmatch", "hurm", "ggteam", "snowball", "onefa"}
WIN_BY_TWO = {"competitive", "premier"}   # prolongations : 2 manches d'écart


class RiotLocalClient:
    """Accès à l'API locale du Riot Client (le port et le mot de passe changent à chaque lancement)."""

    def __init__(self):
        self.http = requests.Session()
        self.http.verify = False
        self.base = None
        self.puuid = None

    def _connect(self):
        try:
            _, _, port, password, _ = LOCKFILE.read_text().split(":")
        except (OSError, ValueError):
            return False
        self.base = f"https://127.0.0.1:{port}"
        self.http.auth = ("riot", password)
        session = self._get("/chat/v1/session")
        self.puuid = session.get("puuid") if session else None
        return self.puuid is not None

    def _get(self, path):
        try:
            resp = self.http.get(self.base + path, timeout=2)
            return resp.json() if resp.status_code == 200 else None
        except (requests.exceptions.RequestException, ValueError):
            return None

    def my_presence(self):
        """Présence Valorant décodée du joueur connecté, ou None."""
        if self.puuid is None and not self._connect():
            return None
        data = self._get("/chat/v4/presences")
        if data is None:
            self.puuid = None          # Riot Client relancé ? on relira le lockfile
            return None
        for p in data.get("presences", []):
            if p.get("puuid") == self.puuid and p.get("product") == "valorant" and p.get("private"):
                try:
                    return json.loads(base64.b64decode(p["private"]))
                except (ValueError, TypeError):
                    return None
        return None

    def close(self):
        self.http.close()


def read_state(presence):
    """Champs utiles, quel que soit le format (Riot a déplacé des champs en 2024-2025)."""
    match = presence.get("matchPresenceData") or {}
    party = presence.get("partyPresenceData") or {}

    def pick(key, *sources):
        for src in sources:
            if src.get(key) not in (None, ""):
                return src[key]
        return None

    return {
        "state": pick("sessionLoopState", match, presence) or "MENUS",
        "map":   (pick("matchMap", match, presence) or "").rstrip("/").split("/")[-1],
        "queue": (pick("queueId", match, presence) or "").lower(),
        "flow":  pick("provisioningFlow", match, presence),
        "ally":  pick("partyOwnerMatchScoreAllyTeam", presence, party) or 0,
        "enemy": pick("partyOwnerMatchScoreEnemyTeam", presence, party) or 0,
    }


def match_point(ally, enemy, target, win_by_two=False):
    """
    Qui peut gagner le match à la prochaine manche : "ally", "enemy", "both"
    (manche décisive) ou None. Avec win_by_two, à égalité à target-1 il faut 2 manches d'écart.
    """
    if target is None:
        return None

    def wins_next(a, b):     # l'équipe à `a` gagne-t-elle si elle prend la prochaine manche ?
        if a + 1 < target:
            return False
        return a + 1 - b >= 2 if win_by_two else True

    def already_won(a, b):
        return a >= target and (a - b >= 2 if win_by_two else a > b)

    if already_won(ally, enemy) or already_won(enemy, ally):
        return None
    ally_mp, enemy_mp = wins_next(ally, enemy), wins_next(enemy, ally)
    if ally_mp and enemy_mp:
        return "both"
    return "ally" if ally_mp else "enemy" if enemy_mp else None


class ValorantWatcher(Watcher):
    name = "valorant"
    processes = ("VALORANT-Win64-Shipping.exe",)
    poll_interval = 1.0

    def on_start(self):
        self.riot = RiotLocalClient()
        self.prev = None          # dernier état lu
        self.theme = None
        self.theme_at = 0.0

    def on_stop(self):
        self.leds.clear_idle()
        self.riot.close()

    def poll(self):
        presence = self.riot.my_presence()
        if presence is None:
            return
        cur = read_state(presence)
        prev = self.prev or {**cur, "state": None}
        self.prev = cur

        if cur["state"] != prev["state"]:
            print(f"[valorant] {prev['state']} → {cur['state']}  carte={cur['map']} mode={cur['queue']}")
            if DUMP_PRESENCE:
                self.dump(presence, cur["state"])
            self.on_state_change(prev, cur)
        elif cur["state"] == "INGAME":
            self.on_score(prev, cur)

        self.update_theme(cur)

    # ── Transitions ──────────────────────────────────────────────────────────

    def on_state_change(self, prev, cur):
        if cur["state"] == "PREGAME":
            self.send("agent_select", {"map": cur["map"]})
        elif cur["state"] == "INGAME" and prev["state"] is not None:
            self.send("match_start", {"map": cur["map"]})
        elif prev["state"] == "INGAME":
            self.match_end(prev)

    def match_end(self, last):
        """Fin de match : résultat d'après le dernier score connu."""
        self.leds.clear_idle()
        self.theme = None
        if last["queue"] in NO_ROUNDS or last["ally"] == last["enemy"] == 0:
            result = "unknown"
        else:
            result = "win" if last["ally"] > last["enemy"] else \
                     "loss" if last["enemy"] > last["ally"] else "draw"
        self.send("match_end", {"result": result, "ally": last["ally"], "enemy": last["enemy"]})

    def on_score(self, prev, cur):
        target = WIN_TARGET.get(cur["queue"], 13)
        if cur["queue"] in NO_ROUNDS:
            return
        won, lost = cur["ally"] - prev["ally"], cur["enemy"] - prev["enemy"]
        if won < 0 or lost < 0 or (won == 0 and lost == 0):
            return   # pas de changement (ou score remis à zéro)
        data = {"ally": cur["ally"], "enemy": cur["enemy"], "target": target,
                "match_point": self.match_point(cur)}
        self.send("round_won" if won >= lost else "round_lost", data)

    @staticmethod
    def match_point(cur):
        if cur["queue"] in NO_ROUNDS:
            return None
        return match_point(cur["ally"], cur["enemy"], WIN_TARGET.get(cur["queue"], 13),
                           cur["queue"] in WIN_BY_TWO)

    # ── Ambiance ─────────────────────────────────────────────────────────────

    def update_theme(self, cur):
        if cur["state"] == "INGAME":
            theme = ("theme_map", {"map": cur["map"], "match_point": self.match_point(cur)})
        elif cur["state"] == "PREGAME":
            theme = ("theme_pregame", {})
        else:
            theme = ("theme_menu", {})

        changed = theme != self.theme
        if changed or time.time() - self.theme_at > THEME_RESEND:
            self.send(*theme, quiet=not changed)
            self.theme, self.theme_at = theme, time.time()

    def dump(self, presence, state):
        DUMP_DIR.mkdir(exist_ok=True)
        path = DUMP_DIR / f"valorant_{time.strftime('%Y%m%d_%H%M%S')}_{state}.json"
        path.write_text(json.dumps(presence, indent=2, ensure_ascii=False), encoding="utf-8")
