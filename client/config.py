"""
Configuration commune du côté PC (hub, watchers, calibration).
"""

from pathlib import Path

PI_IP         = "192.168.1.24"   # ← IP de ton Raspberry Pi
PI_PORT       = 5005             # doit correspondre à UDP_PORT dans server/led_server.py
NUM_LEDS      = 59               # doit correspondre à NUM_LEDS dans server/led_server.py

SCAN_INTERVAL = 2.0              # secondes entre deux détections de jeux lancés
FALLBACK_DELAY = 10.0            # secondes sans jeu avant de relancer le watcher par défaut
                                 # (laisse finir l'animation de fin de partie)

LAYOUT_FILE   = Path(__file__).with_name("led_layout.json")   # écrit par calibrate.py
