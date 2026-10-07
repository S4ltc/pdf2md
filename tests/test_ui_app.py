"""Schnittstelle des Fensters (ui_app.Api) ohne Fenster: Lauf im Thread, Ereignisse, Einstellungen, Werkzeuge."""
import json
import sys
import time

import pytest

import einstellungen
import pdf2md
import ui_app
from conftest import FUELLTEXT, erzeuge_buch, erzeuge_pdf


@pytest.fixture
def basis(tmp_path, monkeypatch):
    for name in ("EINGANG", "FERTIG", "PRUEFEN", "PROTOKOLL", "SICHERUNG"):
        monkeypatch.setattr(pdf2md, name, getattr(pdf2md, name))           # nach dem Test zuruecksetzen
    (tmp_path / "Eingang").mkdir()
    # wie conftest.arbeitsordner: kein Netz, keine (langsame) Formelreparatur
    (tmp_path / einstellungen.DATEINAME).write_text(
        json.dumps({"pdf2md.ONLINE_ABGLEICH": False, "pdf2md.FORMELN_REPARIEREN": False}), encoding="utf-8")
    yield tmp_path
    einstellungen.anwenden(einstellungen.standardwerte())


@pytest.fixture
def api(basis):
    a = ui_app.Api(basis)
    yield a
    a.abbrechen()
    a._warten(60)


def warte_auf(api, art, zeit=60):
    ende = time.time() + zeit
    while time.time() < ende:
        for e in api.ereignisse(0)["ereignisse"]:
            if e["art"] == art:
                return e
        time.sleep(0.05)
    raise AssertionError(f"kein Ereignis {art}")


def test_api_setzt_ablage_und_einstellungen(api, basis):
    assert pdf2md.EINGANG == basis / "Eingang" and pdf2md.PROTOKOLL == basis / "Protokoll.csv"
    assert pdf2md.ONLINE_ABGLEICH is False and pdf2md.FORMELN_REPARIEREN is False


def test_lauf_meldet_ereignisse_und_endet(api, basis):
    erzeuge_buch(basis / "Eingang" / "a.pdf")
    assert api.starten() == {"ok": True}
    ende = warte_auf(api, "lauf_ende")
    assert ende["fehler"] is None and ende["ergebnis"]["ok"] == 1
    arten = [e["art"] for e in api.ereignisse(0)["ereignisse"]]
    assert arten[0] == "lauf_beginnt" and arten[1] == "datei_beginnt" and "fortschritt" in arten
    assert "meldung" in arten and "datei_fertig" in arten
    assert api.ereignisse(0)["lauf"] is None
    stand = api.stand()
    assert stand["fertig"][0]["name"] == "Testbuch - Anna Beispiel - 2019" and stand["eingang"] == []
    assert stand["kennzahlen"]["fertig"] == 1 and stand["kennzahlen"]["seiten"] == 2
    assert stand["mini"]["laeufe"][0]["dateien"] == 1
    json.dumps(stand)                                                          # alles muss nach JavaScript


def test_ereignisse_nach_nummer(api, basis):
    api._ereignis("meldung", text="eins")
    api._ereignis("meldung", text="zwei")
    alle = api.ereignisse(0)
    assert [e["text"] for e in api.ereignisse(alle["letzte"] - 1)["ereignisse"]] == ["zwei"]


def test_zweiter_start_waehrend_lauf_wird_abgelehnt_und_abbruch(api, basis):
    for n in "abc":
        erzeuge_buch(basis / "Eingang" / f"{n}.pdf", titel=f"Buch {n}")
    assert api.starten()["ok"]
    assert api.starten() == {"ok": False, "grund": "Es läuft bereits ein Lauf."}
    assert api.einstellungen()["gesperrt"]
    assert not api.einstellung_setzen("tabellen.TOLERANZ", 3)["ok"]
    api.abbrechen()
    ende = warte_auf(api, "lauf_ende")
    assert ende["ergebnis"]["abgebrochen"]
    assert len(list((basis / "Eingang").glob("*.pdf"))) >= 2                  # nach hoechstens einer Datei Schluss


def test_einstellung_setzen_speichert_und_wendet_an(api, basis):
    import tabellen
    antwort = api.einstellung_setzen("tabellen.TOLERANZ", "3")
    assert antwort["ok"] and antwort["eintrag"]["wert"] == 3.0
    gespeichert = json.loads((basis / einstellungen.DATEINAME).read_text(encoding="utf-8"))
    assert gespeichert["tabellen.TOLERANZ"] == 3.0 and tabellen.MIN_UEBERSTAND == 9.0
    assert not api.einstellung_setzen("zitierdaten.USER_AGENT", "x")["ok"]
    api.einstellungen_zuruecksetzen("tabellen.TOLERANZ")
    assert "tabellen.TOLERANZ" not in json.loads((basis / einstellungen.DATEINAME).read_text(encoding="utf-8"))
    api.einstellungen_zuruecksetzen()
    assert json.loads((basis / einstellungen.DATEINAME).read_text(encoding="utf-8")) == {}
    assert pdf2md.ONLINE_ABGLEICH is True
    json.dumps(api.einstellungen())


