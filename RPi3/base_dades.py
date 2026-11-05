#!/usr/bin/env python3
#############################################################################
# base_dades.py
# modificat: 
#	30/10/26 : creació
#   02/11/26 : Canvio el nom dels camps mq135_ppm i mq135_brut per lectura_ppm i lectura_brut
#   05/11/26 : corregit lectures(): la variable del bucle 'resultat' trepitjava la llista de sortida
#
"""
base_dades.py - Gestió de la base de dades SQLite (compartit pel receptor LoRa i pel web).

Dues taules:
  lectures       una fila per cada lectura rebuda de la Pico
  configuracio   una sola fila (id = 1) amb els paràmetres de la Pico que es canvien des del web

Dates i hores en UTC, en format ISO 8601 ('2026-11-01T14:05:00Z').
Cada procés (receptor, web) ha d'obrir la seva pròpia connexió amb obre_bd().
"""
#############################################################################

import os
import sqlite3
from datetime import datetime, timezone

import configuracio as CFG
import protocol as P

####################################################################################
# Definicións de Taules per si cal recrear
####################################################################################
#///////////////////////////////////////////////////////////////////////////////////
ESQUEMA = """
CREATE TABLE IF NOT EXISTS lectures (
    id          INTEGER PRIMARY KEY,
    data_hora   TEXT    NOT NULL,   -- en format UTC, ho posa la RPi3 que se se suposa que te NTP
    lectura_ppm   REAL,             -- Parts per Milió ( de moment amb el MQ-135 faig una estimació doncs el model de sensor no dona lectures de qualitat)
    lectura_brut  INTEGER,          -- valor cru de l'ADC (permet recalcular el ppm si recalibro)
    temperatura REAL,               -- °C
    humitat     REAL,               -- %
    rssi        INTEGER,            -- senyal LoRa
    snr         REAL,               -- qualitat del senyal LoRa
    seq         INTEGER             -- número de seqüència 0-255 (detecta paquets perduts)
);
CREATE INDEX IF NOT EXISTS idx_lectures_data_hora ON lectures(data_hora);

CREATE TABLE IF NOT EXISTS configuracio (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    periode_lectura  INTEGER NOT NULL DEFAULT 60 CHECK (periode_lectura  BETWEEN 10 AND 86400), -- entre 10 segons i un dia
    nombre_mostres   INTEGER NOT NULL DEFAULT 5  CHECK (nombre_mostres   BETWEEN 1 AND 60),     -- cada periode de mostres fa aquest nombre de mostres
    interval_mostres INTEGER NOT NULL DEFAULT 2  CHECK (interval_mostres BETWEEN 2 AND 3600),   
    versio           INTEGER NOT NULL DEFAULT 1,   -- puja 1 a cada canvi de configuració manual des del web
    versio_aplicada  INTEGER NOT NULL DEFAULT 0,   -- versió que la Pico diu tenir (darrera lectura)
    actualitzacio    TEXT    NOT NULL              -- data del darrer canvi (UTC) - No cal que sigui format date-time
);
"""
#///////////////////////////////////////////////////////////////////////////////////

####################################################################################
# Funcions de suport i de accès a la BD
####################################################################################

#///////////////////////////////////////////////////////////////////////////////////
# Retorna la data i hora actuals
def ara_utc():
    return datetime.now(timezone.utc)
#///////////////////////////////////////////////////////////////////////////////////

# tambè en format text, pel camp actualització de la taula configuració
def text_utc(data):
    return data.strftime("%Y-%m-%dT%H:%M:%SZ")
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Obre una connexió. Amb inicialitza=True (per defecte) crea la carpeta, les taules i la fila
# de configuració per defecte si no existeixen. El web ho fa una vegada en arrencar i després obre una
# connexió per petició amb inicialitza=False (així no escriu res només per consultar).
def obre_bd(ruta=None, inicialitza=True):

    ruta = ruta or CFG.RUTA_BD
    if inicialitza:
        carpeta = os.path.dirname(ruta) # mira si existeix
        if carpeta: # si no existex la creo
            os.makedirs(carpeta, exist_ok=True)
            
    bd = sqlite3.connect(ruta, timeout=5)
    bd.row_factory = sqlite3.Row          # vull accedir pel nom de la columna, no per index de camp en tuples
    bd.execute("PRAGMA busy_timeout=5000")
    if inicialitza:  # si cal crear la BD
        bd.execute("PRAGMA journal_mode=WAL")    # el web pot llegir mentre el receptor escriu. registre d'escriptura prèvia
        bd.executescript(ESQUEMA)
        bd.execute("INSERT OR IGNORE INTO configuracio (id, actualitzacio) VALUES (1, ?)",
                   (text_utc(ara_utc()),))
        bd.commit()
    return bd
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# lectures
# dades = dicionari de protocol.descodifica_dades(). data_hora = datetime UTC
def desa_lectura(bd, data_hora, dades, rssi, snr, seq):
    
    bd.execute(
        "INSERT INTO lectures (data_hora, lectura_ppm, lectura_brut, temperatura, humitat, rssi, snr, seq) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (text_utc(data_hora), dades["ppm"], dades["brut"], dades["temperatura"],
         dades["humitat"], rssi, snr, seq))
    bd.commit()
#///////////////////////////////////////////////////////////////////////////////////    

