"""Ablage: Listen fuer Eingang, Prüfen und Fertig, Signatur der Ordner, Kopieren nach Eingang."""
import os

import ablage
import pdf2md


def md_schreiben(pfad, **kopf):
    pfad.write_text(pdf2md.kopf_schreiben(kopf) + "Text", encoding="utf-8")


def test_eingang_liste_nur_unterstuetzte_dateien(tmp_path):
    (tmp_path / "b.pdf").write_bytes(b"x" * 2048)
    (tmp_path / "a.epub").write_bytes(b"x")
    (tmp_path / "notiz.txt").write_text("x")
    (tmp_path / "~$offen.docx").write_bytes(b"x")
    assert ablage.eingang_liste(tmp_path) == [{"name": "a.epub", "format": "EPUB", "groesse": 1},
                                              {"name": "b.pdf", "format": "PDF", "groesse": 2048}]
    assert ablage.eingang_liste(tmp_path / "fehlt") == []


def test_pruefen_liste_kennzeichnet_bereit(tmp_path):
    md_schreiben(tmp_path / "x.md", titel="T", autor="A", jahr="2001", pruefen="Jahr fehlt")
    (tmp_path / "x.pdf").write_bytes(b"x")
    md_schreiben(tmp_path / "y.md", titel="T", autor=None, jahr=None, pruefen="Autor fehlt; Jahr fehlt")
    (tmp_path / "y.docx").write_bytes(b"x")
    liste = {e["name"]: e for e in ablage.pruefen_liste(tmp_path)}
    assert liste["x.pdf"]["bereit"] and liste["x.pdf"]["hinweis"] == "bereit zur Übernahme"
    assert liste["x.pdf"]["grund"] == "Jahr fehlt"
    assert not liste["y.docx"]["bereit"] and liste["y.docx"]["grund"] == "Autor fehlt; Jahr fehlt"
    assert liste["y.docx"]["hinweis"] == "Autor fehlt; Jahr fehlt" and liste["y.docx"]["format"] == "DOCX"


def test_pruefen_liste_ohne_original(tmp_path):
    md_schreiben(tmp_path / "z.md", titel="T", autor="A", jahr="2001", pruefen="Autor fehlt")
    eintrag = ablage.pruefen_liste(tmp_path)[0]
    assert eintrag["name"] == "z.md" and not eintrag["bereit"] and eintrag["hinweis"] == "Originaldatei fehlt"


def test_fertig_je_buch_neueste_oben(tmp_path):
    for i, n in enumerate(("Alt", "Neu", "Mitte")):
        (tmp_path / f"{n}.pdf").write_bytes(b"x")
        md_schreiben(tmp_path / f"{n}.md", titel=n)
        zeit = 1_700_000_000 + {"Alt": 0, "Mitte": 100, "Neu": 200}[n]
        os.utime(tmp_path / f"{n}.md", (zeit, zeit))
    liste = ablage.fertig_liste(tmp_path)
    assert [e["name"] for e in liste] == ["Neu", "Mitte", "Alt"]
    assert liste[0]["format"] == "PDF" and liste[0]["md"] == "Neu.md" and len(liste[0]["datum"]) == 10


def test_signatur_aendert_sich_bei_neuer_oder_geaenderter_datei(tmp_path):
    datei = tmp_path / "Protokoll.csv"
    vorher = ablage.signatur(tmp_path, datei)
    (tmp_path / "a.pdf").write_bytes(b"x")
    nachher = ablage.signatur(tmp_path, datei)
    assert nachher != vorher and ablage.signatur(tmp_path, datei) == nachher
    datei.write_text("x")
    assert ablage.signatur(tmp_path, datei) != nachher


def test_kopieren_mit_namensgleichheit_und_abgelehnten_formaten(tmp_path):
    quelle, eingang = tmp_path / "q", tmp_path / "Eingang"
    quelle.mkdir()
    eingang.mkdir()
    (quelle / "a.pdf").write_bytes(b"1")
    (quelle / "b.txt").write_text("x")
    (eingang / "a.pdf").write_bytes(b"0")
    erg = ablage.kopieren([quelle / "a.pdf", quelle / "b.txt", tmp_path / "weg.pdf"], eingang)
    assert erg["kopiert"] == ["a (2).pdf"]
    assert erg["abgelehnt"] == [("b.txt", "Format nicht unterstützt"), ("weg.pdf", "nicht gefunden")]
    assert (quelle / "a.pdf").exists() and (eingang / "a (2).pdf").read_bytes() == b"1"   # Original bleibt


def test_kopieren_ganzer_ordner_und_datei_aus_dem_eingang(tmp_path):
    quelle, eingang = tmp_path / "q", tmp_path / "Eingang"
    quelle.mkdir()
    (quelle / "a.pdf").write_bytes(b"1")
    (quelle / "b.docx").write_bytes(b"2")
    erg = ablage.kopieren([quelle], eingang)                                  # Eingang wird angelegt
    assert sorted(erg["kopiert"]) == ["a.pdf", "b.docx"]
    erg = ablage.kopieren([eingang / "a.pdf"], eingang)
    assert erg == {"kopiert": [], "abgelehnt": [("a.pdf", "liegt schon im Eingang")]}
