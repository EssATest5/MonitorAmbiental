"use strict";
/*
 * grafica.js - Gràfic de línies en SVG, sense dependències (funciona sense internet).
 *
 * new Grafica(contenidor, { clau: "temperatura", unitat: "°C", decimals: 1, color: "var(--color-temperatura)" })
 * grafica.posa(files, { inici: ms, fi: ms })
 *
 * `files` són les de /api/dades. Per a la clau "x" s'usa la mitjana f.x i, si hi ha, la banda
 * f.x_min .. f.x_max. Els forats de dades (comunicació perduda) es deixen en blanc.
 */
class Grafica {
  constructor(contenidor, opcions) {
    this.arrel = contenidor;
    this.o = Object.assign({ clau: "v", unitat: "", decimals: 1, color: "var(--accent)", alcada: 230 }, opcions);
    this.arrel.classList.add("grafica");
    this.files = [];
    this.finestra = null;
    this.ampladaDibuixada = 0;
    this.cos = document.createElement("div");
    this.tip = document.createElement("div");
    this.tip.className = "grafica-tip";
    this.arrel.appendChild(this.cos);
    this.arrel.appendChild(this.tip);
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (Math.abs(this.arrel.clientWidth - this.ampladaDibuixada) > 1) { this.dibuixa(); }
      }).observe(this.arrel);
    }
  }

  posa(files, finestra) {
    this.files = files || [];
    this.finestra = finestra || null;
    this.dibuixa();
  }

  static escalaBonica(min, max, n) {
    if (min === max) { min -= 1; max += 1; }
    const pas0 = (max - min) / n;
    const mag = Math.pow(10, Math.floor(Math.log10(pas0)));
    const r = pas0 / mag;
    const pas = (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag;
    const ini = Math.floor(min / pas + 1e-9) * pas;
    const fi = Math.ceil(max / pas - 1e-9) * pas;
    const marques = [];
    for (let v = ini; v <= fi + pas / 2; v += pas) { marques.push(Number(v.toPrecision(12))); }
    return { min: ini, max: fi, marques: marques, decimals: Math.max(0, -Math.floor(Math.log10(pas) + 1e-9)) };
  }

  dibuixa() {
    const o = this.o;
    const W = Math.max(280, Math.floor(this.arrel.clientWidth) || 600);
    const H = o.alcada;
    this.ampladaDibuixada = this.arrel.clientWidth;
    const m = { e: 52, d: 12, s: 10, i: 26 };
    this.tip.style.display = "none";

    const clau = o.clau;
    const punts = this.files.map(function (f) {
      const mn = f[clau + "_min"], mx = f[clau + "_max"];
      return { t: Date.parse(f.t), v: f[clau], mn: (mn === undefined ? null : mn),
               mx: (mx === undefined ? null : mx), n: f.n };
    }).filter(function (p) { return !isNaN(p.t) && p.v !== null && p.v !== undefined; });

    if (!punts.length) {
      this.cos.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '"><text class="buit" x="' + W / 2 +
        '" y="' + H / 2 + '">Sense dades en aquest període</text></svg>';
      return;
    }

    let t0 = this.finestra ? this.finestra.inici : punts[0].t;
    let t1 = this.finestra ? this.finestra.fi : punts[punts.length - 1].t;
    if (t1 <= t0) { t1 = t0 + 60000; }

    let ymin = Infinity, ymax = -Infinity;
    punts.forEach(function (p) {
      ymin = Math.min(ymin, p.mn !== null ? p.mn : p.v);
      ymax = Math.max(ymax, p.mx !== null ? p.mx : p.v);
    });
    const marge = (ymax - ymin) * 0.05;
    const esc = Grafica.escalaBonica(ymin - marge, ymax + marge, 5);

    const X = function (t) { return m.e + (t - t0) / (t1 - t0) * (W - m.e - m.d); };
    const Y = function (v) { return m.s + (1 - (v - esc.min) / (esc.max - esc.min)) * (H - m.s - m.i); };

    // Segments: es talla la línia quan falten dades (més de 3 vegades el pas habitual).
    const dts = [];
    for (let i = 1; i < punts.length; i++) { dts.push(punts[i].t - punts[i - 1].t); }
    dts.sort(function (a, b) { return a - b; });
    const mediana = dts.length ? dts[Math.floor(dts.length / 2)] : 60000;
    const llindar = Math.max(3 * mediana, 1000);
    const segments = [];
    let seg = [];
    punts.forEach(function (p) {
      if (seg.length && p.t - seg[seg.length - 1].t > llindar) { segments.push(seg); seg = []; }
      seg.push(p);
    });
    if (seg.length) { segments.push(seg); }

    let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img">';

    // Reixeta i eix Y
    esc.marques.forEach(function (v) {
      const y = Y(v).toFixed(1);
      svg += '<line class="reixeta" x1="' + m.e + '" x2="' + (W - m.d) + '" y1="' + y + '" y2="' + y + '"/>';
      svg += '<text class="eix-text" x="' + (m.e - 6) + '" y="' + (Number(y) + 4) + '" text-anchor="end">' +
             Comu.numero(v, esc.decimals) + '</text>';
    });

    // Eix X
    const PASSOS = [60e3, 300e3, 600e3, 1800e3, 3600e3, 10800e3, 21600e3, 43200e3, 86400e3, 172800e3, 604800e3];
    const objectiu = (W - m.e - m.d) / 90;
    let pas = PASSOS[PASSOS.length - 1];
    for (let i = 0; i < PASSOS.length; i++) { if ((t1 - t0) / PASSOS[i] <= objectiu) { pas = PASSOS[i]; break; } }
    const desfase = Comu.desfase(t0);
    for (let tk = Math.ceil((t0 + desfase) / pas) * pas - desfase; tk <= t1; tk += pas) {
      const x = X(tk).toFixed(1);
      const etiqueta = pas >= 86400e3 ? Comu.dia(tk) : ((t1 - t0) > 86400e3 ? Comu.diaHora(tk) : Comu.hora(tk));
      svg += '<line class="reixeta" x1="' + x + '" x2="' + x + '" y1="' + (H - m.i) + '" y2="' + (H - m.i + 4) + '"/>';
      svg += '<text class="eix-text" x="' + x + '" y="' + (H - 8) + '" text-anchor="middle">' + etiqueta + '</text>';
    }

    // Bandes mín-màx, línies i punts
    const mostraPunts = punts.length <= 80;
    segments.forEach(function (s) {
      const ambBanda = s.every(function (p) { return p.mn !== null && p.mx !== null; }) &&
                       s.some(function (p) { return p.mx > p.mn; });
      if (ambBanda && s.length > 1) {
        let d = "M" + X(s[0].t).toFixed(1) + " " + Y(s[0].mx).toFixed(1);
        for (let i = 1; i < s.length; i++) { d += "L" + X(s[i].t).toFixed(1) + " " + Y(s[i].mx).toFixed(1); }
        for (let i = s.length - 1; i >= 0; i--) { d += "L" + X(s[i].t).toFixed(1) + " " + Y(s[i].mn).toFixed(1); }
        svg += '<path class="banda" fill="' + o.color + '" d="' + d + 'Z"/>';
      }
      if (s.length > 1) {
        let d = "";
        s.forEach(function (p, i) { d += (i ? "L" : "M") + X(p.t).toFixed(1) + " " + Y(p.v).toFixed(1); });
        svg += '<path class="linia" stroke="' + o.color + '" d="' + d + '"/>';
      }
      if (mostraPunts || s.length === 1) {
        s.forEach(function (p) {
          svg += '<circle class="punt" fill="' + o.color + '" r="2.5" cx="' + X(p.t).toFixed(1) +
                 '" cy="' + Y(p.v).toFixed(1) + '"/>';
        });
      }
    });

    svg += '<line class="cursor" id="cursor" x1="0" x2="0" y1="' + m.s + '" y2="' + (H - m.i) + '" style="display:none"/>';
    svg += '<circle id="cursor-punt" r="4" fill="' + o.color + '" style="display:none"/>';
    svg += '</svg>';
    this.cos.innerHTML = svg;

    // Interacció: el punter (ratolí o dit) mostra el valor més proper.
    const elSvg = this.cos.firstChild, cursor = elSvg.querySelector("#cursor"), dot = elSvg.querySelector("#cursor-punt");
    const tip = this.tip, arrel = this.arrel, numero = Comu.numero;
    elSvg.addEventListener("pointermove", function (ev) {
      const r = elSvg.getBoundingClientRect();
      const x = (ev.clientX - r.left) * (W / r.width);
      let lo = 0, hi = punts.length - 1;
      while (hi - lo > 1) { const mig = (lo + hi) >> 1; if (X(punts[mig].t) < x) { lo = mig; } else { hi = mig; } }
      const p = Math.abs(X(punts[lo].t) - x) <= Math.abs(X(punts[hi].t) - x) ? punts[lo] : punts[hi];
      const px = X(p.t), py = Y(p.v);
      cursor.setAttribute("x1", px); cursor.setAttribute("x2", px); cursor.style.display = "";
      dot.setAttribute("cx", px); dot.setAttribute("cy", py); dot.style.display = "";
      const u = o.unitat ? " " + o.unitat : "";
      let html = "<b>" + Comu.dataHora(p.t) + "</b><br>" + numero(p.v, o.decimals) + u;
      if (p.n > 1 && p.mn !== null && p.mx !== null) {
        html += "<br>mín " + numero(p.mn, o.decimals) + " · màx " + numero(p.mx, o.decimals) + "<br>" + p.n + " lectures";
      }
      tip.innerHTML = html;
      tip.style.display = "block";
      const escala = r.width / W;
      let esquerra = px * escala + 12;
      if (esquerra + tip.offsetWidth > arrel.clientWidth) { esquerra = px * escala - tip.offsetWidth - 12; }
      tip.style.left = Math.max(0, esquerra) + "px";
      tip.style.top = Math.max(0, py * escala - 10) + "px";
    });
    elSvg.addEventListener("pointerleave", function () {
      cursor.style.display = "none"; dot.style.display = "none"; tip.style.display = "none";
    });
  }
}
