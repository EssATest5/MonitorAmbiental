#############################################################################
# protocol.py
# modificat: 
#   27/10/26 : creació
#   03/11/26 : creo la funció mi_print() per evitar que es pengi el no tenir terminal connectat i funcionar sense USB.
#              mirar variable DEPURACIO 
#   03/11/26 : espera d'arrencada, reintents de LoRa i reinici automàtic en lloc de sys.exit()
#              (sense registre.txt ni watchdog, per simplicitat)
#
"""
Configuració de ràdio i protocol de comunicació Pico <-> RPi3.

FITXER COMPARTIT: la RPi3 i la Pico han de tenir exactament aquesta mateixa còpia
(al costat de la llibreria lora.py). Així la ràdio i el format de les trames no es poden desquadrar.
Compatible amb Python 3 i MicroPython.

TRAMA (capçalera de 4 bytes, igual que als exemples duplex de la Llibreria lora convertida ):
    [destinatari][remitent][id missatge 0-255][longitud del cos]  +  cos (text UTF-8)

COS DELS MISSATGES (camps separats per ';'):
    D;<ppm>;<brut>;<temp>;<hum>;<versio>        Pico -> RPi3   lectura
        ppm, brut, temp, hum poden anar buits (= sense lectura).
        <versio> = versió de configuració que la Pico té aplicada.
    R;<seq>                                     RPi3 -> Pico   resposta: "he rebut la lectura <seq>"
    R;<seq>;<periode>;<mostres>;<interval>;<versio>
                                                RPi3 -> Pico   la mateixa resposta + nova configuració

Mecanisme de configuració: la Pico informa de la seva <versio> a cada lectura. Si la
RPi3 en té una de diferent ( a la taula configuració de la BD), afegeix la configuració a la resposta.
Si la resposta es perd, la lectura següent torna a mostrar la versió antiga i es reenvia: s'autorepara.
"""
#############################################################################

#####################################################################################
# Definición de paràmetres
#####################################################################################

# ---- Configuració de ràdio de referència (idèntica als dos extrems)
FREQUENCIA = 868E6        # 868 MHz
FACTOR_EXPANSIO = 9       # spreading factor SF12 -- Canviat a SF9, el 12 consumex massa
AMPLADA_BANDA = 125E3     # 125 kHz
TAXA_CODI = 5             # coding rate 4/5
PARAULA_SINCRO = 0x12     # sync word (per defecte). Per aïllar-te d'altres xarxes: p. ex. 0xF3, als dos extrems

# ---- Adreces LoRa (les que ja fas servir)
ADR_RPI = 0xBB
ADR_PICO = 0x55
ADR_TOTS = 0xFF           # difusió (broadcast)

# ---- Límits dels paràmetres de configuració de la Pico
MARGE_S = 5               # temps reservat per enviar i rebre la resposta dins de cada període
LIMITS = {
    "periode": (10, 86400),   # segons entre enviaments
    "mostres": (1, 60),       # lectures que es promitgen
    "interval": (2, 3600),    # segons entre mostres (el DHT11 necessita >= 1 s; 2 per seguretat)
}


#####################################################################################
# Funcions desuport
#####################################################################################

