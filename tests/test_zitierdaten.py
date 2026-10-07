"""Quellenangaben im IEEE-Stil (zitierdaten.py), ohne Netz: Crossref und DNB werden nachgebildet."""
import json

import pytest

import pdf2md as p
import zitierdaten as z

BUCH_DOI = "10.1007/978-3-000-00002-8"
CROSSREF = {
    f"https://api.crossref.org/works/{BUCH_DOI}": {
        "type": "reference-book", "title": ["Atlas der Beispiele"],
        "subtitle": ["Fachlicher Träger Beispielgesellschaft"],
        "editor": [{"given": "Petra", "family": "Sommer"}, {"given": "Jonas", "family": "Winter"}],
        "publisher": "Springer Berlin Heidelberg", "publisher-location": "Berlin, Heidelberg",
        "edition-number": "12", "ISBN": ["9783000000013"], "isbn-type": [{"type": "print", "value": "9783000000013"}],
        "issued": {"date-parts": [[2019]]}, "DOI": BUCH_DOI},
    f"https://api.crossref.org/works/{BUCH_DOI}_5": {
        "type": "book-chapter", "title": ["Berechnung von Beispielen"],
        "author": [{"given": "Hans-Jürgen", "family": "Muster"}, {"given": "Eva", "family": "Beispiel"}],
        "page": "33-48", "container-title": ["Atlas der Beispiele"], "DOI": f"{BUCH_DOI}_5"},
}
DNB = """<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><records><record><recordData>
<record xmlns="http://www.loc.gov/MARC21/slim">
 <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Atlas der Beispiele</subfield></datafield>
 <datafield tag="250" ind1=" " ind2=" "><subfield code="a">12. Auflage</subfield></datafield>
 <datafield tag="264" ind1=" " ind2="1"><subfield code="a">Berlin</subfield><subfield code="b">Springer Vieweg</subfield>
  <subfield code="c">[2019]</subfield></datafield>
 <datafield tag="700" ind1="1" ind2=" "><subfield code="a">Sommer, Petra</subfield><subfield code="4">edt</subfield>
 </datafield>
</record></recordData></record></records></searchRetrieveResponse>"""


@pytest.fixture
def netz(monkeypatch):
    """Ersetzt den Abruf: liefert die Antworten oben und merkt sich jede abgefragte Adresse."""
    abgefragt = []

    def abrufen(url):
        abgefragt.append(url)
        if url in CROSSREF:
            return json.dumps({"message": CROSSREF[url]}).encode()
        if url.startswith("https://services.dnb.de/") and "9783000000013" in url:
            return DNB.encode()
        return None

    monkeypatch.setattr(z, "_abrufen", abrufen)
    return abgefragt


class TestIeee:
    @pytest.mark.parametrize("vorname, erwartet", [
        ("Peter", "P."), ("Hans-Jürgen", "H.-J."), ("Alfred Herbert", "A. H."), ("Yuri A.W.", "Y. A. W."), ("", "")])
    def test_initialen(self, vorname, erwartet):
        assert z.initialen(vorname) == erwartet

    def test_personen(self):
        leute = [("Anna", "A"), ("Bert", "B"), ("Carl", "C")]
        assert z.personen_ieee(leute[:1]) == "A. A"
        assert z.personen_ieee(leute[:2]) == "A. A und B. B"
        assert z.personen_ieee(leute) == "A. A, B. B und C. C"
        assert z.personen_ieee(leute * 3) == "A. A et al."

    def test_buch_mit_auflage(self):
        d = {"titel": "Beispielkunde", "autoren": [("Hans Dieter", "Muster"), ("Stefan", "Beispiel")],
             "auflage": "16., aktualisierte Auflage", "ort": "Berlin", "verlag": "Springer Vieweg", "jahr": "2016",
             "doi": "10.1007/978-3-000-00003-7"}
        assert z.ieee_buch(d) == ("H. D. Muster und S. Beispiel, *Beispielkunde*, 16. Aufl. Berlin: Springer Vieweg, "
                                  "2016, doi: 10.1007/978-3-000-00003-7.")

    def test_erste_auflage_und_ohne_verlag(self):
        d = {"titel": "Titel", "autoren": [("Peter", "Muster")], "auflage": "1", "jahr": "2021"}
        assert z.ieee_buch(d) == "P. Muster, *Titel*. 2021."

    def test_norm(self):
        norm = {"bezeichnung": "DIN EN ISO 12345", "ausgabe": "2023-07", "jahr": "2023", "titel": "Klebtechnik – Teil"}
        assert z.ieee_norm(norm) == "*Klebtechnik – Teil*, DIN EN ISO 12345:2023-07, 2023."
        entwurf = dict(norm, bezeichnung="E DIN EN ISO 24680-1", ausgabe="2025-10", jahr="2025", entwurf=True)
        assert "E DIN EN ISO 24680-1:2025-10 (Entwurf), 2025." in z.ieee_norm(entwurf)


