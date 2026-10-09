/* pdf2md – Oberfläche. Spricht nur über rufe() mit Python (ui_app.Api): im Fenster über window.pywebview.api,
   im Entwicklungsserver (werkzeuge/ui_vorschau.py, erkennbar am meta-Tag pdf2md-modus) per HTTP.
   Zustand kommt immer aus Python; die Oberfläche fragt Signatur und Ereignisse regelmäßig ab. */
(function () {
  "use strict";
  const $ = sel => document.querySelector(sel);
  const D = window.Diagramme;
  const zahl = new Intl.NumberFormat("de-DE");
  const zahl0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
  const zahl1 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });
  const zahlFest1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const MODUS = (document.querySelector('meta[name="pdf2md-modus"]') || {}).content === "http" ? "http" : "fenster";
  /* Eine Aktion heißt überall gleich: Menüeintrag (index.html), Dialogknopf (hier) und Schlussmeldung
     (zusammenfassung). Python liefert als Laufart den Menütitel (ui_app.WERKZEUGE). */
  const AKTION = { rueckgaengig: "Rückgängig machen", namen: "Namen reparieren", text: "Text erneuern",
    literatur: "Literaturliste exportieren" };
  const LAUF_KURZ = { "Letzten Lauf rückgängig machen": "Rückgängig machen" };
  const HERKUNFT = [
    { name: "Crossref", farbe: "akzent" }, { name: "Norm", farbe: "akzent-linie" }, { name: "Text", farbe: "grau-1" },
    { name: "PDF-Metadaten", farbe: "grau-2" }, { name: "Dokument", farbe: "grau-3" },
    { name: "von Hand", farbe: "grau-4" }, { name: "fehlt", farbe: "gefahr" }];
  const LAUFARTEN = [{ name: "Umwandlung", farbe: "akzent" }, { name: "Text erneuert", farbe: "grau-2" }];

  const zustand = {
    seite: "uebersicht", stand: null, lauf: null, signatur: null, ereignis: 0, fehler: {},
    auswertung: null, einstellungen: null, filter: "",
  };

  /* ------------------------------------------------------------ Brücke zu Python */
  const bereit = new Promise(los => {
    if (MODUS === "http") return los();
    if (window.pywebview && window.pywebview.api) return los();
    window.addEventListener("pywebviewready", () => los(), { once: true });
  });

  /* Fehler unterscheiden: keine Verbindung (Vorschau-Server weg) oder Fehler in Python (Ausnahme, HTTP 500) */
  function rufFehler(methode, grund, verbindung) {
    const f = new Error(grund);
    f.methode = methode;
    f.verbindung = verbindung;
    return f;
  }
  async function rufe(methode, ...args) {
    await bereit;
    if (MODUS === "fenster") {
      try { return await window.pywebview.api[methode](...args); }
      catch (f) { throw rufFehler(methode, (f && f.message) || String(f), false); }
    }
    let antwort;
    try {
      antwort = await fetch("/api/" + methode, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(args),
      });
    } catch (f) {
      throw rufFehler(methode, f.message, true);
    }
    if (!antwort.ok) throw rufFehler(methode, `HTTP ${antwort.status}`, false);
    return antwort.json();
  }
  function fehlerText(f) {
    if (f && f.verbindung) return "Keine Verbindung zum Programm. pdf2md neu starten.";
    const grund = f && f.message ? f.message : String(f);
    return `Programmfehler${f && f.methode ? ` bei „${f.methode}“` : ""}: ${grund}. Erneut versuchen; ` +
      "bleibt der Fehler, pdf2md neu starten.";
  }

  /* ------------------------------------------------------------ Hilfen */
  function element(name, klasse, inhalt) {
    const e = document.createElement(name);
    if (klasse) e.className = klasse;
    if (inhalt != null) e.textContent = inhalt;
    return e;
  }
  /* Mehrzahl richtig bilden: anzahl(1, "Datei", "Dateien") = "1 Datei" */
  function anzahl(n, eins, mehr) {
    return `${zahl.format(n)} ${n === 1 ? eins : mehr}`;
  }
  function groesse(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${zahl.format(Math.round(bytes / 1024))} KB`;
    return `${zahl1.format(bytes / 1048576)} MB`;
  }
  function datum(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(iso || "");
    return m ? `${m[3]}.${m[2]}.${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "") : (iso || "");
  }
  function kurzdatum(iso) {
    const m = /^\d{4}-(\d{2})-(\d{2})/.exec(iso || "");
    return m ? `${m[2]}.${m[1]}.` : "";
  }
  function dauer(sekunden) {
    if (sekunden == null) return "";
    const m = Math.floor(sekunden / 60), s = sekunden % 60;
    return m ? `${m} min ${String(s).padStart(2, "0")} s` : `${s} s`;
  }
  function prozent(anteil) {
    return anteil == null ? "–" : `${(anteil < 0.1 ? zahl1 : zahl0).format(anteil * 100)} %`;
  }
  function normal(text) {
    return (text || "").toLocaleLowerCase("de-DE").normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  /* Statuszeile: Antwort auf eine Aktion des Nutzers. Lange Texte stehen vollständig im title. */
  function melde(text) {
    const status = $("#status");
    status.textContent = text || "";
    status.title = text || "";
  }
  /* Laufereignisse stehen im Laufprotokoll; Screenreader hören sie über diese Live-Region */
  function ansagen(text) {
    $("#ansage").textContent = text || "";
  }
  function speicherLesen(schluessel) {
    try { return localStorage.getItem("pdf2md." + schluessel); } catch (e) { return null; }
  }
  function speicherSchreiben(schluessel, wert) {
    try { localStorage.setItem("pdf2md." + schluessel, wert); } catch (e) { /* ohne Speicher geht es auch */ }
  }

  /* ------------------------------------------------------------ Navigation */
  function zeigeSeite(name) {
    zustand.seite = name;
    for (const s of document.querySelectorAll(".seite")) s.hidden = s.id !== "seite-" + name;
    for (const b of document.querySelectorAll(".nav")) {
      if (b.dataset.seite === name) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    }
    speicherSchreiben("seite", name);
    if (name === "auswertung") ladeAuswertung();
    if (name === "einstellungen") ladeEinstellungen();
    if (name === "uebersicht") zeigeDiagrammeUebersicht(true);
  }

  /* ------------------------------------------------------------ Übersicht */
  async function ladeStand() {
    zustand.stand = await rufe("stand");
    zustand.signatur = zustand.stand.signatur;
    zustand.lauf = zustand.stand.lauf;
    zeigeUebersicht();
    zeigeLauf();
    zeigeVersion();
    if (zustand.seite === "auswertung") ladeAuswertung();
  }

  /* Versionsnummer im Kopf; gibt es auf GitHub eine neuere, ein Hinweis mit Link (aktualisierung.py) */
  function zeigeVersion() {
    const v = zustand.stand && zustand.stand.version;
    if (!v) return;
    $("#version").textContent = v.aktuell;
    const knopf = $("#update");
    knopf.hidden = !v.neu;
    knopf.textContent = v.neu ? `Version ${v.neu} verfügbar` : "";
  }

  function statusText(status, name) {
    if (!status) return { text: "", fehler: false };
    if (status === "läuft") return { text: "läuft …", fehler: false };
    if (status.startsWith("OK")) return { text: "fertig → " + (status.split("->")[1] || "").trim(), fehler: false };
    if (status.startsWith("PRÜFEN")) {
      const grund = /\((.*)\)/.exec(status);
      return { text: "nach Prüfen" + (grund ? ": " + grund[1] : ""), fehler: false };
    }
    if (status.startsWith("TEXT_ERNEUERT")) return { text: "Text erneuert", fehler: false };
    if (status.startsWith("FEHLER")) {
      // "FEHLER  datei.pdf: Grund  (Original blieb unverändert)" -> nur der Grund, der Name steht schon darüber
      let grund = status.replace(/^FEHLER\s+/, "").replace(/\s*\((?:Original|alte \.md) (?:blieb|bleibt) unverändert\)\s*$/, "");
      if (name && grund.startsWith(name + ": ")) grund = grund.slice(name.length + 2);
      return { text: "Fehler: " + grund + " Die Datei bleibt im Eingang.", fehler: true };
    }
    return { text: status, fehler: false };
  }

  /* Liste nur neu aufbauen, wenn sich ihr Inhalt geändert hat (Kennung), und dabei Fokus und Scrollstand
     erhalten. Sonst ginge im Takt (0,4 s während eines Laufs) der Tastaturfokus verloren, und ein Klick
     könnte ein Element treffen, das zwischen Drücken und Loslassen ersetzt wurde. Bedienbare Elemente in
     Listen tragen data-ziel, daran wird der Fokus nach dem Neuaufbau wiedergefunden. */
  function listeErneuern(liste, kennung, baue) {
    if (liste.dataset.kennung === kennung) return;
    const aktiv = document.activeElement;
    const drin = !!aktiv && liste.contains(aktiv);
    const ziel = drin ? aktiv.dataset.ziel : null;
    const stelle = drin ? Array.from(liste.querySelectorAll("[data-ziel]")).indexOf(aktiv) : -1;
    const scroll = liste.scrollTop;
    liste.textContent = "";
    baue(liste);
    liste.dataset.kennung = kennung;
    liste.scrollTop = scroll;
    if (!drin) return;
    // dasselbe Element; ist die Datei weg (verschoben), das an derselben Stelle; ist die Liste leer, die Überschrift
    // der Spalte. preventScroll: der Scrollstand oben gilt, Liste und Seite springen nicht zum Element.
    const ziele = Array.from(liste.querySelectorAll("[data-ziel]"));
    let neu = ziele.find(e => e.dataset.ziel === ziel) || ziele[Math.min(Math.max(stelle, 0), ziele.length - 1)];
    if (!neu) {
      neu = liste.closest(".spalte").querySelector("h2");
      neu.tabIndex = -1;
    }
    neu.focus({ preventScroll: true });
  }

  function zeigeUebersicht() {
    if (!zustand.stand) return;
    zeigeEingang();
    zeigePruefen();
    zeigeFertig();
    zeigeKennzahlen();
    zeigeDiagrammeUebersicht();
  }

  function zeigeEingang() {
    const s = zustand.stand;
    if (!s) return;
    // Eingang: Dateien des laufenden Laufs zuerst (mit Status), dann der Rest
    const eingang = new Map(s.eingang.map(e => [e.name, e]));
    const lauf = zustand.lauf && zustand.lauf.art === "Umwandlung" ? zustand.lauf : null;
    const eintraege = [];
    if (lauf) {
      for (const [name, status] of Object.entries(lauf.dateien)) {
        eintraege.push({ name, datei: eingang.get(name), status });
        eingang.delete(name);
      }
    }
    for (const e of eingang.values()) eintraege.push({ name: e.name, datei: e, status: zustand.fehler[e.name] });
    const kennung = JSON.stringify(eintraege.map(e => [e.name, e.datei && e.datei.format, e.datei && e.datei.groesse, e.status]));
    listeErneuern($("#liste-eingang"), kennung, liste => {
      for (const e of eintraege) {
        const li = element("li");
        // schon verarbeitete Dateien des Laufs liegen nicht mehr im Eingang: nur anzeigen
        const name = e.datei ? dateiKnopf("eingang", e.name, e.name, "original", `${e.name} öffnen`)
          : element("span", "name", e.name);
        name.title = e.datei ? `${e.name} öffnen` : e.name;
        const aktionen = element("span", "datei-aktionen");
        aktionen.append(element("span", "neben", e.datei ? `${e.datei.format} · ${groesse(e.datei.groesse)}` : ""));
        li.append(name, aktionen);
        const st = statusText(e.status, e.name);
        if (st.text) li.append(element("span", "unter" + (st.fehler ? " fehler-text" : ""), st.text));
        if (e.status === "läuft") li.classList.add("aktiv");
        if (st.fehler) li.classList.add("fehler");
        liste.appendChild(li);
      }
    });
    $("#anzahl-eingang").textContent = s.eingang.length ? zahl.format(s.eingang.length) : "";
    $("#leer-eingang").hidden = eintraege.length > 0;
    $("#eingang-liste-titel").hidden = !lauf || !eintraege.length;     // Stand je Datei gibt es nur bei Umwandlungen
  }

  function zeigePruefen() {
    const s = zustand.stand;
    if (!s) return;
    // Prüfen: Name öffnet die .md (dort den Kopfblock ergänzen), das Formatkürzel das Original
    listeErneuern($("#liste-pruefen"), JSON.stringify(s.pruefen), liste => {
      for (const e of s.pruefen) {
        const li = element("li");
        const aktionen = element("span", "datei-aktionen");
        if (e.format !== "?") aktionen.append(formatKnopf("pruefen", e.md, e.format, e.name));
        li.append(dateiKnopf("pruefen", e.md, e.name, "md", `${e.md} öffnen (Kopfblock ergänzen)`), aktionen);
        const unter = [e.grund, !e.bereit && !e.grund.includes(e.hinweis) ? e.hinweis : ""].filter(Boolean).join(" · ");
        if (unter) li.append(element("span", "unter", unter));
        if (e.bereit) li.append(element("span", "marke-bereit", "bereit zur Übernahme"));
        liste.appendChild(li);
      }
    });
    const bereit = s.pruefen.filter(e => e.bereit).length;
    $("#anzahl-pruefen").textContent = s.pruefen.length ? zahl.format(s.pruefen.length) + (bereit ? `, ${bereit} bereit` : "") : "";
    $("#leer-pruefen").hidden = s.pruefen.length > 0;
  }

  /* Dateien öffnen (Standardprogramm von Windows): Name = .md bzw. Datei im Eingang, Formatkürzel = Original */
  async function oeffnen(bereich, name, art) {
    const antwort = await rufe("datei_oeffnen", bereich, name, art);
    melde(antwort.ok ? `${antwort.datei} geöffnet` : antwort.grund);
  }
  function dateiKnopf(bereich, name, anzeige, art, titel) {
    const knopf = element("button", "name-knopf", anzeige);
    knopf.type = "button";
    knopf.title = titel;
    knopf.dataset.ziel = `${art}:${name}`;
    knopf.addEventListener("click", () => oeffnen(bereich, name, art));
    return knopf;
  }
  function formatKnopf(bereich, md, format, anzeige) {
    const knopf = element("button", "knopf-text format-knopf", format);
    knopf.type = "button";
    knopf.dataset.ziel = `original:${md}`;
    knopf.title = `Original öffnen (${format})`;
    knopf.setAttribute("aria-label", `${anzeige}: Original (${format}) öffnen`);
    knopf.addEventListener("click", () => oeffnen(bereich, md, "original"));
    return knopf;
  }

  function zeigeFertig() {
    const s = zustand.stand;
    if (!s) return;
    const filter = normal(zustand.filter.trim());
    const treffer = filter ? s.fertig.filter(e => normal(e.name).includes(filter)) : s.fertig;
    listeErneuern($("#liste-fertig"), filter + "\n" + JSON.stringify(treffer), liste => {
      const rest = document.createDocumentFragment();
      for (const e of treffer) {
        const li = element("li");
        const aktionen = element("span", "datei-aktionen");
        aktionen.append(element("span", "neben", datum(e.datum)));
        if (e.format !== "?") aktionen.append(formatKnopf("fertig", e.md, e.format, e.name));
        li.append(dateiKnopf("fertig", e.md, e.name, "md", `${e.name}.md öffnen`), aktionen);
        rest.appendChild(li);
      }
      liste.appendChild(rest);
    });
    $("#anzahl-fertig").textContent = filter ? `${zahl.format(treffer.length)} von ${zahl.format(s.fertig.length)}`
      : (s.fertig.length ? zahl.format(s.fertig.length) : "");
    const leer = $("#leer-fertig");
    leer.hidden = treffer.length > 0;
    leer.textContent = filter ? "Kein Treffer." : "Noch nichts fertig.";
  }

  function zeigeKennzahlen() {
    const k = zustand.stand.kennzahlen;
    const dl0 = $("#kennzahlen");
    const kennung = JSON.stringify(k);
    if (dl0.dataset.kennung === kennung) return;
    dl0.dataset.kennung = kennung;
    if (!k) {                                   // Kennzahlen rechnet Python noch im Hintergrund (viele Bücher)
      const dl = $("#kennzahlen");
      dl.textContent = "";
      for (const titel of ["Bücher in Fertig", "In Prüfen", "Seiten in Fertig", "Mit gedruckter Seitenzahl"]) {
        const div = element("div");
        const dd = element("dd", null, "…");
        dd.append(element("small", null, "wird berechnet"));
        div.append(element("dt", null, titel), dd);
        dl.appendChild(div);
      }
      return;
    }
    const felder = [
      ["Bücher in Fertig", zahl.format(k.fertig), ""],
      ["In Prüfen", zahl.format(k.pruefen), k.bereit ? `${zahl.format(k.bereit)} bereit` : ""],
      ["Seiten in Fertig", zahl.format(k.seiten), ""],
      ["Mit gedruckter Seitenzahl", prozent(k.gedruckt_anteil), k.gedruckt_anteil == null ? "noch keine neuen Marker"
        : k.gedruckt_erfasst < k.fertig ? `aus ${zahl.format(k.gedruckt_erfasst)} von ${zahl.format(k.fertig)} Büchern` : "der Seiten"],
    ];
    const dl = $("#kennzahlen");
    dl.textContent = "";
    for (const [titel, wert, zusatz] of felder) {
      const div = element("div");
      const dd = element("dd", null, wert);
      if (zusatz) dd.append(element("small", null, zusatz));
      div.append(element("dt", null, titel), dd);
      dl.appendChild(div);
    }
  }

  function laufDaten(laeufe, wert) {
    return laeufe.map(l => ({
      label: kurzdatum(l.lauf), wert: wert(l), reihe: l.art,
      tipp: `${datum(l.lauf)} · ${l.art}: ${anzahl(l.dateien, "Datei", "Dateien")}` + (l.pruefen ? `, ${l.pruefen} nach Prüfen` : "")
        + (l.fehler ? `, ${l.fehler} Fehler` : "") + (l.seiten_pro_min ? ` · ${zahl.format(l.seiten_pro_min)} Seiten/min` : ""),
    }));
  }

  function herkunftZeilen(h) {
    return [["Titel", "titel"], ["Autor", "autor"], ["Jahr", "jahr"]].map(([label, feld]) => ({ label, werte: h[feld] || {} }));
  }

  /* neu gezeichnet wird nur bei anderen Daten oder anderer Breite (sonst ginge der Tastaturfokus im Diagramm
     bei jeder Änderung der Ordner verloren); erzwingen = nach einem Seitenwechsel */
  function zeigeDiagrammeUebersicht(erzwingen) {
    const s = zustand.stand;
    if (!s || zustand.seite !== "uebersicht") return;
    const mini = $("#seite-uebersicht .mini");
    const kennung = JSON.stringify(s.mini) + "|" + mini.clientWidth;
    if (!erzwingen && mini.dataset.kennung === kennung) return;
    mini.dataset.kennung = kennung;
    const laeufe = s.mini.laeufe;
    D.saeulen($("#mini-laeufe"), laufDaten(laeufe, l => l.dateien), {
      hoehe: 132, reihen: LAUFARTEN.filter(r => laeufe.some(l => l.art === r.name)), leer: "Noch kein Lauf im Protokoll.",
      beschreibung: `Dateien je Lauf, ${anzahl(laeufe.length, "Lauf", "Läufe")}`,
    });
    D.gestapelt($("#mini-herkunft"), s.mini.herkunft ? herkunftZeilen(s.mini.herkunft) : [], HERKUNFT, {
      leer: s.mini.herkunft ? "Noch keine Bücher." : "Wird berechnet …", beschreibung: "Herkunft von Titel, Autor und Jahr",
    });
  }

  /* ------------------------------------------------------------ Lauf */
  function zeigeLauf() {
    const lauf = zustand.lauf;
    const block = $("#lauf");
    const knopf = $("#starten");
    document.body.classList.toggle("laeuft", !!lauf);
    for (const b of document.querySelectorAll("[data-werkzeug]")) b.disabled = !!lauf;
    if (!lauf) {
      block.hidden = true;
      knopf.textContent = "Starten";
      knopf.className = "knopf haupt";
      knopf.disabled = false;
      knopf.title = "Eingang verarbeiten, fertige Prüfen-Dateien übernehmen (Strg+Enter)";
      sperreEinstellungen(false);
      return;
    }
    knopf.textContent = lauf.abbrechen ? "Wird abgebrochen …" : "Abbrechen";
    knopf.className = "knopf gefahr";
    knopf.disabled = !!lauf.abbrechen;
    knopf.title = "Bricht nach der aktuellen Datei ab";
    sperreEinstellungen(true);
    block.hidden = false;
    block.textContent = "";
    const a = lauf.aktuell;
    const kopf = element("div", "lauf-kopf");
    kopf.append(element("span", "lauf-titel", lauf.art === "Umwandlung" ? "Wird umgewandelt" : lauf.art),
      element("span", null, (a ? `Datei ${a.nummer} von ${a.anzahl} · ` : "") + dauer(lauf.sekunden)));
    block.append(kopf);
    if (a) {
      const name = element("div", "lauf-name", a.name);
      name.title = a.name;
      const phase = element("div", "lauf-phase");
      phase.append(element("span", null, a.phase || "beginnt …"),
        element("span", null, a.gesamt ? `${zahl.format(a.erledigt)} / ${zahl.format(a.gesamt)}` : ""));
      block.append(name, phase);
    }
    const balken = element("div", "balken");
    balken.setAttribute("role", "progressbar");
    balken.setAttribute("aria-label", "Fortschritt der aktuellen Datei");
    const innen = element("span");
    if (a && a.gesamt) {
      const p = Math.round((a.erledigt / a.gesamt) * 100);
      innen.style.width = p + "%";
      balken.setAttribute("aria-valuemin", "0");
      balken.setAttribute("aria-valuemax", "100");
      balken.setAttribute("aria-valuenow", String(p));
    } else {
      balken.classList.add("unbestimmt");
    }
    balken.append(innen);
    block.append(balken);
    if (lauf.abbrechen) block.append(element("p", "hinweis", "Abbruch nach der aktuellen Datei."));
  }

  async function startenOderAbbrechen() {
    if (zustand.lauf) {
      await rufe("abbrechen");
      return holeEreignisse();
    }
    const antwort = await rufe("starten");
    if (!antwort.ok) melde(antwort.grund);
    zustand.fehler = {};
    await holeEreignisse();
  }

  /* ------------------------------------------------------------ Ereignisse und Laufprotokoll */
  function protokollZeile(zeit, text, fehler) {
    const ol = $("#protokoll-liste");
    const li = element("li", fehler ? "fehler-text" : null);
    li.append(element("time", null, zeit), document.createTextNode(text));
    ol.appendChild(li);
    while (ol.children.length > 1000) ol.removeChild(ol.firstChild);
    if (!ol.hidden) ol.scrollTop = ol.scrollHeight;
    $("#protokoll-letzte").textContent = text;
  }

  function laufName(art) {
    return LAUF_KURZ[art] || art;
  }
  function zusammenfassung(e) {
    if (e.fehler) return `${laufName(e.lauf_art)} abgebrochen, Fehler: ${e.fehler}`;
    const r = e.ergebnis || {};
    const ab = r.abgebrochen ? " (abgebrochen)" : "";
    if (e.lauf_art === "Umwandlung") {
      return `Umwandlung beendet${ab}: ${zahl.format(r.ok)} fertig, ${zahl.format(r.pruefen)} nach Prüfen, ` +
        `${zahl.format(r.fehler)} Fehler` + (r.nachgebessert ? `, ${zahl.format(r.nachgebessert)} aus Prüfen übernommen` : "");
    }
    if ("erneuert" in r) return `Text erneuert${ab}: ${anzahl(r.erneuert, "Buch", "Bücher")}`;
    if ("umbenannt" in r) return `Namen repariert${ab}: ${anzahl(r.umbenannt, "Datei", "Dateien")} umbenannt`;
    if ("zurueck" in r) return `Letzter Lauf rückgängig gemacht: ${anzahl(r.zurueck, "Datei", "Dateien")} an den alten Ort zurück`;
    if ("eintraege" in r) {
      const datei = String(r.datei || "").split(/[\\/]/).pop();
      return `Literaturliste exportiert: ${anzahl(r.eintraege, "Eintrag", "Einträge")}` + (datei ? ` in ${datei}` : "");
    }
    return `${laufName(e.lauf_art)} beendet`;
  }

  function verarbeiteEreignisse(antwort) {
    let ende = false;
    for (const e of antwort.ereignisse) {
      zustand.ereignis = Math.max(zustand.ereignis, e.nr);
      if (e.art === "meldung") protokollZeile(e.zeit, e.text, /^FEHLER|^\s*FEHLER/.test(e.text));
      else if (e.art === "lauf_beginnt") {
        if (e.lauf_art === "Umwandlung") zustand.fehler = {};
        const text = `${laufName(e.lauf_art)} gestartet`;
        protokollZeile(e.zeit, text);
        ansagen(text);
        melde("");                                  // alte Antwort auf eine Aktion passt nicht mehr
      } else if (e.art === "datei_fertig" && String(e.status).startsWith("FEHLER")) zustand.fehler[e.name] = e.status;
      else if (e.art === "lauf_ende") {
        ende = true;
        const text = zusammenfassung(e);
        protokollZeile(e.zeit, text, !!e.fehler);
        ansagen(text);
      }
    }
    const vorher = !!zustand.lauf;
    zustand.lauf = antwort.lauf;
    zeigeLauf();
    // im Takt nur der Eingang (Status je Datei); Prüfen, Fertig, Kennzahlen und Diagramme folgen der Signatur
    if (zustand.lauf || vorher || ende) zeigeEingang();
    if (ende && zustand.seite === "einstellungen") ladeEinstellungen();
    if (ende && zustand.seite === "auswertung") ladeAuswertung();
  }

  async function holeEreignisse() {
    verarbeiteEreignisse(await rufe("ereignisse", zustand.ereignis));
  }

  let taktLaeuft = false;
  async function takt() {
    if (taktLaeuft) return;
    taktLaeuft = true;
    try {
      await holeEreignisse();
      const signatur = await rufe("signatur");
      if (signatur !== zustand.signatur) await ladeStand();
    } catch (fehler) {
      melde(fehlerText(fehler));
    } finally {
      taktLaeuft = false;
      setTimeout(takt, zustand.lauf ? 400 : 1500);
    }
  }

  /* ------------------------------------------------------------ Hinzufügen und Ablegen */
  async function hinzufuegen() {
    const antwort = await rufe("hinzufuegen_dialog");
    if (antwort.hinweis) return melde(antwort.hinweis);
    const teile = [];
    if (antwort.kopiert.length) teile.push(`${anzahl(antwort.kopiert.length, "Datei", "Dateien")} nach Eingang kopiert`);
    if (antwort.abgelehnt.length) teile.push("abgelehnt: " + antwort.abgelehnt.map(([n, g]) => `${n} (${g})`).join(", "));
    if (teile.length) melde(teile.join("; "));
    await ladeStand();
  }

  function ablegenEinrichten() {
    let tiefe = 0;
    const hatDateien = e => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
    const zeige = an => {
      $("#ablegen").hidden = !an;
      if (an && zustand.seite !== "uebersicht") zeigeSeite("uebersicht");
    };
    document.addEventListener("dragenter", e => { if (hatDateien(e)) { tiefe++; zeige(true); } });
    document.addEventListener("dragleave", () => { tiefe = Math.max(0, tiefe - 1); if (!tiefe) zeige(false); });
    document.addEventListener("dragover", e => { if (hatDateien(e)) e.preventDefault(); });
    document.addEventListener("drop", e => {
      e.preventDefault();
      tiefe = 0;
      zeige(false);
      if (MODUS === "http") melde("In der Browser-Vorschau lassen sich keine Dateien ablegen.");
      else melde("Dateien werden nach Eingang kopiert …");
    });
  }

  /* ------------------------------------------------------------ Dialoge */
  function frage(titel, text, ja, nein) {
    const dialog = $("#frage-dialog");
    $("#frage-titel").textContent = titel;
    $("#frage-text").textContent = text;
    $("#frage-ja").textContent = ja;
    $("#frage-nein").textContent = nein;
    const vorher = document.activeElement;
    dialog.returnValue = "";
    dialog.showModal();
    $("#frage-nein").focus();
    return new Promise(los => dialog.addEventListener("close", () => {
      if (vorher && vorher.isConnected && typeof vorher.focus === "function") vorher.focus();
      los(dialog.returnValue === "ja");
    }, { once: true }));
  }

  async function werkzeugOeffnen(name) {
    menueSchliessen(false);
    if (zustand.lauf) return melde("Während eines Laufs nicht möglich.");
    const v = await rufe("werkzeug_vorschau", name);
    const dialog = $("#werkzeug-dialog");
    $("#werkzeug-titel").textContent = v.titel;
    $("#werkzeug-hinweis").textContent = v.hinweis;
    const liste = $("#werkzeug-liste");
    liste.textContent = "";
    for (const e of v.eintraege) {
      const li = element("li");
      li.append(element("span", "alt", e.alt));
      if (e.neu) li.append(element("span", "neu", e.neu));
      liste.appendChild(li);
    }
    liste.setAttribute("aria-label", anzahl(v.anzahl, "Eintrag", "Einträge"));
    const ausfuehren = $("#werkzeug-ausfuehren");
    ausfuehren.hidden = v.leer;
    ausfuehren.textContent = `${AKTION[name]} (${zahl.format(v.anzahl)})`;
    $("#werkzeug-abbrechen").textContent = v.leer ? "Schließen" : "Abbrechen";
    dialog.returnValue = "";
    dialog.showModal();
    $("#werkzeug-abbrechen").focus();
    dialog.addEventListener("close", async () => {
      $("#werkzeuge-knopf").focus();                      // der Menüeintrag ist zu, Fokus zurück auf den Menüknopf
      if (dialog.returnValue !== "ausfuehren") return;
      const antwort = await rufe("werkzeug_starten", name);
      if (!antwort.ok) melde(antwort.grund);
      await holeEreignisse();
    }, { once: true });
  }

  /* Werkzeug-Menü: Pfeiltasten, Esc, Klick außerhalb */
  function menueOeffnen() {
    const liste = $("#werkzeuge-menue");
    liste.hidden = false;
    $("#werkzeuge-knopf").setAttribute("aria-expanded", "true");
    const erster = liste.querySelector("button:not(:disabled)");
    if (erster) erster.focus();
  }
  function menueSchliessen(fokus) {
    const liste = $("#werkzeuge-menue");
    if (liste.hidden) return;
    liste.hidden = true;
    $("#werkzeuge-knopf").setAttribute("aria-expanded", "false");
    if (fokus) $("#werkzeuge-knopf").focus();
  }
  function menueEinrichten() {
    const knopf = $("#werkzeuge-knopf");
    const liste = $("#werkzeuge-menue");
    knopf.addEventListener("click", () => (liste.hidden ? menueOeffnen() : menueSchliessen(false)));
    knopf.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); menueOeffnen(); }
    });
    liste.addEventListener("keydown", e => {
      const knoepfe = Array.from(liste.querySelectorAll("button:not(:disabled)"));
      const i = knoepfe.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); knoepfe[(i + 1) % knoepfe.length].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); knoepfe[(i - 1 + knoepfe.length) % knoepfe.length].focus(); }
      else if (e.key === "Home") { e.preventDefault(); knoepfe[0].focus(); }
      else if (e.key === "End") { e.preventDefault(); knoepfe[knoepfe.length - 1].focus(); }
      else if (e.key === "Escape") { e.preventDefault(); menueSchliessen(true); }
      else if (e.key === "Tab") menueSchliessen(false);
    });
    for (const b of liste.querySelectorAll("[data-werkzeug]")) {
      b.addEventListener("click", () => werkzeugOeffnen(b.dataset.werkzeug));
    }
    document.addEventListener("click", e => { if (!e.target.closest(".menue")) menueSchliessen(false); });
  }

  /* ------------------------------------------------------------ Einstellungen */
  let zeilenNummer = 0;
  const tooltip = { el: null, zeit: null };

  function nachkommastellen(schritt) {
    const s = String(schritt);
    return s.includes(".") ? s.split(".")[1].length : 0;
  }
  const formate = new Map();                    // je Anzahl Nachkommastellen ein Format, nicht je Aufruf
  function festFormat(stellen) {
    if (!formate.has(stellen)) {
      formate.set(stellen, new Intl.NumberFormat("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen }));
    }
    return formate.get(stellen);
  }
  function wertText(e, wert) {
    if (e.typ === "bool") return wert ? "an" : "aus";
    if (e.typ === "wahl") return (e.optionen.find(o => o[0] === wert) || [wert, wert])[1];
    const text = festFormat(e.typ === "float" ? nachkommastellen(e.schritt) : 0).format(wert);
    return e.einheit ? `${text} ${e.einheit}` : text;
  }

  async function ladeEinstellungen() {
    zustand.einstellungen = await rufe("einstellungen");
    zeigeEinstellungen();
  }

  function zeigeEinstellungen() {
    const daten = zustand.einstellungen;
    if (!daten) return;
    const datei = $("#einstellungen-datei");
    datei.textContent = "Änderungen werden sofort in Einstellungen.json gespeichert und gelten ab dem nächsten Lauf.";
    datei.title = daten.datei;
    const offen = $("#experte").open;
    for (const [stufe, ziel] of [["normal", "#einstellungen-normal"], ["experte", "#einstellungen-experte"]]) {
      const container = $(ziel);
      container.textContent = "";
      for (const gruppe of daten.gruppen) {
        const eintraege = daten.eintraege.filter(e => e.stufe === stufe && e.gruppe === gruppe);
        if (!eintraege.length) continue;
        const abschnitt = element("section", "gruppe");
        const id = `gruppe-${stufe}-${gruppe.replace(/\W+/g, "-")}`;
        const titel = element(stufe === "normal" ? "h2" : "h3", null, gruppe);
        titel.id = id;
        abschnitt.setAttribute("aria-labelledby", id);
        abschnitt.append(titel, ...eintraege.map(einstellungsZeile));
        container.appendChild(abschnitt);
      }
    }
    const experten = daten.eintraege.filter(e => e.stufe === "experte");
    const geaendert = experten.filter(e => e.wert !== e.standard).length;
    $("#experte-anzahl").textContent = `${experten.length} Werte, an 58 Büchern gemessen` + (geaendert ? `, ${geaendert} geändert` : "");
    $("#experte").open = offen || speicherLesen("experte") === "offen";
    sperreEinstellungen(!!zustand.lauf || daten.gesperrt);
  }

  function einstellungsZeile(e) {
    const id = `einst-${++zeilenNummer}`;
    const zeile = element("div", "zeile" + (e.wert !== e.standard ? " geaendert" : ""));
    zeile.dataset.schluessel = e.schluessel;
    zeile.dataset.tooltip = e.tooltip;
    const label = element("label");
    label.htmlFor = id;
    label.append(element("span", null, e.titel), element("span", "schluessel", e.name));
    const beschreibung = element("span", "nur-vorlesen", e.tooltip);
    beschreibung.id = id + "-hilfe";
    const steuer = element("div", "steuer");
    const wert = element("span", "wert", wertText(e, e.wert));
    let eingabe;
    if (e.typ === "bool") {
      eingabe = element("input");
      eingabe.type = "checkbox";
      eingabe.setAttribute("role", "switch");
      eingabe.checked = !!e.wert;
      eingabe.addEventListener("change", () => setzenPlanen(e, eingabe.checked));
      wert.className = "schalter-text";
      wert.setAttribute("aria-hidden", "true");
      steuer.append(eingabe, wert);
    } else if (e.typ === "wahl") {
      eingabe = element("select");
      for (const [w, text] of e.optionen) {
        const o = element("option", null, text);
        o.value = w;
        o.selected = w === e.wert;
        eingabe.appendChild(o);
      }
      eingabe.addEventListener("change", () => setzenPlanen(e, eingabe.value));
      steuer.append(eingabe);
      wert.hidden = true;
      steuer.append(wert);
    } else {
      const regler = element("div", "regler");
      regler.style.setProperty("--p", String((e.standard - e.min) / (e.max - e.min)));
      const marke = element("span", "standardmarke");
      marke.title = "Standard: " + wertText(e, e.standard);
      eingabe = element("input");
      eingabe.type = "range";
      eingabe.min = e.min;
      eingabe.max = e.max;
      eingabe.step = e.schritt;
      eingabe.value = e.wert;
      eingabe.setAttribute("aria-valuetext", wertText(e, e.wert));
      eingabe.addEventListener("input", () => {
        const v = Number(eingabe.value);
        wert.textContent = wertText(e, v);
        eingabe.setAttribute("aria-valuetext", wertText(e, v));
      });
      eingabe.addEventListener("change", () => setzenPlanen(e, Number(eingabe.value)));
      regler.append(marke, eingabe);
      steuer.append(regler, wert);
    }
    eingabe.id = id;
    eingabe.setAttribute("aria-describedby", beschreibung.id);
    eingabe.dataset.steuer = "1";
    const zurueck = element("button", "knopf-text zuruecksetzen", "Standard");
    zurueck.type = "button";
    zurueck.disabled = e.wert === e.standard;
    zurueck.setAttribute("aria-label", `${e.titel} auf Standard zurücksetzen (${wertText(e, e.standard)})`);
    zurueck.title = "Standard: " + wertText(e, e.standard);
    zurueck.addEventListener("click", async () => {
      const antwort = await rufe("einstellungen_zuruecksetzen", e.schluessel);
      if (!antwort.ok) return melde(antwort.grund);
      zustand.einstellungen = antwort;
      zeigeEinstellungen();
      const neu = document.querySelector(`.zeile[data-schluessel="${e.schluessel}"] [data-steuer]`);
      if (neu) neu.focus();
      melde(`${e.titel}: Standard wiederhergestellt`);
    });
    zeile.append(label, steuer, zurueck, beschreibung);
    return zeile;
  }

  /* Speichern: kurz gesammelt (Pfeiltasten am Regler feuern je Schritt ein change) und strikt nacheinander,
     damit nie ein älterer Wert einen neueren überholt. Die Zeile wird an Ort und Stelle aktualisiert. */
  let schlange = Promise.resolve();
  const geplant = new Map();
  function setzenPlanen(e, wert) {
    clearTimeout(geplant.get(e.schluessel));
    geplant.set(e.schluessel, setTimeout(() => {
      geplant.delete(e.schluessel);
      schlange = schlange.then(() => setzen(e, wert)).catch(f => melde("Speichern fehlgeschlagen. " + fehlerText(f)));
    }, 250));
  }

  async function setzen(e, wert) {
    const antwort = await rufe("einstellung_setzen", e.schluessel, wert);
    const zeile = document.querySelector(`.zeile[data-schluessel="${e.schluessel}"]`);
    if (!zeile) return;
    const alt = zeile.querySelector(".fehlermeldung");
    if (alt) alt.remove();
    if (!antwort.ok) {
      zeile.append(element("p", "fehlermeldung", antwort.grund));
      return;
    }
    const neu = antwort.eintrag;
    const i = zustand.einstellungen.eintraege.findIndex(x => x.schluessel === e.schluessel);
    zustand.einstellungen.eintraege[i] = neu;
    zeile.classList.toggle("geaendert", neu.wert !== neu.standard);
    zeile.querySelector(".zuruecksetzen").disabled = neu.wert === neu.standard;
    if (!geplant.has(e.schluessel)) {                     // nur wenn nicht schon der nächste Wert unterwegs ist
      const eingabe = zeile.querySelector("[data-steuer]");
      if (neu.typ === "bool") eingabe.checked = !!neu.wert; else eingabe.value = neu.wert;
      const anzeige = zeile.querySelector(".wert, .schalter-text");
      if (anzeige) anzeige.textContent = wertText(neu, neu.wert);
      if (neu.typ !== "bool" && neu.typ !== "wahl") eingabe.setAttribute("aria-valuetext", wertText(neu, neu.wert));
    }
    melde(`${neu.titel}: ${wertText(neu, neu.wert)} gespeichert`);
    const experten = zustand.einstellungen.eintraege.filter(x => x.stufe === "experte");
    const geaendert = experten.filter(x => x.wert !== x.standard).length;
    $("#experte-anzahl").textContent = `${experten.length} Werte, an 58 Büchern gemessen` + (geaendert ? `, ${geaendert} geändert` : "");
  }

  function sperreEinstellungen(gesperrt) {
    $("#einstellungen-sperre").hidden = !gesperrt;
    for (const e of document.querySelectorAll("#seite-einstellungen input, #seite-einstellungen select, #seite-einstellungen .zuruecksetzen, #alle-zuruecksetzen")) {
      if (gesperrt) { e.dataset.warAktiv = e.disabled ? "" : "1"; e.disabled = true; }
      else if (e.dataset.warAktiv !== undefined) { e.disabled = e.dataset.warAktiv !== "1"; delete e.dataset.warAktiv; }
    }
  }

  /* Tooltip: nach 600 ms bei Maus oder Tastaturfokus; Esc schließt. Der Text steht im Element, auf das
     aria-describedby zeigt (Screenreader lesen ihn so sofort). Quellen: Einstellungszeilen (Anker: die Beschriftung)
     und Elemente mit data-tipp (z. B. die Werkzeuge im Menü, data-tipp="links": links daneben statt darunter). */
  function tippQuelle(ziel) {
    if (!ziel || !ziel.closest) return null;
    const zeile = ziel.closest("#seite-einstellungen .zeile");
    if (zeile) return { steuer: zeile.querySelector("[data-steuer]"), anker: zeile.querySelector("label"), seite: "unten" };
    const el = ziel.closest("[data-tipp]");
    return el ? { steuer: el, anker: el, seite: el.dataset.tipp || "unten" } : null;
  }
  function tooltipZeigen(quelle) {
    const id = quelle.steuer && quelle.steuer.getAttribute("aria-describedby");
    const text = id && document.getElementById(id) ? document.getElementById(id).textContent : "";
    if (!text || !quelle.anker.isConnected || quelle.anker.offsetParent === null) return;
    const el = $("#tooltip");
    el.textContent = text;
    el.hidden = false;
    const r = quelle.anker.getBoundingClientRect();
    const breite = el.offsetWidth, hoehe = el.offsetHeight;
    let x = r.left, y = r.bottom + 6;
    if (quelle.seite === "links" && r.left - breite - 8 >= 8) { x = r.left - breite - 8; y = r.top; }
    if (y + hoehe > window.innerHeight - 8) y = Math.max(8, r.top - hoehe - 6);
    x = Math.max(8, Math.min(x, window.innerWidth - breite - 8));
    el.style.left = x + "px";
    el.style.top = y + "px";
  }
  function tooltipVerbergen() {
    clearTimeout(tooltip.zeit);
    tooltip.zeit = null;
    $("#tooltip").hidden = true;
  }
  function tooltipEinrichten() {
    const planen = quelle => {
      clearTimeout(tooltip.zeit);
      tooltip.zeit = setTimeout(() => tooltipZeigen(quelle), 600);
    };
    const gleich = (a, b) => a && b && a.steuer === b.steuer;
    document.addEventListener("pointerover", e => {
      const quelle = tippQuelle(e.target);
      if (quelle && !gleich(quelle, tippQuelle(e.relatedTarget))) planen(quelle);
    });
    document.addEventListener("pointerout", e => {
      const quelle = tippQuelle(e.target);
      if (quelle && !gleich(quelle, tippQuelle(e.relatedTarget))) tooltipVerbergen();
    });
    document.addEventListener("focusin", e => {
      const quelle = tippQuelle(e.target);
      if (quelle && e.target === quelle.steuer) planen(quelle); else tooltipVerbergen();
    });
    document.addEventListener("focusout", tooltipVerbergen);
    document.addEventListener("keydown", e => { if (e.key === "Escape") tooltipVerbergen(); });
    document.addEventListener("click", tooltipVerbergen);
    main().addEventListener("scroll", tooltipVerbergen, { passive: true });
  }

  /* ------------------------------------------------------------ Auswertung */
  async function ladeAuswertung() {
    zustand.auswertung = await rufe("auswertung");
    zeigeAuswertung();
  }

  /* true, wenn Daten oder Breite anders sind als beim letzten Zeichnen. Im Lauf ändert sich die Auswertung je
     Datei; unveränderte Diagramme bleiben stehen, damit ein per Pfeiltaste gewählter Wert nicht verloren geht. */
  function neuZeichnen(ziel, daten) {
    const kennung = JSON.stringify(daten) + "|" + ziel.clientWidth;
    if (ziel.dataset.kennung === kennung) return false;
    ziel.dataset.kennung = kennung;
    return true;
  }

  function zeigeAuswertung() {
    const a = zustand.auswertung;
    if (!a || zustand.seite !== "auswertung") return;
    if (neuZeichnen($("#d-bereiche"), a.bestand.bereiche)) {
      D.balken($("#d-bereiche"), Object.entries(a.bestand.bereiche).map(([label, wert]) => ({ label, wert })),
        { beschreibung: "Dateien je Bereich" });
    }
    if (neuZeichnen($("#d-formate"), a.bestand.formate)) {
      D.balken($("#d-formate"), Object.entries(a.bestand.formate).map(([label, wert]) => ({ label, wert })),
        { beschreibung: "Dateien je Format", leer: "Keine Dateien." });
    }
    const mitTempo = a.laeufe.filter(l => l.seiten_pro_min);
    if (neuZeichnen($("#d-tempo"), mitTempo)) {
      D.saeulen($("#d-tempo"), laufDaten(mitTempo, l => l.seiten_pro_min).map((d, i) => Object.assign(d, {
        tipp: `${datum(mitTempo[i].lauf)} · ${mitTempo[i].art}: ${zahl.format(mitTempo[i].seiten_pro_min)} Seiten/min ` +
          `(${zahl.format(mitTempo[i].seiten)} Seiten in ${dauer(mitTempo[i].dauer_s)})`,
      })), { hoehe: 180, reihen: LAUFARTEN.filter(r => mitTempo.some(l => l.art === r.name)),
        beschreibung: "Seiten pro Minute je Lauf", leer: "Noch kein Lauf mit Dauer und Seitenzahl." });
    }
    if (neuZeichnen($("#d-dauer"), a.dauern)) {
      D.streuung($("#d-dauer"), a.dauern.map(d => ({ x: d.seiten, y: d.dauer_s,
        tipp: `${d.name}: ${zahl.format(d.seiten)} Seiten, ${dauer(d.dauer_s)}` })),
      { hoehe: 200, xName: "Seiten", yName: "Sekunden", beschreibung: "Dauer gegen Seitenzahl je Datei",
        leer: "Noch keine Umwandlung mit Dauer." });
    }
    if (neuZeichnen($("#d-herkunft"), a.herkunft)) {
      D.gestapelt($("#d-herkunft"), herkunftZeilen(a.herkunft), HERKUNFT,
        { beschreibung: "Herkunft von Titel, Autor und Jahr", leer: "Noch keine Bücher." });
    }
    if (neuZeichnen($("#d-gruende"), a.pruefgruende)) {
      D.balken($("#d-gruende"), a.pruefgruende.map(([label, wert]) => ({ label, wert })),
        { beschreibung: "Häufigste Prüfgründe", leer: "Keine Datei in Prüfen.", farbe: "grau-2" });
    }
    D.meter($("#d-ieee"), a.ieee[0], a.ieee[1], { beschreibung: "Bücher mit vollständiger Quellenangabe",
      text: "Vollständig heißt: Verlag und Ort über DOI/ISBN nachgeschlagen, oder Norm.", leer: "Noch keine Bücher." });

    const s = a.textsummen;
    const hinweis = $("#text-hinweis");
    hinweis.textContent = s.buecher === 0 ? "Noch keine Bücher in Fertig." :
      `Je Punkt der erreichte Wert und die höchstmögliche Anzahl über ${zahl.format(s.buecher)} Bücher in Fertig` + (s.aktuell < s.buecher
        ? `; ${zahl.format(s.buecher - s.aktuell)} davon sind mit einem älteren Verfahren erzeugt. Punkte, deren Verfahren dort noch nicht lief, zählen nur die übrigen Bücher („Werkzeuge → Text erneuern“ holt das nach).`
        : ".");
    // je Punkt: erreichter Wert / höchstmögliche Anzahl, gezählt über die Bücher, bei denen das Verfahren lief
    const dl = $("#summen");
    dl.textContent = "";
    for (const p of a.textqualitaet) {
      const div = element("div");
      const dd = element("dd", null, zahl.format(p.wert));
      dd.append(element("small", "max", `/ ${zahl.format(p.max)}`));
      const unter = element("p", "summe-unter", p.max ? `${prozent(p.wert / p.max)} von ${p.nenner}` : `keine ${p.nenner}`);
      if (p.buecher < p.alle) unter.textContent += ` · aus ${zahl.format(p.buecher)} von ${zahl.format(p.alle)} Büchern`;
      div.append(element("dt", null, p.titel), dd, unter);
      dl.appendChild(div);
    }
    const tbody = $("#offene-stellen tbody");
    tbody.textContent = "";
    if (!a.offene_stellen.length) {
      const tr = element("tr");
      const td = element("td", "leer", "Keine offenen Stellen gezählt.");
      td.colSpan = 6;
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    for (const b of a.offene_stellen) {
      const tr = element("tr");
      const name = element("td", null, b.name);
      name.title = b.name;
      tr.append(name, ...[b.seiten, b.fragezeichen, b.unsicher, b.nur_pdf].map(w => element("td", "zahl", zahl.format(w))),
        element("td", "zahl", zahlFest1.format(b.je_100)));
      tbody.appendChild(tr);
    }
  }

  /* ------------------------------------------------------------ Start */
  function main() { return $("#inhalt"); }

  function tastaturEinrichten() {
    document.addEventListener("keydown", e => {
      if (document.querySelector("dialog[open]")) return;
      if (e.ctrlKey && !e.altKey && !e.shiftKey) {
        if (e.key === "o" || e.key === "O") { e.preventDefault(); hinzufuegen(); }
        else if (e.key === "Enter") { e.preventDefault(); startenOderAbbrechen(); }
        else if (["1", "2", "3"].includes(e.key)) {
          e.preventDefault();
          zeigeSeite(["uebersicht", "auswertung", "einstellungen"][Number(e.key) - 1]);
        }
      }
    });
  }

  function groesseBeobachten() {
    let warte = null;
    new ResizeObserver(() => {
      clearTimeout(warte);
      warte = setTimeout(() => {
        if (zustand.seite === "uebersicht") zeigeDiagrammeUebersicht();
        if (zustand.seite === "auswertung") zeigeAuswertung();
      }, 120);
    }).observe(main());
  }

  window.app = {
    async schliessenFragen() {
      const ja = await frage("Ein Lauf ist noch aktiv",
        "Nach der aktuellen Datei beenden und das Fenster schließen? Die angefangene Datei wird noch fertig.",
        "Beenden und schließen", "Weiterlaufen lassen");
      if (ja) {
        await rufe("schliessen_anfragen");
        melde("Das Fenster schließt nach der aktuellen Datei.");
      }
    },
  };

  function einrichten() {
    // Fehler einer Python-Abfrage, die keine Stelle selbst behandelt, landen sichtbar in der Statuszeile
    window.addEventListener("unhandledrejection", e => melde(fehlerText(e.reason)));
    // ?thema=hell|dunkel und ?seite=... nur fuer Tests und Screenshots (werkzeuge/ui_vorschau.py)
    const thema = new URLSearchParams(location.search).get("thema");
    if (thema === "hell" || thema === "dunkel") document.documentElement.dataset.theme = thema === "hell" ? "light" : "dark";
    for (const b of document.querySelectorAll(".nav")) b.addEventListener("click", () => zeigeSeite(b.dataset.seite));
    $("#starten").addEventListener("click", startenOderAbbrechen);
    $("#hinzufuegen").addEventListener("click", hinzufuegen);
    $("#update").addEventListener("click", () => rufe("update_oeffnen"));
    $("#filter-fertig").addEventListener("input", e => { zustand.filter = e.target.value; zeigeFertig(); });
    for (const b of document.querySelectorAll("[data-ordner]")) {
      b.addEventListener("click", async () => {
        const antwort = await rufe("ordner_oeffnen", b.dataset.ordner);
        melde(antwort.ok ? `Ordner geöffnet: ${antwort.ordner}` : antwort.grund);
      });
    }
    $("#protokoll-knopf").addEventListener("click", e => {
      const offen = e.currentTarget.getAttribute("aria-expanded") !== "true";
      e.currentTarget.setAttribute("aria-expanded", String(offen));
      $("#protokoll-liste").hidden = !offen;
      speicherSchreiben("protokoll", offen ? "offen" : "zu");
      if (offen) $("#protokoll-liste").scrollTop = $("#protokoll-liste").scrollHeight;
    });
    if (speicherLesen("protokoll") === "offen") $("#protokoll-knopf").click();
    if (new URLSearchParams(location.search).get("experte") === "offen") $("#experte").open = true;
    $("#experte").addEventListener("toggle", e => speicherSchreiben("experte", e.target.open ? "offen" : "zu"));
    $("#alle-zuruecksetzen").addEventListener("click", async () => {
      if (!await frage("Alle Einstellungen zurücksetzen?", "Alle Werte gehen auf den Standard zurück; Einstellungen.json enthält danach keine Abweichungen mehr.",
        "Alle zurücksetzen", "Abbrechen")) return;
      const antwort = await rufe("einstellungen_zuruecksetzen", null);
      if (!antwort.ok) return melde(antwort.grund);
      zustand.einstellungen = antwort;
      zeigeEinstellungen();
      melde("Alle Einstellungen auf Standard zurückgesetzt");
    });
    menueEinrichten();
    ablegenEinrichten();
    tooltipEinrichten();
    tastaturEinrichten();
    groesseBeobachten();
    const seite = new URLSearchParams(location.search).get("seite") || speicherLesen("seite");
    zeigeSeite(["uebersicht", "auswertung", "einstellungen"].includes(seite) ? seite : "uebersicht");
    ladeStand().catch(f => melde(fehlerText(f))).finally(takt);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", einrichten);
  else einrichten();
})();
