"""
lol_watcher.py — à lancer sur ton PC pendant une partie LoL
Surveille la Live Client Data API et envoie les événements au Raspberry Pi via UDP.

Dépendances : pip install requests
Usage       : python lol_watcher.py
"""

import requests
import socket
import json
import time
import urllib3

# ── Configuration ──────────────────────────────────────────────────────────────
RASPBERRY_PI_IP  = "192.168.1.XX"   # ← remplace par l'IP de ton Pi (ex: 192.168.1.42)
RASPBERRY_PI_PORT = 5005             # port UDP écouté par led_server.py
POLL_INTERVAL    = 0.5               # secondes entre chaque poll

LOL_API_URL = "https://127.0.0.1:2999/liveclientdata/eventdata"

# Désactive l'avertissement SSL (l'API LoL utilise un cert auto-signé)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# ───────────────────────────────────────────────────────────────────────────────

# Événements déjà traités (on stocke leurs IDs pour ne pas les rejouer)
seen_event_ids = set()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_event(event_name: str, data: dict = None):
    """Envoie un événement JSON au Raspberry Pi via UDP."""
    payload = {"event": event_name, "data": data or {}}
    message = json.dumps(payload).encode("utf-8")
    sock.sendto(message, (RASPBERRY_PI_IP, RASPBERRY_PI_PORT))
    print(f"  → envoyé : {event_name}  {data or ''}")


def handle_event(evt: dict):
    """
    Analyse un événement LoL et appelle send_event avec le bon nom.
    Référence complète des types : https://developer.riotgames.com/docs/lol
    """
    etype = evt.get("EventName", "")

    if etype == "ChampionKill":
        # Récupérer qui a fait le kill
        killer = evt.get("KillerName", "")
        victim = evt.get("VictimName", "")

        # Pour savoir si c'est notre joueur, on utiliserait activePlayer
        # Ici on envoie toujours les deux infos, le Pi décide
        send_event("kill", {"killer": killer, "victim": victim})

    elif etype == "Multikill":
        kill_streak = evt.get("KillStreak", 1)
        send_event("multikill", {"streak": kill_streak})

    elif etype == "Ace":
        send_event("ace", {})

    elif etype == "DragonKill":
        dragon_type = evt.get("DragonType", "Unknown")   # Air, Earth, Fire, Water, Elder, Hextech, Chemtech
        send_event("dragon", {"type": dragon_type})

    elif etype == "BaronKill":
        send_event("baron", {})

    elif etype == "HeraldKill":
        send_event("herald", {})

    elif etype == "TurretKilled":
        send_event("turret", {})

    elif etype == "InhibKilled":
        send_event("inhibitor", {})

    elif etype == "GameEnd":
        result = evt.get("Result", "Unknown")   # "Win" ou "Lose"
        send_event("game_end", {"result": result})

    elif etype == "GameStart":
        send_event("game_start", {})

    # Ajoute d'autres types ici si besoin


def poll_once():
    """Un cycle de poll : récupère les événements et traite les nouveaux."""
    try:
        resp = requests.get(LOL_API_URL, verify=False, timeout=2)
        if resp.status_code != 200:
            return

        events = resp.json().get("Events", [])
        for evt in events:
            evt_id = evt.get("EventID")
            if evt_id not in seen_event_ids:
                seen_event_ids.add(evt_id)
                handle_event(evt)

    except requests.exceptions.ConnectionError:
        # Pas de partie en cours — silence
        pass
    except Exception as e:
        print(f"[erreur] {e}")


def main():
    print("=== LoL LED Watcher ===")
    print(f"Pi cible   : {RASPBERRY_PI_IP}:{RASPBERRY_PI_PORT}")
    print(f"Poll toutes: {POLL_INTERVAL}s")
    print("En attente d'une partie… (Ctrl+C pour quitter)\n")

    while True:
        poll_once()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nArrêt.")
        sock.close()
