#!/usr/bin/env python3
#############################################################################
# web.py
# modificat: 
#	31/10/26 : creació
#   02/11/26 : Canvio el nom dels camps mq135_ppm i mq135_brut per lectura_ppm i lectura_brut
#       
"""
web.py - Servidor web (Flask) del monitor ambiental.

Pàgines:   /  (tauler)      /historic      /configuracio
API JSON:  /api/estat       /api/dades     /api/dades.csv
El web només parla amb la base de dades: mai toca la ràdio. Quan es canvia la configuració,
es desa a la BD i el servei lora_receptor la fa arribar a la Pico amb la propera lectura.

ATENCIÓ: no té contrasenya. Qualsevol dispositiu de la xarxa on és la RPi3 pot canviar la
configuració de la Pico.
"""
#############################################################################
import csv
import io
import os
from datetime import datetime, timedelta

from flask import (Flask, Response, flash, g, jsonify, redirect, render_template,
                   request, url_for)

import base_dades as BD
import configuracio as CFG
import protocol as P

####################################################################################
# Crea els objectes per la app
####################################################################################
app = Flask(__name__, template_folder="plantilles_web", static_folder="recursos",
            static_url_path="/recursos")
app.secret_key = os.urandom(24)    # només per als missatges flash (canvia a cada arrencada)

FORMAT_UTC = "%Y-%m-%dT%H:%M:%SZ"


#///////////////////////////////////////////////////////////////////////////////////
# Connexió de la petició actual (es tanca sola al final)
def bd():
    
    if "bd" not in g:
        g.bd = BD.obre_bd(inicialitza=False)
    return g.bd
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
@app.teardown_appcontext
def tanca_bd(_error):
    connexio = g.pop("bd", None)
    if connexio is not None:
        connexio.close()
#///////////////////////////////////////////////////////////////////////////////////

class ErrorPeticio(Exception):
    pass

#///////////////////////////////////////////////////////////////////////////////////
# Retorna (inici, fi) en text UTC. Accepta ?ultims=<segons> o ?inici=..&fi=.. (UTC, ISO)
def interpreta_interval(args):
    
    ara = BD.ara_utc().replace(tzinfo=None)
    try:
        if "ultims" in args:
            segons = int(args["ultims"])
            if segons <= 0:
                raise ValueError
            return (ara - timedelta(seconds=segons)).strftime(FORMAT_UTC), ara.strftime(FORMAT_UTC)
        inici = datetime.strptime(args["inici"], FORMAT_UTC)
        fi = datetime.strptime(args["fi"], FORMAT_UTC) if args.get("fi") else ara
    except (KeyError, ValueError):
        raise ErrorPeticio("Interval no vàlid: cal ?ultims=<segons> o bé ?inici=AAAA-MM-DDTHH:MM:SSZ&fi=...")
    if fi < inici:
        raise ErrorPeticio("La data final és anterior a la inicial")
    return inici.strftime(FORMAT_UTC), fi.strftime(FORMAT_UTC)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
@app.errorhandler(ErrorPeticio)
def error_peticio(e):
    return jsonify(error=str(e)), 400
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
#  pàgines
@app.route("/")
def tauler():
    return render_template("tauler.html")
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
@app.route("/historic")
def historic():
    return render_template("historic.html")
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
@app.route("/configuracio", methods=["GET", "POST"])
def configuracio():
    valors = None
    if request.method == "POST":
        valors = {"periode": request.form.get("periode", ""),
                  "mostres": request.form.get("mostres", ""),
                  "interval": request.form.get("interval", "")}
        try:
            BD.desa_configuracio(bd(), valors["periode"], valors["mostres"], valors["interval"])
        except ValueError as e:
            flash(str(e), "error")      # tornem a mostrar el formulari amb el que s'ha escrit
        else:
            flash("Configuració desada. La Pico la rebrà amb la propera lectura.", "ok")
            return redirect(url_for("configuracio"))
    cfg = BD.llegeix_configuracio(bd())
    if valors is None:
        valors = {"periode": cfg["periode"], "mostres": cfg["mostres"], "interval": cfg["interval"]}
    return render_template("configuracio.html", cfg=cfg, valors=valors,
                           pendent=BD.configuracio_pendent(cfg), limits=P.LIMITS, marge=P.MARGE_S)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
# API
@app.route("/api/estat")
def api_estat():
    cfg = BD.llegeix_configuracio(bd())
    return jsonify(ara=BD.text_utc(BD.ara_utc()), ultima=BD.ultima_lectura(bd()),
                   configuracio=cfg, pendent=BD.configuracio_pendent(cfg))
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
def llegeix_dades():
    inici, fi = interpreta_interval(request.args)
    agrupa = request.args.get("agrupa", "cru")
    if agrupa not in BD.AGRUPACIONS:
        raise ErrorPeticio("Agrupació desconeguda. Opcions: " + ", ".join(BD.AGRUPACIONS))
    files, truncat = BD.lectures(bd(), inici, fi, agrupa)
    return inici, fi, agrupa, files, truncat
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
@app.route("/api/dades")
def api_dades():
    inici, fi, agrupa, files, truncat = llegeix_dades()
    return jsonify(inici=inici, fi=fi, agrupa=agrupa, truncat=truncat,
                   resum=BD.resum(bd(), inici, fi), files=files)
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
@app.route("/api/dades.csv")
def api_dades_csv():
    inici, fi, agrupa, files, _truncat = llegeix_dades()
    sortida = io.StringIO()
    escriptor = csv.writer(sortida)
    columnes = ["n"]
    capcalera = ["data_hora_utc", "n"]
    for clau, _ in BD.VARIABLES:
        columnes += [clau, clau + "_min", clau + "_max"]
        capcalera += [clau + "_mitjana", clau + "_min", clau + "_max"]
    columnes += ["rssi", "snr"]
    capcalera += ["rssi", "snr"]
    escriptor.writerow(capcalera)
    for f in files:
        escriptor.writerow([f["t"]] + ["" if f[c] is None else f[c] for c in columnes])
    nom = "lectures_%s_%s.csv" % (inici[:10], fi[:10])
    return Response(sortida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % nom})
#///////////////////////////////////////////////////////////////////////////////////

#///////////////////////////////////////////////////////////////////////////////////
#/// M A I N ///////////////////////////////////////////////////////////////////////
#///////////////////////////////////////////////////////////////////////////////////
if __name__ == "__main__":
    connexio = BD.obre_bd()   # obre (i crea si cal) la BD i les taules
    connexio.close()          # tanca la connexió; només volíem assegurar que existeixen
    app.run(host=CFG.HOST_WEB, port=CFG.PORT_WEB, threaded=True)
