"""
engine.py — moteur d'animations du serveur LED.

Chaque fichier de animations/ déclare ses animations avec le décorateur :

    from engine import animation

    @animation("lol", "kill")
    def kill(ctx, data):
        ctx.fill(255, 0, 0)
        ctx.sleep(0.2)
        ctx.off()

Le couple (app, event) correspond au message UDP envoyé par le watcher :
    {"app": "lol", "event": "kill", "data": {...}}

Une animation d'ambiance (idle=True) tourne en boucle en fond : les autres animations
l'interrompent, puis elle reprend automatiquement quand elles sont terminées.
"""

import importlib
import json
import pkgutil
import threading
import time
import traceback
from pathlib import Path


# ── Registre des animations ────────────────────────────────────────────────────

class Animation:
    def __init__(self, fn, threaded, idle):
        self.fn = fn
        self.threaded = threaded
        self.idle = idle


_REGISTRY = {}


def animation(app, event, threaded=True, idle=False):
    """
    Enregistre une animation pour l'événement `event` de l'application `app`.

    threaded=True  : l'animation tourne dans un thread et peut durer longtemps
                     (elle est interrompue dès qu'un nouvel événement arrive).
    threaded=False : exécutée immédiatement, pour les rendus instantanés
                     (ex: une frame envoyée 30× par seconde).
    idle=True      : animation d'ambiance qui boucle jusqu'à être interrompue,
                     et qui reprend après chaque autre animation
                     (jusqu'à l'événement system/idle_clear).
    """
    def decorator(fn):
        key = (app, event)
        if key in _REGISTRY:
            print(f"[warn] animation {app}/{event} définie deux fois, la dernière gagne")
        _REGISTRY[key] = Animation(fn, threaded or idle, idle)
        return fn
    return decorator


def get_animation(app, event):
    return _REGISTRY.get((app, event))


def load_animations(package="animations"):
    """Importe tous les modules du dossier animations/ (sauf ceux préfixés par _)."""
    pkg = importlib.import_module(package)
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{package}.{mod.name}")
        except Exception:
            print(f"[erreur] impossible de charger {package}/{mod.name}.py :")
            traceback.print_exc()

    apps = {}
    for (app, event), anim in _REGISTRY.items():
        apps.setdefault(app, []).append(event + (" (ambiance)" if anim.idle else ""))
    return apps


# ── Disposition des LEDs (résultat de calibrate.py côté PC) ────────────────────

def _perimeter_point(t):
    """Point du bord de l'écran à la fraction t du tour (départ coin bas-gauche, sens horaire)."""
    side, f = divmod(4 * (t % 1.0), 1.0)
    return [(0.0, 1.0 - f), (f, 0.0), (1.0, f), (1.0 - f, 1.0)][int(side)]