class TestNachschlagen:
    def test_crossref_und_dnb_zusammen(self, netz):
        d = z.nachschlagen([BUCH_DOI])
        assert d["quelle"] == "Crossref + DNB"
        assert (d["verlag"], d["ort"], d["auflage"]) == ("Springer Vieweg", "Berlin", "12. Auflage")   # DNB vor Crossref
        assert d["titel"] == "Atlas der Beispiele"                    # "Fachlicher Träger ..." ist kein Untertitel
        assert z.ieee_buch(d) == ("P. Sommer und J. Winter, Hrsg., *Atlas der Beispiele*, 12. Aufl. Berlin: Springer "
                                  f"Vieweg, 2019, doi: {BUCH_DOI}.")

    def test_es_wird_nur_doi_und_isbn_gesendet(self, netz):
        z.nachschlagen([BUCH_DOI, "978-3-000-00001-3"])
        for url in netz:
            abfrage = url.split("/works/")[-1] if "crossref" in url else url.split("query=num%3D")[-1]
            assert abfrage in (BUCH_DOI, "9783000000013")

    def test_user_agent_ohne_persoenliche_angaben(self, monkeypatch):
        gesehen = {}

        def urlopen(anfrage, timeout):
            gesehen["ua"] = anfrage.get_header("User-agent")
            gesehen["url"] = anfrage.full_url
            raise OSError("offline")

        monkeypatch.setattr(z.urllib.request, "urlopen", urlopen)
        z._zwischenspeicher.clear()
        assert z.crossref("10.1000/xyz") is None
        assert gesehen["ua"] == "pdf2md/1.0" and gesehen["url"] == "https://api.crossref.org/works/10.1000/xyz"

    def test_offline(self, monkeypatch):
        monkeypatch.setattr(z, "_abrufen", lambda url: None)
        assert z.nachschlagen([BUCH_DOI, "9783000000013"]) is None


class TestKapitel:
    def test_kapitelquelle_am_kapitelanfang(self, netz):
        buch = z.nachschlagen([BUCH_DOI])
        text = ("<!-- Seite 32 (PDF 40) -->\nText.\n\n<!-- Seite 33 (PDF 41) -->\n# 5 Berechnung\n"
                f"Text\nhttps://doi.org/{BUCH_DOI}_5\n\n<!-- Seite 34 (PDF 42) -->\nweiter")
        neu, anzahl = z.kapitel_einfuegen(text, buch)
        assert anzahl == 1
        erwartet = ("<!-- Seite 33 (PDF 41) -->\n<!-- Kapitelquelle (IEEE): H.-J. Muster und E. Beispiel, "
                    "„Berechnung von Beispielen“, in *Atlas der Beispiele*, 12. Aufl., P. Sommer und J. Winter, "
                    f"Hrsg. Berlin: Springer Vieweg, 2019, S. 33–48, doi: {BUCH_DOI}_5. -->\n# 5 Berechnung")
        assert erwartet in neu

    def test_monografie_bekommt_keine_kapitelquellen(self, netz):
        buch = {"titel": "T", "autoren": [("A", "B")], "doi": BUCH_DOI, "typ": "monograph"}
        text = f"<!-- Seite 1 (PDF 1) -->\nhttps://doi.org/{BUCH_DOI}_5"
        assert z.kapitel_einfuegen(text, buch) == (text, 0)


