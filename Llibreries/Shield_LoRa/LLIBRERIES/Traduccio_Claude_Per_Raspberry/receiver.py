# Equivalent a LoRaReceiver.ino (sondeig amb parse_packet)
import sys
from lora import LoRa, sleep_ms, decode

FREQUENCY = 915E6

lora = LoRa()
print("LoRa Receiver")
if not lora.begin(FREQUENCY):
    print("Starting LoRa failed!")
    sys.exit()

try:
    while True:
        packet_size = lora.parse_packet()
        if packet_size:
            data = lora.read_all()
            print("Received packet '%s' with RSSI %d" % (decode(data), lora.packet_rssi()))
        sleep_ms(2)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
