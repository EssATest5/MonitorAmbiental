# Equivalent a LoRaSetSyncWord.ino
# Radios amb diferent sync word no es reben entre elles (és com un identificador de xarxa). L'altre extrem ha d'usar el mateix.
import sys
import random
from lora import LoRa, millis, ticks_diff, sleep_ms, decode

FREQUENCY = 915E6

lora = LoRa()
msg_count = 0


def send_message(outgoing):
    lora.begin_packet()
    lora.print(outgoing)
    lora.end_packet()


def on_receive(packet_size):
    if packet_size == 0:
        return
    incoming = decode(lora.read_all())
    print("Message:", incoming)
    print("RSSI:", lora.packet_rssi())
    print("Snr:", lora.packet_snr())
    print()


print("LoRa Duplex - Set sync word")
if not lora.begin(FREQUENCY):
    print("LoRa init failed. Check your connections.")
    sys.exit()

lora.set_sync_word(0xF3)       # 0-0xFF, per defecte 0x12
print("LoRa init succeeded.")

interval = 2000
last_send = millis()
try:
    while True:
        if ticks_diff(millis(), last_send) > interval:
            message = "RPi diu : HeLoRa World! " + str(msg_count)
            send_message(message)
            print("Sending " + message)
            last_send = millis()
            interval = 1000 + random.randrange(2000)   # 1-3 segons
            msg_count += 1   # (a l'.ino original s'incrementava dues vegades)
        on_receive(lora.parse_packet())
        sleep_ms(2)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
