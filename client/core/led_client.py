"""
Envoi des messages UDP vers led_server.py.

Format : {"app": "lol", "event": "kill", "data": {...}}
"""

import json
import socket


class LedClient:
    def __init__(self, host, port):
        self.addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, app, event, data=None, quiet=False):
        payload = {"app": app, "event": event, "data": data or {}}
        self._sock.sendto(json.dumps(payload).encode("utf-8"), self.addr)
        if not quiet:
            print(f"  → [{app}] {event}  {data or ''}")

    # ── Raccourcis vers les animations "system" du serveur ────────────────────

    def frame(self, pixels):
        """Affiche une image complète : pixels = liste de (r, g, b), une par LED."""
        hexa = "".join(f"{r:02x}{g:02x}{b:02x}" for r, g, b in pixels)
        self.send("system", "frame", {"pixels": hexa}, quiet=True)

    def fill(self, r, g, b):
        self.send("system", "fill", {"color": [r, g, b]}, quiet=True)

    def off(self):
        self.send("system", "off", quiet=True)

    def clear_idle(self):
        """Arrête l'animation d'ambiance en cours sur le serveur."""
        self.send("system", "idle_clear", quiet=True)

    def send_layout(self, layout):
        """Transmet la calibration au serveur (qui la sauvegarde)."""
        self.send("system", "layout", layout.to_dict(), quiet=True)

    def close(self):
        self._sock.close()
