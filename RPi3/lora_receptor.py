#!/usr/bin/env python3
####################################################################################
# lora_receptor.py
# modificat: 
#	27/10/26 : creació
#   05/11/26 : processa() es crida sempre (abans no s'executava si el LED estava desactivat)
#
"""
Servei de la RPi3: rep les lectures de la Pico per LoRa, les desa a
la base de dades i respon a la Pico (confirmació + configuració pendent, si n'hi ha).

Necessita al mateix directori: lora.py, protocol.py, configuracio.py i base_dades.py.
Només aquest procés toca la ràdio; el web només parla amb la base de dades.

Nota: a la Pi 3 el callback en_rebre s'executa en un fil de la llibreria. Dins del callback
només llegim la trama i la posem en una cua; l'escriptura a la BD i l'enviament de la
resposta es fan des del fil principal.
"""
####################################################################################

import sys
import time
import queue
import signal

try:
    import RPi.GPIO as GPIO
except ImportError:      # per poder executar-ho també fora de la RPi (proves)
    GPIO = None

from lora import LoRa
import protocol as P
import configuracio as CFG
import base_dades as BD

####################################################################################
# Funcions bàsiques
####################################################################################
#///////////////////////////////////////////////////////////////////////////////////
def led_inicia():
    if CFG.PIN_LED is None or GPIO is None:
        return False
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(CFG.PIN_LED, GPIO.OUT, initial=GPIO.HIGH)   # encès = funcionant
    return True
#///////////////////////////////////////////////////////////////////////////////////    

#///////////////////////////////////////////////////////////////////////////////////
def led_apaga_i_allibera(actiu):
    if actiu:
        GPIO.output(CFG.PIN_LED, 0)
        GPIO.cleanup(CFG.PIN_LED)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Per cada lectura desada, el LED (normalment encès) s'apaga i s'encén 'vegades' cops.
def led_parpelleja(actiu, vegades=3):
    
    if actiu:
        for _ in range(vegades):
            GPIO.output(CFG.PIN_LED, 0)
            time.sleep(0.1)
            GPIO.output(CFG.PIN_LED, 1)
            time.sleep(0.1)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Envia a la Pico la confirmació de la lectura seq (amb la configuració si cal).
def respon(lora, estat, destinatari, seq, cfg, versio_pico):

    nova = cfg if cfg["versio"] != versio_pico else None
    text = P.codifica_resposta(seq, nova)
    time.sleep(CFG.PAUSA_ABANS_RESPOSTA_S)
    P.envia_trama(lora, destinatari, P.ADR_RPI, estat["id_missatge"], text)
    estat["id_missatge"] = (estat["id_missatge"] + 1) & 0xFF
    lora.receive()    # tornem a escoltar
    return text
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Tracta un element de la cua: (data_hora, rssi, snr, trama). Retorna True si ha 
# desat una lectura.
def processa(bd, lora, estat, element):
    
    data_hora, rssi, snr, trama = element
    marca = data_hora.strftime("%Y-%m-%d %H:%M:%S")
    if trama is None:
        print("%s trama invàlida (capçalera/longitud), descartada" % marca)
        return False
    dest, orig, seq, text = trama
    if dest != P.ADR_RPI and dest != P.ADR_TOTS:
        return False    # no és per a mi
    if orig != P.ADR_PICO:
        print("%s trama de l'adreça desconeguda 0x%02X, ignorada" % (marca, orig))
        return False
    dades = P.descodifica_dades(text)
    if dades is None:
        print("%s cos desconegut de 0x%02X: %r" % (marca, orig, text))
        return False

    BD.desa_lectura(bd, data_hora, dades, rssi, snr, seq)
    BD.marca_versio_aplicada(bd, dades["versio"])
    cfg = BD.llegeix_configuracio(bd)
    resposta = respon(lora, estat, orig, seq, cfg, dades["versio"])

    print("%s seq=%d ppm=%s brut=%s T=%s H=%s rssi=%d snr=%.2f cfg=v%d -> %s" % (
        marca, seq, dades["ppm"], dades["brut"], dades["temperatura"], dades["humitat"],
        rssi, snr, dades["versio"], resposta))
    return True
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
#/// M A I N ///////////////////////////////////////////////////////////////////////
#///////////////////////////////////////////////////////////////////////////////////
def principal():
    bd = BD.obre_bd()
    led = led_inicia()
    lora = LoRa(reset=CFG.PIN_LORA_RESET, dio0=CFG.PIN_LORA_DIO0,
                spi_bus=CFG.SPI_BUS, spi_device=CFG.SPI_DISPOSITIU)    # pins a configuracio.py
    if not lora.begin(P.FREQUENCIA):
        print("LoRa: no s'ha detectat el mòdul. Revisa el cablejat i que SPI estigui activat.")
        led_apaga_i_allibera(led)
        sys.exit(1)
    P.configura_radio(lora)

    cua = queue.Queue()
    estat = {"id_missatge": 0, "en_marxa": True}

    def en_rebre(mida_paquet):
        if mida_paquet == 0:
            return
        data_hora = BD.ara_utc()
        rssi, snr = lora.packet_rssi(), lora.packet_snr()
        cua.put((data_hora, rssi, snr, P.llegeix_trama(lora)))

    lora.on_receive(en_rebre)
    lora.receive()
    print("Receptor LoRa en marxa (%.1f MHz). BD: %s" % (P.FREQUENCIA / 1e6, CFG.RUTA_BD))

    def atura(*_):
        estat["en_marxa"] = False

    signal.signal(signal.SIGTERM, atura)
    signal.signal(signal.SIGINT, atura)

    try:
        while estat["en_marxa"]:
            try:
                element = cua.get(timeout=1)
            except queue.Empty:
                continue
            desat = processa(bd, lora, estat, element)   # sempre es processa, hi hagi LED o no
            led_parpelleja(led and desat)
    finally:
        lora.end()
        led_apaga_i_allibera(led)
        bd.close()
        print("Receptor aturat.")


if __name__ == "__main__":
    principal()