def test_werkzeug_vorschau_aendert_nichts_und_start_fuehrt_sie_aus(api, basis):
    fertig = basis / "Fertig"
    fertig.mkdir()
    kopf = {"titel": "Beispielelemente 1", "autor": "Erika Muster", "jahr": "2023"}
    (fertig / "Mein Buch.md").write_text(pdf2md.kopf_schreiben(kopf) + "Text", encoding="utf-8")
    (fertig / "Mein Buch.pdf").write_bytes(b"pdf")
    assert api.werkzeug_starten("namen") == {"ok": False, "grund": "Erst die Vorschau öffnen."}
    vorschau = api.werkzeug_vorschau("namen")
    assert vorschau["eintraege"] == [{"alt": "Mein Buch", "neu": "Beispielelemente 1 - Erika Muster - 2023"}]
    assert (fertig / "Mein Buch.pdf").exists()
    json.dumps(vorschau)
    assert api.werkzeug_starten("namen")["ok"]
    assert warte_auf(api, "lauf_ende")["ergebnis"]["umbenannt"] == 1
    assert (fertig / "Beispielelemente 1 - Erika Muster - 2023.pdf").exists()

    vorschau = api.werkzeug_vorschau("rueckgaengig")                          # der Umbenennen-Lauf
    assert vorschau["anzahl"] == 1 and vorschau["eintraege"][0]["alt"].startswith("Beispielelemente")
    json.dumps(vorschau)


def test_leere_vorschauen(api):
    for name in ui_app.WERKZEUGE:
        vorschau = api.werkzeug_vorschau(name)
        assert vorschau["leer"] and vorschau["hinweis"]
    assert "fehler" in api.werkzeug_vorschau("gibt_es_nicht")


def test_text_erneuern_als_werkzeug(api, basis):
    erzeuge_buch(basis / "Eingang" / "a.pdf")
    api.starten()
    warte_auf(api, "lauf_ende")
    md = next((basis / "Fertig").glob("*.md"))
    md.write_text(md.read_text(encoding="utf-8").replace(f'textquelle: "{pdf2md.erwartete_textquelle()}"',
                                                         'textquelle: "PDFium"'), encoding="utf-8")
    api._ereignisliste.clear()
    assert api.werkzeug_vorschau("text")["anzahl"] == 1
    assert api.werkzeug_starten("text")["ok"]
    ende = warte_auf(api, "lauf_ende")
    assert ende["ergebnis"] == {"erneuert": 1, "abgebrochen": False}
    assert any(e["art"] == "datei_fertig" for e in api.ereignisse(0)["ereignisse"])


def test_hinzufuegen_kopiert_nach_eingang(api, basis, tmp_path_factory):
    quelle = tmp_path_factory.mktemp("quelle")
    erzeuge_pdf(quelle / "neu.pdf", ["x", FUELLTEXT])
    (quelle / "notiz.txt").write_text("x")
    antwort = api.hinzufuegen([str(quelle / "neu.pdf"), str(quelle / "notiz.txt")])
    assert antwort == {"kopiert": ["neu.pdf"], "abgelehnt": [["notiz.txt", "Format nicht unterstützt"]]}
    assert [e["name"] for e in api.stand()["eingang"]] == ["neu.pdf"]
    assert "Dateidialog" in api.hinzufuegen_dialog()["hinweis"]               # ohne Fenster kein Dialog


def test_auswertung_hat_alle_abschnitte(api, basis):
    erzeuge_buch(basis / "Eingang" / "a.pdf")
    erzeuge_pdf(basis / "Eingang" / "b.pdf", ["x", FUELLTEXT])
    api.starten()
    warte_auf(api, "lauf_ende")
    a = api.auswertung()
    assert a["bestand"]["bereiche"] == {"Eingang": 0, "Prüfen": 1, "Fertig": 1}
    assert a["laeufe"][0]["dateien"] == 2 and a["pruefgruende"][0][0] == "Titel fehlt"
    assert a["ieee"] == [0, 1] and a["textsummen"]["buecher"] == 1
    assert {"dauern", "herkunft", "offene_stellen"} <= set(a)
    json.dumps(a)


