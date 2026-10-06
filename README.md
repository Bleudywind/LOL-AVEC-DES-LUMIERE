# LED Gaming – Ruban WS2812B réactif à tes jeux

Pilote un ruban LED WS2812B depuis un Raspberry Pi en fonction de ce qui se passe
dans tes jeux : League of Legends (Faille, ARAM, Arena), Teamfight Tactics et
VALORANT — et reprend les couleurs de ton fond d'écran le reste du temps.
Ajouter un jeu = **un fichier watcher côté PC + un fichier d'animations côté Pi**.

---

## Architecture

```
PC (Windows)                                Raspberry Pi
┌──────────────────────────────┐            ┌──────────────────────────────┐
│ hub.py  (seul script à lancer)│            │ led_server.py (seul script)   │
│   détecte les jeux lancés     │            │   reçoit {app, event, data}   │
│        │                      │  UDP/JSON  │        │                      │
│        ├─▶ watchers/lol.py  ──────────────▶│        ├─▶ animations/lol.py   │
│        └─▶ watchers/xxx.py  ──────────────▶│        ├─▶ animations/xxx.py   │
│                               │            │        └─▶ animations/system.py│
│ calibrate.py ─▶ led_layout.json ──────────▶│ led_layout.json               │
└──────────────────────────────┘            │        ▼                      │
                                            │ led_controller.py → ruban SPI │
                                            └──────────────────────────────┘
```

Chaque message UDP est de la forme `{"app": "lol", "event": "kill", "data": {...}}`.
Le serveur joue l'animation enregistrée pour `lol/kill`. Une seule animation tourne
à la fois : un nouvel événement interrompt la précédente.

Une animation peut être une **ambiance** (`idle=True`) : elle tourne en boucle en
fond (ex : le thème de la Faille pendant une partie), est interrompue par les
animations d'événements, puis reprend toute seule quand elles sont finies.
Le watcher l'arrête avec `self.leds.clear_idle()` (fin de partie, jeu fermé).

---

## Fichiers du projet

```
client/                     ← sur le PC
├── hub.py                  # point d'entrée : détecte les jeux, lance les watchers
├── calibrate.py            # calibrage de la position des LEDs autour de l'écran
├── config.py               # IP du Pi, port, nombre de LEDs
├── led_layout.json         # généré par calibrate.py
├── requirements.txt
├── core/
│   ├── watcher.py          # classe de base Watcher
│   ├── led_client.py       # envoi UDP vers le Pi
│   ├── layout.py           # lecture/écriture de la calibration
│   └── capture.py          # capture du fond d'écran + couleurs des bords
└── watchers/
    ├── lol.py              # League of Legends (Faille, ARAM, Arena)
    ├── tft.py              # Teamfight Tactics
    ├── valorant.py         # VALORANT
    ├── _riot.py            # code commun LoL / TFT (API live, mode de jeu)
    ├── wallpaper.py        # par défaut sans jeu : couleurs du fond d'écran
    └── _exemple.py         # modèle pour un nouveau jeu

server/                     ← sur le Raspberry Pi
├── led_server.py           # point d'entrée : serveur UDP
├── engine.py               # registre d'animations, contexte, exécution
├── led_controller.py       # pilote SPI du ruban
├── led_layout.json         # reçu du PC après calibration
└── animations/
    ├── system.py           # off, fill, frame (image brute), test
    ├── lol.py              # animations + ambiances League of Legends
    ├── tft.py              # animations + ambiance Teamfight Tactics
    ├── valorant.py         # animations + ambiances VALORANT
    ├── _fx.py              # outils de couleur partagés
    └── _exemple.py         # modèle pour un nouveau jeu
```

Les fichiers commençant par `_` sont ignorés par le chargement automatique.

---

## Prérequis

### Sur le PC

- Python 3.8+
- ```bash
  pip install -r client/requirements.txt
  ```

### Sur le Raspberry Pi

- Python 3.8+
- SPI activé (voir plus bas)
- ```bash
  pip install spidev --break-system-packages
  ```