class TestKopfblock:
    def test_ohne_netz_aus_titel_autor_jahr(self, monkeypatch):
        monkeypatch.setattr(p, "ONLINE_ABGLEICH", False)
        felder, _ = p.zitierangaben({"titel": "Mein Buch", "autor": "Anna Beispiel, Bernd Muster", "jahr": "2020",
                                     "kennungen": []}, "Text")
        assert felder["quellenangabe"] == "A. Beispiel und B. Muster, *Mein Buch*. 2020."
        assert felder["zitierdaten_quelle"].startswith("nur ")

    def test_norm(self):
        norm = {"bezeichnung": "DIN EN ISO 13579", "ausgabe": "2023-07", "jahr": "2023", "titel": "Klebtechnik – Liste"}
        felder, _ = p.zitierangaben({"titel": "x", "autor": "DIN", "jahr": "2023", "kennungen": []}, "Text", norm)
        assert felder["quellenangabe"] == "*Klebtechnik – Liste*, DIN EN ISO 13579:2023-07, 2023."
        assert set(felder) == {"quellenangabe", "zitierstil", "bibtex"}

    def test_online(self, netz, monkeypatch):
        monkeypatch.setattr(p, "ONLINE_ABGLEICH", True)
        text = f"<!-- Seite 1 (PDF 1) -->\n© 2019 Springer\nhttps://doi.org/{BUCH_DOI}"
        felder, _ = p.zitierangaben({"titel": "Atlas der Beispiele", "autor": "Petra Sommer", "jahr": "2019",
                                     "kennungen": []}, text)
        assert felder["verlag"] == "Springer Vieweg" and felder["doi"] == BUCH_DOI
        assert felder["herausgeber"] == "Petra Sommer, Jonas Winter"


BUCH = {"titel": "Beispielkunde", "autoren": [("Hans Dieter", "Muster"), ("Stefan", "Beispiel")],
        "auflage": "16., aktualisierte Auflage", "ort": "Berlin", "verlag": "Springer Vieweg", "jahr": "2016",
        "isbn": "9783000000037", "doi": "10.1007/978-3-000-00003-7"}
HRSG = {"titel": "Atlas der Beispiele", "herausgeber": [("Petra", "Sommer"), ("Jonas", "Winter")], "auflage": "12",
        "ort": "Berlin", "verlag": "Springer Vieweg", "jahr": "2019"}
KAPITEL = {"titel": "Berechnung von Beispielen", "autoren": [("Hans-Jürgen", "Muster"), ("Eva", "Beispiel")],
           "seiten": "33-48", "doi": "10.1007/978-3-000-00002-8_5"}
NORM = {"bezeichnung": "DIN EN ISO 12345", "ausgabe": "2023-07", "jahr": "2023", "titel": "Klebtechnik – Teil",
        "herausgeber": "DIN"}


