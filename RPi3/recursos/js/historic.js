"use strict";
/* historic.js - Consulta per rang de dates i agrupació, amb gràfics, resum, taula i CSV. */
(function () {
  const MAX_FILES_TAULA = 500;
  const el = function (id) { return document.getElementById(id); };

  const grafiques = {
    gas: new Grafica(el("g-gas"), { clau: "ppm", unitat: "ppm", decimals: 0, color: "var(--color-gas)" }),
    temperatura: new Grafica(el("g-temperatura"), { clau: "temperatura", unitat: "°C", decimals: 1, color: "var(--color-temperatura)" }),
    humitat: new Grafica(el("g-humitat"), { clau: "humitat", unitat: "%", decimals: 0, color: "var(--color-humitat)" }),
    rssi: new Grafica(el("g-rssi"), { clau: "rssi", unitat: "dBm", decimals: 0, color: "var(--color-rssi)" })
  };
  let ara = Date.now(), dades = null, finestra = null;

  function senseValor(v) { return v === null || v === undefined; }

  function pintaResum() {
    const r = dades.resum, cos = document.querySelector("#resum tbody");
    const files = [];
    if (!senseValor(r.ppm.mitjana)) { files.push(["Sensor Gas (ppm)", r.ppm, 0]); }
    if (!senseValor(r.brut.mitjana)) { files.push(["Sensor, valor cru (ADC)", r.brut, 0]); }
    files.push(["Temperatura (°C)", r.temperatura, 1], ["Humitat (%)", r.humitat, 0]);
    cos.innerHTML = r.n ? files.map(function (f) {
      return "<tr><td>" + f[0] + "</td><td>" + Comu.numero(f[1].min, f[2]) + "</td><td>" +
             Comu.numero(f[1].max, f[2]) + "</td><td>" + Comu.numero(f[1].mitjana, f[2]) + "</td></tr>";
    }).join("") : '<tr><td colspan="4">Sense lectures en aquest interval.</td></tr>';
  }

  function pintaTaula() {
    const crues = dades.agrupa === "cru", r = dades.resum;
    const variables = [["ppm", "PPM", 0], ["brut", "ADC", 0], ["temperatura", "T (°C)", 1], ["humitat", "Hum (%)", 0]]
      .filter(function (v) { return v[0] !== "ppm" || !senseValor(r.ppm.mitjana); });
    let cap = "<tr><th>" + (crues ? "Data i hora" : "Inici de l'interval") + "</th>" + (crues ? "" : "<th>Lectures</th>");
    variables.forEach(function (v) {
      cap += crues ? "<th>" + v[1] + "</th>" : "<th>" + v[1] + " mitj.</th><th>mín</th><th>màx</th>";
    });
    cap += "<th>RSSI</th><th>SNR</th></tr>";
    el("dades").querySelector("thead").innerHTML = cap;

    const files = dades.files.slice(-MAX_FILES_TAULA).reverse();
    el("dades").querySelector("tbody").innerHTML = files.map(function (f) {
      let h = "<tr><td>" + Comu.dataHora(Date.parse(f.t)) + "</td>" + (crues ? "" : "<td>" + f.n + "</td>");
      variables.forEach(function (v) {
        h += "<td>" + Comu.numero(f[v[0]], v[2]) + "</td>";
        if (!crues) { h += "<td>" + Comu.numero(f[v[0] + "_min"], v[2]) + "</td><td>" + Comu.numero(f[v[0] + "_max"], v[2]) + "</td>"; }
      });
      return h + "<td>" + Comu.numero(f.rssi, 0) + "</td><td>" + Comu.numero(f.snr, 1) + "</td></tr>";
    }).join("");
    let nota = "";
    if (dades.files.length > MAX_FILES_TAULA) { nota = "Es mostren les últimes " + MAX_FILES_TAULA + " files de " + dades.files.length + " (de més noves a més antigues); el CSV les inclou totes. "; }
    if (dades.truncat) { nota += "L'interval té més de 20.000 files: només s'han carregat les més recents. Tria una agrupació més gran. "; }
    el("nota-taula").textContent = nota;
  }

  function pinta() {
    if (!dades) { return; }
    const teppm = dades.files.some(function (f) { return !senseValor(f.ppm); });
    grafiques.gas.o.clau = teppm ? "ppm" : "brut";
    grafiques.gas.o.unitat = teppm ? "ppm" : "ADC";
    el("g-gas-titol").textContent = teppm ? "Sensor Gas (ppm)" : "Sensor Gas (valor cru de l'ADC, sense calibrar)";
    Object.keys(grafiques).forEach(function (k) { grafiques[k].posa(dades.files, finestra); });
    pintaResum(); pintaTaula();
    const n = dades.resum.n;
    el("estat").className = "estat";
    el("estat").textContent = n ? n + " lectures a l'interval, de " + Comu.dataHora(Date.parse(dades.resum.primera)) +
      " a " + Comu.dataHora(Date.parse(dades.resum.darrera)) + (Comu.fus === "utc" ? " UTC." : ".")
      : "No hi ha lectures en aquest interval.";
  }

  async function consulta(iniciMs, fiMs) {
    const agrupa = el("agrupa").value;
    const parametres = "inici=" + Comu.isoUtc(iniciMs) + "&fi=" + Comu.isoUtc(fiMs) + "&agrupa=" + agrupa;
    el("csv").href = "/api/dades.csv?" + parametres;
    try {
      dades = await Comu.demana("/api/dades?" + parametres);
      finestra = { inici: iniciMs, fi: fiMs };
      pinta();
    } catch (e) {
      el("estat").className = "estat error";
      el("estat").textContent = "No s'ha pogut carregar: " + e.message;
    }
  }

  function mostra() {
    const inici = Comu.deInput(el("inici").value), fi = Comu.deInput(el("fi").value) + 59000;
    if (isNaN(inici) || isNaN(fi)) { return; }
    consulta(inici, fi);
  }

  function interval(hores) {
    const fi = ara, inici = hores ? ara - hores * 3600e3 : Date.UTC(2000, 0, 1);
    el("inici").value = Comu.aInput(inici); el("fi").value = Comu.aInput(fi);
    consulta(inici, fi).then(function () {
      if (!hores && dades && dades.resum.primera) {      // "Tot": ajusta l'inici a la primera lectura
        const primera = Date.parse(dades.resum.primera);
        el("inici").value = Comu.aInput(primera);
        finestra = { inici: primera, fi: fi };
        pinta();
      }
    });
  }

  el("filtre").addEventListener("submit", mostra);
  el("mostra").addEventListener("click", mostra);
  document.querySelectorAll("#rapids button").forEach(function (b) {
    b.addEventListener("click", function () { interval(Number(b.getAttribute("data-hores"))); });
  });
  document.addEventListener("fus-canviat", function () {
    if (finestra) { el("inici").value = Comu.aInput(finestra.inici); el("fi").value = Comu.aInput(finestra.fi - 59000); }
    pinta();
  });

  Comu.demana("/api/estat").then(function (e) { ara = Date.parse(e.ara); }, function () { /* usem el rellotge del navegador */ })
    .then(function () { interval(168); });
})();
