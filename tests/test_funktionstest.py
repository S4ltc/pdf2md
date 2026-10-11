"""Phase 2 des Start-Tests (Funktionstest des gebauten Programms): ui_app._starttest wandelt die erfundenen
Testdateien (werkzeuge/testdateien.py) ueber die Api um, werkzeuge/bauen.py legt sie an und bewertet die Befunde.
Gebaut wird hier nichts: das Fenster ist nachgebildet, die Api echt (Ablage in tmp_path), das Programm in
bauen.starttest ein nachgebildeter Aufruf. Der echte Lauf im Paket steht als Hinweis am Build-Lauf (bauen.yml)."""
import ast
import concurrent.futures
import importlib.util
import json
import subprocess
import sys
import time
import types
import urllib.request
from pathlib import Path

import pytest

import aktualisierung
import einstellungen
import pdf2md
import ui_app

WURZEL = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bauen", WURZEL / "werkzeuge" / "bauen.py")
bauen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bauen)
testdateien = bauen.testdateien_modul()

PDF_QUELLE = "PDFium + Lesezeichen + Tabellen"
ERWARTUNG = {"textquellen": {".pdf": PDF_QUELLE, ".docx": "MarkItDown"}, "referenzschriften": 3}


class FensterNachbau:
    """Wie ein pywebview-Fenster, dessen Oberflaeche die Versionsnummer sofort zeigt."""
    def __init__(self):
        self.geschlossen = False

    def evaluate_js(self, code):
        return aktualisierung.VERSION

    def destroy(self):
        self.geschlossen = True


@pytest.fixture
def basis(tmp_path, monkeypatch):
    """Ablage fuer eine echte Api; wie in test_ui_app ohne Netz und ohne (langsame) Formelreparatur."""
    for name in ("EINGANG", "FERTIG", "PRUEFEN", "PROTOKOLL", "SICHERUNG"):
        monkeypatch.setattr(pdf2md, name, getattr(pdf2md, name))           # nach dem Test zuruecksetzen
    ordner = tmp_path / "ablage"
    ordner.mkdir()
    (ordner / einstellungen.DATEINAME).write_text(
        json.dumps({"pdf2md.ONLINE_ABGLEICH": False, "pdf2md.FORMELN_REPARIEREN": False}), encoding="utf-8")
    monkeypatch.setattr(ui_app, "STARTTEST_TAKT", 0.05)
    monkeypatch.setattr(ui_app, "PARALLEL_AB_BUECHERN", 3)                  # wenige Kopien, ein Unterprozess
    yield ordner
    einstellungen.anwenden(einstellungen.standardwerte())


@pytest.fixture
def api(basis):
    a = ui_app.Api(basis)
    yield a
    a.abbrechen()
    a._warten(60)


def gute_befunde() -> dict:
    """Befunde von ui_app._funktionstest, wenn im Paket alles stimmt (erfundene Werte wie im echten Lauf)."""
    buch, dokument = "Beispielbuch - Erika Muster - 2019", "Beispieldokument - Erika Muster - 2020"
    kopf = {"ordner": "Fertig", "pruefen": None, "warnung": None, "einstellungen": None, "autor": "Erika Muster",
            "kolumnentitel_im_text": 0}
    return {
        "dateien": ["beispielbuch.pdf", "beispieldokument.docx"], "schritt": "fertig",
        "lauf": {"ende": True, "fehler": None, "ergebnis": {"ok": 2}, "sekunden": 1.0, "meldungen": ["[1/2] x"]},
        "ablage": {"eingang": [], "pruefen": [], "fertig": [f"{buch}.md", f"{buch}.pdf", f"{dokument}.docx",
                                                             f"{dokument}.md"]},
        "kopfblock": {
            f"{buch}.md": {**kopf, "originaldatei": "beispielbuch.pdf", "titel": "Beispielbuch", "jahr": "2019",
                           "textquelle": PDF_QUELLE, "lesezeichen": "3 Überschriften", "tabellen": "1 Tabellen",
                           "seitenzahlen": "gedruckte Seitenzahl für 4 von 4 PDF-Seiten (Seitenzahlen am Seitenrand)",
                           "quellenangabe": "E. Muster, *Beispielbuch*. 2019."},
            f"{dokument}.md": {**kopf, "originaldatei": "beispieldokument.docx", "titel": "Beispieldokument",
                               "jahr": "2020", "textquelle": "MarkItDown", "lesezeichen": None, "tabellen": None,
                               "seitenzahlen": None, "quellenangabe": "E. Muster, *Beispieldokument*. 2020."}},
        "protokoll": ["OK", "OK"], "module_fehlen": [], "referenzschriften": 3,
        "rueckgaengig": {"eintraege": 2, "ende": True, "fehler": None, "ergebnis": {"zurueck": 2},
                         "ablage": {"eingang": ["beispielbuch.md", "beispielbuch.pdf", "beispieldokument.docx",
                                                "beispieldokument.md"], "fertig": [], "pruefen": []}},
        "kennzahlen": {"kopien": 40, "erwartet": 40, "fertig": 40, "angekommen": True, "sekunden": 2.0,
                       "unterprozesse": {"aufrufe": 1, "berechnet": 40, "fehler": None}, "auswertung_fertig": 40},
        "sekunden": 5.0}


