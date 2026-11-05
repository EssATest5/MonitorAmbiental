# Prova MQ135 + DHT11/DHT22 amb MicroPython
from machine import Pin
from time import sleep
from dht import DHT11, DHT22
from MQ135 import MQ135

PIN_MQ135 = 26
PIN_DHT = 27
TIPUS_DHT = "DHT11"  # Canviar a "DHT22" si cal 

mq135_sensor = MQ135(
    pin=PIN_MQ135,
    rzero=76.63,
    rload=10.0,
    vcc=5.0,
    adc_vref=3.3,
    divider_top=10000.0,
    divider_bottom=15000.0,
)

# Crea objecte DHT per temperatura i humitat, per defecte DHT11
dht_pin = Pin(PIN_DHT, Pin.IN)
if TIPUS_DHT == "DHT22":
    dht = DHT22(dht_pin)
else:
    dht = DHT11(dht_pin)



while True:
    try:
        dht.measure()
        temperature = dht.temperature()
        humidity = dht.humidity()

        if temperature is None or humidity is None:
            raise OSError("Lectura DHT no vàlida")

        rzero = mq135_sensor.getRZero()
        corrected_rzero = mq135_sensor.getCorrectedRZero(
            temperature, humidity
        )
        resistance = mq135_sensor.getResistance()
        ppm = mq135_sensor.getPPM()
        corrected_ppm = mq135_sensor.getCorrectedPPM(
            temperature, humidity
        )

        print(
            "T: {:.1f} C | HR: {:.1f}% | "
            "RZero: {:.2f} kOhm | RZero corregit: {:.2f} kOhm | "
            "Resistència: {:.2f} kOhm | PPM: {:.1f} | "
            "PPM corregits: {:.1f}".format(
                temperature, humidity, rzero, corrected_rzero,
                resistance, ppm, corrected_ppm
            )
        )

    except (OSError, ValueError) as exc:
        print("Error llegint DHT/MQ135:", exc)

    sleep(2)  # Un DHT11/DHT22 no s'ha de llegir cada 300 ms