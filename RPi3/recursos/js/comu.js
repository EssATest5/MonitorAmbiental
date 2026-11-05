"use strict";
/* comu.js - Utilitats compartides per totes les pàgines: fus horari, formats i peticions. */
const Comu = (function () {
  let fus = "local";
  try { fus = localStorage.getItem("fus") === "utc" ? "utc" : "local"; } catch (e) { /* sense localStorage */ }

  const dos = function (n) { return (n < 10 ? "0" : "") + n; };

  function parts(ms) {
    const d = new Date(ms);
    if (fus === "utc") {
      return { a: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(),
               h: d.getUTCHours(), mi: d.getUTCMinutes(), s: d.getUTCSeconds() };
    }
    return { a: d.getFullYear(), m: d.getMonth() + 1, d: d.getDate(),
             h: d.getHours(), mi: d.getMinutes(), s: d.getSeconds() };
  }

  /* Diferència (ms) entre l'hora mostrada i UTC en aquest instant. */
  function desfase(ms) { return fus === "utc" ? 0 : -new Date(ms).getTimezoneOffset() * 60000; }

  function dataHora(ms) {
    const p = parts(ms);
    return dos(p.d) + "/" + dos(p.m) + "/" + p.a + " " + dos(p.h) + ":" + dos(p.mi) + ":" + dos(p.s);
  }
  function hora(ms) { const p = parts(ms); return dos(p.h) + ":" + dos(p.mi); }
  function dia(ms) { const p = parts(ms); return dos(p.d) + "/" + dos(p.m); }
  function diaHora(ms) { return dia(ms) + " " + hora(ms); }

  function numero(valor, decimals) {
    if (valor === null || valor === undefined || isNaN(valor)) { return "—"; }
    try {
      return Number(valor).toLocaleString("ca", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    } catch (e) { return Number(valor).toFixed(decimals); }
  }

  function durada(segons) {
    segons = Math.max(0, Math.round(segons));
    if (segons < 60) { return segons + " s"; }
    if (segons < 3600) { return Math.floor(segons / 60) + " min " + (segons % 60) + " s"; }
    if (segons < 86400) { return Math.floor(segons / 3600) + " h " + Math.floor((segons % 3600) / 60) + " min"; }
    return Math.floor(segons / 86400) + " d " + Math.floor((segons % 86400) / 3600) + " h";
  }

  function isoUtc(ms) { return new Date(ms).toISOString().slice(0, 19) + "Z"; }

  /* Per als camps <input type="datetime-local"> (valor "AAAA-MM-DDTHH:MM" en el fus triat). */
  function aInput(ms) {
    const p = parts(ms);
    return p.a + "-" + dos(p.m) + "-" + dos(p.d) + "T" + dos(p.h) + ":" + dos(p.mi);
  }
  function deInput(text) {
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(text || "");
    if (!m) { return NaN; }
    const n = m.slice(1).map(Number);
    return fus === "utc" ? Date.UTC(n[0], n[1] - 1, n[2], n[3], n[4])
                         : new Date(n[0], n[1] - 1, n[2], n[3], n[4]).getTime();
  }

  async function demana(url) {
    const resposta = await fetch(url, { cache: "no-store" });
    let dades = null;
    try { dades = await resposta.json(); } catch (e) { /* no era JSON */ }
    if (!resposta.ok) { throw new Error((dades && dades.error) || resposta.statusText); }
    return dades;
  }

  /* Elements amb data-utc="2026-11-01T12:00:00Z": es mostren en el fus triat. */
  function pintaDates() {
    document.querySelectorAll("[data-utc]").forEach(function (e) {
      const ms = Date.parse(e.getAttribute("data-utc"));
      if (!isNaN(ms)) { e.textContent = dataHora(ms) + (fus === "utc" ? " UTC" : ""); }
    });
  }

  const selector = document.getElementById("fus");
  if (selector) {
    selector.value = fus;
    selector.addEventListener("change", function () {
      fus = selector.value === "utc" ? "utc" : "local";
      try { localStorage.setItem("fus", fus); } catch (e) { /* res */ }
      pintaDates();
      document.dispatchEvent(new Event("fus-canviat"));
    });
  }
  document.addEventListener("DOMContentLoaded", pintaDates);

  return {
    get fus() { return fus; },
    desfase: desfase, dataHora: dataHora, hora: hora, dia: dia, diaHora: diaHora,
    numero: numero, durada: durada, isoUtc: isoUtc, aInput: aInput, deInput: deInput,
    demana: demana, pintaDates: pintaDates
  };
})();