class Layout:
    """
    Accès en lecture à la calibration :
        layout.side("top")   -> indices des LEDs du haut, de gauche à droite
        layout.position(12)  -> (x, y) normalisés 0..1 (0,0 = coin haut-gauche)
    """

    def __init__(self, data=None):
        self.data = data or {}

    @property
    def calibrated(self):
        return bool(self.data.get("sides"))

    def side(self, name):
        return list(self.data.get("sides", {}).get(name, []))

    def position(self, index):
        positions = self.data.get("positions") or []
        if 0 <= index < len(positions) and positions[index] is not None:
            return tuple(positions[index])
        return None

    def positions(self, num_leds):
        """Position de chaque LED ; sans calibration, le ruban est supposé faire le tour de l'écran."""
        return [self.position(i) or _perimeter_point(i / num_leds) for i in range(num_leds)]

    @classmethod
    def load(cls, path: Path):
        try:
            return cls(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return cls()
        except Exception as e:
            print(f"[warn] layout illisible ({e}), ignoré")
            return cls()

    def save(self, path: Path):
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


# ── Contexte passé à chaque animation ──────────────────────────────────────────

# Durée du fondu enchaîné quand une ambiance démarre ou reprend après un événement
IDLE_FADE_IN = 1.2


class AnimContext:
    def __init__(self, leds, layout, stop_event, blend_in=0.0, idle_follows=lambda: False):
        self.leds = leds
        self.layout = layout
        self._stop = stop_event
        self._positions = None
        # Fondu enchaîné depuis l'image affichée avant cette animation
        self._blend_from = leds.shown if blend_in > 0 else None
        self._blend_in = blend_in
        self._started = time.monotonic()
        self._idle_follows = idle_follows

    @property
    def num_leds(self):
        return self.leds.num_leds

    @property
    def stopped(self):
        return self._stop.is_set()

    @property
    def positions(self):
        """[(x, y), ...] pour chaque LED, 0..1, (0, 0) = haut-gauche de l'écran."""
        if self._positions is None:
            self._positions = self.layout.positions(self.num_leds)
        return self._positions

    def sleep(self, seconds):
        """Attend `seconds`. Renvoie False si l'animation doit s'arrêter."""
        return not self._stop.wait(seconds)

    def loop(self, fps=30):
        """
        Boucle d'animation : `for t in ctx.loop(): ...` donne le temps écoulé
        (en secondes) à chaque image, jusqu'à ce que l'animation soit interrompue.
        """
        start = time.monotonic()
        while not self.stopped:
            yield time.monotonic() - start
            if not self.sleep(1 / fps):
                break

    # ── Affichage ────────────────────────────────────────────────────────────

    def fill(self, r, g, b):
        self.leds.set_all(r, g, b)
        self.show()

    def set_pixel(self, index, r, g, b):
        self.leds.set_pixel(index, r, g, b)

    def set_all(self, r, g, b):
        self.leds.set_all(r, g, b)

    def show_colors(self, colors):
        """Affiche une couleur (r, g, b) par LED (valeurs float acceptées)."""
        for i, (r, g, b) in enumerate(colors[:self.num_leds]):
            self.leds.set_pixel(i, _byte(r), _byte(g), _byte(b))
        self.show()

    def show(self):
        """Envoie le buffer au ruban (mélangé à l'image précédente pendant le fondu d'entrée)."""
        pixels = self.leds.pixels
        if self._blend_from is not None:
            k = (time.monotonic() - self._started) / self._blend_in
            if k >= 1:
                self._blend_from = None
            else:
                k = k * k * (3 - 2 * k)                          # démarrage et fin en douceur
                pixels = [tuple(_byte(a + (b - a) * k) for a, b in zip(old, new))
                          for old, new in zip(self._blend_from, pixels)]
        self.leds.show_pixels(pixels)

    def off(self):
        self.leds.set_all(0, 0, 0)
        self.leds.show_pixels(self.leds.pixels)

    # ── Transitions ──────────────────────────────────────────────────────────

    def fade_out(self, duration=0.4):
        """Fondu de l'image affichée vers le noir. Renvoie False si interrompu."""
        start = self.leds.shown
        steps = max(1, int(duration * 30))
        for k in range(steps - 1, -1, -1):
            f = (k / steps) ** 2                                 # décroissance douce pour l'œil
            self.leds.show_pixels([tuple(_byte(v * f) for v in px) for px in start])
            if not self.sleep(1 / 30):
                return False
        self.leds.set_all(0, 0, 0)
        return True

    def flash(self, color, hold=0.06, fade=0.25):
        """Flash : allume `color` pendant `hold` s puis redescend en `fade` s. False si interrompu."""
        self.fill(*color)
        return self.sleep(hold) and self.fade_out(fade)

    def end(self, fade=0.5):
        """
        Fin d'une animation d'événement : si une ambiance va reprendre, on garde la
        dernière image (l'ambiance fera un fondu enchaîné depuis elle) ; sinon fondu au noir.
        """
        if not self.stopped and not self._idle_follows():
            self.fade_out(fade)


def _byte(v):
    return 0 if v <= 0 else 255 if v >= 255 else int(v)


# ── Exécution : une seule animation à la fois, + ambiance en fond ──────────────

# Fin d'ambiance : fondu au noir (interrompu par l'animation suivante, ex : victoire)
_IDLE_FADE_OUT = Animation(lambda ctx, data: ctx.fade_out(0.8), threaded=True, idle=False)


class Runner:
    def __init__(self, leds, layout):
        self.leds = leds
        self.layout = layout
        self._lock = threading.Lock()
        self._thread = None
        self._stop = None
        self._current = None   # Animation en cours (ou dernière jouée)
        self._idle = None      # (Animation, data) de l'ambiance active

    def play(self, anim: Animation, data: dict):
        with self._lock:
            if anim.idle:
                same = self._idle is not None and self._idle == (anim, data)
                self._idle = (anim, data)
                if self._running() and not self._current.idle:
                    return   # une animation d'événement tourne : l'ambiance reprendra après
                if same and self._running():
                    return   # déjà en cours (le watcher renvoie l'ambiance régulièrement)
            self._start(anim, data)

    def clear_idle(self):
        """Désactive l'ambiance (fin de partie, fermeture du jeu)."""
        with self._lock:
            self._idle = None
            if self._running() and self._current.idle:
                self._start(_IDLE_FADE_OUT, {})

    def stop(self):
        with self._lock:
            self._idle = None
            self._stop_current()

    # ── interne (appelé avec self._lock) ─────────────────────────────────────

    def _running(self):
        return self._thread is not None and self._thread.is_alive()

    def _start(self, anim, data):
        self._stop_current()
        stop = threading.Event()
        self._stop = stop
        self._current = anim
        ctx = AnimContext(self.leds, self.layout, stop,
                          blend_in=IDLE_FADE_IN if anim.idle else 0.0,
                          idle_follows=lambda: self._idle is not None)
        if anim.threaded:
            self._thread = threading.Thread(target=self._thread_main,
                                            args=(anim, ctx, data, stop), daemon=True)
            self._thread.start()
        else:
            self._safe_run(anim.fn, ctx, data)

    def _stop_current(self):
        if self._stop is not None:
            self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None

    def _thread_main(self, anim, ctx, data, stop):
        self._safe_run(anim.fn, ctx, data)
        if anim.idle:
            return
        # Fin naturelle d'une animation d'événement → reprise de l'ambiance.
        # acquire avec timeout : si un nouvel événement arrive au même moment,
        # le thread principal nous arrête (stop) et attend notre fin.
        while not stop.is_set():
            if self._lock.acquire(timeout=0.05):
                try:
                    if not stop.is_set() and self._idle is not None:
                        self._start(*self._idle)
                finally:
                    self._lock.release()
                return

    @staticmethod
    def _safe_run(fn, ctx, data):
        try:
            fn(ctx, data)
        except Exception:
            print(f"[erreur] animation {fn.__module__}.{fn.__name__} :")
            traceback.print_exc()