class TestTestdateien:
    def test_pdf_und_docx(self, tmp_path):
        dateien = testdateien.anlegen(tmp_path / "testdateien")
        assert [p.name for p in dateien] == list(testdateien.DATEIEN)
        assert all(p.stat().st_size > 1000 for p in dateien)
        info = pdf2md.metadaten_lesen(dateien[0])
        assert (info["titel"], info["autor"], info["seiten"]) == ("Beispielbuch", "Erika Muster", 4)
        assert pdf2md.lesezeichen_lesen(dateien[0])                        # Gliederung fuer die Ueberschriften
        info = pdf2md.metadaten_lesen(dateien[1])
        assert (info["titel"], info["autor"]) == ("Beispieldokument", "Erika Muster")

    def test_keine_kennung_kein_netz(self, tmp_path):
        """Ohne ISBN/DOI fragt pdf2md nie bei Crossref nach (Titel, Autor und Jahr sind ohnehin vollstaendig)."""
        for datei in testdateien.anlegen(tmp_path / "testdateien"):
            info = pdf2md.metadaten_lesen(datei)
            assert not info["kennungen"]

    def test_kolumnentitel_steht_in_der_pdf(self, tmp_path):
        """Die Test-PDF hat den Kolumnentitel, den ui_app im Text zaehlt, wirklich auf den Seiten 2 bis 4; sonst zaehlte
        der Funktionstest einen Text, den es nicht gibt, und die Bewertung bliebe ohne Wirkung gruen."""
        import pypdfium2
        assert testdateien.KOLUMNENTITEL == ui_app.KOLUMNENTITEL
        pdf = testdateien.anlegen(tmp_path / "testdateien")[0]
        dokument = pypdfium2.PdfDocument(str(pdf))
        try:
            texte = [dokument[i].get_textpage().get_text_range() for i in range(len(dokument))]
        finally:
            dokument.close()
        soll = ui_app.KOLUMNENTITEL.format(autor="Erika Muster", titel="Beispielbuch")
        assert [t.count(soll) for t in texte] == [0, 1, 1, 1]

    def test_kopffelder_zaehlen_den_kolumnentitel_nur_im_text(self, tmp_path):
        """Gezaehlt wird im ganzen Text nach dem Kopfblock (auch hinter den ersten 8000 Zeichen), nicht im Kopfblock."""
        kopf = pdf2md.kopf_schreiben({"titel": "Beispielbuch", "autor": "Erika Muster", "seitenzahlen": "x",
                                      "bibtex": "Erika Muster: Beispielbuch"})
        md = tmp_path / "Beispielbuch.md"
        pdf2md.md_schreiben(md, kopf + "Erika Muster: Beispielbuch\nText\n" + "Fülltext " * 1000
                            + "\nErika Muster: Beispielbuch Text")
        felder = ui_app._kopffelder(md)
        assert felder["kolumnentitel_im_text"] == 2
        assert (felder["titel"], felder["seitenzahlen"], felder["quellenangabe"]) == ("Beispielbuch", "x", None)
        pdf2md.md_schreiben(md, pdf2md.kopf_schreiben({"titel": "Beispielbuch"}) + "Text")
        assert ui_app._kopffelder(md)["kolumnentitel_im_text"] is None                    # ohne Autor


def erwartung_jetzt() -> dict:
    """Wie bauen.erwartung_aus_quellstand, aber mit den Einstellungen der Test-Api (ohne Formelreparatur)."""
    return {"textquellen": {".pdf": pdf2md.erwartete_textquelle(), ".docx": "MarkItDown"}, "referenzschriften": 3}


