# Equivalent a LoRaDuplexCallback.ino (recepció per callback, adreçament d'un byte)
# Nota: mentre s'envia, la ràdio no escolta; després d'enviar tornem a receive().
import sys
import random
from lora import LoRa, millis, ticks_diff, sleep_ms, decode

#////////////////////////////////////////////////////////////////////////////////////////////////////
import RPi.GPIO as GPIO
from time import sleep

# Definim el pin utilitzant la numeració GPIO (BCM)
LED_D1  = 26 # a la pico és el 25

# Configuració dels pins
GPIO.setmode(GPIO.BCM)       # Fes servir  la numeració de Broadcom (GPIO)
GPIO.setup( LED_D1,  GPIO.OUT) # Configura el pins com a sortida . Des de una llista de pins
# Configuració dels pins
GPIO.setmode(GPIO.BCM)       # Fes servir  la numeració de Broadcom (GPIO)
GPIO.setup( LED_D1,  GPIO.OUT) # Configura el pins com a sortida . Des de una llista de pins
#////////////////////////////////////////////////////////////////////////////////////////////////////


FREQUENCY = 915E6
LOCAL_ADDRESS = 0xBB   # adreça d'aquest dispositiu (a l'altre, canvia-la)
DESTINATION = 0xFF     # destinatari (0xFF = broadcast)

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
        print("error: la longitud del missatge no coincideix amb la longitud")
        return
    if recipient != LOCAL_ADDRESS and recipient != 0xFF:
        print("Aquest missatge no és per a mi.")
        return

    print("Rebut de: 0x%X" % sender)
    print("Enviat a: 0x%X" % recipient)
    print("ID del Missatge:", incoming_id)
    print("Longitud del Missatge:", incoming_length)
    print("Missatge:", decode(incoming))
    print("RSSI:", lora.packet_rssi())
    print("Snr:", lora.packet_snr())
    print()


print("LoRa Duplex amb callback")
if not lora.begin(FREQUENCY):
    print("Ha fallat la inicialització de LoRa. Comproveu les connexions.")
    sys.exit()

lora.on_receive(on_receive)
lora.receive()
print("Inicialització de LoRa amb exit.")

interval = 2000
last_send = millis()

GPIO.output(LED_D1, 1) # Funcionant

try:
    while True:
        
        lora.poll()                  # imprescindible a la Pico (a la Pi 3 no fa res)
        if ticks_diff(millis(), last_send) > interval:
            message = "RPi 3B+ diu : Is there anybody out there???"
            #message = "PICO diu: Hey you, would you help me to carry the stone? Open your heart, I'm coming home"
            send_message(message)
            print("Enviant " + message)
            last_send = millis()
            interval = 1000 + random.randrange(2000)   # 1-3 segons
            lora.receive()           # tornem al mode recepció

        sleep_ms(5)

except KeyboardInterrupt:
    print("\nAturant el programa...")
finally:
    GPIO.output(LED_D1, 0) # Apaga
    lora.end()
    GPIO.cleanup() # Neteja la configuració dels pins al sortir
    print("Pins i LoRa alliberats correctament.")

