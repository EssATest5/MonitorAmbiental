# Equivalent a LoRaReceiverCallback.ino
import sys
from lora import LoRa, sleep_ms

FREQUENCY = 915E6

lora = LoRa()


def on_receive(packet_size):
    data = bytearray()
    for _ in range(packet_size):
        data.append(lora.read())
    try:
        text = bytes(data).decode()
    except Exception:
        text = repr(bytes(data))
    print("Received packet '%s' with RSSI %d" % (text, lora.packet_rssi()))


print("LoRa Receiver Callback")
if not lora.begin(FREQUENCY):
    print("Starting LoRa failed!")
    sys.exit()

lora.on_receive(on_receive)   # registra el callback
lora.receive()                # ràdio en mode recepció

try:
    while True:
        lora.poll()           # imprescindible a la Pico (a la Pi 3 no fa res)
        sleep_ms(5)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