#///////////////////////////////////////////////////////////////////////////////////
# configuració
# Retorna dict(periode, mostres, interval, versio, versio_aplicada, actualitzacio)
def llegeix_configuracio(bd):
    
    resultat = bd.execute("SELECT * FROM configuracio WHERE id = 1").fetchone()  # només tenim un registre, si hi han més per error retorna el ID 1
    return {
        "periode": resultat["periode_lectura"],
        "mostres": resultat["nombre_mostres"],
        "interval": resultat["interval_mostres"],
        "versio": resultat["versio"],
        "versio_aplicada": resultat["versio_aplicada"],
        "actualitzacio": resultat["actualitzacio"],
    }
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Desa una nova configuració (la valida primer; llança ValueError si no és vàlida).
# Puja la versió: el receptor la farà arribar a la Pico a la propera lectura.
def desa_configuracio(bd, periode, mostres, interval):

    periode, mostres, interval = P.valida_parametres(periode, mostres, interval)
    bd.execute(
        "UPDATE configuracio SET periode_lectura = ?, nombre_mostres = ?, interval_mostres = ?, "
        "versio = versio + 1, actualitzacio = ? WHERE id = 1",
        (periode, mostres, interval, text_utc(ara_utc())))
    bd.commit()
#///////////////////////////////////////////////////////////////////////////////////    

#///////////////////////////////////////////////////////////////////////////////////
# Registra la versió de configuració que la Pico diu tenir (la informa a cada lectura)
def marca_versio_aplicada(bd, versio):
    
    bd.execute("UPDATE configuracio SET versio_aplicada = ? WHERE id = 1 AND versio_aplicada != ?",
               (versio, versio))
    bd.commit()
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# True si la Pico encara no té la darrera configuració
def configuracio_pendent(cfg):
    return cfg["versio"] != cfg["versio_aplicada"]
#///////////////////////////////////////////////////////////////////////////////////

####################################################################################
#
# consultes especìfiques del web
#
####################################################################################

# Agrupacions per període: expressió SQL que dona l'inici de cada interval (UTC)
AGRUPACIONS = {
    "cru": None,    # sense agrupar: cada lectura tal com és
    "minut": "substr(data_hora, 1, 16) || ':00Z'",
    "10min": "substr(data_hora, 1, 15) || '0:00Z'",
    "hora": "substr(data_hora, 1, 13) || ':00:00Z'",
    "dia": "substr(data_hora, 1, 10) || 'T00:00:00Z'",
}
# (clau a l'API, columna de la BD)
VARIABLES = (("ppm", "lectura_ppm"), ("brut", "lectura_brut"),
             ("temperatura", "temperatura"), ("humitat", "humitat"))
LIMIT_FILES = 20000

#///////////////////////////////////////////////////////////////////////////////////
def _arrodoneix(valor):
    return None if valor is None else round(valor, 2)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Darrera lectura rebuda (dict) o None si encara no n'hi ha
def ultima_lectura(bd):
    f = bd.execute("SELECT * FROM lectures ORDER BY id DESC LIMIT 1").fetchone()
    return None if f is None else dict(f)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Lectures entre inici i fi (el text ha de ser UTC ISO), agrupades segons AGRUPACIONS.
# Retorna (files, truncat). Cada fila: t, n, i per a cada variable (ppm, brut, temperatura,
# humitat) la mitjana i les claus <var>_min i <var>_max; a més rssi i snr (mitjanes).
# Si hi ha més de `limit` files es retornen les més recents i truncat = True.
def lectures(bd, inici, fi, agrupa="cru", limit=LIMIT_FILES):

    if agrupa not in AGRUPACIONS:
        raise ValueError("Agrupació desconeguda: %s" % agrupa)
    expressio = AGRUPACIONS[agrupa]
    if expressio is None:
        sql = ("SELECT data_hora AS t, 1 AS n, "
               + ", ".join("%s AS %s, %s AS %s_min, %s AS %s_max" % (c, k, c, k, c, k)
                           for k, c in VARIABLES)
               + ", rssi, snr FROM lectures WHERE data_hora >= ? AND data_hora <= ? "
               "ORDER BY data_hora DESC LIMIT ?")
    else:
        sql = ("SELECT %s AS t, COUNT(*) AS n, " % expressio
               + ", ".join("AVG(%s) AS %s, MIN(%s) AS %s_min, MAX(%s) AS %s_max" % (c, k, c, k, c, k)
                           for k, c in VARIABLES)
               + ", AVG(rssi) AS rssi, AVG(snr) AS snr FROM lectures "
               "WHERE data_hora >= ? AND data_hora <= ? GROUP BY t ORDER BY t DESC LIMIT ?")
    files = bd.execute(sql, (inici, fi, limit + 1)).fetchall()
    truncat = len(files) > limit
    resultat = []
    for fila in reversed(files[:limit]):
        resultat.append({clau: (fila[clau] if clau in ("t", "n") else _arrodoneix(fila[clau]))
                         for clau in fila.keys()})
    return resultat, truncat
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# Estadístiques de totes les lectures de l'interval (sobre les dades crues)
def resum(bd, inici, fi):

    columnes = ", ".join("MIN(%s), MAX(%s), AVG(%s)" % (c, c, c) for _, c in VARIABLES)
    resultat = bd.execute("SELECT COUNT(*), MIN(data_hora), MAX(data_hora), %s FROM lectures "
                   "WHERE data_hora >= ? AND data_hora <= ?" % columnes, (inici, fi)).fetchone()
    valors = tuple(resultat)
    sortida = {"n": valors[0], "primera": valors[1], "darrera": valors[2]}
    for i, (clau, _) in enumerate(VARIABLES):
        mn, mx, mitjana = valors[3 + 3 * i: 6 + 3 * i]
        sortida[clau] = {"min": _arrodoneix(mn), "max": _arrodoneix(mx), "mitjana": _arrodoneix(mitjana)}
    return sortida
#///////////////////////////////////////////////////////////////////////////////////