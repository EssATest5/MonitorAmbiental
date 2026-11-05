# Comprova la connexió amb el mòdul SX127x i bolca els registres.
# Si la versió NO és 0x12 -> revisa cablejat/SPI (0x00 o 0xFF = sense resposta).
import sys
from lora import LoRa

lora = LoRa()
if lora.begin(915E6):
    print("OK: SX127x detectat, versió = 0x%02X" % lora.read_register(0x42))
    lora.dump_registers()
else:
    print("ERROR: versió llegida = 0x%02X (esperada 0x12)" % lora.read_register(0x42))
lora.end()
