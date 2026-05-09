"""
Contrôleur LED WS2812B via SPI (spidev).
Usage depuis un autre fichier :
    from led_controller import LEDController
    leds = LEDController(num_leds=59)
    leds.couleur_unie(255, 0, 0)   # Rouge
    leds.set_pixel(0, 0, 255, 0)   # LED 0 en vert
    leds.show()
    leds.close()
"""

import spidev
import time


# Table de correspondance : 2 bits WS2812B → 1 octet SPI
_LOOKUP = {
    (0, 0): 0b10001000,
    (0, 1): 0b10001110,
    (1, 0): 0b11101000,
    (1, 1): 0b11101110,
}


def _encode_byte(byte):
    result = []
    for i in range(3, -1, -1):  # 4 paires de bits
        bit_high = (byte >> (i * 2 + 1)) & 1
        bit_low  = (byte >> (i * 2)) & 1
        result.append(_LOOKUP[(bit_high, bit_low)])
    return result


class LEDController:
    """
    Contrôleur pour ruban LED WS2812B via SPI.

    Paramètres
    ----------
    num_leds   : nombre de LEDs du ruban (défaut : 59)
    bus        : bus SPI (défaut : 0)
    device     : device SPI (défaut : 0)
    speed_hz   : fréquence SPI en Hz (défaut : 2 400 000)
    """

    def __init__(self, num_leds=59, bus=0, device=0, speed_hz=2_400_000):
        self.num_leds = num_leds
        self._pixels = [(0, 0, 0)] * num_leds

        self._spi = spidev.SpiDev()
        self._spi.open(bus, device)
        self._spi.max_speed_hz = speed_hz
        self._spi.mode = 0

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_pixel(self, index, r, g, b):
        """Définit la couleur d'une LED individuelle (sans l'envoyer)."""
        if not (0 <= index < self.num_leds):
            raise IndexError(f"Index {index} hors plage (0–{self.num_leds - 1})")
        self._pixels[index] = (r, g, b)

    def set_all(self, r, g, b):
        """Définit la même couleur pour toutes les LEDs (sans envoyer)."""
        self._pixels = [(r, g, b)] * self.num_leds

    def show(self):
        """Envoie le buffer courant vers le ruban."""
        self._send_pixels(self._pixels)

    def couleur_unie(self, r, g, b):
        """Raccourci : applique une couleur unique et l'envoie immédiatement."""
        self.set_all(r, g, b)
        self.show()

    def eteindre(self):
        """Éteint toutes les LEDs."""
        self.couleur_unie(0, 0, 0)

    def close(self):
        """Éteint les LEDs et ferme proprement la connexion SPI."""
        for _ in range(3):      # quelques trames pour s'assurer de l'extinction
            self.eteindre()
            time.sleep(0.1)
        self._spi.close()

    # ------------------------------------------------------------------
    # Context manager  (with LEDController() as leds: ...)
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _send_pixels(self, pixels):
        data = []
        for r, g, b in pixels:
            data += _encode_byte(g)   # ordre GRB imposé par WS2812B
            data += _encode_byte(r)
            data += _encode_byte(b)
        data += [0] * 50              # trame de reset
        self._spi.xfer2(data)


# ------------------------------------------------------------------
# Script autonome (comportement original)
# ------------------------------------------------------------------

if __name__ == "__main__":
    with LEDController(num_leds=59) as leds:
        try:
            print("Démarrage dans 10 secondes...")
            time.sleep(10)

            print("Rouge...")
            leds.couleur_unie(255, 0, 0)
            time.sleep(5)

            print("Vert...")
            leds.couleur_unie(0, 255, 0)
            time.sleep(5)

            print("Bleu...")
            leds.couleur_unie(0, 0, 255)
            time.sleep(5)

            print("Blanc...")
            leds.couleur_unie(255, 255, 255)
            time.sleep(5)

        except KeyboardInterrupt:
            print("Arrêt...")

    print("Terminé.")
