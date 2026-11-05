#!/usr/bin/env python3
"""
exporta_copia.py - Fa una còpia consistent de la base de dades, segura encara que el
receptor hi estigui escrivint (no copiïs mai sensors.db a mà: està en mode WAL).

Ús:   python3 exporta_copia.py                  -> dades/copia.db
      python3 exporta_copia.py /ruta/altra.db   -> la ruta que triïs
"""
import os
import sqlite3
import sys

import configuracio as CFG


def fes_copia(ruta_desti):
    if os.path.exists(ruta_desti):
        os.remove(ruta_desti)
    origen = sqlite3.connect("file:%s?mode=ro" % CFG.RUTA_BD, uri=True, timeout=10)
    desti = sqlite3.connect(ruta_desti)
    try:
        origen.backup(desti)
        estat = desti.execute("PRAGMA integrity_check").fetchone()[0]
        lectures = desti.execute("SELECT COUNT(*) FROM lectures").fetchone()[0]
    finally:
        desti.close()
        origen.close()
    return estat, lectures


if __name__ == "__main__":
    desti = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(CFG.RUTA_BD), "copia.db")
    estat, lectures = fes_copia(desti)
    print("Còpia feta a %s (%d lectures, integritat: %s)" % (desti, lectures, estat))
    sys.exit(0 if estat == "ok" else 1)
