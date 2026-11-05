
from machine import ADC, Pin
from time import sleep, ticks_ms, ticks_diff
import math

from MQ135 import MQ135


# ---------- CONFIGURACIO ----------
PIN_ANALOGIC = 26       # GP26 = ADC0
PIN_DIGITAL = 22        # GP22 = DOUT

VREF = 3.3
FACTOR_DIVISOR = 25 / 15   # 10k senyal, 15k GND

N_MOSTRES = 50
PAUSA_MOSTRA = 0.02        # 20 ms
PAUSA_CICLE = 2            # 2 segons

ALPHA = 0.15               # Filtre exponencial

sensor = ADC(PIN_ANALOGIC)
digital = Pin(PIN_DIGITAL, Pin.IN)

filtre = None
lectura_anterior = None
inici = ticks_ms()


mq135 = MQ135(
    pin=PIN_ANALOGIC,
    rzero=76.63,
    rload=10.0,
    vcc=5.0,
    adc_vref=VREF,
    divider_top=10000.0,
    divider_bottom=15000.0
)



print("Monitor MQ-135 - Raspberry Pi Pico")
print("ADC en GP26; DOUT en GP22")
print("Escalfament i estabilitzacio necessaris")
print("----------------------------------------")

while True:
    valors = []
    suma = 0

    # Recollida de mostres
    for i in range(N_MOSTRES):
        valor = sensor.read_u16()
        valors.append(valor)
        suma += valor
        sleep(PAUSA_MOSTRA)

    mitjana = suma / N_MOSTRES
    minim = min(valors)
    maxim = max(valors)

    # Desviacio estandard de les mostres
    variancia = sum((x - mitjana) ** 2
                    for x in valors) / N_MOSTRES
    desviacio = math.sqrt(variancia)

    # Tensio al pin ADC
    v_adc = mitjana * VREF / 65535

    # Tensio estimada abans del divisor
    v_aout = v_adc * FACTOR_DIVISOR

    # Filtre exponencial
    if filtre is None:
        filtre = v_aout
    else:
        filtre = ALPHA * v_aout + (1 - ALPHA) * filtre

    # Tendencia simple
    if lectura_anterior is None:
        tendencia = "Inicialitzant"
    elif filtre > lectura_anterior + 0.01:
        tendencia = "Pujant"
    elif filtre < lectura_anterior - 0.01:
        tendencia = "Baixant"
    else:
        tendencia = "Estable"

    lectura_anterior = filtre

    # Estat digital del comparador
    estat_digital = not digital.value() # el senyal digital està normalment a alt i s'activa per logica negativa

    temps = ticks_diff(ticks_ms(), inici) / 1000

    print()
    print("Temps:", round(temps, 1), "s")
    print("ADC mitja:", round(mitjana))
    print("ADC minim/maxim:", minim, "/", maxim)
    print("Desviacio ADC:", round(desviacio, 1))
    print("Tensio ADC:", round(v_adc, 4), "V")
    print("Tensio AOUT estimada:", round(v_aout, 4), "V")
    print("AOUT filtrada:", round(filtre, 4), "V")
    print("Tendencia:", tendencia)
    print("DOUT GP22:", estat_digital)
    ppm = mq135.getPPM()
    print("PPM estimats:", round(ppm, 1))
    print("----------------------------------------")

    sleep(PAUSA_CICLE)
