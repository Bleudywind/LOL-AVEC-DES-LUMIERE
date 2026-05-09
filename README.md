# LED LoL – Ruban WS2812B réactif aux événements League of Legends

Pilote un ruban LED WS2812B depuis un Raspberry Pi en fonction des événements
de ta partie League of Legends (kills, morts, Baron, dragon…).

---

## Architecture

```
PC (Windows)                         Raspberry Pi
┌─────────────────────┐              ┌──────────────────────────┐
│  League of Legends  │              │  led_server.py           │
│  localhost:2999     │              │  (serveur UDP)           │
│  Live Client API    │              │        │                 │
│         │           │   UDP/JSON   │        ▼                 │
│  lol_watcher.py ───────────────────────► led_controller.py   │
│  (poll 500ms)       │  Wi-Fi/ETH   │        │                 │
└─────────────────────┘              │        ▼                 │
                                     │  Ruban WS2812B (SPI)    │
                                     └──────────────────────────┘
```

---

## Fichiers du projet

| Fichier | Où | Rôle |
|---|---|---|
| `lol_watcher.py` | PC (Windows) | Poll l'API LoL et envoie les événements au Pi |
| `led_server.py` | Raspberry Pi | Reçoit les événements et déclenche les animations |
| `led_controller.py` | Raspberry Pi | Pilote le ruban via SPI (module réutilisable) |

---

## Prérequis

### Sur le PC

- Python 3.8+
- League of Legends installé
- Bibliothèque `requests` :
  ```bash
  pip install requests
  ```

### Sur le Raspberry Pi

- Python 3.8+
- SPI activé (voir section Raspberry Pi ci-dessous)
- Bibliothèque `spidev` :
  ```bash
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

## Configuration du Raspberry Pi

### 1. Activer le SPI

```bash
sudo raspi-config
# Interface Options → SPI → Enable → Reboot
```

Vérifie que le SPI est bien actif après redémarrage :

```bash
ls /dev/spidev*
# doit afficher : /dev/spidev0.0
```

### 2. Trouver l'IP du Pi

```bash
hostname -I
# exemple : 192.168.1.42
```

Note cette adresse, tu en auras besoin pour configurer `lol_watcher.py`.

### 3. Copier les fichiers sur le Pi

Depuis ton PC (en remplaçant l'IP) :

```bash
scp led_controller.py led_server.py pi@192.168.1.42:~/lol-leds/
```

Ou via un partage réseau / clé USB.

---

## Configuration des scripts

### `lol_watcher.py` (sur le PC)

Ouvre le fichier et modifie la ligne suivante :

```python
RASPBERRY_PI_IP = "192.168.1.XX"   # ← IP de ton Raspberry Pi
```

Les autres paramètres par défaut fonctionnent sans modification :

```python
RASPBERRY_PI_PORT = 5005   # doit correspondre à led_server.py
POLL_INTERVAL     = 0.5    # secondes entre chaque requête à l'API LoL
NUM_LEDS          = 59     # dans led_controller.py
```

---

## Lancement

### Ordre à respecter

1. **Démarre le Pi en premier**
2. Lance LoL et entre en partie
3. Lance le watcher sur le PC

### Sur le Raspberry Pi

```bash
cd ~/lol-leds
python led_server.py
```

Le serveur affiche :
```
=== LED Server démarré (UDP :5005) ===
En attente d'événements LoL…
```

### Sur le PC

```bash
python lol_watcher.py
```

Le watcher affiche :
```
=== LoL LED Watcher ===
Pi cible   : 192.168.1.42:5005
Poll toutes: 0.5s
En attente d'une partie… (Ctrl+C pour quitter)
```

Dès qu'un événement est détecté :
```
  → envoyé : kill  {'killer': 'Jinx', 'victim': 'Caitlyn'}
