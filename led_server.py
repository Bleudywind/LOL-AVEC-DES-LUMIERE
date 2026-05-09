"""
led_server.py — à lancer sur le Raspberry Pi
Reçoit les événements LoL via UDP et pilote le ruban WS2812B.

Dépendances : spidev (déjà installé), aucune autre
Usage       : python led_server.py
              (ou : sudo python led_server.py si le SPI le requiert)
"""

import socket
import json
import time
import threading
from led_controller import LEDController   # ton module SPI

# ── Configuration ──────────────────────────────────────────────────────────────
UDP_PORT  = 5005       # doit correspondre à RASPBERRY_PI_PORT dans lol_watcher.py
NUM_LEDS  = 59         # ton nombre de LEDs
# ───────────────────────────────────────────────────────────────────────────────

leds = LEDController(num_leds=NUM_LEDS)

# Verrou pour ne pas mixer deux animations simultanées
anim_lock   = threading.Lock()
stop_event  = threading.Event()   # signal pour interrompre l'animation en cours


# ── Utilitaires d'animation ────────────────────────────────────────────────────

def _stop_current():
    """Demande l'arrêt de l'animation en cours et attend qu'elle se termine."""
    stop_event.set()
    time.sleep(0.05)   # laisse le thread en cours voir le signal


def _run_anim(fn):
    """Lance fn dans un thread dédié (sans bloquer le serveur UDP)."""
    stop_event.clear()
    t = threading.Thread(target=fn, daemon=True)
    t.start()


# ── Animations ─────────────────────────────────────────────────────────────────

def anim_kill():
    """Flash rouge vif × 3."""
    for _ in range(3):
        if stop_event.is_set():
            break
        leds.couleur_unie(255, 0, 0)
        time.sleep(0.12)
        leds.couleur_unie(0, 0, 0)
        time.sleep(0.08)
    leds.couleur_unie(0, 0, 0)


def anim_death():
    """Bleu qui s'éteint progressivement (fade-out)."""
    for brightness in range(255, 0, -5):
        if stop_event.is_set():
            break
        leds.couleur_unie(0, 0, brightness)
        time.sleep(0.02)
    leds.couleur_unie(0, 0, 0)


def anim_multikill(streak: int):
    """Flash rouge de plus en plus rapide selon le streak."""
    flashes = min(streak, 6)
    delay   = max(0.04, 0.15 - streak * 0.02)
    for _ in range(flashes):
        if stop_event.is_set():
            break
        leds.couleur_unie(255, 50, 0)
        time.sleep(delay)
        leds.couleur_unie(0, 0, 0)
        time.sleep(delay * 0.5)
    leds.couleur_unie(0, 0, 0)


