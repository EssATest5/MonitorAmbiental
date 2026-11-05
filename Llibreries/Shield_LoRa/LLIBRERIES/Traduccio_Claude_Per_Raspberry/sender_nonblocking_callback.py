# Equivalent a LoRaSenderNonBlockingCallback.ino
import sys
from lora import LoRa, millis, ticks_diff, sleep_ms

FREQUENCY = 915E6
INTERVAL_MS = 1000

lora = LoRa()


def on_tx_done():
    print("TxDone")


print("LoRa Sender non-blocking Callback")
if not lora.begin(FREQUENCY):
    print("Starting LoRa failed!")
    sys.exit()

lora.on_tx_done(on_tx_done)

counter = 0
last = millis() - INTERVAL_MS
try:
    while True:
        lora.poll()               # imprescindible a la Pico (a la Pi 3 no fa res)
        if ticks_diff(millis(), last) >= INTERVAL_MS:
            last = millis()
            print("Sending packet non-blocking:", counter)
            lora.begin_packet()
            lora.print("hello ")
            lora.print(counter)
            lora.end_packet(True)  # asíncron
            counter += 1
        sleep_ms(5)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
