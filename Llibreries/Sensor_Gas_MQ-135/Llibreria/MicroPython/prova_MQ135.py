# Prova de MQ135.py sense sensor DHT
from time import sleep
from MQ135 import MQ135

# GP26 = ADC0.
# Divisor extern: 10k des d'AOUT fins al punt ADC,
# i 15k des del punt ADC fins a GND.
# Revisa que rload sigui el valor real del teu mòdul.
mq135_sensor = MQ135(
    pin=26,
    rzero=76.63,
    rload=10.0,
    vcc=5.0,
    adc_vref=3.3,
    divider_top=10000.0,
    divider_bottom=15000.0,
)

temperature = 21.0
humidity = 25.0

while True:
    try:
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
            "MQ135 RZero: {:.2f} kOhm | "
            "Corrected RZero: {:.2f} kOhm | "
            "Resistance: {:.2f} kOhm | "
            "PPM: {:.1f} | Corrected PPM: {:.1f}".format(
                rzero, corrected_rzero, resistance, ppm, corrected_ppm
            )
        )
    except (ValueError, OSError) as exc:
        print("Error de lectura MQ135:", exc)

    sleep(0.3)
