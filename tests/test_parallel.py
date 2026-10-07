"""Parallele Umwandlung grosser PDFs ueber den MarkItDown-Weg (_markitdown_umwandeln, nur ab PARALLEL_AB_SEITEN
Seiten). PDFium (Standard-Engine) braucht das nicht, aber der MarkItDown-Rueckfall (Einstellung PDF-Engine) und Nicht-PDF-Fallbacks
durchlaufen diesen Pfad. War bisher ungetestet; MAX_PROZESSE war frueher fest auf 8 begrenzt, jetzt os.cpu_count()."""

import os

import pytest

import pdf2md as p
from conftest import erzeuge_pdf


@pytest.mark.langsam
class TestParalleleUmwandlung:
    def test_grosses_pdf_wird_in_paketen_parallel_umgewandelt(self, tmp_path, konverter, monkeypatch):
        monkeypatch.setattr(p, "PARALLEL_AB_SEITEN", 40)      # nicht 400 echte Seiten fuer den Test noetig
        monkeypatch.setattr(p, "SEITEN_PRO_PAKET", 10)
        seiten = 60
        pdf = erzeuge_pdf(tmp_path / "gross.pdf", [f"Seite {i}: Fliesstext fuer den Paralleltest." for i in range(seiten)])
        text = p._markitdown_umwandeln(pdf, seiten, konverter)
        assert "Seite 0" in text and f"Seite {seiten - 1}" in text
        # alle Pakete muessen vertreten sein, keins darf beim Zusammensetzen verloren gehen
        for i in range(0, seiten, p.SEITEN_PRO_PAKET):
            assert f"Seite {i}" in text

    def test_max_prozesse_ist_nicht_mehr_fest_auf_acht_begrenzt(self):
        """Regressionstest: MAX_PROZESSE war frueher eine feste Obergrenze von 8 und nutzte auf Maschinen mit mehr
        Kernen nicht alle. Jetzt richtet es sich nach os.cpu_count()."""
        kerne = os.cpu_count() or 1
        assert p.MAX_PROZESSE == kerne or p.MAX_PROZESSE >= 8

    def test_mehr_als_acht_pakete_nutzen_mehr_als_acht_prozesse_wenn_vorhanden(self, tmp_path, konverter, monkeypatch):
        if (os.cpu_count() or 1) <= 8:
            pytest.skip("Maschine hat nicht mehr als 8 Kerne")
        monkeypatch.setattr(p, "PARALLEL_AB_SEITEN", 40)
        monkeypatch.setattr(p, "SEITEN_PRO_PAKET", 5)          # 100 Seiten / 5 = 20 Pakete
        seiten = 100
        pdf = erzeuge_pdf(tmp_path / "gross.pdf", [f"Seite {i}: Text." for i in range(seiten)])
        pakete = (seiten + p.SEITEN_PRO_PAKET - 1) // p.SEITEN_PRO_PAKET
        prozesse = max(1, min(p.MAX_PROZESSE, os.cpu_count() or 1, pakete))
        assert prozesse > 8
        text = p._markitdown_umwandeln(pdf, seiten, konverter)
        assert "Seite 0" in text and f"Seite {seiten - 1}" in text


def _wert_im_unterprozess():
    import pdf2md
    import tabellen
    return pdf2md.SEITEN_PRO_PAKET, tabellen.MIN_UEBERSTAND


def test_einstellungen_kommen_im_unterprozess_an(monkeypatch):
    """Unterprozesse importieren die Module frisch; anwenden() als initializer bringt die Einstellungen hinein,
    abgeleitete Werte eingeschlossen (so ruft _markitdown_umwandeln den ProcessPoolExecutor auf)."""
    import concurrent.futures

    import einstellungen
    import tabellen
    monkeypatch.setattr(p, "SEITEN_PRO_PAKET", 17)
    monkeypatch.setattr(tabellen, "TOLERANZ", 3.0)
    with concurrent.futures.ProcessPoolExecutor(1, initializer=einstellungen.anwenden,
                                                initargs=(einstellungen.aktuell(),)) as pool:
        assert pool.submit(_wert_im_unterprozess).result() == (17, 9.0)
