#############################################################################
# MQ135_test_DHT11_v5.py
# modificat: 
#	27/10/26 : creació
#   03/11/26 : creo la funció mi_print() per evitar que es pengi el no tenir terminal connectat i funcionar sense USB.
#              mirar variable DEPURACIO 
#
"""
 Lectura del sensor MQ-135 i DHT11
 Raspberry Pi Pico - MicroPython

 Aqui hi ha el que depen d'aquest muntatge (pins, divisor, RLOAD, RZERO); els
 calculs del MQ-135 els fa la llibreria MQ135.py.

 El nombre de mostres i l'interval entre mostres els decideix main.py
 (configuracio rebuda de la BD); aqui nomes hi ha una lectura d'una mostra:

   llegir_brut()           -> valor ADC cru (0-65535)
   calcula_ppm(brut)       -> ppm estimats a partir d'un valor cru (o None)
   llegir_dht11_mostra()   -> (temperatura, humitat) d'una mesura, o None si falla

 Per modo test:
 Executat sol (per ex. des de Thonny) mostra una mostra cada 5 s i l'RZERO que
 surt de la lectura actual: serveix per comprovar el cablejat i per calibrar
 RZERO a l'aire net (amb el sensor ja escalfat).
"""

"""
nomès per fer el test de lectures durant un periode de temps

"""
#############################################################################

import machine
from machine import ADC, Pin
from time import sleep, localtime
from dht import DHT11
from MQ135 import MQ135

# ==========================================
# CONFIGURACIÓ GLOBAL DE DEPURACIÓ
# ==========================================
# True  -> Mostra els missatges de debug per pantalla (amb ordinador connectat)
# False -> Desactiva tots els mi_prints automàticament (per producció / sense ordinador)
DEPURACIO = False
def mi_print(*args, **kwargs):
    if DEPURACIO:
        print(*args, **kwargs)


#####################################################################################
# Definicions de paràmetres
#////////////////////////////////////////////////////////////////////////////////////
# ---------------------------------------------------------------------------
# CONFIGURACIO
# ---------------------------------------------------------------------------

PIN_MQ135 = 26
PIN_DHT = 27

INTERVAL_MINUTS = 0.25
DURADA_HORES = 24

FITXER = "registre_mq135.csv"

# Divisor: 10k en serie i 15k a GND
DIVISOR_TOP = 10000.0
DIVISOR_BOTTOM = 15000.0

VREF_ADC = 3.3

# Parametres MQ135
VCC = 5.0
RLOAD = 0.92       # kOhm
RZERO = 22.68      # kOhm, provisional

# -------------------------------------------------
# INICIALITZACIÓ
# -------------------------------------------------
# Objecte MQ135 de la llibreria 
mq135_sensor = MQ135(
    pin=PIN_MQ135,
    rzero=RZERO,
    rload=RLOAD,
    vcc=VCC,
    adc_vref=VREF_ADC,
    divider_top=DIVISOR_TOP,
    divider_bottom=DIVISOR_BOTTOM
)

adc = ADC(Pin(PIN_MQ135))

# DHT11
dht = DHT11(Pin(PIN_DHT))


#####################################################################################
# Funcions bàsiques
#////////////////////////////////////////////////////////////////////////////////////
# ---------------------------------------------------------------------------
# LECTURA MQ-135
# ---------------------------------------------------------------------------
def llegir_sensor():

    # Mitjana de 10 lectures rapides
    suma = 0

    for i in range(10):
        suma += adc.read_u16()
        sleep(0.1)

    raw = suma / 10

    v_adc = raw * VREF_ADC / 65535

    # Recuperem la tensio original d'AOUT
    v_aout = v_adc * (
        (DIVISOR_TOP + DIVISOR_BOTTOM) /
        DIVISOR_BOTTOM
    )

    # Rs en kOhm
    if v_aout <= 0 or v_aout >= VCC:
        return None

    rs = ((VCC / v_aout) - 1) * RLOAD

    return raw, v_adc, v_aout, rs

# ---------------------------------------------------------------------------
# LECTURA DHT11
# ---------------------------------------------------------------------------

def llegir_dht():

    try:
        dht.measure()

        temperatura = dht.temperature()
        humitat = dht.humidity()

        return temperatura, humitat

    except Exception as e:
        mi_print("Error llegint DHT11:", e)
        return None, None
#////////////////////////////////////////////////////////////////////////////////

def obtenir_hora():

    t = localtime()

    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2],
        t[3], t[4], t[5]
    )


#////////////////////////////////////////////////////////////////////////////////
#/// M A I N ////////////////////////////////////////////////////////////////////
#////////////////////////////////////////////////////////////////////////////////
# ---------------------------------------------------------------------------
# REGISTRE PROGRAMA DE PROVA
# -------------------------------------------------

interval = INTERVAL_MINUTS * 60
total_lectures = int(DURADA_HORES * 60 / INTERVAL_MINUTS)

mi_print("Inici registre MQ135 + DHT11")
mi_print("RLOAD:", RLOAD, "kOhm")
mi_print("RZERO:", RZERO, "kOhm")
mi_print("Interval:", INTERVAL_MINUTS, "minuts")
mi_print("Durada:", DURADA_HORES, "hores")
mi_print("Nombre de lectures:", total_lectures)


with open(FITXER, "a") as f:    # "a" = afegeix (així un reinici no esborra les lectures anteriors)

    f.write("# arrencada, causa=%d\n" % machine.reset_cause())    # 1 = alimentació, 3 = reinici
    f.write(
        "Hora,ADC,GP26_V,AOUT_V,Rs_kOhm,"
        "Temperatura_C,Humitat_percent\n"
    )
    f.flush()

    try:
        for n in range(total_lectures):

            hora = obtenir_hora()

            # Lectura MQ135
            resultat = llegir_sensor()

            # Lectura DHT11
            temperatura, humitat = llegir_dht()

            if resultat is not None:

                raw, v_adc, v_aout, rs = resultat

                temp_txt = (
                    "{:.1f}".format(temperatura)
                    if temperatura is not None else "ERROR"
                )

                hum_txt = (
                    "{:.1f}".format(humitat)
                    if humitat is not None else "ERROR"
                )

                linia = (
                    "{},{:.0f},{:.4f},{:.4f},{:.4f},{},{}"
                    .format(
                        hora, raw, v_adc, v_aout, rs,
                        temp_txt, hum_txt
                    )
                )

            else:
                linia = "{},ERROR,ERROR,ERROR,ERROR,{},{}".format(
                    hora,
                    temperatura if temperatura is not None else "ERROR",
                    humitat if humitat is not None else "ERROR"
                )

            f.write(linia + "\n")
            f.flush()

            mi_print(n + 1, "/", total_lectures, linia)

            if n < total_lectures - 1:
                sleep(interval)

        mi_print("Registre finalitzat.")

    except Exception as e:
        f.write("# EXCEPCIO %s\n" % repr(e))
        f.flush()