def anim_ace():
    """Vague dorée de gauche à droite."""
    for _ in range(2):
        for i in range(NUM_LEDS):
            if stop_event.is_set():
                break
            leds.set_all(0, 0, 0)
            for j in range(max(0, i - 4), i + 1):
                intensity = 255 - (i - j) * 50
                leds.set_pixel(j, intensity, intensity // 2, 0)
            leds.show()
            time.sleep(0.03)
    leds.couleur_unie(0, 0, 0)


def anim_dragon(dragon_type: str):
    """Couleur selon le type de dragon, pulse 2×."""
    colors = {
        "Fire":      (255, 60,  0),
        "Infernal":  (255, 60,  0),
        "Water":     (0,  150, 255),
        "Ocean":     (0,  150, 255),
        "Air":       (180, 240, 255),
        "Mountain":  (120, 80,  40),
        "Earth":     (120, 80,  40),
        "Elder":     (255, 200, 0),
        "Hextech":   (100, 0,  255),
        "Chemtech":  (50,  200, 50),
    }
    r, g, b = colors.get(dragon_type, (255, 255, 255))
    for _ in range(2):
        if stop_event.is_set():
            break
        leds.couleur_unie(r, g, b)
        time.sleep(0.4)
        leds.couleur_unie(0, 0, 0)
        time.sleep(0.2)
    leds.couleur_unie(0, 0, 0)


def anim_baron():
    """Pulse violet lent × 3."""
    for _ in range(3):
        for brightness in range(0, 200, 8):
            if stop_event.is_set():
                break
            leds.couleur_unie(brightness, 0, brightness)
            time.sleep(0.02)
        for brightness in range(200, 0, -8):
            if stop_event.is_set():
                break
            leds.couleur_unie(brightness, 0, brightness)
            time.sleep(0.02)
    leds.couleur_unie(0, 0, 0)


def anim_herald():
    """Pulse violet clair × 2."""
    for _ in range(2):
        leds.couleur_unie(100, 0, 200)
        time.sleep(0.4)
        leds.couleur_unie(0, 0, 0)
        time.sleep(0.2)
    leds.couleur_unie(0, 0, 0)


def anim_turret():
    """Flash cyan court."""
    leds.couleur_unie(0, 200, 200)
    time.sleep(0.3)
    leds.couleur_unie(0, 0, 0)


def anim_inhibitor():
    """Flash orange."""
    for _ in range(2):
        leds.couleur_unie(255, 100, 0)
        time.sleep(0.25)
        leds.couleur_unie(0, 0, 0)
        time.sleep(0.15)
    leds.couleur_unie(0, 0, 0)


def anim_win():
    """Vague arc-en-ciel qui parcourt le ruban 3×."""
    def rainbow_step(pos):
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        else:
            pos -= 170
            return (pos * 3, 0, 255 - pos * 3)

    for _ in range(3):
        for offset in range(256):
            if stop_event.is_set():
                break
            for i in range(NUM_LEDS):
                r, g, b = rainbow_step((i * 256 // NUM_LEDS + offset) % 256)
                leds.set_pixel(i, r, g, b)
            leds.show()
            time.sleep(0.015)
    leds.couleur_unie(0, 0, 0)


def anim_lose():
    """Extinction rouge progressive."""
    leds.couleur_unie(200, 0, 0)
    time.sleep(0.5)
    for brightness in range(200, 0, -4):
        if stop_event.is_set():
            break
        leds.couleur_unie(brightness, 0, 0)
        time.sleep(0.03)
    leds.couleur_unie(0, 0, 0)


def anim_game_start():
    """Balayage blanc au démarrage de la partie."""
    for i in range(NUM_LEDS):
        if stop_event.is_set():
            break
        leds.set_pixel(i, 200, 200, 200)
        leds.show()
        time.sleep(0.03)
    time.sleep(0.5)
    leds.couleur_unie(0, 0, 0)


# ── Dispatch des événements ────────────────────────────────────────────────────

def dispatch(event_name: str, data: dict):
    print(f"[event] {event_name}  {data}")

    with anim_lock:
        _stop_current()

        if event_name == "kill":
            _run_anim(anim_kill)

        elif event_name == "multikill":
            streak = data.get("streak", 2)
            _run_anim(lambda: anim_multikill(streak))

        elif event_name == "ace":
            _run_anim(anim_ace)

        elif event_name == "dragon":
            dtype = data.get("type", "Unknown")
            _run_anim(lambda: anim_dragon(dtype))

        elif event_name == "baron":
            _run_anim(anim_baron)

        elif event_name == "herald":
            _run_anim(anim_herald)

        elif event_name == "turret":
            _run_anim(anim_turret)

        elif event_name == "inhibitor":
            _run_anim(anim_inhibitor)

        elif event_name == "game_end":
            result = data.get("result", "")
            if result == "Win":
                _run_anim(anim_win)
            else:
                _run_anim(anim_lose)

        elif event_name == "game_start":
            _run_anim(anim_game_start)

        else:
            print(f"  [inconnu] événement ignoré : {event_name}")


# ── Serveur UDP ────────────────────────────────────────────────────────────────

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
    print(f"=== LED Server démarré (UDP :{UDP_PORT}) ===")
    print("En attente d'événements LoL…\n")

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            try:
                payload    = json.loads(data.decode("utf-8"))
                event_name = payload.get("event", "")
                event_data = payload.get("data", {})
                dispatch(event_name, event_data)
            except json.JSONDecodeError:
                print(f"[erreur] JSON invalide reçu de {addr}")

    except KeyboardInterrupt:
        print("\nArrêt…")
    finally:
        _stop_current()
        time.sleep(0.2)
        leds.close()
        sock.close()
        print("Terminé.")


if __name__ == "__main__":
    main()