class TestPhase2:
    def test_ende_zu_ende_ohne_abweichung(self, api, basis, tmp_path):
        """Derselbe Weg wie im Paket: hinzufuegen, starten, Rueckgaengig, Kennzahlen in Unterprozessen. Die Befunde
        bestehen die Bewertung von bauen.py."""
        assert bauen.testdateien_anlegen(tmp_path / "testdateien") is None
        fenster = FensterNachbau()
        ui_app._starttest(fenster, tmp_path / "ergebnis.json", api)
        ergebnis = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))
        assert ergebnis["ok"] and fenster.geschlossen and api._schliessen_erlaubt
        f = ergebnis["funktion"]
        assert bauen.funktion_bewerten(f, erwartung_jetzt(), testdateien.DATEIEN) == []
        assert f["schritt"] == "fertig" and "fehler" not in f
        assert f["protokoll"] == ["OK", "OK"] and f["module_fehlen"] == [] and f["referenzschriften"] == 3
        assert sorted(f["ablage"]["fertig"]) == ["Beispielbuch - Erika Muster - 2019.md",
                                                 "Beispielbuch - Erika Muster - 2019.pdf",
                                                 "Beispieldokument - Erika Muster - 2020.docx",
                                                 "Beispieldokument - Erika Muster - 2020.md"]
        assert {"beispielbuch.pdf", "beispieldokument.docx"} <= set(f["rueckgaengig"]["ablage"]["eingang"])
        kopf = {k["originaldatei"]: k for k in f["kopfblock"].values()}
        assert kopf["beispielbuch.pdf"]["seitenzahlen"].startswith("gedruckte Seitenzahl für")
        assert kopf["beispielbuch.pdf"]["kolumnentitel_im_text"] == 0 == kopf["beispieldokument.docx"][
            "kolumnentitel_im_text"]
        assert "Beispieldokument" in kopf["beispieldokument.docx"]["quellenangabe"]
        k = f["kennzahlen"]
        assert k["kopien"] == 3 and k["angekommen"] and k["unterprozesse"]["berechnet"] == 3
        assert k["unterprozesse"]["fehler"] is None and k["auswertung_fertig"] == 3
        assert "_parallel_rechnen" not in vars(api)                         # die Huelle ist wieder weg
        assert (tmp_path / "testdateien" / "beispielbuch.pdf").exists()      # hinzufuegen kopiert nur

    @staticmethod
    def netz_zaehlen(monkeypatch) -> list:
        """Jeder Netzabruf (pdf2md, zitierdaten und aktualisierung rufen urllib.request.urlopen auf) wird gezaehlt und
        scheitert wie ohne Netz."""
        aufrufe = []

        def kein_netz(*args, **kwargs):
            aufrufe.append(args)
            raise OSError("kein Netz im Test")
        monkeypatch.setattr(urllib.request, "urlopen", kein_netz)
        return aufrufe

    def test_online_abgleich_an_kein_netzaufruf(self, basis, tmp_path, monkeypatch):
        """Das Paket startet mit den Standard-Einstellungen, also mit Online-Abgleich. Die Testdateien haben keine
        ISBN/DOI: die Umwandlung fragt nie im Netz nach (ein Runner ohne Netz oder ein langsames Crossref verfaelschte
        sonst Phase 2), die Quellenangabe entsteht aus Titel, Autor und Jahr, und die Bewertung findet nichts."""
        aufrufe = self.netz_zaehlen(monkeypatch)
        (basis / einstellungen.DATEINAME).write_text(json.dumps({"pdf2md.FORMELN_REPARIEREN": False}),
                                                     encoding="utf-8")
        api = ui_app.Api(basis)
        try:
            assert einstellungen.standardwerte()["pdf2md.ONLINE_ABGLEICH"] is True and pdf2md.ONLINE_ABGLEICH is True
            assert bauen.testdateien_anlegen(tmp_path / "testdateien") is None
            ui_app._starttest(FensterNachbau(), tmp_path / "ergebnis.json", api)
        finally:
            api.abbrechen()
            api._warten(60)
        f = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))["funktion"]
        assert aufrufe == []
        assert bauen.funktion_bewerten(f, erwartung_jetzt(), testdateien.DATEIEN) == []
        assert all(k["quellenangabe"] for k in f["kopfblock"].values())

    @pytest.mark.langsam
    def test_ende_zu_ende_mit_standard_einstellungen(self, basis, tmp_path, monkeypatch):
        """Wie im Paket: Standard-Einstellungen (Formelreparatur, Online-Abgleich), nur ohne Netz. Die Befunde passen
        genau zur Erwartung, die bauen.py aus dem Quellstand bildet, ohne einen einzigen Netzabruf."""
        aufrufe = self.netz_zaehlen(monkeypatch)
        (basis / einstellungen.DATEINAME).unlink()
        api = ui_app.Api(basis)
        try:
            assert bauen.testdateien_anlegen(tmp_path / "testdateien") is None
            ui_app._starttest(FensterNachbau(), tmp_path / "ergebnis.json", api)
        finally:
            api.abbrechen()
            api._warten(60)
        f = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))["funktion"]
        erwartung = bauen.erwartung_aus_quellstand()
        assert "Formelreparatur" in erwartung["textquellen"][".pdf"]
        assert bauen.funktion_bewerten(f, erwartung, testdateien.DATEIEN) == []
        assert aufrufe == []

    def test_ohne_testordner_nur_phase_1(self, api, basis, tmp_path):
        ui_app._starttest(FensterNachbau(), tmp_path / "ergebnis.json", api)
        ergebnis = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))
        assert ergebnis["ok"] and "funktion" not in ergebnis
        assert not (basis / "Eingang").exists() or not any((basis / "Eingang").iterdir())

    def test_phase_1_steht_vor_phase_2_fest(self, tmp_path):
        """Beendet bauen.py das Programm im Zeitlimit von Phase 2, bleibt das Ergebnis von Phase 1 lesbar; eine
        Ausnahme in Phase 2 wird Befund, das Fenster schliesst trotzdem."""
        (tmp_path / "testdateien").mkdir()
        (tmp_path / "testdateien" / "a.pdf").write_bytes(b"%PDF")
        ziel = tmp_path / "ergebnis.json"
        gesehen = {}

        class ApiNachbau:
            _schliessen_erlaubt = False

            def hinzufuegen(self, pfade):
                gesehen["vorher"] = json.loads(ziel.read_text(encoding="utf-8"))
                gesehen["pfade"] = pfade
                raise RuntimeError("Absturz in Phase 2")

            def abbrechen(self):
                gesehen["abgebrochen"] = True

        fenster = FensterNachbau()
        ui_app._starttest(fenster, ziel, ApiNachbau())
        assert gesehen["vorher"]["ok"] and "funktion" not in gesehen["vorher"]
        assert [Path(p).name for p in gesehen["pfade"]] == ["a.pdf"] and gesehen["abgebrochen"]
        ergebnis = json.loads(ziel.read_text(encoding="utf-8"))
        assert ergebnis["ok"] and ergebnis["funktion"]["fehler"] == "RuntimeError: Absturz in Phase 2"
        assert fenster.geschlossen

    def test_zwischenstand_zeigt_wie_weit_phase_2_kam(self, tmp_path, monkeypatch):
        """Haengt Phase 2 (etwa ein Unterprozess) und bauen.py beendet das Programm, steht der letzte Zwischenstand in
        der Ergebnisdatei; die Bewertung meldet ihn als nicht zu Ende gelaufen, auch wenn alles davor stimmte. Das
        Beenden bildet hier eine Ausnahme nach, die _funktionstest nicht abfaengt."""
        monkeypatch.setattr(ui_app, "STARTTEST_TAKT", 0.01)
        (tmp_path / "testdateien").mkdir()
        (tmp_path / "testdateien" / "a.pdf").write_bytes(b"%PDF")
        ziel = tmp_path / "ergebnis.json"

        class Beendet(BaseException):
            pass

        class ApiNachbau:
            def hinzufuegen(self, pfade):
                return {"kopiert": ["a.pdf"], "abgelehnt": []}

            def ereignisse(self, nach=0):
                return {"ereignisse": [{"art": "lauf_ende", "ergebnis": {"ok": 1}, "fehler": None, "nr": 1}],
                        "letzte": 0}

            def starten(self):
                return {"ok": True}

            def _warten(self, sekunden):
                pass

            def _protokoll(self):
                return [{"status": "OK"}]

            def werkzeug_vorschau(self, name):
                raise Beendet()

        fenster = FensterNachbau()
        with pytest.raises(Beendet):
            ui_app._starttest(fenster, ziel, ApiNachbau())
        ergebnis = json.loads(ziel.read_text(encoding="utf-8"))
        f = ergebnis["funktion"]
        assert ergebnis["ok"] and f["schritt"] == "rueckgaengig" and "sekunden" not in f
        assert f["lauf"]["ende"] and f["protokoll"] == ["OK"]
        abweichungen = bauen.funktion_bewerten(f, ERWARTUNG, {"a.pdf": {}})
        assert abweichungen[0].startswith("Phase 2 nicht zu Ende gelaufen") and "rueckgaengig" in abweichungen[0]
        assert fenster.geschlossen                     # sonst liefe das Programm bis zum Zeitlimit von bauen.py

    @staticmethod
    def testordner(tmp_path) -> None:
        (tmp_path / "testdateien").mkdir()
        (tmp_path / "testdateien" / "a.pdf").write_bytes(b"%PDF")

    def test_fehler_nach_phase_2_schliesst_das_fenster(self, tmp_path):
        """Eine Ausnahme ausserhalb von _funktionstest (hier beim Abbrechen) haelt das Fenster nicht offen; das
        Ergebnis von Phase 1 bleibt lesbar."""
        self.testordner(tmp_path)

        class ApiNachbau:
            def hinzufuegen(self, pfade):
                raise RuntimeError("Absturz in Phase 2")

            def abbrechen(self):
                raise RuntimeError("Abbrechen gescheitert")

        fenster = FensterNachbau()
        with pytest.raises(RuntimeError, match="Abbrechen gescheitert"):
            ui_app._starttest(fenster, tmp_path / "ergebnis.json", ApiNachbau())
        assert fenster.geschlossen
        assert json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))["ok"]

    def test_unerwarteter_wert_im_bericht(self, tmp_path, monkeypatch):
        """Ein Wert, den json nicht kennt (etwa ein Path), verhindert weder das Ergebnis noch das Schliessen; es bleibt
        keine Hilfsdatei liegen."""
        self.testordner(tmp_path)

        class ApiNachbau:
            _schliessen_erlaubt = False

            def abbrechen(self):
                pass

        monkeypatch.setattr(ui_app, "_funktionstest",
                            lambda api, pfade, zwischenstand: {"datei": pfade[0], "sekunden": 0.1})
        fenster = FensterNachbau()
        ui_app._starttest(fenster, tmp_path / "ergebnis.json", ApiNachbau())
        ergebnis = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))
        assert ergebnis["funktion"]["datei"] == str(tmp_path / "testdateien" / "a.pdf") and fenster.geschlossen
        assert sorted(p.name for p in tmp_path.iterdir()) == ["ergebnis.json", "testdateien"]

    def test_ergebnis_atomar_geschrieben(self, tmp_path, monkeypatch):
        """Beendet bauen.py das Programm mitten im Schreiben (hier: vor dem Ersetzen), bleibt der vorige Stand ganz und
        lesbar; bauen.py fand sonst eine halbe Datei vor."""
        ziel = tmp_path / "ergebnis.json"
        ui_app._ergebnis_schreiben(ziel, {"ok": True, "funktion": {"schritt": "umwandlung"}})

        class Beendet(BaseException):
            pass

        def beendet(*args):
            raise Beendet()
        monkeypatch.setattr(ui_app.os, "replace", beendet)
        with pytest.raises(Beendet):
            ui_app._ergebnis_schreiben(ziel, {"ok": True, "funktion": {"schritt": "kennzahlen", "x": "y" * 10 ** 6}})
        assert json.loads(ziel.read_text(encoding="utf-8")) == {"ok": True, "funktion": {"schritt": "umwandlung"}}

    def test_nur_in_leerer_ablage(self, api, basis, tmp_path):
        """Phase 2 laesst Kopien in Fertig zurueck und macht den letzten Lauf rueckgaengig: in einer Ablage mit Dateien
        (Nutzerdaten) laeuft sie nicht, es wird nichts kopiert oder verschoben."""
        assert bauen.testdateien_anlegen(tmp_path / "testdateien") is None
        (basis / "Fertig").mkdir()
        (basis / "Fertig" / "Vorhanden.md").write_text("---\ntitel: \"Beispielelemente\"\n---\nText", encoding="utf-8")
        ui_app._starttest(FensterNachbau(), tmp_path / "ergebnis.json", api)
        f = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))["funktion"]
        assert f["fehler"].startswith("RuntimeError: Ablage nicht leer") and "lauf" not in f
        assert sorted(p.name for p in basis.rglob("*") if p.is_file()) == [einstellungen.DATEINAME, "Vorhanden.md"]
        assert bauen.funktion_bewerten(f, ERWARTUNG, testdateien.DATEIEN)[0].startswith("Ausnahme: RuntimeError")

    def test_lauf_abwarten_mit_zeitlimit(self, monkeypatch):
        monkeypatch.setattr(ui_app, "STARTTEST_TAKT", 0.01)

        class ApiNachbau:
            def ereignisse(self, nach=0):
                return {"ereignisse": [{"art": "meldung", "text": "haengt", "nr": 2}], "letzte": 1}

        ergebnis = ui_app._lauf_abwarten(ApiNachbau(), lambda: {"ok": True}, time.time() + 0.1)
        assert ergebnis["ende"] is False and ergebnis["fehler"] == "Zeitlimit" and ergebnis["meldungen"] == ["haengt"]
        abgelehnt = ui_app._lauf_abwarten(ApiNachbau(), lambda: {"ok": False, "grund": "Es läuft bereits ein Lauf."},
                                          time.time() + 1)
        assert abgelehnt == {"ende": False, "fehler": "Es läuft bereits ein Lauf."}

    def test_kaputte_unterprozesse_fallen_auf(self, api, basis, monkeypatch):
        """Scheitern die Unterprozesse, rechnet das Fenster die Kennzahlen still im Thread: sie kommen an, die Huelle
        zaehlt aber 0 und haelt den Fehler fest. Genau das soll im Paket nicht unbemerkt gruen bleiben."""
        class Kaputt:
            def __init__(self, *args, **kwargs):
                raise OSError("kein Unterprozess")
        monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", Kaputt)
        k = ui_app._kennzahlen_pruefen(api, [], time.time() + 30)
        assert k["angekommen"] and k["fertig"] == 3 == k["erwartet"]
        assert k["unterprozesse"]["berechnet"] == 0 and "kein Unterprozess" in k["unterprozesse"]["fehler"]
        abweichungen = bauen.funktion_bewerten({"kennzahlen": k}, ERWARTUNG, {})
        assert "Unterprozesse haben 0 von 3 Kennzahlen gerechnet (OSError: kein Unterprozess)" in abweichungen
        assert "_parallel_rechnen" not in vars(api)

    def test_fehlendes_modul_wird_gemeldet(self, monkeypatch):
        monkeypatch.setattr(pdf2md, "tabellen", None)
        monkeypatch.setattr(pdf2md, "formeln", None)
        assert ui_app._referenzschriften() == 0
        assert [n for n in ui_app.OPTIONALE_MODULE if getattr(pdf2md, n, None) is None] == ["formeln", "tabellen"]

    def test_optionale_module_wie_in_pdf2md(self):
        """OPTIONALE_MODULE muss alle Module nennen, die pdf2md.py per try/except importiert (und dann still auf None
        setzt), sonst bliebe ein neues Modul, das im Paket fehlt, im Funktionstest unbemerkt."""
        def setzt_none(knoten: ast.Try, name: str) -> bool:
            return any(isinstance(z, ast.Assign) and isinstance(z.value, ast.Constant) and z.value.value is None
                       and any(isinstance(t, ast.Name) and t.id == name for t in z.targets)
                       for h in knoten.handlers for z in h.body)

        baum = ast.parse((WURZEL / "pdf2md.py").read_text(encoding="utf-8"))
        optional = [k.body[0].names[0].name for k in baum.body if isinstance(k, ast.Try)
                    and isinstance(k.body[0], ast.Import) and setzt_none(k, k.body[0].names[0].name)]
        assert sorted(optional) == sorted(ui_app.OPTIONALE_MODULE)

    def test_main_gibt_die_api_an_den_starttest(self, tmp_path, monkeypatch, basis):
        """Nur die Zeile in main(): mit PDF2MD_STARTTEST bekommt _starttest Fenster, Ergebnisdatei und Api."""
        aufrufe = []

        class Ereignis:
            def __iadd__(self, funktion):
                return self

        fenster = types.SimpleNamespace(events=types.SimpleNamespace(closing=Ereignis(), loaded=Ereignis()))
        webview = types.ModuleType("webview")
        webview.create_window = lambda *args, **kwargs: fenster
        webview.start = lambda *args, **kwargs: aufrufe.append(args)
        monkeypatch.setitem(sys.modules, "webview", webview)
        monkeypatch.setattr(ui_app, "einzelinstanz", lambda basis: True)
        monkeypatch.setattr(ui_app.plattform, "vorbereiten", lambda: None)      # setzte unter Linux os.environ
        monkeypatch.setattr(ui_app, "system_dunkel", lambda: False)
        monkeypatch.setenv("PDF2MD_ABLAGE", str(basis))
        monkeypatch.setenv("PDF2MD_STARTTEST", str(tmp_path / "ergebnis.json"))
        assert ui_app.main() == 0
        funktion, (f, ziel, api) = aufrufe[0]
        assert funktion is ui_app._starttest and f is fenster and ziel == tmp_path / "ergebnis.json"
        assert isinstance(api, ui_app.Api) and api._fenster is fenster


