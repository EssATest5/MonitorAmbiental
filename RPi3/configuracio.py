#############################################################################
# configuracio.py
# modificat: 
#	27/10/26 : creació
#
# - Configuració pròpia de la RPi3 (la de ràdio i protocol és a protocol.py)
#############################################################################
import os

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_BD = os.path.join(DIR_BASE, "dades", "sensors.db")

# Connexió del shield LoRa (numeració BCM = número de GPIO, no el pin físic).
# Els pins SCK (GPIO11), MOSI (GPIO10) i MISO (GPIO9) de l'SPI0 són fixos del maquinari.
PIN_LORA_RESET = 25          # GPIO connectat a RESET del shield (D9)
PIN_LORA_DIO0 = 24           # GPIO connectat a DIO0 del shield (D2)
SPI_BUS = 0                  # 0 = SPI0
SPI_DISPOSITIU = 0           # 0 = CE0 (GPIO8, NSS/D10 del shield), 1 = CE1 (GPIO7)

PIN_LED = 26                 # LED de "funcionant" (BCM). None per desactivar.
PAUSA_ABANS_RESPOSTA_S = 0.15   # deixa que la Pico torni a escoltar abans de respondre-li

HOST_WEB = "0.0.0.0"         # accessible des de la xarxa local
PORT_WEB = 5002              # http://<ip de la RPi3>:5002