---

## Montage électronique

```
Raspberry Pi                Ruban WS2812B
─────────────               ─────────────
Pin 2  (5V)  ──────────────  +5V
Pin 6  (GND) ──────────────  GND
Pin 19 (MOSI)── [300 Ω] ───  DIN
```

**Condensateur :** place un condensateur **1000 µF** entre le +5V et le GND
juste à l'entrée du ruban (absorbe les pics de courant).

**Alimentation externe :** si tu as plus de ~10 LEDs, alimente le ruban
directement depuis une source 5V dédiée (max ~3,5 A pour 59 LEDs en blanc
plein). Relie le GND de cette source au GND du Pi.

---

## Installation

### 1. Raspberry Pi

```bash
sudo raspi-config          # Interface Options → SPI → Enable → Reboot
ls /dev/spidev*            # doit afficher /dev/spidev0.0
hostname -I                # note l'IP du Pi
```

Copie le dossier `server/` sur le Pi (depuis le PC) :

```bash
scp -r server pi@192.168.1.42:~/leds
```

### 2. PC

Dans `client/config.py`, renseigne l'IP du Pi et le nombre de LEDs :

```python
PI_IP    = "192.168.1.42"
PI_PORT  = 5005    # = UDP_PORT dans server/led_server.py
NUM_LEDS = 59      # = NUM_LEDS dans server/led_server.py
```

---

## Lancement

Sur le Pi :

```bash
cd ~/leds
python led_server.py
```

```
=== LED Server démarré (UDP :5005, 59 LEDs) ===
  lol       : ace, baron, death, dragon, game_end, game_start, ...
  system    : fill, frame, off, test
Calibration : oui
```

Sur le PC (à laisser tourner en permanence) :

```bash
python client/hub.py
```

Le hub scanne les processus toutes les 2 s. Quand une partie de LoL est en cours
(`League of Legends.exe` + API live active), le watcher `lol` ou `tft` démarre selon
le mode de jeu ; quand le jeu se ferme, il s'arrête.

Quand aucun jeu ne tourne, le watcher **wallpaper** prend le relais : les LEDs
reprennent les couleurs des bords de ton fond d'écran (voir plus bas). Il est
coupé dès qu'un jeu démarre, et relancé `FALLBACK_DELAY` secondes (10 par défaut,
dans `config.py`) après la fermeture du jeu, pour laisser finir l'animation de fin
de partie.

Options utiles :

```bash
python client/hub.py --list          # watchers disponibles et exe surveillés
python client/hub.py --force lol     # démarre un watcher sans attendre le jeu
```

---

## Calibrer la position des LEDs

```bash
python client/calibrate.py
```

Le serveur doit tourner sur le Pi. Pour chacun des 4 coins de l'écran, une LED
blanche s'allume sur le ruban : déplace-la avec ← → (↑ ↓ pour ±10) jusqu'au coin
indiqué à l'écran, puis Entrée. `S` si un coin n'a pas de LED, `Retour arrière`
pour annuler.

