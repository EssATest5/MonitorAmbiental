#############################################################################
# main.py
# modificat: 
#   27/10/26 : creació
#   03/11/26 : creo la funció mi_print() per evitar que es pengi el no tenir terminal connectat i funcionar sense USB.
#              mirar variable DEPURACIO 
#   03/11/26 : espera d'arrencada, reintents de LoRa i reinici automàtic en lloc de sys.exit()
#              (sense registre.txt ni watchdog, per simplicitat)
#   05/11/26 : mostreja(): brut = màxim de les mostres (descarta les caigudes del sensor, no la mitjana)
#              alies de import: P -> PROT, S -> SENSOR; comentaris d'aplica_config(), espera() i mostreja() a l'estil nou
#
"""
 Per la Pico, en MicroPython  amb sensors: MQ-135 + DHT11 -> LoRa.

 Com que és main.py arrenca sol, lora.py (llibreria del DRAGINO LoRa Shield v1.4), protocol.py,
MQ135_DHT11.py (lectura dels sensors; allà hi ha els pins, RZERO i la resta de calibratge)
i MQ135.py (llibreria del sensor de gas).

Cada cicle de PERIODE segons:
  1. pren MOSTRES lectures separades INTERVAL segons i en fa la mitjana,
  2. envia la lectura a la RPi3 (missatge D),
  3. escolta la resposta (missatge R): confirmació i, si cal, nova configuració.
La configuració (període, mostres, interval) es canvia des del web de la RPi3 i es desa a
configuracio.csv (una sola línia: periode;mostres;interval;versio) perquè sobrevisqui a un reinici.

LED integrat a la PICO (GP25): encès = funcionant (si no s'encén, LoRa no ha arrencat); parpelleig curt a cada
enviament. (La seva funció es redefinirà més endavant.)

Pins LoRa: definits com a PIN_LORA_* (a sota); per defecte SPI0: SCK=GP18, MOSI=GP19, MISO=GP16,
CS=GP17, RESET=GP20, DIO0=GP21. Si se canvien SCK, MOSI i MISO siguin d'un mateix bus SPI.
"""
#############################################################################


import machine
from machine import Pin
from lora import LoRa, millis, ticks_diff, sleep_ms
import protocol as PROT
import MQ135_DHT11 as SENSOR    # lectura dels sensors i càlcul del PPM

PIN_LED = 25

# Connexió del shield LoRa (numeració GP). SCK, MOSI i MISO han de ser pins d'un mateix bus SPI de la
# Pico (SPI0: SCK GP2/6/18, MOSI GP3/7/19, MISO GP0/4/16; SPI1: SCK GP10/14, MOSI GP11/15, MISO GP8/12).
PIN_LORA_SCK = 18        # D13 del shield
PIN_LORA_MOSI = 19       # D11
PIN_LORA_MISO = 16       # D12
PIN_LORA_CS = 17         # D10 (NSS): a la Pico el mou el programa, pot ser qualsevol GP
PIN_LORA_RESET = 20      # D9
PIN_LORA_DIO0 = 21       # D2
SPI_ID = 0               # 0 = SPI0, 1 = SPI1
FITXER_CONFIG = "configuracio.csv"    # una línia: periode;mostres;interval;versio
CONFIG_DEFECTE = {"periode": 60, "mostres": 5, "interval": 2, "versio": 0}

led = Pin(PIN_LED, Pin.OUT)
lora = LoRa(reset=PIN_LORA_RESET, dio0=PIN_LORA_DIO0,
            spi_id=SPI_ID, sck=PIN_LORA_SCK, mosi=PIN_LORA_MOSI, miso=PIN_LORA_MISO, cs=PIN_LORA_CS)

config = dict(CONFIG_DEFECTE)
estat = {"seq": 0, "ultim_ack": -1}

ESPERA_ARRENCADA_MS = 3000    # deixa estabilitzar l'alimentació i el mòdul LoRa
INTENTS_LORA = 5              # intents de detectar el mòdul LoRa abans de donar-lo per perdut

# ==========================================
# CONFIGURACIÓ GLOBAL DE DEPURACIÓ
# ==========================================
# True  -> Mostra els missatges de debug per pantalla (amb ordinador connectat)
# False -> Desactiva tots els prints automàticament (per producció / sense ordinador)
DEPURACIO = False
def mi_print(*args, **kwargs):
    if DEPURACIO:
        print(*args, **kwargs)