class TestApa:
    def test_buch(self):
        assert z.apa_buch(BUCH) == ("Muster, H. D., & Beispiel, S. (2016). *Beispielkunde* (16. Aufl.). Springer "
                                    "Vieweg. https://doi.org/10.1007/978-3-000-00003-7")

    def test_eine_person_erste_auflage_ohne_verlag(self):
        assert z.apa_buch({"titel": "Titel", "autoren": [("Peter", "Muster")], "auflage": "1", "jahr": "2021"}) == \
            "Muster, P. (2021). *Titel*."

    def test_herausgeber(self):
        assert z.apa_buch(HRSG) == "Sommer, P., & Winter, J. (Hrsg.). (2019). *Atlas der Beispiele* (12. Aufl.). " \
                                   "Springer Vieweg."

    def test_ohne_jahr(self):
        assert z.apa_buch({"titel": "Titel", "autoren": [("Peter", "Muster")]}) == "Muster, P. (o. J.). *Titel*."

    def test_kapitel(self):
        assert z.apa_kapitel(KAPITEL, HRSG) == (
            "Muster, H.-J., & Beispiel, E. (2019). Berechnung von Beispielen. In P. Sommer & J. Winter (Hrsg.), "
            "*Atlas der Beispiele* (12. Aufl., S. 33–48). Springer Vieweg. https://doi.org/10.1007/978-3-000-00002-8_5")

    def test_norm_und_entwurf(self):
        assert z.apa_norm(NORM) == "DIN. (2023). *Klebtechnik – Teil* (DIN EN ISO 12345:2023-07)."
        entwurf = dict(NORM, bezeichnung="E DIN 9876", ausgabe="2026-09", jahr="2026", entwurf=True)
        assert z.apa_norm(entwurf) == "DIN. (2026). *Klebtechnik – Teil* (E DIN 9876:2026-09, Entwurf)."


class TestDin690:
    def test_buch(self):
        assert z.din_buch(BUCH) == ("MUSTER, Hans Dieter und Stefan BEISPIEL, 2016. *Beispielkunde*. 16. Aufl. "
                                    "Berlin: Springer Vieweg. ISBN 9783000000037. DOI: 10.1007/978-3-000-00003-7")

    def test_mehr_als_drei_personen(self):
        leute = [("Anna", "A"), ("Bert", "B"), ("Carl", "C"), ("Dora", "D")]
        assert z.din_buch({"titel": "T", "autoren": leute, "jahr": "2020"}) == "A, Anna et al., 2020. *T*."

    def test_herausgeber(self):
        assert z.din_buch(HRSG) == ("SOMMER, Petra und Jonas WINTER, Hrsg., 2019. *Atlas der Beispiele*. 12. Aufl. "
                                    "Berlin: Springer Vieweg.")

    def test_kapitel(self):
        assert z.din_kapitel(KAPITEL, HRSG) == (
            "MUSTER, Hans-Jürgen und Eva BEISPIEL, 2019. Berechnung von Beispielen. In: Petra SOMMER und Jonas "
            "WINTER, Hrsg. *Atlas der Beispiele*. 12. Aufl. Berlin: Springer Vieweg, S. 33–48. "
            "DOI: 10.1007/978-3-000-00002-8_5")

    def test_norm(self):
        assert z.din_norm(NORM) == "DIN EN ISO 12345:2023-07, 2023. *Klebtechnik – Teil*."
        entwurf = dict(NORM, bezeichnung="E DIN 9876", ausgabe="2026-09", jahr="2026", entwurf=True)
        assert z.din_norm(entwurf) == "E DIN 9876:2026-09 (Entwurf), 2026. *Klebtechnik – Teil*."


class TestStilWahl:
    @pytest.mark.parametrize("stil, anfang", [("ieee", "H. D. Muster und S. Beispiel, *"),
                                              ("apa", "Muster, H. D., & Beispiel, S. (2016)"),
                                              ("din", "MUSTER, Hans Dieter und Stefan BEISPIEL, 2016.")])
    def test_buch_im_stil(self, stil, anfang):
        assert z.buch(BUCH, stil).startswith(anfang)

    def test_unbekannter_stil_ist_ieee(self):
        assert z.buch(BUCH, "xyz") == z.ieee_buch(BUCH) and z.norm(NORM, "xyz") == z.ieee_norm(NORM)


