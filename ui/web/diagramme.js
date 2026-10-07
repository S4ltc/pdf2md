/* Diagramme als SVG, ohne Bibliothek (offline). Regeln (Visualisierungs-Leitfaden):
   - Form nach Aufgabe: Säulen für Größen über die Zeit, waagerechte Balken für Kategorien mit langen Namen,
     gestapelte Balken für Anteile, Streuung für zwei Größen.
   - Farbe zuletzt: eine Reihe = Akzent, weitere Kategorien = feste Grautöne (Hervorhebung statt Regenbogen).
     Die Farbe hängt an der Kategorie, nie am Rang.
   - Balken höchstens 24 px dick, 4 px gerundet am Datenende, gerade an der Grundlinie; 2 px Lücke zwischen
     gestapelten Teilen statt einer Kontur.
   - Gitterlinien 1 px und zurückhaltend, keine senkrechten Gitterlinien auf der Zeitachse; eine y-Achse.
   - Eine Reihe braucht keine Legende; ab zwei Reihen Legende mit kleinen Quadraten, Text in Textfarbe.
   - Hover zeigt je Element einen Tipp; jede Zahl gerundet und deutsch formatiert.
   Gezeichnet wird in echten Pixeln der Containerbreite (neu bei Größenänderung), damit Schrift nie skaliert. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const zahl = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });
  /* Beschriftung auf einer Fläche: dunkle Flächen hell beschriften, helle dunkel */
  const TEXT_AUF = { "akzent": "auf-akzent", "grau-1": "auf-grau", "grau-2": "auf-grau", "gefahr": "auf-grau" };

  function el(name, attribute, eltern) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attribute || {})) e.setAttribute(k, v);
    if (eltern) eltern.appendChild(e);
    return e;
  }

  function text(eltern, x, y, inhalt, attribute) {
    const t = el("text", Object.assign({ x, y }, attribute || {}), eltern);
    t.textContent = inhalt;
    return t;
  }

  /* Achsenteilung mit "runden" Schritten (1, 2, 2,5, 5 × 10^n) */
  function teilung(max, anzahl) {
    if (!(max > 0)) return [0, 1];
    const roh = max / (anzahl || 4);
    const basis = Math.pow(10, Math.floor(Math.log10(roh)));
    const schritt = [1, 2, 2.5, 5, 10].map(f => f * basis).find(s => s >= roh) || roh;
    const werte = [];
    for (let w = 0; w <= max + schritt * 0.001; w += schritt) werte.push(Math.round(w * 1000) / 1000);
    if (werte[werte.length - 1] < max) werte.push(Math.round((werte[werte.length - 1] + schritt) * 1000) / 1000);
    return werte;
  }

  function kurz(wert) {
    if (wert >= 10000) return zahl.format(Math.round(wert / 1000)) + " Tsd.";
    return zahl.format(wert);
  }

  /* Pfad eines Balkens: gerade an der Grundlinie, gerundet am Datenende */
  function saeulenpfad(x, y, b, h, r) {
    r = Math.max(0, Math.min(r, b / 2, h));
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + b - r}Q${x + b},${y} ${x + b},${y + r}V${y + h}Z`;
  }
  function balkenpfad(x, y, b, h, r) {
    r = Math.max(0, Math.min(r, h / 2, b));
    return `M${x},${y}H${x + b - r}Q${x + b},${y} ${x + b},${y + r}V${y + h - r}Q${x + b},${y + h} ${x + b - r},${y + h}H${x}Z`;
  }

  function leeren(ziel) {
    ziel.textContent = "";
    ziel.onmousemove = ziel.onmouseleave = null;
  }

  function leer(ziel, hinweis) {
    leeren(ziel);
    const p = document.createElement("p");
    p.className = "leer";
    p.textContent = hinweis || "Noch keine Daten.";
    ziel.appendChild(p);
  }

  function svgFuer(ziel, hoehe, beschreibung) {
    const breite = Math.max(200, Math.floor(ziel.clientWidth || 300));
    const svg = el("svg", { viewBox: `0 0 ${breite} ${hoehe}`, width: breite, height: hoehe, role: "img",
      "aria-label": beschreibung });
    ziel.appendChild(svg);
    return { svg, breite };
  }

  /* Tipp beim Überfahren: jedes Element mit data-tipp */
  function tippAnbinden(ziel) {
    let tipp = null;
    ziel.onmousemove = ereignis => {
      const quelle = ereignis.target.closest && ereignis.target.closest("[data-tipp]");
      if (!quelle) { if (tipp) tipp.hidden = true; return; }
      if (!tipp) {
        tipp = document.createElement("div");
        tipp.className = "diagramm-tipp";
        ziel.appendChild(tipp);
      }
      tipp.textContent = quelle.getAttribute("data-tipp");
      tipp.hidden = false;
      const rahmen = ziel.getBoundingClientRect();
      const x = ereignis.clientX - rahmen.left, y = ereignis.clientY - rahmen.top;
      const breite = tipp.offsetWidth;
      tipp.style.left = Math.max(0, Math.min(rahmen.width - breite, x - breite / 2)) + "px";
      tipp.style.top = Math.max(0, y - 34) + "px";
    };
    ziel.onmouseleave = () => { if (tipp) tipp.hidden = true; };
  }

  function legende(ziel, reihen) {
    const ul = document.createElement("ul");
    ul.className = "legende";
    for (const r of reihen) {
      const li = document.createElement("li");
      const i = document.createElement("i");
      i.style.background = `var(--${r.farbe})`;
      li.append(i, document.createTextNode(r.name + (r.wert != null ? " " + zahl.format(r.wert) : "")));
      ul.appendChild(li);
    }
    ziel.appendChild(ul);
  }

  /* Säulen über Kategorien oder Zeit. daten: [{label, wert, reihe, tipp}], reihen: [{name, farbe}] */
  function saeulen(ziel, daten, o) {
    o = Object.assign({ hoehe: 160, beschreibung: "Säulendiagramm", reihen: null, einheit: "" }, o || {});
    if (!daten.length) return leer(ziel, o.leer);
    leeren(ziel);
    if (o.reihen && o.reihen.length > 1) legende(ziel, o.reihen);
    const { svg, breite } = svgFuer(ziel, o.hoehe, o.beschreibung);
    const max = Math.max(...daten.map(d => d.wert || 0), 1);
    const ticks = teilung(max, 3);
    const oben = 8, unten = 20;
    const links = Math.max(...ticks.map(t => kurz(t).length)) * 6.2 + 8;
    const innenB = breite - links - 4, innenH = o.hoehe - oben - unten;
    const y = w => oben + innenH - (w / ticks[ticks.length - 1]) * innenH;
    for (const t of ticks) {
      el("line", { x1: links, x2: breite, y1: y(t), y2: y(t), class: t === 0 ? "achse" : "gitter" }, svg);
      text(svg, links - 6, y(t) + 4, kurz(t), { "text-anchor": "end" });
    }
    const platz = innenB / daten.length;
    const b = Math.max(2, Math.min(24, platz * 0.64));
    const jede = Math.max(1, Math.ceil(daten.length / Math.max(1, Math.floor(innenB / 56))));
    const farbe = name => (o.reihen || []).find(r => r.name === name);
    daten.forEach((d, i) => {
      const x = links + platz * i + (platz - b) / 2;
      const h = Math.max(0, oben + innenH - y(d.wert || 0));
      const f = farbe(d.reihe);
      el("path", { d: saeulenpfad(x, oben + innenH - h, b, Math.max(h, 0.5), 4),
        class: "marke-" + (f ? f.farbe : "akzent"), "data-tipp": d.tipp || `${d.label}: ${zahl.format(d.wert)}${o.einheit}` }, svg);
      if (i % jede === 0) text(svg, x + b / 2, o.hoehe - 4, d.label, { "text-anchor": "middle" });
    });
    tippAnbinden(ziel);
  }

  /* Waagerechte Balken mit Beschriftung am Wert. daten: [{label, wert, tipp}] */
  function balken(ziel, daten, o) {
    o = Object.assign({ beschreibung: "Balkendiagramm", zeile: 28, farbe: "akzent" }, o || {});
    if (!daten.length) return leer(ziel, o.leer);
    leeren(ziel);
    const hoehe = daten.length * o.zeile + 4;
    const { svg, breite } = svgFuer(ziel, hoehe, o.beschreibung);
    const max = Math.max(...daten.map(d => d.wert || 0), 1);
    const beschriftung = Math.min(breite * 0.45, Math.max(...daten.map(d => d.label.length)) * 6.4 + 12);
    const wertBreite = Math.max(...daten.map(d => zahl.format(d.wert).length)) * 7 + 12;
    const innen = Math.max(20, breite - beschriftung - wertBreite);
    daten.forEach((d, i) => {
      const yy = i * o.zeile + 4, h = Math.min(20, o.zeile - 8);
      const label = text(svg, 0, yy + h / 2 + 4, d.label);
      if (d.label.length * 6.4 > beschriftung - 8) {
        label.textContent = d.label.slice(0, Math.max(4, Math.floor((beschriftung - 8) / 6.4) - 1)) + "…";
        el("title", {}, label).textContent = d.label;
      }
      const b = Math.max(1, (d.wert / max) * innen);
      el("path", { d: balkenpfad(beschriftung, yy, b, h, 4), class: "marke-" + (d.farbe || o.farbe),
        "data-tipp": d.tipp || `${d.label}: ${zahl.format(d.wert)}` }, svg);
      text(svg, beschriftung + b + 6, yy + h / 2 + 4, zahl.format(d.wert), { class: "wert" });
    });
    tippAnbinden(ziel);
  }

  /* Gestapelte waagerechte Balken (Anteile). zeilen: [{label, werte: {Kategorie: n}}], kategorien: [{name, farbe}] */
  function gestapelt(ziel, zeilen, kategorien, o) {
    o = Object.assign({ beschreibung: "Gestapeltes Balkendiagramm", zeile: 30 }, o || {});
    const summe = z => Object.values(z.werte).reduce((a, b) => a + b, 0);
    if (!zeilen.length || !zeilen.some(summe)) return leer(ziel, o.leer);
    leeren(ziel);
    const benutzt = kategorien.filter(k => zeilen.some(z => z.werte[k.name]));
    legende(ziel, benutzt.map(k => ({ name: k.name, farbe: k.farbe })));
    const hoehe = zeilen.length * o.zeile + 4;
    const { svg, breite } = svgFuer(ziel, hoehe, o.beschreibung);
    const beschriftung = Math.max(...zeilen.map(z => z.label.length)) * 6.6 + 12;
    const innen = breite - beschriftung - 4;
    zeilen.forEach((z, i) => {
      const yy = i * o.zeile + 4, h = Math.min(20, o.zeile - 10), gesamt = summe(z) || 1;
      text(svg, 0, yy + h / 2 + 4, z.label);
      let x = beschriftung;
      const teile = benutzt.filter(k => z.werte[k.name]);
      teile.forEach((k, j) => {
        const n = z.werte[k.name], letzte = j === teile.length - 1;
        const b = (n / gesamt) * innen - (letzte ? 0 : 2);
        const anteil = Math.round((n / gesamt) * 100);
        const pfad = letzte ? balkenpfad(x, yy, Math.max(b, 1), h, 4) : `M${x},${yy}h${Math.max(b, 1)}v${h}h${-Math.max(b, 1)}Z`;
        el("path", { d: pfad, class: "marke-" + k.farbe, "data-tipp": `${z.label} · ${k.name}: ${zahl.format(n)} (${anteil} %)` }, svg);
        if (b > 44) text(svg, x + 6, yy + h / 2 + 4, `${anteil} %`, { class: TEXT_AUF[k.farbe] || "auf-hell" });
        x += b + (letzte ? 0 : 2);
      });
    });
    tippAnbinden(ziel);
  }

  /* Streuung zweier Größen. punkte: [{x, y, tipp}] */
  function streuung(ziel, punkte, o) {
    o = Object.assign({ hoehe: 200, beschreibung: "Streudiagramm", xName: "", yName: "" }, o || {});
    if (!punkte.length) return leer(ziel, o.leer);
    leeren(ziel);
    const { svg, breite } = svgFuer(ziel, o.hoehe, o.beschreibung);
    const xt = teilung(Math.max(...punkte.map(p => p.x), 1), 4);
    const yt = teilung(Math.max(...punkte.map(p => p.y), 1), 3);
    const oben = 8, unten = 34;
    const links = Math.max(...yt.map(t => kurz(t).length)) * 6.2 + 22;
    const innenB = breite - links - 12, innenH = o.hoehe - oben - unten;
    const X = v => links + (v / xt[xt.length - 1]) * innenB;
    const Y = v => oben + innenH - (v / yt[yt.length - 1]) * innenH;
    for (const t of yt) {
      el("line", { x1: links, x2: breite - 12, y1: Y(t), y2: Y(t), class: t === 0 ? "achse" : "gitter" }, svg);
      text(svg, links - 6, Y(t) + 4, kurz(t), { "text-anchor": "end" });
    }
    for (const t of xt) text(svg, X(t), oben + innenH + 14, kurz(t), { "text-anchor": "middle" });
    text(svg, links + innenB / 2, o.hoehe - 2, o.xName, { "text-anchor": "middle" });
    const yl = text(svg, 10, oben + innenH / 2, o.yName, { "text-anchor": "middle" });
    yl.setAttribute("transform", `rotate(-90 10 ${oben + innenH / 2})`);
    for (const p of punkte) el("circle", { cx: X(p.x), cy: Y(p.y), r: 4, class: "punkt", "data-tipp": p.tipp || "" }, svg);
    tippAnbinden(ziel);
  }

  /* Anteil gegen ein Ganzes: Zahl plus schmale Spur */
  function meter(ziel, teil, ganzes, o) {
    o = Object.assign({ beschreibung: "Anteil" }, o || {});
    if (!ganzes) return leer(ziel, o.leer);
    leeren(ziel);
    const anteil = Math.round((teil / ganzes) * 100);
    const div = document.createElement("div");
    div.className = "meter";
    div.setAttribute("role", "img");
    div.setAttribute("aria-label", `${o.beschreibung}: ${anteil} Prozent (${teil} von ${ganzes})`);
    div.innerHTML = `<div><span class="meter-zahl">${anteil} %</span> <span class="hinweis">${zahl.format(teil)} von ${zahl.format(ganzes)} Büchern</span></div>` +
      `<div class="meter-spur"><span style="width:${anteil}%"></span></div>` + (o.text ? `<p class="hinweis">${o.text}</p>` : "");
    ziel.appendChild(div);
  }

  window.Diagramme = { saeulen, balken, gestapelt, streuung, meter, zahl };
})();
