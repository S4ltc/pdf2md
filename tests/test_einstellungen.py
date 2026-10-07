"""Einstellungen: Verzeichnis, Speichern/Laden (Einstellungen.json), Anwenden auf die Module."""
import importlib
import json
import re
from pathlib import Path

import pytest

import einstellungen as E


@pytest.fixture(autouse=True)
def standard_zuruecksetzen():
    """anwenden() aendert Modulwerte: nach jedem Test wieder alles auf Standard."""
    yield
    E.anwenden(E.standardwerte())


def test_standard_entspricht_dem_code():
    """Verzeichnis und Module duerfen nicht auseinanderlaufen."""
    for e in E.EINSTELLUNGEN:
        assert getattr(importlib.import_module(e.modul), e.name) == e.standard, e.schluessel


def test_ausgenommen_und_vollstaendig():
    namen = {e.schluessel for e in E.EINSTELLUNGEN}
    assert "zitierdaten.USER_AGENT" not in namen and "formeln.DIAGNOSE" not in namen
    assert "tabellen.MIN_UEBERSTAND" not in namen and "zitierdaten.TIMEOUT" not in namen   # abgeleitet
    assert len(namen) == len(E.EINSTELLUNGEN) == 89
    assert sum(e.stufe == "normal" for e in E.EINSTELLUNGEN) == 15
    assert {e.typ for e in E.EINSTELLUNGEN} == {"bool", "int", "float", "wahl"}


def test_jede_zahl_hat_bereich_und_standard_liegt_darin():
    for e in E.EINSTELLUNGEN:
        if e.typ in ("int", "float"):
            assert e.bereich and e.bereich[0] <= e.standard <= e.bereich[1], e.schluessel
            assert e.schritt and e.schritt > 0, e.schluessel


def test_tooltip_hoechstens_zwei_saetze_plus_standard():
    for e in E.EINSTELLUNGEN:
        assert e.titel and e.gruppe, e.schluessel
        assert 1 <= len(re.findall(r"[.!?](?:\s|$)", e.hilfe)) <= 2, e.schluessel
        assert "Standard:" not in e.hilfe and E.tooltip(e).endswith(".")
        assert "Standard:" in E.tooltip(e)


def test_tooltip_nennt_standard_lesbar():
    assert E.tooltip(E.NACH_SCHLUESSEL["pdf2md.FORMELSATZ"]).endswith("Standard: an.")
    assert E.tooltip(E.NACH_SCHLUESSEL["pdf2md.ONLINE_TIMEOUT"]).endswith("Standard: 10 s.")
    assert E.tooltip(E.NACH_SCHLUESSEL["pdf2md.PDF_ENGINE"]).endswith("Standard: PDFium.")


def test_pruefen_klemmt_und_wandelt():
    assert E.pruefen("tabellen.TOLERANZ", "99") == 8.0
    assert E.pruefen("tabellen.MIN_ZEILEN", 2.6) == 3
    assert E.pruefen("pdf2md.FORMELSATZ", 0) is False
    assert E.pruefen("pdf2md.FORMELSATZ", "aus") is False
    assert E.pruefen("pdf2md.PDF_ENGINE", "markitdown") == "markitdown"
    with pytest.raises(ValueError):
        E.pruefen("pdf2md.PDF_ENGINE", "ocr")
    with pytest.raises(ValueError):
        E.pruefen("tabellen.TOLERANZ", "abc")
    with pytest.raises(KeyError):
        E.pruefen("zitierdaten.USER_AGENT", "x")


def test_speichern_nur_abweichungen_und_laden(tmp_path):
    werte = E.standardwerte() | {"tabellen.TOLERANZ": 3.0}
    E.speichern(tmp_path / E.DATEINAME, werte)
    assert json.loads((tmp_path / E.DATEINAME).read_text(encoding="utf-8")) == {"tabellen.TOLERANZ": 3.0}
    assert E.laden(tmp_path / E.DATEINAME)["tabellen.TOLERANZ"] == 3.0
    E.speichern(tmp_path / E.DATEINAME, E.standardwerte())
    assert json.loads((tmp_path / E.DATEINAME).read_text(encoding="utf-8")) == {}


def test_fehlende_kaputte_oder_fremde_werte_werden_ignoriert(tmp_path):
    assert E.laden(tmp_path / E.DATEINAME) == E.standardwerte()
    (tmp_path / E.DATEINAME).write_text('{"pdf2md.MAX_NAME_LEN": 90', encoding="utf-8")   # abgeschnitten
    assert E.laden(tmp_path / E.DATEINAME) == E.standardwerte()
    (tmp_path / E.DATEINAME).write_text('{"tabellen.TOLERANZ": "abc", "x.Y": 1, "pdf2md.MAX_NAME_LEN": 90}',
                                        encoding="utf-8")
    assert E.laden(tmp_path / E.DATEINAME) == E.standardwerte() | {"pdf2md.MAX_NAME_LEN": 90}


def test_anwenden_setzt_module_und_zieht_abgeleitete_werte_mit():
    import pdf2md
    import tabellen
    import zitierdaten
    E.anwenden(E.standardwerte() | {"tabellen.TOLERANZ": 3.0, "pdf2md.ONLINE_TIMEOUT": 20,
                                     "pdf2md.FORMELSATZ": False})
    assert tabellen.TOLERANZ == 3.0 and tabellen.MIN_UEBERSTAND == 9.0
    assert pdf2md.ONLINE_TIMEOUT == 20 and zitierdaten.TIMEOUT == 20 and pdf2md.FORMELSATZ is False
    assert E.aktuell()["tabellen.TOLERANZ"] == 3.0


def test_anwenden_setzt_formel_referenz_zurueck_wenn_sich_das_raster_aendert():
    import formeln
    formeln._REFERENZ = "alt"
    E.anwenden(E.standardwerte())
    assert formeln._REFERENZ == "alt"
    E.anwenden(E.standardwerte() | {"formeln.RASTER": 30})
    assert formeln._REFERENZ is None


def test_abweichungstext():
    assert E.abweichungstext(E.standardwerte()) is None
    text = E.abweichungstext(E.standardwerte() | {"pdf2md.FORMELSATZ": False, "tabellen.TOLERANZ": 3.0,
                                                   "formelsatz.KLEINER": 0.8})
    assert text == "abweichend: FORMELSATZ=aus, tabellen.TOLERANZ=3, KLEINER=0.8"


def test_keine_einstellung_wird_beim_import_kopiert():
    """Defaultwerte von Funktionen oder from-Importe wuerden eine Einstellung beim Import festschreiben."""
    wurzel = Path(E.__file__).parent
    for e in E.EINSTELLUNGEN:
        for datei in wurzel.glob("*.py"):
            quelle = datei.read_text(encoding="utf-8")
            assert not re.search(rf"def \w+\([^)]*=\s*{e.name}\b", quelle), (e.schluessel, datei.name)
            assert not re.search(rf"from {e.modul} import [^\n]*\b{e.name}\b", quelle), (e.schluessel, datei.name)