def test_signatur_folgt_den_ordnern(api, basis):
    vorher = api.signatur()
    erzeuge_buch(basis / "Eingang" / "a.pdf")
    assert api.signatur() != vorher


def test_fortschritt_wird_gedrosselt(api):
    for i in range(1, 201):
        api._fortschritt("Text lesen", i, 200)
    schritte = [e for e in api.ereignisse(0)["ereignisse"] if e["art"] == "fortschritt"]
    assert 2 <= len(schritte) < 10 and schritte[-1]["erledigt"] == 200      # das Ende kommt immer an


def test_schliessen_ohne_lauf(api):
    assert api.schliessen_anfragen() == {"laeuft": False}
    assert api._beim_schliessen() is True


def test_schliessen_waehrend_lauf_fragt_erst(api, basis):
    for n in "ab":
        erzeuge_buch(basis / "Eingang" / f"{n}.pdf", titel=f"Buch {n}")
    api.starten()
    assert api._beim_schliessen() is False                                     # Fenster bleibt offen, Rueckfrage
    assert api.schliessen_anfragen() == {"laeuft": True}
    warte_auf(api, "lauf_ende")
    assert api._beim_schliessen() is True


@pytest.mark.skipif(sys.platform != "win32", reason="benannter Mutex nur unter Windows")
def test_einzelinstanz_je_ordner(tmp_path):
    assert ui_app.einzelinstanz(tmp_path / "eins")
    assert not ui_app.einzelinstanz(tmp_path / "eins")
    assert ui_app.einzelinstanz(tmp_path / "zwei")


def test_web_ordner_enthaelt_die_oberflaeche():
    assert (ui_app.web_ordner() / "index.html").is_file()


