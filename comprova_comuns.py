#!/usr/bin/env python3
#############################################################################
# comprova_comuns.py
# modificat:
#   05/11/26 : creació
#
"""
Comprova que els fitxers compartits (lora.py i protocol.py) són idèntics a RPi3/ i a PICO/.
Si no ho són, la Pico i la RPi3 poden deixar de entendre's. Ús:  python3 comprova_comuns.py
"""
#############################################################################
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
COMUNS = ("lora.py", "protocol.py")

#///////////////////////////////////////////////////////////////////////////////////
def llegeix(carpeta, nom):
    with open(os.path.join(DIR, carpeta, nom), "rb") as f:
        return f.read().replace(b"\r\n", b"\n")    # ignora les diferències de final de línia
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
#/// M A I N ///////////////////////////////////////////////////////////////////////
#///////////////////////////////////////////////////////////////////////////////////
errors = 0
for nom in COMUNS:
    igual = llegeix("RPi3", nom) == llegeix("PICO", nom)
    print("%-12s %s" % (nom, "igual a RPi3/ i PICO/" if igual else "DIFERENT entre RPi3/ i PICO/"))
    errors += not igual
sys.exit(1 if errors else 0)
