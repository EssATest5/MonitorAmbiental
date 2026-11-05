# Equivalent a LoRaDuplex.ino (adreçament d'un byte, 0xFF = broadcast)
import sys
import random
from lora import LoRa, millis, ticks_diff, sleep_ms, decode

FREQUENCY = 915E6
LOCAL_ADDRESS = 0xBB   # adreça d'aquest dispositiu (a l'altre, canvia-la)
DESTINATION = 0xFF     # destinatari

lora = LoRa()
msg_count = 0


def send_message(outgoing):
    global msg_count
    payload = outgoing.encode()
    lora.begin_packet()
    lora.write(DESTINATION)
    lora.write(LOCAL_ADDRESS)
    lora.write(msg_count)
    lora.write(len(payload))
    lora.write(payload)
    lora.end_packet()
    msg_count = (msg_count + 1) & 0xFF


def on_receive(packet_size):
    if packet_size == 0:
        return
    recipient = lora.read()
    sender = lora.read()
    incoming_id = lora.read()
    incoming_length = lora.read()
    incoming = lora.read_all()

    if incoming_length != len(incoming):
        print("error: message length does not match length")
        return
    if recipient != LOCAL_ADDRESS and recipient != 0xFF:
        print("This message is not for me.")
        return

    print("Received from: 0x%X" % sender)
    print("Sent to: 0x%X" % recipient)
    print("Message ID:", incoming_id)
    print("Message length:", incoming_length)
    print("Message:", decode(incoming))
    print("RSSI:", lora.packet_rssi())
    print("Snr:", lora.packet_snr())
    print()


print("LoRa Duplex")
if not lora.begin(FREQUENCY):
    print("LoRa init failed. Check your connections.")
    sys.exit()
# Per igualar paràmetres amb l'altre extrem (valors per defecte: SF7, BW125k, CR4/5, sync 0x12):
# lora.set_spreading_factor(9); lora.set_signal_bandwidth(125E3)
# lora.set_coding_rate4(5);     lora.set_sync_word(0x12)
print("LoRa init succeeded.")

interval = 2000
last_send = millis()
try:
    while True:
        if ticks_diff(millis(), last_send) > interval:
            message = "RPi 3 Diu: Bon Dia!"
            send_message(message)
            print("Sending " + message)
            last_send = millis()
            interval = random.randint(1000, 3000)
        on_receive(lora.parse_packet())
        sleep_ms(2)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