def test_vorschau_server_ruft_nur_oeffentliche_methoden(basis):
    """werkzeuge/ui_vorschau.py: dieselbe Oberflaeche im Browser, Api per HTTP (nur 127.0.0.1)."""
    import importlib.util
    import threading
    import urllib.error
    import urllib.request
    spec = importlib.util.spec_from_file_location("ui_vorschau", ui_app.Path(__file__).parent.parent / "werkzeuge" / "ui_vorschau.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    s = modul.server(basis, 0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{s.server_port}"
        anfrage = urllib.request.Request(url + "/api/signatur", data=b"[]", method="POST")
        assert isinstance(json.loads(urllib.request.urlopen(anfrage).read()), str)
        anfrage = urllib.request.Request(url + "/api/einstellung_setzen", data=b'["tabellen.TOLERANZ", 3]', method="POST")
        assert json.loads(urllib.request.urlopen(anfrage).read())["ok"]
        for name in ("_speichern", "gibt_es_nicht"):
            with pytest.raises(urllib.error.HTTPError) as fehler:
                urllib.request.urlopen(urllib.request.Request(url + "/api/" + name, data=b"[]", method="POST"))
            assert fehler.value.code == 404
        assert b'name="pdf2md-modus" content="http"' in urllib.request.urlopen(url + "/").read()
        assert urllib.request.urlopen(url + "/app.js").status == 200
    finally:
        s.shutdown()
        s.server_close()


@pytest.fixture
def geoeffnet(monkeypatch):
    liste = []
    monkeypatch.setattr(ui_app, "extern_oeffnen", lambda pfad: liste.append(pfad))
    return liste


def test_datei_oeffnen_nur_in_den_drei_ordnern(api, basis, geoeffnet):
    fertig = basis / "Fertig"
    fertig.mkdir()
    (fertig / "Buch.md").write_text("x", encoding="utf-8")
    (fertig / "Buch.pdf").write_bytes(b"x")
    (basis / "Eingang" / "neu.epub").write_bytes(b"x")
    assert api.datei_oeffnen("fertig", "Buch.md")["ok"]
    assert api.datei_oeffnen("fertig", "Buch.md", "original")["datei"] == "Buch.pdf"
    assert api.datei_oeffnen("eingang", "neu.epub", "original")["ok"]
    assert geoeffnet == [fertig / "Buch.md", fertig / "Buch.pdf", basis / "Eingang" / "neu.epub"]
    for bereich, name in (("fertig", r"..\Einstellungen.json"), ("fertig", "../Protokoll.csv"), ("fertig", "fehlt.md"),
                          ("sicherung", "Buch.md"), ("pruefen", "Buch.md"), ("fertig", "")):
        assert not api.datei_oeffnen(bereich, name)["ok"], (bereich, name)
    assert len(geoeffnet) == 3


def test_ordner_oeffnen_legt_ihn_bei_bedarf_an(api, basis, geoeffnet):
    assert api.ordner_oeffnen("pruefen") == {"ok": True, "ordner": str(basis / "Prüfen")}
    assert (basis / "Prüfen").is_dir() and geoeffnet == [basis / "Prüfen"]
    assert not api.ordner_oeffnen(r"C:\Windows")["ok"]


def test_uebersicht_kommt_sofort_und_kennzahlen_folgen(api, basis, monkeypatch):
    """Haertetest: 640 Buecher brauchten 24 s bis zur ersten Uebersicht, so lange blieb das Fenster leer. Jetzt
    kommen die Listen sofort, die Kennzahlen rechnet ein Hintergrund-Thread; danach aendert sich die Signatur."""
    import auswertung
    fertig = basis / "Fertig"
    fertig.mkdir()
    for i in range(5):
        (fertig / f"Buch {i}.md").write_text(pdf2md.kopf_schreiben({"titel": f"B{i}", "seiten": 10}) + "Text",
                                              encoding="utf-8")
        (fertig / f"Buch {i}.pdf").write_bytes(b"%PDF")
    echt = auswertung.buchkennzahlen

    def langsam(*args, **kwargs):
        time.sleep(0.2)
        return echt(*args, **kwargs)
    monkeypatch.setattr(auswertung, "buchkennzahlen", langsam)
    vorher = api.signatur()
    start = time.time()
    stand = api.stand()
    assert time.time() - start < 0.5
    assert len(stand["fertig"]) == 5 and stand["kennzahlen"] is None and stand["mini"]["herkunft"] is None
    ende = time.time() + 10
    while api.signatur() == vorher and time.time() < ende:
        time.sleep(0.05)
    stand = api.stand()
    assert stand["kennzahlen"]["fertig"] == 5 and stand["kennzahlen"]["seiten"] == 50
    assert stand["mini"]["herkunft"] is not None


def test_viele_buecher_rechnen_unterprozesse(api, basis, monkeypatch):
    """Ab PARALLEL_AB_BUECHERN fehlenden Kennzahlen rechnen Unterprozesse (ablage.kennzahlen_lesen); das Ergebnis muss
    dasselbe sein wie im Thread."""
    fertig = basis / "Fertig"
    fertig.mkdir()
    for i in range(4):
        (fertig / f"Buch {i}.md").write_text(pdf2md.kopf_schreiben({"titel": f"B{i}", "seiten": 7})
                                              + "<!-- PDF-Seite 1 -->\nText �", encoding="utf-8")
    monkeypatch.setattr(ui_app, "PARALLEL_AB_BUECHERN", 1)
    api._parallel_rechnen()
    assert len(api._zwischenspeicher) == 4
    assert api._im_speicher(fertig)
    buecher = api._buecher(fertig)
    assert [b["seiten"] for b in buecher] == [7] * 4 and buecher[0]["fragezeichen"] == 1


def test_literaturliste_als_werkzeug(api, basis):
    fertig = basis / "Fertig"
    fertig.mkdir()
    kopf = {"titel": "Beispielkunde", "autor": "Hans Muster", "jahr": "2016"}
    (fertig / "Beispielkunde - Hans Muster - 2016.md").write_text(pdf2md.kopf_schreiben(kopf) + "Text", encoding="utf-8")
    vorschau = api.werkzeug_vorschau("literatur")
    assert vorschau["eintraege"] == [{"alt": "Beispielkunde - Hans Muster - 2016", "neu": "muster2016beispielkunde"}]
    assert not (basis / "Literatur.bib").exists()
    assert api.werkzeug_starten("literatur")["ok"]
    assert warte_auf(api, "lauf_ende")["ergebnis"] == {"eintraege": 1, "datei": str(basis / "Literatur.bib")}
    assert "@book{muster2016beispielkunde" in (basis / "Literatur.bib").read_text(encoding="utf-8")


def test_version_und_update_hinweis(api, monkeypatch):
    import aktualisierung
    assert api.stand()["version"] == {"aktuell": aktualisierung.VERSION, "neu": None}
    monkeypatch.setattr(aktualisierung, "neuere_version", lambda: "99.0.0")
    vorher = api.signatur()
    api.update_pruefen_starten()
    api._update_thread.join(10)
    assert api.stand()["version"] == {"aktuell": aktualisierung.VERSION, "neu": "99.0.0"}
    assert api.signatur() != vorher                          # das Fenster laedt neu und zeigt den Hinweis


def test_update_seite_oeffnet_nur_die_feste_adresse(api, monkeypatch):
    import aktualisierung
    geoeffnet = []
    monkeypatch.setattr(ui_app, "link_oeffnen", geoeffnet.append)
    assert api.update_oeffnen() == {"ok": True} and geoeffnet == [aktualisierung.SEITE]