class TestBewertung:
    def test_alles_gut(self):
        assert bauen.funktion_bewerten(gute_befunde(), ERWARTUNG, testdateien.DATEIEN) == []

    def test_ausweichen_auf_markitdown_und_fehlende_module(self):
        """Der Fall, der bisher gruen blieb: ein Modul fehlt im Paket, pdf2md setzt es auf None und weicht aus."""
        f = gute_befunde()
        f["kopfblock"]["Beispielbuch - Erika Muster - 2019.md"].update(textquelle="MarkItDown", tabellen=None)
        f["module_fehlen"], f["referenzschriften"] = ["formeln", "tabellen"], 0
        assert bauen.funktion_bewerten(f, ERWARTUNG, testdateien.DATEIEN) == [
            f"beispielbuch.pdf: textquelle 'MarkItDown' statt '{PDF_QUELLE}'",
            "beispielbuch.pdf: kein Feld tabellen im Kopfblock",
            "Module fehlen im Paket: formeln, tabellen",
            "Referenzschriften der Formelreparatur: 0 statt 3"]

    def test_seitenzahlen_quellenangabe_und_kolumnentitel(self):
        """Felder, die im Quellstand entstehen: fehlt zitierdaten im Paket, fehlt die Quellenangabe; seitenzahlen steht
        auch ohne gefundene Seitenzahlen da, zaehlt dann aber nicht. Der Kolumnentitel darf nicht im Text stehen."""
        f = gute_befunde()
        buch = f["kopfblock"]["Beispielbuch - Erika Muster - 2019.md"]
        buch.update(seitenzahlen="keine gedruckten Seitenzahlen gefunden, Marker nennen nur die PDF-Seite",
                    quellenangabe=None, kolumnentitel_im_text=3)
        f["kopfblock"]["Beispieldokument - Erika Muster - 2020.md"]["quellenangabe"] = ""
        assert bauen.funktion_bewerten(f, ERWARTUNG, testdateien.DATEIEN) == [
            "beispielbuch.pdf: kein Feld quellenangabe im Kopfblock",
            "beispielbuch.pdf: seitenzahlen 'keine gedruckten Seitenzahlen gefunden, Marker nennen nur die PDF-Seite' "
            "statt 'gedruckte Seitenzahl für' …",
            "beispielbuch.pdf: Kolumnentitel 3-mal im Text statt 0 (Kopfzeile nicht entfernt)",
            "beispieldokument.docx: kein Feld quellenangabe im Kopfblock"]
        buch.update(seitenzahlen=None, kolumnentitel_im_text=None)
        assert bauen.funktion_bewerten(f, ERWARTUNG, testdateien.DATEIEN) == [
            "beispielbuch.pdf: kein Feld seitenzahlen im Kopfblock",
            "beispielbuch.pdf: kein Feld quellenangabe im Kopfblock",
            "beispielbuch.pdf: Kolumnentitel im Text nicht gezählt",
            "beispieldokument.docx: kein Feld quellenangabe im Kopfblock"]

    def test_pruefen_statt_fertig(self):
        f = gute_befunde()
        f["ablage"]["pruefen"] = ["beispieldokument.docx", "beispieldokument.md"]
        f["ablage"]["fertig"] = f["ablage"]["fertig"][:2]
        f["kopfblock"]["Beispieldokument - Erika Muster - 2020.md"].update(ordner="Prüfen", jahr=None,
                                                                           pruefen="Jahr fehlt")
        f["protokoll"] = ["OK", "PRÜFEN"]
        abweichungen = bauen.funktion_bewerten(f, ERWARTUNG, testdateien.DATEIEN)
        assert "beispieldokument.docx: pruefen: Jahr fehlt" in abweichungen
        assert "beispieldokument.docx: jahr None statt '2020'" in abweichungen
        assert any(a.startswith("in Fertig ") for a in abweichungen)
        assert any(a.startswith("Protokoll ['OK', 'PRÜFEN']") for a in abweichungen)

    def test_rueckgaengig_und_zeitlimit(self):
        f = gute_befunde()
        f["rueckgaengig"].update(ende=False, fehler="Zeitlimit", ablage={"eingang": []})
        f["kennzahlen"].update(angekommen=False, fertig=None, sekunden=0)
        abweichungen = bauen.funktion_bewerten(f, ERWARTUNG, testdateien.DATEIEN)
        assert "Rückgängig: Zeitlimit" in abweichungen and not any("Vorschau" in a for a in abweichungen)
        assert any(a.startswith("nach Rückgängig im Eingang []") for a in abweichungen)
        assert "Kennzahlen nicht angekommen: None statt 40 Bücher nach 0 s" in abweichungen

    def test_ohne_befunde(self):
        assert bauen.funktion_bewerten(None, ERWARTUNG, testdateien.DATEIEN) == [
            "kein Ergebnis von Phase 2 (Programm vorher beendet oder Zeitlimit)"]
        abweichungen = bauen.funktion_bewerten({"fehler": "OSError: x", "sekunden": 0.1}, ERWARTUNG,
                                               testdateien.DATEIEN)
        assert abweichungen == ["Ausnahme: OSError: x", "Umwandlung: nicht beendet"]
        zwischenstand = {k: v for k, v in gute_befunde().items() if k != "sekunden"} | {"schritt": "kennzahlen"}
        assert bauen.funktion_bewerten(zwischenstand, ERWARTUNG, testdateien.DATEIEN) == [
            f"Phase 2 nicht zu Ende gelaufen (Programm beendet, Zeitlimit {bauen.STARTTEST_ZEIT} s?), zuletzt im "
            "Schritt kennzahlen"]

    def test_erwartung_aus_dem_quellstand(self):
        """Mit den Standard-Einstellungen (das Paket startet ohne Einstellungen.json), egal was dieser Prozess gerade
        eingestellt hat; dessen Einstellungen bleiben."""
        einstellungen.anwenden(einstellungen.standardwerte())
        standard = pdf2md.erwartete_textquelle()
        assert "Formelreparatur" in standard
        try:
            einstellungen.anwenden({"pdf2md.FORMELN_REPARIEREN": False})
            erwartung = bauen.erwartung_aus_quellstand()
            assert pdf2md.FORMELN_REPARIEREN is False
        finally:
            einstellungen.anwenden(einstellungen.standardwerte())
        assert erwartung["textquellen"] == {".pdf": standard, ".docx": "MarkItDown"}
        assert erwartung["referenzschriften"] == 3                          # STIX aufrecht, STIX kursiv, DejaVu