```

---

## Animations par événement

| Événement | Animation |
|---|---|
| Kill | Flash rouge × 3 |
| Double kill / Triple… | Flash orange, vitesse selon le streak |
| Ace | Vague dorée de gauche à droite |
| Dragon | Couleur selon le type (feu, eau, air, elder…) |
| Baron Nashor | Pulse violet lent × 3 |
| Héraut de la Faille | Pulse violet clair |
| Tour détruite | Flash cyan |
| Inhibiteur | Flash orange × 2 |
| Victoire | Arc-en-ciel défilant |
| Défaite | Extinction rouge progressive |
| Début de partie | Balayage blanc |

### Couleurs des dragons

| Dragon | Couleur |
|---|---|
| Fire / Infernal | Orange vif |
| Water / Ocean | Bleu |
| Air | Blanc bleuté |
| Mountain / Earth | Marron |
| Elder | Doré |
| Hextech | Violet |
| Chemtech | Vert |

---

## Dépannage

### Les LEDs ne s'allument pas

- Vérifie que le SPI est actif : `ls /dev/spidev*`
- Vérifie le câblage (Pin 19 = MOSI = GPIO 10)
- Si le Pi démarre mais les LEDs clignotent bizarrement : ajoute le condensateur 1000 µF

### `lol_watcher.py` ne détecte aucun événement

- LoL doit être **en partie** (pas en lobby) pour que l'API soit active
- Test manuel depuis ton PC :
  ```bash
  curl -k https://127.0.0.1:2999/liveclientdata/eventdata
  ```
  Doit retourner un JSON avec une liste `Events`.

### Le Pi ne reçoit rien

- Vérifie que `led_server.py` tourne bien sur le Pi
- Vérifie que l'IP dans `lol_watcher.py` est correcte
- Vérifie que le pare-feu Windows autorise Python sur le réseau local
- Test de connectivité depuis le PC :
  ```bash
  ping 192.168.1.42
  ```

### Erreur `Permission denied` sur `/dev/spidev0.0`

```bash
sudo usermod -a -G spi $USER
# puis redémarre la session
```

---

## Lancer le serveur automatiquement au démarrage du Pi

Pour que `led_server.py` démarre sans intervention :

```bash
# Crée le service systemd
sudo nano /etc/systemd/system/lol-leds.service
```

Contenu du fichier :

```ini
[Unit]
Description=LoL LED Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/lol-leds/led_server.py
WorkingDirectory=/home/pi/lol-leds
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

Active et démarre le service :

```bash
sudo systemctl enable lol-leds
sudo systemctl start lol-leds

# Vérifier le statut
sudo systemctl status lol-leds

# Voir les logs en direct
sudo journalctl -u lol-leds -f
```

---

## Personalisation

### Modifier une animation

Dans `led_server.py`, chaque animation est une fonction indépendante.
Par exemple, pour changer la couleur du kill en vert :

```python
def anim_kill():
    for _ in range(3):
        if stop_event.is_set():
            break
        leds.couleur_unie(0, 255, 0)   # ← change ici
        time.sleep(0.12)
        leds.couleur_unie(0, 0, 0)
        time.sleep(0.08)
```

### Distinguer ses propres kills de ceux des alliés

L'API expose le nom du joueur actif via :
```
https://127.0.0.1:2999/liveclientdata/activeplayername
```

Dans `lol_watcher.py`, récupère ce nom au démarrage et compare-le
avec `KillerName` / `VictimName` dans `handle_event()` pour envoyer
`my_kill` ou `my_death` plutôt que `kill`.

### Ajouter un événement

1. Dans `lol_watcher.py`, ajoute un `elif` dans `handle_event()`
2. Dans `led_server.py`, ajoute une fonction `anim_xxx()` et un cas dans `dispatch()`

Liste complète des types d'événements LoL :
https://developer.riotgames.com/docs/lol#game-client-api_live-client-data-api

---

## Structure des fichiers

```
lol-leds/
├── README.md
├── led_controller.py   # Pi — module SPI WS2812B
├── led_server.py       # Pi — serveur UDP + animations
└── lol_watcher.py      # PC — watcher API LoL
```
