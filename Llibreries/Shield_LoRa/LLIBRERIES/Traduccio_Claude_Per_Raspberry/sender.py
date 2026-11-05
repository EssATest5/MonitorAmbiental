# Equivalent a LoRaSender.ino
import sys
from lora import LoRa, sleep_ms

FREQUENCY = 915E6   # Ha de ser igual que als Arduinos (868E6 si el mòdul és de 868 MHz)

lora = LoRa()
print("LoRa Sender")
if not lora.begin(FREQUENCY):
    print("Starting LoRa failed!")
    sys.exit()

counter = 0
try:
    while True:
        print("RPi 3 Sending packet:", counter)
        lora.begin_packet()
        lora.print("RPi 3 diu, hello ")
        lora.print(counter)
        lora.end_packet()
        counter += 1
        sleep_ms(1000)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