Les côtés sont déduits des coins (la LED d'un coin appartient aux deux côtés),
quel que soit le sens de câblage ou l'endroit où commence le ruban. À la dernière
étape, le ruban affiche chaque côté dans sa couleur : `G` `H` `D` `B` activent ou
désactivent un côté. Un côté sans LED (ex : ruban en U sans le bas) est détecté
et désactivé automatiquement.

Ensuite, **Enregistrer** :
- écrit `client/led_layout.json` (utilisé par les watchers via `self.layout`) ;
- l'envoie au Pi, qui le sauvegarde (utilisé par les animations via `ctx.layout`) ;
- joue l'animation `system/test` qui allume chaque côté dans sa couleur.

Ce que la calibration fournit :

```python
layout.side("top")      # indices des LEDs du haut, de gauche à droite
layout.side("left")     # de bas en haut ; "right" de haut en bas ; "bottom" de droite à gauche
layout.position(12)     # (x, y) entre 0 et 1 — (0, 0) = coin haut-gauche de l'écran
```

---

## Ambiance fond d'écran (watcher `wallpaper`)

Nécessite la calibration. Les couleurs de chaque LED sont calculées à partir de la
bande de l'écran la plus proche, ~20 fois par seconde, avec une transition douce.

- Fonctionne avec **Wallpaper Engine** (fonds animés, scènes, vidéos, web) et avec un
  fond d'écran Windows classique.
- Le fond d'écran est capturé **même s'il est caché par des fenêtres** (capture
  Windows Graphics Capture de la fenêtre du bureau). Les icônes du bureau sont
  incluses dans la capture.
- Si Wallpaper Engine met son fond en pause (application en plein écran), les LEDs
  restent sur la dernière image.

Réglages en haut de `client/watchers/wallpaper.py` :

| Réglage | Défaut | Rôle |
|---|---|---|
| `MONITOR` | `None` | écran entouré par les LEDs (`None` = principal, sinon 0, 1…) |
| `FPS` | 20 | images envoyées par seconde |
| `DEPTH` | 0.08 | profondeur de la bande analysée le long du bord |
| `BRIGHTNESS` | 0.6 | luminosité max (limite aussi la consommation) |
| `SATURATION` | 1.3 | couleurs plus vives |
| `GAMMA` | 2.2 | garde les couleurs sombres sombres sur les LEDs |
| `SMOOTHING` | 0.25 | vitesse de transition (1 = instantané) |

`core/capture.py` (`EdgeSampler`) est réutilisable pour un autre watcher, par
exemple un ambilight de l'écran en jeu.

---

## Ajouter un jeu

### 1. Le watcher (PC) — `client/watchers/mon_jeu.py`

Copie `watchers/_exemple.py` :

```python
from core.watcher import Watcher

class MonJeuWatcher(Watcher):
    name = "mon_jeu"                  # = APP côté serveur
    processes = ("MonJeu.exe",)       # Gestionnaire des tâches → Détails
    poll_interval = 0.5

    def on_start(self):               # au lancement du jeu
        ...

    def poll(self):                   # en boucle tant que le jeu tourne
        if quelque_chose_se_passe:
            self.send("boom", {"force": 3})

    def on_stop(self):                # à la fermeture du jeu
        ...
```

Pour une détection plus fine que le nom du processus, surcharge
`detect(cls, running)` (classmethod, `running` = noms d'exe en minuscules).
Avec `fallback = True`, le watcher devient un watcher « par défaut » : il ne tourne
que quand aucun watcher de jeu n'est actif (comme `wallpaper`).

Un watcher peut aussi piloter le ruban directement, sans animation côté serveur,
avec `self.leds.frame([(r, g, b), ...])` — utile par exemple pour un effet
« ambilight » qui calcule la couleur de chaque LED à partir de `self.layout`.

### 2. Les animations (Pi) — `server/animations/mon_jeu.py`

Copie `animations/_exemple.py` :

```python
from engine import animation

APP = "mon_jeu"

@animation(APP, "boom")
def boom(ctx, data):
    for _ in range(data.get("force", 1)):
        ctx.fill(255, 0, 0)
        if not ctx.sleep(0.1):     # False = un autre événement est arrivé → on arrête
            break
        ctx.fill(0, 0, 0)
        if not ctx.sleep(0.1):
            break
    ctx.off()
```

Outils du contexte : `ctx.fill`, `ctx.set_pixel`, `ctx.set_all`, `ctx.show`,
`ctx.off`, `ctx.sleep`, `ctx.num_leds`, `ctx.layout`, `ctx.positions` (x, y de
chaque LED), `ctx.show_colors(liste)` et `ctx.loop(fps)` pour les animations en boucle.

Transitions : `ctx.flash(couleur, hold, fade)` (flash qui redescend en douceur),
`ctx.fade_out(durée)`, et `ctx.end()` à la fin d'une animation d'événement — l'ambiance
reprend alors en **fondu enchaîné** depuis la dernière image (`IDLE_FADE_IN` dans
`engine.py`, 1,2 s), ou fondu au noir s'il n'y a pas d'ambiance.

Pour une ambiance qui tourne en fond pendant la partie :

```python
@animation(APP, "theme", idle=True)
def theme(ctx, data):
    for t in ctx.loop(30):                  # s'arrête tout seul quand c'est interrompu
        k = 0.5 + 0.5 * math.sin(t)
        ctx.show_colors([(0, 80 * k, 120)] * ctx.num_leds)
```

Côté watcher : `self.send("theme")` pour la lancer (la renvoyer régulièrement ne la
redémarre pas), `self.leds.clear_idle()` pour l'arrêter.

Copie le nouveau fichier sur le Pi et relance `led_server.py`.

---

## Animations League of Legends

### Ambiances (en fond, entre les événements)

| Mode | Ambiance |
|---|---|
| Faille de l'invocateur | Comme la minimap : base bleue en bas à gauche, base rouge en haut à droite, jungle verte, rivière scintillante en diagonale. La rivière prend la couleur du terrain élémentaire (Infernal, Océan…) une fois l'âme révélée |
| ARAM (Abîme hurlant) | Bleu glacier qui ondule, flocons qui scintillent |
| Arena | Braises orangées, éclat doré qui tourne autour de l'écran |

L'ambiance s'arrête à la fin de la partie (après l'animation de victoire / défaite).

Seuls les événements qui te concernent sont animés : les kills des autres joueurs
et les monstres neutres pris par l'équipe adverse sont ignorés. Le watcher reconnaît
ton Riot ID et ton équipe via `/playerlist` au début de la partie.

### Événements

| Événement | Animation |
|---|---|
| Ton kill | Flash rouge × 3 |
| Ta mort | Fondu bleu |
| Ton assist | Deux vagues dorées qui se rejoignent au centre |
| Ton double kill / triple… | Flash orange, vitesse selon le streak |
| Ace de ton équipe | Vague dorée de gauche à droite |
| Dragon pris par ton équipe | Couleur selon le type (feu, eau, air, elder…) |
| Baron pris par ton équipe | Pulse violet lent × 3 |
| Héraut pris par ton équipe | Pulse violet clair |
| Objectif volé | Stroboscope blanc avant l'animation du monstre |
| Tour détruite | Flash cyan |
| Inhibiteur | Flash orange × 2 |
| Victoire | Arc-en-ciel défilant |
| Défaite | Extinction rouge progressive |
| Début de partie | Balayage blanc |

Si le hub démarre alors qu'une partie est déjà en cours, les anciens événements
ne sont pas rejoués.

---

## Animations Teamfight Tactics

L'API live de Riot donne très peu d'informations en TFT (pas de rounds, ni
d'adversaires, ni de synergies) : les animations s'appuient sur la vie et le
niveau de ton tacticien.

| Événement | Animation |
|---|---|
| Ambiance | Tourbillon violet / bleu avec des étincelles dorées |
| Vie ≤ 20 | L'ambiance devient un battement de cœur rouge |
| Round perdu (vie qui baisse) | Flash rouge (plus fort selon les dégâts), puis jauge de vie en bas de l'écran |
| Montée de niveau | Vague dorée du bas vers le haut |
| Élimination | Violet qui se brise, LEDs qui s'éteignent une à une |
| Début de partie | Tourbillon qui se remplit autour de l'écran |
| Victoire | Tourbillon or et violet |

`DUMP_GAME_DATA` (en haut de `client/watchers/tft.py`) enregistre les données de
l'API dans `client/debug/` au début et à la fin de chaque partie, pour vérifier ce
qui est disponible.

---

## Animations VALORANT

Valorant n'a pas d'API live officielle. Le watcher lit, en local et en lecture
seule, la « présence » que le jeu publie au Riot Client (identifiants dans
`%LOCALAPPDATA%\Riot Games\Riot Client\Config\lockfile`) : étape (menus,
sélection d'agent, en jeu), carte, mode et **score des deux équipes**. Les kills, le
spike et la vie n'y sont pas : aucune animation ne s'appuie dessus.

Ton équipe est en turquoise (comme le HUD), l'ennemi en rouge Valorant.

| Moment | Animation |
|---|---|
| Menus | Rouge Valorant qui respire, traversé par un trait blanc |
| Sélection d'agent | Éclair blanc → turquoise, puis ambiance turquoise avec un point qui tourne (compte à rebours) |
| Début du match | Ton équipe arrive par la gauche, l'ennemi par la droite, choc blanc au centre |
| En jeu | Les couleurs de la carte défilent doucement (Ascent, Bind, Haven, Split, Icebox, Breeze, Fracture, Pearl, Lotus, Sunset, Abyss, champ de tir) |
| Manche gagnée | Double flash turquoise, puis **le score sur le bord haut** (toi à gauche, l'ennemi à droite) |
| Manche perdue | Rouge qui tombe du haut vers le bas, puis le score |
| Balle de match | 3 pulsations après le score, et l'ambiance pulse toutes les 2 s (turquoise pour toi, rouge pour l'ennemi, blanc si manche décisive) |
| Victoire / défaite | Vagues turquoise et étincelles / rouge qui s'éteint lentement |

Les manches à gagner dépendent du mode (13 en compét / non classée / Premier, 5 en
Swiftplay, 4 en Spike Rush ; 2 manches d'écart en prolongations de compét). En
deathmatch et modes sans manches, seule l'ambiance de la carte tourne.

`DUMP_PRESENCE` (en haut de `client/watchers/valorant.py`) enregistre ta présence
décodée dans `client/debug/` à chaque changement d'étape.

---

## Anti-cheat (Vanguard)

LoL, TFT et VALORANT sont protégés par Vanguard. Le projet ne touche jamais aux jeux :

- **Détection des jeux** : liste des noms de processus via un instantané Windows
  (`CreateToolhelp32Snapshot`), sans ouvrir de handle sur aucun processus.
- **LoL / TFT** : Live Client Data API (`127.0.0.1:2999`), l'API officielle fournie par
  Riot pour ça.
- **VALORANT** : présence publiée au Riot Client local (la même que voient tes amis),
  en lecture seule. Aucun appel aux serveurs de Riot.
- **Fond d'écran** : capture de la fenêtre du bureau, et seulement quand aucun jeu
  n'est lancé.
- Aucune lecture de mémoire, injection, simulation de clavier/souris ni analyse
  de l'image du jeu.

Si tu ajoutes un watcher pour un jeu avec anti-cheat, garde ces règles.

---

## Dépannage

### Les LEDs ne s'allument pas

- Vérifie que le SPI est actif : `ls /dev/spidev*`
- Vérifie le câblage (Pin 19 = MOSI = GPIO 10)
- Si les LEDs clignotent bizarrement : ajoute le condensateur 1000 µF

### Le watcher LoL ne détecte aucun événement

- `python client/hub.py --list` doit afficher `lol`
- LoL doit être **en partie** (pas en lobby) pour que l'API réponde :
  ```bash
  curl -k https://127.0.0.1:2999/liveclientdata/eventdata
  ```

### Le Pi ne reçoit rien

- Vérifie que `led_server.py` tourne et que `PI_IP` dans `client/config.py` est correct
- Vérifie que le pare-feu Windows autorise Python sur le réseau local
- `ping <ip du Pi>`

### Erreur `Permission denied` sur `/dev/spidev0.0`

```bash
sudo usermod -a -G spi $USER
# puis redémarre la session
```

---

## Lancer le serveur automatiquement au démarrage du Pi

```bash
sudo nano /etc/systemd/system/leds.service
```

```ini
[Unit]
Description=LED Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/leds/led_server.py
WorkingDirectory=/home/pi/leds
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now leds
sudo journalctl -u leds -f        # logs en direct
```
