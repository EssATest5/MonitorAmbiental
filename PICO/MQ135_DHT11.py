#############################################################################
# MQ135_DHT11.py
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
#############################################################################

from machine import Pin
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
PIN_DHT11 = 27

# MQ-135
VCC = 5.0
VREF_ADC = 3.3

# Divisor de tensio:
# A0 MQ135 -> 10k -> GP26 -> 15k -> GND
DIVISOR_SUPERIOR = 10000.0
DIVISOR_INFERIOR = 15000.0

RLOAD = 0.92       # kOhm
RZERO = 22.68      # kOhm (provisional)


# ---------------------------------------------------------------------------
# INICIALITZACIO
# ---------------------------------------------------------------------------

# Objecte MQ135 de la llibreria 
sensor_mq135 = MQ135(
    pin=PIN_MQ135,
    rzero=RZERO,
    rload=RLOAD,
    vcc=VCC,
    adc_vref=VREF_ADC,
    divider_top=DIVISOR_SUPERIOR,
    divider_bottom=DIVISOR_INFERIOR,
)

# DHT11
dht11 = DHT11(Pin(PIN_DHT11))


#####################################################################################
# Funcions bàsiques
#////////////////////////////////////////////////////////////////////////////////////
# ---------------------------------------------------------------------------
# LECTURA MQ-135
# ---------------------------------------------------------------------------
def llegir_brut():

    # Lectura ADC de 16 bits
    return sensor_mq135.llegir_brut()


def calcula_ppm(brut):

    # La llibreria avisa amb ValueError si la tensio es fora de rang
    # (0 V o >= Vcc): en aquest cas no hi ha ppm.
    try:
        return round(sensor_mq135.getPPM(brut), 1)

    except ValueError:
        return None


# ---------------------------------------------------------------------------
# LECTURA DHT11
# ---------------------------------------------------------------------------

def llegir_dht11_mostra():

    # Una sola mesura. Retorna (temperatura, humitat) o None si falla.
    try:
        dht11.measure()
        return dht11.temperature(), dht11.humidity()

    except Exception as e:
        mi_print("Error DHT11:", e)
        return None
#////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////
#/// M A I N ////////////////////////////////////////////////////////////////////
#////////////////////////////////////////////////////////////////////////////////
# ---------------------------------------------------------------------------
# PROGRAMA DE PROVA
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    from time import sleep

    while True:

        brut = llegir_brut()
        mesura = llegir_dht11_mostra()

        mi_print("--------------------------------")
        mi_print("MQ-135   brut:", brut, "  PPM:", calcula_ppm(brut))

        # RZERO que correspondria a aire net (426,89 ppm) amb la lectura actual
        try:
            mi_print("         RZERO estimat:", round(sensor_mq135.getRZero(brut), 2), "kOhm")
            if mesura is not None:
                mi_print("         RZERO corregit per temperatura i humitat:",
                      round(sensor_mq135.getCorrectedRZero(mesura[0], mesura[1], brut), 2), "kOhm")
        except ValueError as e:
            mi_print("         RZERO no calculable:", e)

        if mesura is not None:
            mi_print("DHT11    temperatura:", mesura[0], "  humitat:", mesura[1])

        sleep(5)
