# Equivalent a LoRaSenderNonBlocking.ino
# begin_packet() retorna 0 mentre la ràdio encara està transmetent.
import sys
from lora import LoRa, sleep_ms

FREQUENCY = 915E6

lora = LoRa()
print("LoRa Sender non-blocking")
if not lora.begin(FREQUENCY):
    print("Starting LoRa failed!")
    sys.exit()

counter = 0
try:
    while True:
        # espera fins que la ràdio estigui lliure
        while lora.begin_packet() == 0:
            print("waiting for radio ... ")
            sleep_ms(100)

        print("Sending packet non-blocking:", counter)

        lora.begin_packet()
        lora.print("RPi 3 diu: hello ")
        lora.print(counter)
        lora.end_packet(True)     # True = asíncron / no bloquejant

        counter += 1
except KeyboardInterrupt:
    pass
finally:
    lora.end()
