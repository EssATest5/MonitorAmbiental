"use strict";
/* configuracio.js - Comprova en directe que el mostreig cap dins del període. */
(function () {
  const el = function (id) { return document.getElementById(id); };
  const text = el("comprovacio");
  const marge = Number(text.getAttribute("data-marge"));

  function comprova() {
    const periode = Number(el("periode").value), mostres = Number(el("mostres").value), interval = Number(el("interval").value);
    if (!periode || !mostres || !interval) { text.textContent = ""; return; }
    const durada = (mostres - 1) * interval;
    if (durada + marge > periode) {
      text.className = "comprovacio error";
      text.textContent = "El mostreig dura " + durada + " s i, amb " + marge + " s de marge per enviar, no cap dins del període de " + periode + " s.";
    } else {
      text.className = "comprovacio ok";
      text.textContent = "El mostreig dura " + durada + " s; queden " + (periode - durada) + " s abans de la lectura següent.";
    }
  }
  ["periode", "mostres", "interval"].forEach(function (id) { el(id).addEventListener("input", comprova); });
  comprova();
})();
