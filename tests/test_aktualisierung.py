"""Version und Update-Suche (aktualisierung.py): GitHub wird nachgebildet, kein Test geht ins Netz."""
import json
import re

import pytest

import aktualisierung as A


def test_version_ist_eine_versionsnummer():
    assert re.fullmatch(r"\d+\.\d+\.\d+", A.VERSION)


@pytest.mark.parametrize("text, erwartet", [("v1.2.0", (1, 2, 0)), ("1.10", (1, 10, 0)), ("V2", (2, 0, 0)),
                                            ("1.2.0-beta", None), ("", None), (None, None)])
def test_zahlen(text, erwartet):
    assert A.zahlen(text) == erwartet


@pytest.fixture
def github(monkeypatch):
    """Ersetzt den Abruf; antwort["tag"] ist der Tag des neuesten Releases (None = offline)."""
    antwort = {"tag": "v99.0.0", "abrufe": []}

    def abrufen(adresse):
        antwort["abrufe"].append(adresse)
        return None if antwort["tag"] is None else json.dumps({"tag_name": antwort["tag"]}).encode()
    monkeypatch.setattr(A, "_abrufen", abrufen)
    return antwort


def test_neuere_version(github):
    assert A.neuere_version() == "99.0.0" and github["abrufe"] == [A.ADRESSE]


@pytest.mark.parametrize("tag", [f"v{A.VERSION}", "v0.0.1", "kaputt", None])
def test_keine_neuere(github, tag):
    github["tag"] = tag
    assert A.neuere_version() is None


def test_ausgeschaltet_fragt_nicht(github, monkeypatch):
    monkeypatch.setattr(A, "SUCHEN", False)
    assert A.neuere_version() is None and github["abrufe"] == []


def test_anfrage_ohne_persoenliche_angaben(monkeypatch):
    gesehen = {}

    def urlopen(anfrage, timeout):
        gesehen["url"], gesehen["kopf"] = anfrage.full_url, dict(anfrage.header_items())
        raise OSError("offline")
    monkeypatch.setattr(A.urllib.request, "urlopen", urlopen)
    assert A.neuere_version() is None
    assert gesehen["url"] == "https://api.github.com/repos/S4ltc/pdf2md/releases/latest"
    assert gesehen["kopf"] == {"User-agent": "pdf2md/1.0", "Accept": "application/vnd.github+json"}
