"""Kopfblock der .md: Schreiben, tolerantes Lesen (BOM, fehlende Anfuehrungszeichen), Zeilenenden."""

import pdf2md as p


def test_roundtrip_mit_sonderzeichen():
    werte = {"titel": 'Ein "Buch": mit Umlauten äöü', "jahr": "2019", "seiten": 12, "kennung": None}
    lesbar, text = p.kopf_lesen(p.kopf_schreiben(werte) + "Der Text.")
    assert lesbar == werte
    assert text == "Der Text."


def test_text_bleibt_beim_umschreiben_unveraendert():
    werte, text = p.kopf_lesen(p.kopf_schreiben({"a": "1"}) + "\nErste Zeile\nZweite")
    wieder, text2 = p.kopf_lesen(p.kopf_schreiben(werte) + text)
    assert text2 == text


def test_tolerantes_lesen_ohne_anfuehrungszeichen():
    werte, _ = p.kopf_lesen("---\ntitel: Mein Buch: mit Untertitel\njahr: 2019\nautor:\n---\n\nText")
    assert werte["titel"] == "Mein Buch: mit Untertitel"
    assert werte["jahr"] == 2019 and werte["autor"] == ""


def test_kein_kopfblock():
    werte, text = p.kopf_lesen("Nur Text ohne Kopf")
    assert werte is None and text == "Nur Text ohne Kopf"


def test_md_wird_immer_mit_lf_geschrieben(tmp_path):
    datei = tmp_path / "a.md"
    p.md_schreiben(datei, "Zeile 1\nZeile 2\n")
    assert b"\r" not in datei.read_bytes()