#####################################################################################
# Funcions bàsiques
#####################################################################################
#////////////////////////////////////////////////////////////////////////////////////
# errors
def error_fatal(codi):
    """Avisa amb `codi` pampallugues, repetits uns segons, i reinicia la Pico."""
    for _ in range(4):
        for _ in range(codi):
            led.value(1)
            sleep_ms(200)
            led.value(0)
            sleep_ms(200)
        sleep_ms(1200)
    machine.reset()
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# configuració
def carrega_config():
    """Llegeix configuracio.csv. Si no existeix o és incorrecte, torna a la configuració per defecte
    (versió 0): la RPi3 ho detecta i li reenvia la configuració vigent."""
    try:
        with open(FITXER_CONFIG) as f:
            camps = f.readline().strip().split(";")
        periode, mostres, interval = PROT.valida_parametres(camps[0], camps[1], camps[2])
        return {"periode": periode, "mostres": mostres, "interval": interval, "versio": int(camps[3])}
    except Exception:
        return dict(CONFIG_DEFECTE)
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# Aplica una configuració rebuda de la RPi3 (la RPi3 mana). Ignora la que no sigui vàlida.
def aplica_config(nova):

    try:
        periode, mostres, interval = PROT.valida_parametres(
            nova["periode"], nova["mostres"], nova["interval"])
    except ValueError as e:
        mi_print("Configuració rebuda ignorada:", e)
        return
    config["periode"], config["mostres"], config["interval"] = periode, mostres, interval
    config["versio"] = int(nova["versio"])
    with open(FITXER_CONFIG, "w") as f:
        f.write("%d;%d;%d;%d\n" % (periode, mostres, interval, config["versio"]))
    mi_print("Nova configuració v%d: període=%d s, mostres=%d, interval=%d s" % (
        config["versio"], periode, mostres, interval))
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# recepció
def en_rebre(mida_paquet):
    if mida_paquet == 0:
        return
    trama = PROT.llegeix_trama(lora)
    if trama is None:
        return
    dest, orig, _id, text = trama
    if (dest != PROT.ADR_PICO and dest != PROT.ADR_TOTS) or orig != PROT.ADR_RPI:
        return
    resposta = PROT.descodifica_resposta(text)
    if resposta is None:
        return
    estat["ultim_ack"] = resposta["seq"]
    if resposta["config"] is not None:
        aplica_config(resposta["config"])
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# Espera ms mil·lisegons sense deixar de atendre la ràdio.
def espera(ms):

    inici = millis()
    while ticks_diff(millis(), inici) < ms:
        lora.poll()
        sleep_ms(5)
#////////////////////////////////////////////////////////////////////////////////////        

#////////////////////////////////////////////////////////////////////////////////////
# sensors
def mitjana(valors):
    return None if not valors else sum(valors) / len(valors)
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# Pren config['mostres'] mostres separades config['interval'] s i retorna (ppm, brut, temperatura, humitat).
# Temperatura i humitat: mitjana de les mostres. brut: el valor MÉS ALT de l'ADC, no la mitjana: el
# sensor té caigudes aleatòries que només fan baixar la lectura (apareixen a un 36 % de les mostres) i
# el màxim les descarta. Amb una sola mostra no hi ha protecció: convé mantenir mostres >= 5.
def mostreja():

    n, interval = config["mostres"], config["interval"]
    brutes, temperatures, humitats = [], [], []
    for i in range(n):
        if i:
            espera(interval * 1000)
        brutes.append(SENSOR.llegir_brut())
        mesura = SENSOR.llegir_dht11_mostra()    # None si el DHT11 falla en aquesta mostra
        if mesura is not None:
            temperatures.append(mesura[0])
            humitats.append(mesura[1])
    brut = max(brutes)
    return SENSOR.calcula_ppm(brut), brut, mitjana(temperatures), mitjana(humitats)
#////////////////////////////////////////////////////////////////////////////////////    

#////////////////////////////////////////////////////////////////////////////////////
def led_pampallugues(quantes):
    for i in range(quantes):
        led.value(0)
        sleep_ms(150)
        led.value(1)
        sleep_ms(150)
#////////////////////////////////////////////////////////////////////////////////////        

#////////////////////////////////////////////////////////////////////////////////////        
# cicle
def cicle():
    ppm, brut, temperatura, humitat = mostreja()
    text = PROT.codifica_dades(ppm, brut, temperatura, humitat, config["versio"])
    anterior_ok = estat["ultim_ack"] == (estat["seq"] - 1) & 0xFF
    ok = PROT.envia_trama(lora, PROT.ADR_RPI, PROT.ADR_PICO, estat["seq"], text)
    mi_print("TX #%d %s (%s) | resposta de l'anterior: %s" % (
        estat["seq"], text, "ok" if ok else "ERROR", "sí" if anterior_ok else "no"))
    estat["seq"] = (estat["seq"] + 1) & 0xFF
    lora.receive()    # escoltem la resposta de la RPi3
    led_pampallugues(3)
#////////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
#/// M A I N ///////////////////////////////////////////////////////////////////////
#///////////////////////////////////////////////////////////////////////////////////
def principal():
    sleep_ms(ESPERA_ARRENCADA_MS)
    for intent in range(INTENTS_LORA):
        if lora.begin(PROT.FREQUENCIA):
            break
        mi_print("LoRa: mòdul no detectat (intent %d). Revisa el cablejat." % (intent + 1))
        sleep_ms(1000)
    else:
        error_fatal(2)    # 2 pampallugues repetits i reinici
    PROT.configura_radio(lora)
    lora.on_receive(en_rebre)
    lora.receive()
    config.update(carrega_config())
    mi_print("Node Pico en marxa. Config v%d: període=%d s, mostres=%d, interval=%d s" % (
        config["versio"], config["periode"], config["mostres"], config["interval"]))
    mi_print("Temps en l'aire d'una lectura: %d ms" % PROT.temps_aire_ms(
        len(PROT.codifica_dades(9999.9, 65535, 99.0, 99.0, 99)) + 4))
    led.value(1)    # funcionant

    inici_cicle = millis() - config["periode"] * 1000    # el primer cicle comença de seguida
    while True:
        lora.poll()
        if ticks_diff(millis(), inici_cicle) >= config["periode"] * 1000:
            inici_cicle = millis()
            cicle()
        sleep_ms(5)

#////////////////////////////////////////////////////////////////////////////////////        
# Executa principal(). Si falla alguna cosa, avisa amb pampallugues i reinicia la Pico
#    (amb DEPURACIO = True l'error es mostra a la consola i no es reinicia).
def arrenca():

    try:
        principal()
    except Exception:
        if DEPURACIO:
            raise
        error_fatal(3)    # 3 pampallugues repetits i reinici


if __name__ == "__main__":
    arrenca()