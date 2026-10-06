"""
Capture d'écran / de fond d'écran (Windows) et échantillonnage des bords selon le layout.

- WallpaperCapture : capture le fond d'écran, y compris un fond animé Wallpaper Engine,
  même s'il est recouvert par des fenêtres (Windows Graphics Capture sur "Program Manager").
- EdgeSampler      : calcule la couleur de chaque LED à partir d'une image de l'écran.

Dépendances : pip install windows-capture opencv-python numpy
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import math
import threading

import cv2
import numpy as np

try:
    from windows_capture import WindowsCapture
except ImportError as e:
    raise ImportError("module manquant : pip install windows-capture") from e

from core.layout import LedLayout

_user32 = ctypes.windll.user32

# Coordonnées en pixels physiques, même avec une mise à l'échelle Windows (125 %, 150 %…)
try:
    _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # per-monitor v2
except (AttributeError, OSError):
    pass


# ── Écrans ─────────────────────────────────────────────────────────────────────

class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def list_monitors():
    """[(left, top, right, bottom, principal), ...] dans l'ordre de Windows."""
    monitors = []
    proc_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

    def callback(hmon, hdc, rect, lparam):
        info = _MONITORINFO(ctypes.sizeof(_MONITORINFO))
        _user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        r = info.rcMonitor
        monitors.append((r.left, r.top, r.right, r.bottom, bool(info.dwFlags & 1)))
        return True

    _user32.EnumDisplayMonitors(None, None, proc_type(callback), 0)
    return monitors


def pick_monitor(index=None):
    """Écran d'index `index`, ou l'écran principal si None."""
    monitors = list_monitors()
    if index is None:
        return next(m for m in monitors if m[4])
    return monitors[index]


# ── Échantillonnage des bords ──────────────────────────────────────────────────

class EdgeSampler:
    """
    Pour chaque LED calibrée, moyenne d'une zone de l'image collée au bord de l'écran :
    aussi large que l'espace entre deux LEDs, et profonde de `depth` × (plus petite
    dimension de l'écran).
    """

    def __init__(self, layout: LedLayout, width: int, height: int, depth=0.08):
        self.num_leds = layout.num_leds
        self.boxes = []   # (index LED, y0, y1, x0, x1) en pixels de l'image réduite
        dx = depth * min(width, height) / width
        dy = depth * min(width, height) / height

        for side, indices in layout.sides.items():
            half = 0.5 / (len(indices) - 1) if len(indices) > 1 else 0.5
            for i in indices:
                x, y = layout.position(i)
                if side in ("top", "bottom"):
                    xr = (x - half, x + half)
                    yr = (0.0, dy) if side == "top" else (1.0 - dy, 1.0)
                else:
                    yr = (y - half, y + half)
                    xr = (0.0, dx) if side == "left" else (1.0 - dx, 1.0)
                x0, x1 = self._to_px(xr, width)
                y0, y1 = self._to_px(yr, height)
                self.boxes.append((i, y0, y1, x0, x1))

    @staticmethod
    def _to_px(rng, size):
        a = min(max(int(math.floor(rng[0] * size)), 0), size - 1)
        b = min(max(int(math.ceil(rng[1] * size)), a + 1), size)
        return a, b

    def sample(self, image_bgr) -> np.ndarray:
        """Renvoie un tableau (num_leds, 3) de couleurs RGB (float 0..255)."""
        colors = np.zeros((self.num_leds, 3), dtype=np.float32)
        for i, y0, y1, x0, x1 in self.boxes:
            colors[i] = image_bgr[y0:y1, x0:x1, 2::-1].reshape(-1, 3).mean(axis=0)
        return colors


# ── Capture du fond d'écran ───────────────────────────────────────────────────

class WallpaperCapture:
    """
    Capture en continu le fond d'écran de l'écran `monitor` (tuple de list_monitors),
    réduit à `width` pixels de large, et appelle on_image(image_bgr) à chaque nouvelle image
    (depuis un thread de capture).
    """

    def __init__(self, monitor, on_image, width=192, fps=20):
        self.monitor = monitor
        self.on_image = on_image
        self.width = width
        mw, mh = monitor[2] - monitor[0], monitor[3] - monitor[1]
        self.height = max(1, round(width * mh / mw))
        self.fps = fps
        self._control = None
        self._closed = threading.Event()

    def start(self):
        hwnd = _user32.FindWindowW("Progman", None)
        if not hwnd:
            raise RuntimeError("fenêtre du bureau (Progman) introuvable")
        rect = wt.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        origin = (rect.left, rect.top)
        span = (rect.right - rect.left, rect.bottom - rect.top)

        capture = WindowsCapture(cursor_capture=False, draw_border=False,
                                 minimum_update_interval=int(1000 / self.fps),
                                 window_hwnd=hwnd)

        @capture.event
        def on_frame_arrived(frame, control):
            buf = frame.frame_buffer                     # BGRA, pixels physiques
            sx, sy = buf.shape[1] / span[0], buf.shape[0] / span[1]
            x0 = int((self.monitor[0] - origin[0]) * sx)
            x1 = int((self.monitor[2] - origin[0]) * sx)
            y0 = int((self.monitor[1] - origin[1]) * sy)
            y1 = int((self.monitor[3] - origin[1]) * sy)
            region = buf[max(y0, 0):y1, max(x0, 0):x1]
            if region.size:
                small = cv2.resize(region, (self.width, self.height), interpolation=cv2.INTER_AREA)
                self.on_image(small[:, :, :3])

        @capture.event
        def on_closed():
            self._closed.set()

        self._closed.clear()
        self._control = capture.start_free_threaded()

    @property
    def alive(self):
        return self._control is not None and not self._closed.is_set() \
            and not self._control.is_finished()

    def stop(self):
        if self._control is not None:
            try:
                self._control.stop()
            except Exception:
                pass
            self._control = None