class TestStarttestPhase2:
    @pytest.fixture
    def windows(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bauen, "SYSTEM", "win32")
        monkeypatch.setattr(bauen, "erwartung_aus_quellstand", lambda: ERWARTUNG)
        (tmp_path / "pdf2md.exe").write_bytes(b"exe")

    def laeuft_mit(self, monkeypatch, funktion, ok=True, abbruch=False):
        gesehen = {}

        def laufen(befehl, env, **kw):
            ziel = Path(env["PDF2MD_STARTTEST"])
            gesehen["testdateien"] = sorted(p.name for p in (ziel.parent / "testdateien").iterdir())
            daten = {"ok": ok, "gui": "edgechromium"}
            if funktion is not None:
                daten["funktion"] = funktion
            ziel.write_text(json.dumps(daten), encoding="utf-8")
            if abbruch:
                raise subprocess.TimeoutExpired(befehl, kw["timeout"])
            return subprocess.CompletedProcess(befehl, 0, "", "")
        monkeypatch.setattr(bauen.subprocess, "run", laufen)
        return gesehen

    def test_testdateien_neben_dem_ergebnis_und_ok(self, windows, tmp_path, monkeypatch):
        gesehen = self.laeuft_mit(monkeypatch, gute_befunde())
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 0
        assert gesehen["testdateien"] == ["beispielbuch.pdf", "beispieldokument.docx"]
        bericht = json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))
        assert bericht["funktion_ok"] and bericht["funktion_abweichungen"] == []
        zeilen = bauen.hinweise("windows", tmp_path, tag="probe")
        assert zeilen[0].startswith("::notice title=Start-Test windows::OK ")
        assert zeilen[1].startswith("::notice title=Funktionstest windows::OK ") and '"unterprozesse": 40' in zeilen[1]

    def test_fehler_in_phase_2_vorerst_nur_warnung(self, windows, tmp_path, monkeypatch):
        """Nutzerentscheidung: erst nach mehreren gruenen Laeufen soll Phase 2 den Start-Test scheitern lassen."""
        f = gute_befunde()
        f["module_fehlen"] = ["tabellen"]
        f["lauf"]["meldungen"] = ["[1/2] beispielbuch.pdf", "   PDFium hat die Datei nicht gelesen (x)"]
        self.laeuft_mit(monkeypatch, f)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 0
        bericht = json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))
        assert not bericht["funktion_ok"] and bericht["funktion_abweichungen"] == ["Module fehlen im Paket: tabellen"]
        zeilen = bauen.hinweise("windows", tmp_path, tag="probe")
        assert zeilen[0].startswith("::notice title=Start-Test windows::OK ")
        assert zeilen[1].startswith("::warning title=Funktionstest windows::FEHLER ")
        assert "- Module fehlen im Paket: tabellen" in zeilen[1].replace("%0A", "\n")
        assert "PDFium hat die Datei nicht gelesen" in zeilen[1]

    def test_zeitlimit_in_phase_2_behaelt_phase_1(self, windows, tmp_path, monkeypatch):
        self.laeuft_mit(monkeypatch, None, abbruch=True)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 0
        bericht = json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))
        assert bericht["ok"] and bericht["rueckgabe"] is None and not bericht["funktion_ok"]
        assert bericht["funktion_abweichungen"] == ["kein Ergebnis von Phase 2 (Programm vorher beendet oder Zeitlimit)"]

    @staticmethod
    def nur_phase_1(monkeypatch):
        def laufen(befehl, env, **kw):
            assert not (Path(env["PDF2MD_STARTTEST"]).parent / "testdateien").exists()
            Path(env["PDF2MD_STARTTEST"]).write_text(json.dumps({"ok": True}), encoding="utf-8")
            return subprocess.CompletedProcess(befehl, 0, "", "")
        monkeypatch.setattr(bauen.subprocess, "run", laufen)

    def test_ohne_fpdf2_still_keine_phase_2(self, windows, tmp_path, monkeypatch):
        """Ohne fpdf2/python-docx (etwa ein Test des fertigen Pakets in einem Container) laeuft nur Phase 1, ohne
        Funktionstest-Hinweis; bewertet wird dann auch nichts (pdf2md muss dort nicht importierbar sein)."""
        assert bauen.funktionstest_moeglich()                               # hier (requirements-dev.txt) vorhanden
        monkeypatch.setattr(bauen, "TESTDATEIEN_MODULE", ("fpdf", "gibt_es_nicht_12345"))
        monkeypatch.setattr(bauen, "erwartung_aus_quellstand", lambda: pytest.fail("ohne Phase 2 nichts bewerten"))
        assert not bauen.funktionstest_moeglich()
        self.nur_phase_1(monkeypatch)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 0
        bericht = json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))
        assert bericht["ok"] and "funktion_ok" not in bericht and "funktion_abweichungen" not in bericht
        zeilen = bauen.hinweise("linux-x86_64", tmp_path, tag="probe")
        assert len(zeilen) == 1 and zeilen[0].startswith("::notice title=Start-Test linux-x86_64::OK ")

    def test_testdateien_kaputt_ist_eine_warnung(self, windows, tmp_path, monkeypatch):
        """Sind fpdf2 und python-docx da, scheitert aber das Anlegen (etwa die Schrift fehlt), ist das ein Befund."""
        monkeypatch.setattr(bauen, "testdateien_anlegen", lambda ordner: "FileNotFoundError: DejaVuSans.ttf")
        self.nur_phase_1(monkeypatch)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 0
        bericht = json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))
        assert bericht["funktion_abweichungen"] == [
            "Testdateien nicht angelegt, Phase 2 lief nicht: FileNotFoundError: DejaVuSans.ttf"]
        assert bauen.hinweise("windows", tmp_path, tag="probe")[1].startswith("::warning title=Funktionstest windows::")

    def test_phase_1_entscheidet_weiter(self, windows, tmp_path, monkeypatch):
        self.laeuft_mit(monkeypatch, gute_befunde(), ok=False)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 1

    def test_halbe_ergebnisdatei_gilt_als_kein_ergebnis(self, windows, tmp_path, monkeypatch):
        """Eine Ergebnisdatei, die kein JSON ist (etwa halb geschrieben, als das Zeitlimit das Programm beendete),
        bricht den Start-Test nicht mit einem Traceback ab: sie zaehlt wie eine fehlende."""
        def laufen(befehl, env, **kw):
            Path(env["PDF2MD_STARTTEST"]).write_text('{"ok": true, "funktion": {"schri', encoding="utf-8")
            raise subprocess.TimeoutExpired(befehl, kw["timeout"])
        monkeypatch.setattr(bauen.subprocess, "run", laufen)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 1
        bericht = json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))
        assert bericht["ok"] is False and bericht["fehler"] == "kein Ergebnis vom Programm"
        assert bericht["ergebnisdatei"].startswith("JSONDecodeError: ")
        assert bericht["funktion_abweichungen"] == ["kein Ergebnis von Phase 2 (Programm vorher beendet oder Zeitlimit)"]
        assert bauen.hinweise("windows", tmp_path, tag="probe")[0].startswith("::notice title=Start-Test windows::FEHLER ")

    def test_ergebnis_lesen(self, tmp_path):
        datei = tmp_path / "ergebnis.json"
        assert bauen.ergebnis_lesen(datei) == {"ok": False, "fehler": "kein Ergebnis vom Programm"}
        datei.write_text("null", encoding="utf-8")
        assert bauen.ergebnis_lesen(datei)["ergebnisdatei"] == "kein JSON-Objekt: NoneType"
        datei.write_bytes(b"\xff\xfe{")
        assert bauen.ergebnis_lesen(datei)["ergebnisdatei"].startswith("UnicodeDecodeError")
        datei.write_text('{"ok": true}', encoding="utf-8")
        assert bauen.ergebnis_lesen(datei) == {"ok": True}

    def test_zeitlimit_reicht_fuer_beide_phasen(self):
        assert bauen.STARTTEST_ZEIT >= ui_app.STARTTEST_WARTEN + ui_app.FUNKTIONSTEST_WARTEN + 60

    def test_testdateien_anlegen_raeumt_bei_fehler_auf(self, tmp_path, monkeypatch):
        kaputt = types.SimpleNamespace(anlegen=lambda ordner: (Path(ordner).mkdir(), 1 / 0))
        monkeypatch.setattr(bauen, "testdateien_modul", lambda: kaputt)
        assert bauen.testdateien_anlegen(tmp_path / "testdateien") == "ZeroDivisionError: division by zero"
        assert not (tmp_path / "testdateien").exists()


