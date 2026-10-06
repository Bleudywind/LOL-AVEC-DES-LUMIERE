"""
led_server.py — à lancer sur le Raspberry Pi (seul fichier à lancer)
Reçoit les événements des watchers via UDP et pilote le ruban WS2812B.

Les animations sont dans animations/<app>.py et chargées automatiquement.

Dépendances : spidev
Usage       : python led_server.py
"""

import json
import socket
from pathlib import Path

from engine import Layout, Runner, get_animation, load_animations
from led_controller import LEDController

# ── Configuration ──────────────────────────────────────────────────────────────
UDP_PORT    = 5005       # doit correspondre à PI_PORT dans client/config.py
NUM_LEDS    = 59         # ton nombre de LEDs
LAYOUT_FILE = Path(__file__).with_name("led_layout.json")
# ───────────────────────────────────────────────────────────────────────────────

# Événements trop fréquents ou trop verbeux pour être affichés en entier
QUIET_EVENTS = {("system", "frame"), ("system", "layout")}


def main():
    apps = load_animations()
    layout = Layout.load(LAYOUT_FILE)
    leds = LEDController(num_leds=NUM_LEDS)
    runner = Runner(leds, layout)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))

    print(f"=== LED Server démarré (UDP :{UDP_PORT}, {NUM_LEDS} LEDs) ===")
    for app, events in sorted(apps.items()):
        print(f"  {app:10s}: {', '.join(sorted(events))}")
    print(f"Calibration : {'oui' if layout.calibrated else 'non'}")
    print("En attente d'événements…\n")

    try:
        while True:
            raw, addr = sock.recvfrom(65535)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                print(f"[erreur] JSON invalide reçu de {addr}")
                continue

            app   = payload.get("app", "lol")
            event = payload.get("event", "")
            data  = payload.get("data") or {}

            if (app, event) not in QUIET_EVENTS:
                print(f"[{app}] {event}  {data}")

            # Message spécial : nouvelle calibration envoyée par calibrate.py / hub.py
            if (app, event) == ("system", "layout"):
                runner.layout = Layout(data)
                runner.layout.save(LAYOUT_FILE)
                sides = {s: len(i) for s, i in data.get("sides", {}).items()}
                print(f"[system] calibration reçue : {sides}")
                if data.get("num_leds") not in (None, NUM_LEDS):
                    print(f"  [warn] calibration faite pour {data['num_leds']} LEDs, "
                          f"le serveur en gère {NUM_LEDS}")
                continue

            # Message spécial : fin de l'ambiance (fin de partie, jeu fermé)
            if (app, event) == ("system", "idle_clear"):
                runner.clear_idle()
                continue

            anim = get_animation(app, event)
            if anim is None:
                print(f"  [inconnu] pas d'animation pour {app}/{event}")
                continue
            runner.play(anim, data)

    except KeyboardInterrupt:
        print("\nArrêt…")
    finally:
        runner.stop()
        leds.close()
        sock.close()
        print("Terminé.")


if __name__ == "__main__":
    main()
