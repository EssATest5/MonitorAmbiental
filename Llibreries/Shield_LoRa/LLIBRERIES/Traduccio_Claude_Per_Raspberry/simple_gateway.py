# Equivalent a LoRaSimpleGateway.ino (InvertIQ: Gateway només parla amb Node)
#   Tx: enable_invert_iq   |   Rx: disable_invert_iq
import sys
from lora import LoRa, millis, ticks_diff, sleep_ms, decode

FREQUENCY = 915E6
INTERVAL_MS = 5000

lora = LoRa()


def lora_rx_mode():
    lora.disable_invert_iq()
    lora.receive()                  # mode recepció contínua


def lora_tx_mode():
    lora.idle()
    lora.enable_invert_iq()


def send_message(message):
    lora_tx_mode()
    lora.begin_packet()
    lora.print(message)
    lora.end_packet(True)           # asíncron: on_tx_done avisarà quan acabi


def on_receive(packet_size):
    print("Gateway Receive:", decode(lora.read_all()))


def on_tx_done():
    print("TxDone")
    lora_rx_mode()


print("LoRa Simple Gateway")
if not lora.begin(FREQUENCY):
    print("LoRa init failed. Check your connections.")
    sys.exit()

lora.on_receive(on_receive)
lora.on_tx_done(on_tx_done)
lora_rx_mode()

last = millis() - INTERVAL_MS
try:
    while True:
        lora.poll()                 # imprescindible a la Pico (a la Pi 3 no fa res)
        if ticks_diff(millis(), last) >= INTERVAL_MS:
            last = millis()
            send_message("Esquerra: HeLoRa World! I'm a Gateway! " + str(millis()))
            print("Send Message!")
        sleep_ms(5)
except KeyboardInterrupt:
    pass
finally:
    lora.end()