class TestHinweisformen:
    def test_zwei_und_drei_felder(self):
        """Eintraege der Hinweise sind (titel, text, art); ein Eintrag mit zwei Feldern nimmt die Standard-Art."""
        assert bauen._hinweiszeilen([("A", "x"), ("B", "y\nz", "warning")], "notice") == [
            "::notice title=A::x", "::warning title=B::y%0Az"]
        assert bauen._hinweiszeilen([("C", "50 %")], "warning") == ["::warning title=C::50 %25"]

    def test_zweig_haengt_noch_zwei_tupel_an(self, tmp_path):
        """Ein Zweig, der in hinweise() wie frueher (titel, text) anhaengt, laesst den Lauf nicht scheitern (vorher:
        ValueError beim Entpacken). Nachgestellt mit einer Kopie von bauen.py, in die zwei solche Zeilen eingefuegt
        sind."""
        quelle = (WURZEL / "werkzeuge" / "bauen.py").read_text(encoding="utf-8")
        anker = '        if "funktion_ok" in d:\n'
        assert quelle.count(anker) == 1
        zweig = quelle.replace(anker, '        meldungen.append((f"Nachtrag {name}", "aus einem anderen Zweig"))\n'
                                      '        warnungen.append((f"Hinweis {name}", "mit Art", "notice"))\n' + anker)
        datei = tmp_path / "werkzeuge" / "bauen.py"
        datei.parent.mkdir()
        datei.write_text(zweig, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("bauen_zweig", datei)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        (tmp_path / "starttest.json").write_text(json.dumps({"ok": True, "funktion_ok": True, "funktion": {}}),
                                                 encoding="utf-8")
        zeilen = modul.hinweise("windows", tmp_path, tag="probe")
        assert zeilen[0] == "::notice title=Hinweis windows::mit Art"
        assert zeilen[1].startswith("::notice title=Start-Test windows::OK ")
        assert zeilen[2] == "::notice title=Nachtrag windows::aus einem anderen Zweig"
        assert zeilen[3].startswith("::notice title=Funktionstest windows::OK ")


class TestZertifikate:
    """Gebaute App unter macOS/Linux: plattform.vorbereiten setzt SSL_CERT_FILE auf die Zertifikate von certifi im
    Paket; fehlen sie, scheitert jede HTTPS-Anfrage still. Phase 1 haelt das fest, hinweise warnt."""

    def ergebnis(self, tmp_path, monkeypatch, system: str) -> dict:
        monkeypatch.setattr(ui_app.plattform, "SYSTEM", system)
        ui_app._starttest(FensterNachbau(), tmp_path / "ergebnis.json")
        return json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))

    def test_phase_1_haelt_die_zertifikatsdatei_fest(self, tmp_path, monkeypatch):
        datei = tmp_path / "cacert.pem"
        datei.write_text("Zertifikate", encoding="utf-8")
        monkeypatch.setenv("SSL_CERT_FILE", str(datei))
        ergebnis = self.ergebnis(tmp_path, monkeypatch, "linux")
        assert ergebnis["ok"] and ergebnis["system"] == "linux"
        assert ergebnis["zertifikate"] == {"SSL_CERT_FILE": str(datei), "vorhanden": True}
        monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "fehlt.pem"))
        assert self.ergebnis(tmp_path, monkeypatch, "darwin")["zertifikate"] == {
            "SSL_CERT_FILE": str(tmp_path / "fehlt.pem"), "vorhanden": False}
        monkeypatch.delenv("SSL_CERT_FILE")
        assert self.ergebnis(tmp_path, monkeypatch, "linux")["zertifikate"] == {"SSL_CERT_FILE": None,
                                                                                 "vorhanden": False}
        assert "zertifikate" not in self.ergebnis(tmp_path, monkeypatch, "win32")     # Zertifikatsspeicher von Windows

    @staticmethod
    def hinweise_mit(tmp_path, daten: dict, name="linux-x86_64") -> list[str]:
        (tmp_path / "starttest.json").write_text(json.dumps({"ok": True, **daten}), encoding="utf-8")
        return bauen.hinweise(name, tmp_path, tag="probe")

    def test_warnung_wenn_sie_fehlt(self, tmp_path):
        zeilen = self.hinweise_mit(tmp_path, {"system": "linux",
                                              "zertifikate": {"SSL_CERT_FILE": None, "vorhanden": False}})
        assert zeilen[0].startswith("::notice title=Start-Test linux-x86_64::OK ")
        assert zeilen[1].startswith("::warning title=Zertifikate linux-x86_64::SSL_CERT_FILE nicht gesetzt. ")
        zeilen = self.hinweise_mit(tmp_path, {"system": "darwin", "zertifikate": {"SSL_CERT_FILE": "/x/cacert.pem",
                                                                                   "vorhanden": False}}, "macos-arm64")
        assert zeilen[1].startswith("::warning title=Zertifikate macos-arm64::SSL_CERT_FILE=/x/cacert.pem, die Datei "
                                    "fehlt. ")
        zeilen = self.hinweise_mit(tmp_path, {"system": "darwin"}, "macos-arm64")
        assert zeilen[1].startswith("::warning title=Zertifikate macos-arm64::Zertifikate nicht geprueft")

    def test_keine_warnung(self, tmp_path):
        vorhanden = {"system": "linux", "zertifikate": {"SSL_CERT_FILE": "/x/cacert.pem", "vorhanden": True}}
        assert not any(z.startswith("::warning") for z in self.hinweise_mit(tmp_path, vorhanden))
        assert not any(z.startswith("::warning") for z in self.hinweise_mit(tmp_path, {"system": "win32"}, "windows"))
        # ohne "system" kam kein Ergebnis vom Programm: dann meldet schon der Start-Test den Fehler
        assert len(self.hinweise_mit(tmp_path, {"ok": False, "fehler": "kein Ergebnis vom Programm"})) == 1
