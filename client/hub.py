"""
hub.py — seul script à lancer sur le PC.
Détecte les jeux lancés et démarre / arrête le watcher correspondant
(un fichier par jeu dans watchers/).

Dépendances : pip install -r requirements.txt
Usage       : python hub.py                 détection automatique
              python hub.py --list          liste les watchers disponibles
              python hub.py --force lol     force un watcher (test sans le jeu)
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import importlib
import inspect
import pkgutil
import time
import traceback

import config
from core.layout import LedLayout
from core.led_client import LedClient
from core.watcher import Watcher


def discover_watchers():
    """Importe watchers/*.py et renvoie {name: classe} pour chaque sous-classe de Watcher."""
    import watchers
    found = {}
    for mod in pkgutil.iter_modules(watchers.__path__):
        if mod.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"watchers.{mod.name}")
        except Exception:
            print(f"[erreur] impossible de charger watchers/{mod.name}.py :")
            traceback.print_exc()
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Watcher) and cls is not Watcher and cls.__module__ == module.__name__:
                if not cls.name:
                    print(f"[warn] {cls.__name__} n'a pas de `name`, ignoré")
                    continue
                found[cls.name] = cls
    return found


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", wt.LONG), ("dwFlags", wt.DWORD), ("szExeFile", wt.WCHAR * 260)]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
_kernel32.CreateToolhelp32Snapshot.argtypes = (wt.DWORD, wt.DWORD)
_kernel32.Process32FirstW.argtypes = (wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W))
_kernel32.Process32NextW.argtypes = (wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W))
_kernel32.CloseHandle.argtypes = (wt.HANDLE,)
_TH32CS_SNAPPROCESS = 0x2
_INVALID_HANDLE = wt.HANDLE(-1).value


def running_processes():
    """
    Noms des processus en cours, en minuscules.

    Utilise un instantané système (CreateToolhelp32Snapshot) : on lit seulement la liste
    des noms d'exécutables, sans jamais ouvrir de handle sur un processus — en
    particulier pas sur les jeux protégés par un anti-cheat (Vanguard…).
    """
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, _INVALID_HANDLE):
        return set()
    names = set()
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    return names


def main():
    parser = argparse.ArgumentParser(description="Hub des watchers LED")
    parser.add_argument("--list", action="store_true", help="liste les watchers et quitte")
    parser.add_argument("--force", nargs="+", metavar="NAME", default=[],
                        help="démarre ces watchers sans attendre la détection du jeu")
    args = parser.parse_args()

    classes = discover_watchers()

    if args.list:
        for name, cls in sorted(classes.items()):
            detection = "par défaut, sans jeu" if cls.fallback else                 ", ".join(cls.processes) or "détection personnalisée"
            print(f"  {name:12s} {detection}")
        return

    unknown = set(args.force) - set(classes)
    if unknown:
        parser.error(f"watcher(s) inconnu(s) : {', '.join(sorted(unknown))}")

    leds = LedClient(config.PI_IP, config.PI_PORT)
    layout = LedLayout.load(config.LAYOUT_FILE)
    if layout is not None:
        leds.send_layout(layout)   # resynchronise le Pi au cas où

    print("=== LED Hub ===")
    print(f"Pi cible    : {config.PI_IP}:{config.PI_PORT}")
    print(f"Calibration : {'oui' if layout else 'non (lance calibrate.py)'}")
    print(f"Watchers    : {', '.join(sorted(classes)) or 'aucun'}")
    print("En attente d'un jeu… (Ctrl+C pour quitter)\n")

    active = {}           # name -> instance
    last_game = 0.0       # dernier instant où un watcher non-fallback tournait
    try:
        while True:
            running = running_processes()

            def is_wanted(name, cls):
                try:
                    return name in args.force or cls.detect(running)
                except Exception:
                    traceback.print_exc()
                    return False

            # Les jeux d'abord, puis les watchers par défaut s'il n'y en a aucun
            wanted = {n for n, c in classes.items() if not c.fallback and is_wanted(n, c)}
            if wanted:
                last_game = time.time()
            elif time.time() - last_game >= config.FALLBACK_DELAY:
                wanted = {n for n, c in classes.items() if c.fallback and is_wanted(n, c)}

            # Arrêts avant démarrages, pour ne pas avoir deux watchers sur le ruban
            for name in [n for n in active if n not in wanted]:
                print(f"■ {name} arrêté")
                active.pop(name).stop()
            for name in sorted(wanted - set(active)):
                print(f"▶ {name} démarré")
                active[name] = classes[name](leds, layout)
                active[name].start()

            time.sleep(config.SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\nArrêt…")
    finally:
        for watcher in active.values():
            watcher.stop()
        leds.close()


if __name__ == "__main__":
    main()
