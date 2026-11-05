"use strict";
/* tauler.js - Pàgina principal: darrera lectura, gràfics del període i resum. S'actualitza sola. */
(function () {
  const PERIODES = { "1h": [3600, "cru"], "24h": [86400, "10min"], "7d": [604800, "hora"], "30d": [2592000, "hora"] };
  const NOM_AGRUPA = { cru: "cada lectura", minut: "mitjanes d'1 minut", "10min": "mitjanes de 10 minuts",
                       hora: "mitjanes d'1 hora", dia: "mitjanes d'1 dia" };
  const REFRESC_MS = 30000;
  const el = function (id) { return document.getElementById(id); };

  const grafiques = {
    gas: new Grafica(el("g-gas"), { clau: "ppm", unitat: "ppm", decimals: 0, color: "var(--color-gas)" }),
    temperatura: new Grafica(el("g-temperatura"), { clau: "temperatura", unitat: "°C", decimals: 1, color: "var(--color-temperatura)" }),
    humitat: new Grafica(el("g-humitat"), { clau: "humitat", unitat: "%", decimals: 0, color: "var(--color-humitat)" }),
    rssi: new Grafica(el("g-rssi"), { clau: "rssi", unitat: "dBm", decimals: 0, color: "var(--color-rssi)" })
  };

  let periode = "24h", estat = null, dades = null, finestra = null;

  function senseValor(v) { return v === null || v === undefined; }

  function pintaTargetes() {
    const u = estat.ultima;
    const valor = el("t-gas-valor");
    if (!u) {
      ["t-gas-valor", "t-temperatura-valor", "t-humitat-valor", "t-senyal-valor"].forEach(function (id) { el(id).textContent = "—"; });
      return;
    }
    if (!senseValor(u.lectura_ppm)) {
      el("t-gas-etiqueta").textContent = "Sensor Gas (ppm estimat)";
      valor.innerHTML = Comu.numero(u.lectura_ppm, 0) + " <small>ppm</small>";
    } else {
      el("t-gas-etiqueta").textContent = "Sensor Gas (sense calibrar)";
      valor.innerHTML = Comu.numero(u.lectura_brut, 0) + " <small>ADC</small>";
    }
    el("t-temperatura-valor").innerHTML = senseValor(u.temperatura) ? "—" : Comu.numero(u.temperatura, 1) + " <small>°C</small>";
    el("t-humitat-valor").innerHTML = senseValor(u.humitat) ? "—" : Comu.numero(u.humitat, 0) + " <small>%</small>";
    el("t-senyal-valor").innerHTML = Comu.numero(u.rssi, 0) + " <small>dBm · SNR " + Comu.numero(u.snr, 1) + " dB</small>";
  }

  function pintaEstat() {
    const nodeEstat = el("estat"), u = estat.ultima, cfg = estat.configuracio;
    if (!u) {
      nodeEstat.className = "estat";
      nodeEstat.textContent = "Encara no hi ha cap lectura a la base de dades.";
      return;
    }
    const ara = Date.parse(estat.ara), quan = Date.parse(u.data_hora);
    const edat = (ara - quan) / 1000;
    const vell = edat > 3 * cfg.periode + 10;
    let text = (vell ? "Atenció: sense lectures noves des de fa " : "Darrera lectura fa ") + Comu.durada(edat) +
               " (" + Comu.dataHora(quan) + (Comu.fus === "utc" ? " UTC" : "") + "). Pico: cada " + cfg.periode +
               " s, " + cfg.mostres + (cfg.mostres === 1 ? " mostra" : " mostres") + (cfg.mostres > 1 ? " cada " + cfg.interval + " s" : "") + ".";
    if (estat.pendent) { text += " Configuració pendent d'aplicar."; }
    nodeEstat.className = "estat" + (vell ? " vell" : "");
    nodeEstat.textContent = text;
  }

  function pintaResum() {
    const r = dades.resum, cos = document.querySelector("#resum tbody");
    const files = [];
    if (!senseValor(r.ppm.mitjana)) { files.push(["Sensor Gas (ppm estimat)", r.ppm, 0]); }
    if (!senseValor(r.brut.mitjana)) { files.push(["Sensor, valor cru (ADC)", r.brut, 0]); }
    files.push(["Temperatura (°C)", r.temperatura, 1], ["Humitat (%)", r.humitat, 0]);
    cos.innerHTML = r.n ? files.map(function (f) {
      return "<tr><td>" + f[0] + "</td><td>" + Comu.numero(f[1].min, f[2]) + "</td><td>" +
             Comu.numero(f[1].max, f[2]) + "</td><td>" + Comu.numero(f[1].mitjana, f[2]) + "</td></tr>";
    }).join("") : '<tr><td colspan="4">Sense lectures en aquest període.</td></tr>';
  }

  function pintaGrafiques() {
    const teppm = dades.files.some(function (f) { return !senseValor(f.ppm); });
    grafiques.gas.o.clau = teppm ? "ppm" : "brut";
    grafiques.gas.o.unitat = teppm ? "ppm" : "ADC";
    el("g-gas-titol").textContent = teppm ? "Sensor Gas (ppm estimat)" : "Sensor Gas (valor cru de l'ADC, sense calibrar)";
    Object.keys(grafiques).forEach(function (k) { grafiques[k].posa(dades.files, finestra); });
    el("nota-agrupa").textContent = "Es mostren " + NOM_AGRUPA[dades.agrupa] + (dades.agrupa === "cru" ? "" : " (banda = mínim i màxim)") + ".";
  }

  function pinta() {
    if (!estat || !dades) { return; }
    pintaTargetes(); pintaEstat(); pintaGrafiques(); pintaResum();
  }

  async function carrega() {
    const p = PERIODES[periode];
    try {
      const r = await Promise.all([Comu.demana("/api/estat"),
                                   Comu.demana("/api/dades?ultims=" + p[0] + "&agrupa=" + p[1])]);
      estat = r[0]; dades = r[1];
      const fi = Date.parse(estat.ara);
      finestra = { inici: fi - p[0] * 1000, fi: fi };
      pinta();
    } catch (e) {
      const n = el("estat");
      n.className = "estat error";
      n.textContent = "No s'ha pogut carregar: " + e.message;
    }
  }

  document.querySelectorAll("#periodes button").forEach(function (b) {
    b.addEventListener("click", function () {
      periode = b.getAttribute("data-periode");
      document.querySelectorAll("#periodes button").forEach(function (x) { x.classList.toggle("activa", x === b); });
      carrega();
    });
  });
  document.addEventListener("fus-canviat", pinta);
  setInterval(function () { if (!document.hidden) { carrega(); } }, REFRESC_MS);
  carrega();
})();