#////////////////////////////////////////////////////////////////////////////////////
# Aplica la configuració comuna. Crida-la just després de lora.begin().
def configura_radio(lora):
    lora.set_spreading_factor(FACTOR_EXPANSIO)   # la llibreria ajusta sola el bit LDO a SF11/12
    lora.set_signal_bandwidth(AMPLADA_BANDA)
    lora.set_coding_rate4(TAXA_CODI)
    lora.set_sync_word(PARAULA_SINCRO)
    lora.enable_crc()    # descarta paquets corromputs (per defecte la llibreria no el té actiu)
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
#    Temps en l'aire (ms) d'un paquet de n_bytes (capçalera de 4 bytes inclosa) amb la
#    configuració d'aquest fitxer: preàmbul 8, capçalera explícita, CRC activat.
#    Fórmula del datasheet del SX127x.
def temps_aire_ms(n_bytes):

    sf = FACTOR_EXPANSIO
    t_simbol = 1000.0 * (1 << sf) / AMPLADA_BANDA
    de = 1 if t_simbol > 16 else 0                    # optimització de baixa velocitat
    num = 8 * n_bytes - 4 * sf + 28 + 16              # +16 = CRC
    den = 4 * (sf - 2 * de)
    n_simbols = 8 + max(-(-int(num) // den) * TAXA_CODI, 0)
    return (8 + 4.25 + n_simbols) * t_simbol
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# validació
# Comprova la configuració de la Pico. Retorna (periode, mostres, interval) com a enters
# o llança ValueError amb un missatge.
def valida_parametres(periode, mostres, interval):
    try:
        periode, mostres, interval = int(periode), int(mostres), int(interval)
    except (TypeError, ValueError):
        raise ValueError("Els paràmetres han de ser nombres enters")
    for nom, valor in (("periode", periode), ("mostres", mostres), ("interval", interval)):
        mn, mx = LIMITS[nom]
        if not (mn <= valor <= mx):
            raise ValueError("%s ha d'estar entre %d i %d (és %d)" % (nom, mn, mx, valor))
    durada = (mostres - 1) * interval
    if durada + MARGE_S > periode:
        raise ValueError(
            "El mostreig (%d s) més %d s de marge no cap dins del període (%d s)"
            % (durada, MARGE_S, periode))
    return periode, mostres, interval
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# trama
# Envia una trama. Retorna el resultat d'end_packet (1 = correcte).
def envia_trama(lora, dest, orig, id_missatge, text):
    
    cos = text.encode()
    lora.begin_packet()
    lora.write(dest)
    lora.write(orig)
    lora.write(id_missatge & 0xFF)
    lora.write(len(cos))
    lora.write(cos)
    return lora.end_packet()
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# Llegeix el paquet ja rebut (cridar des d'en_rebre).
# Retorna (dest, orig, id_missatge, text) o None si la trama és invàlida.
# text és None si el cos no és UTF-8 vàlid.
def llegeix_trama(lora):
    dest = lora.read()
    orig = lora.read()
    id_missatge = lora.read()
    longitud = lora.read()
    cos = lora.read_all()
    if dest < 0 or orig < 0 or id_missatge < 0 or longitud < 0 or longitud != len(cos):
        return None
    try:
        text = cos.decode()
    except Exception:
        text = None
    return dest, orig, id_missatge, text

#////////////////////////////////////////////////////////////////////////////////////
# missatge "D" (lectura)
def codifica_dades(ppm, brut, temperatura, humitat, versio):
    def f(valor, format_):
        return "" if valor is None else format_ % valor

    return "D;%s;%s;%s;%s;%d" % (
        f(ppm, "%.1f"), f(brut, "%d"), f(temperatura, "%.1f"), f(humitat, "%.1f"), versio)
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# 'D;...' -> dict(ppm, brut, temperatura, humitat, versio) o None si no és vàlid.
def descodifica_dades(text):
    
    if not text:
        return None
    parts = text.split(";")
    if len(parts) != 6 or parts[0] != "D":
        return None
    try:
        v = [None if p == "" else float(p) for p in parts[1:5]]
        versio = int(parts[5])
    except ValueError:
        return None
    return {
        "ppm": v[0],
        "brut": None if v[1] is None else int(v[1]),
        "temperatura": v[2],
        "humitat": v[3],
        "versio": versio,
    }
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# missatge "R" (resposta)
# config = dict(periode, mostres, interval, versio) o None.
def codifica_resposta(seq, config=None):
    
    if config is None:
        return "R;%d" % seq
    return "R;%d;%d;%d;%d;%d" % (
        seq, config["periode"], config["mostres"], config["interval"], config["versio"])
#////////////////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////
# 'R;...' -> dict(seq, config) (config és None si no n'hi ha) o None si no és vàlid.
def descodifica_resposta(text):
    
    if not text:
        return None
    parts = text.split(";")
    if parts[0] != "R" or len(parts) not in (2, 6):
        return None
    try:
        nums = [int(p) for p in parts[1:]]
    except ValueError:
        return None
    resposta = {"seq": nums[0], "config": None}
    if len(nums) == 5:
        resposta["config"] = {
            "periode": nums[1], "mostres": nums[2], "interval": nums[3], "versio": nums[4]}
    return resposta
#////////////////////////////////////////////////////////////////////////////////////