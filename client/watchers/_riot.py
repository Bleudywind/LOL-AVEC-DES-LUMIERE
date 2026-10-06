"""
Outils communs aux watchers LoL et TFT : Live Client Data API (https://127.0.0.1:2999),
détection du mode de jeu, suivi des événements.
(Le _ devant le nom empêche hub.py de le charger comme un watcher.)
"""

import requests
import urllib3

# L'API LoL utilise un certificat auto-signé
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API = "https://127.0.0.1:2999/liveclientdata"
PROCESS = "league of legends.exe"   # le jeu lui-même (LoL et TFT), pas le launcher

# Si on démarre en pleine partie, on ne rejoue pas les vieux événements
REPLAY_MAX_GAME_TIME = 15.0


class LiveClient:
    def __init__(self, timeout=2.0):
        self.timeout = timeout
        self.http = requests.Session()
        self.http.verify = False

    def get(self, endpoint):
        """JSON de /liveclientdata/<endpoint>, ou None si la partie n'est pas (encore) lancée."""
        try:
            resp = self.http.get(f"{API}/{endpoint}", timeout=self.timeout)
            return resp.json() if resp.status_code == 200 else None
        except (requests.exceptions.RequestException, ValueError):
            return None

    def close(self):
        self.http.close()


def classify(stats):
    """Mode de jeu à partir de /gamestats : "rift", "aram", "arena" ou "tft"."""
    mode = stats.get("gameMode", "")
    map_number = stats.get("mapNumber")
    if mode == "TFT" or map_number == 22:
        return "tft"
    if mode == "CHERRY" or map_number == 30:
        return "arena"
    if mode == "ARAM" or map_number == 12:
        return "aram"
    return "rift"   # CLASSIC, URF, modes temporaires sur la Faille…


# ── Détection du mode pour hub.py ──────────────────────────────────────────────

_detect_client = LiveClient(timeout=0.5)
_detected_mode = None


def detect_mode(running):
    """
    Mode de la partie en cours, ou None (pas de partie / chargement).
    Le mode est mémorisé tant que le jeu tourne, pour qu'une réponse lente de l'API
    n'arrête pas le watcher en pleine partie.
    """
    global _detected_mode
    if PROCESS not in running:
        _detected_mode = None
        return None
    stats = _detect_client.get("gamestats")
    if stats:
        _detected_mode = classify(stats)
    return _detected_mode


# ── Joueurs et équipes ─────────────────────────────────────────────────────────

def _aliases(*names):
    """Toutes les écritures d'un nom : "Nom#TAG", "Nom", en minuscules."""
    out = set()
    for n in names:
        if n:
            n = str(n).strip().lower()
            out.add(n)
            out.add(n.split("#")[0])
    return out


class Roster:
    """
    Qui est qui : toi (is_me) et l'équipe de chaque joueur (is_ally).
    Les événements nomment les joueurs tantôt "Nom#TAG", tantôt "Nom" : on compare
    toutes les variantes.
    """

    def __init__(self):
        self.me = set()
        self.my_team = None
        self.teams = {}        # alias -> "ORDER" / "CHAOS"

    @property
    def ready(self):
        return bool(self.me) and self.my_team is not None

    def load(self, api: LiveClient):
        """Lit /activeplayername et /playerlist. Renvoie True une fois tout connu."""
        active = api.get("activeplayername")
        players = api.get("playerlist")
        if not active or not players:
            return False
        self.me = _aliases(active)
        for p in players:
            names = _aliases(p.get("summonerName"), p.get("riotId"), p.get("riotIdGameName"))
            for n in names:
                self.teams[n] = p.get("team")
            if names & self.me:
                self.me |= names
                self.my_team = p.get("team")
        return self.ready

    def is_me(self, name):
        return bool(_aliases(name) & self.me)

    def is_ally(self, name):
        teams = {self.teams.get(n) for n in _aliases(name)} - {None}
        return self.my_team is not None and self.my_team in teams


# ── Événements ─────────────────────────────────────────────────────────────────

class EventFeed:
    """Renvoie les nouveaux événements de /eventdata à chaque appel de new_events()."""

    def __init__(self):
        self.seen_ids = set()
        self.first_fetch = True

    def new_events(self, api: LiveClient):
        data = api.get("eventdata")
        if not data:
            return []
        events = data.get("Events", [])

        if self.first_fetch:
            self.first_fetch = False
            if any(e.get("EventTime", 0) > REPLAY_MAX_GAME_TIME for e in events):
                print("[riot] partie déjà en cours, anciens événements ignorés")
                self.seen_ids.update(e.get("EventID") for e in events)
                return []

        fresh = [e for e in events if e.get("EventID") not in self.seen_ids]
        self.seen_ids.update(e.get("EventID") for e in fresh)
        return fresh