class TestBibtex:
    def test_buch(self):
        assert z.bibtex_buch(BUCH) == (
            "@book{muster2016beispielkunde, author = {Muster, Hans Dieter and Beispiel, Stefan}, "
            "title = {{Beispielkunde}}, edition = {16}, publisher = {Springer Vieweg}, address = {Berlin}, "
            "year = {2016}, isbn = {9783000000037}, doi = {10.1007/978-3-000-00003-7}}")

    def test_herausgeber_und_erste_auflage(self):
        eintrag = z.bibtex_buch(dict(HRSG, auflage="1"))
        assert eintrag.startswith("@book{sommer2019atlas, editor = {Sommer, Petra and Winter, Jonas}, ")
        assert "edition" not in eintrag

    def test_sonderzeichen_und_umlaute(self):
        eintrag = z.bibtex_buch({"titel": "Über Lager & Wellen: 50 % Last", "autoren": [("Jörg", "Müßig")],
                                 "verlag": "Wiley & Sons", "jahr": "2020"})
        assert eintrag.startswith("@book{muessig2020ueber, ")
        assert "title = {{Über Lager \\& Wellen: 50 \\% Last}}" in eintrag
        assert "publisher = {Wiley \\& Sons}" in eintrag

    def test_schluessel_ohne_fuellwort(self):
        assert z.bibtex_schluessel([("Peter", "Muster")], "2021", "3D mit Beispielen") == "muster2021beispielen"

    def test_norm(self):
        assert z.bibtex_norm(NORM) == (
            "@standard{din12345_2023, title = {{Klebtechnik – Teil}}, number = {DIN EN ISO 12345:2023-07}, "
            "organization = {DIN}, year = {2023}}")
        entwurf = dict(NORM, bezeichnung="E DIN 9876", ausgabe="2026-09", jahr="2026", entwurf=True)
        assert z.bibtex_norm(entwurf).endswith("year = {2026}, note = {Entwurf}}")


class TestKopfblockStile:
    def test_apa_mit_bibtex(self, monkeypatch):
        monkeypatch.setattr(p, "ONLINE_ABGLEICH", False)
        monkeypatch.setattr(p, "ZITIERSTIL", "apa")
        felder, _ = p.zitierangaben({"titel": "Mein Buch", "autor": "Anna Beispiel", "jahr": "2020",
                                     "kennungen": []}, "Text")
        assert felder["quellenangabe"] == "Beispiel, A. (2020). *Mein Buch*."
        assert felder["zitierstil"] == "APA 7" and felder["bibtex"].startswith("@book{beispiel2020mein, ")

    def test_ohne_bibtex(self, monkeypatch):
        monkeypatch.setattr(p, "ONLINE_ABGLEICH", False)
        monkeypatch.setattr(p, "BIBTEX", False)
        felder, _ = p.zitierangaben({"titel": "Mein Buch", "autor": "Anna Beispiel", "jahr": "2020",
                                     "kennungen": []}, "Text")
        assert "bibtex" not in felder and felder["zitierstil"] == "IEEE"

    def test_norm_im_stil(self, monkeypatch):
        monkeypatch.setattr(p, "ZITIERSTIL", "din")
        felder, _ = p.zitierangaben({"titel": "x", "autor": "DIN", "jahr": "2023", "kennungen": []}, "Text", NORM)
        assert felder["quellenangabe"] == "DIN EN ISO 12345:2023-07, 2023. *Klebtechnik – Teil*."
        assert felder["zitierstil"] == "DIN ISO 690" and felder["bibtex"].startswith("@standard{")

    def test_kapitelquelle_im_stil(self, netz, monkeypatch):
        buch = z.nachschlagen([BUCH_DOI])
        text = f"<!-- Seite 33 (PDF 41) -->\n# 5 Berechnung\nhttps://doi.org/{BUCH_DOI}_5\n"
        neu, anzahl = z.kapitel_einfuegen(text, buch, "apa")
        assert anzahl == 1 and "<!-- Kapitelquelle (APA 7): Muster, H.-J., & Beispiel, E. (2019). " in neu

    @pytest.mark.parametrize("stil, im_text", [("ieee", "[Nr., S. S]"), ("apa", "(Autor, Jahr, S. S)"),
                                               ("din", "(AUTOR Jahr, S. S)")])
    def test_zitierhinweis_nennt_stil(self, monkeypatch, stil, im_text):
        monkeypatch.setattr(p, "ZITIERSTIL", stil)
        assert im_text in p.zitierhinweis() and z.STILE[stil] in p.zitierhinweis()
