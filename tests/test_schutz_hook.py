"""Schutz-Hook fuer Claude Code (.claude/hooks/schutz.py): blockiert Schreiben in die Nutzerdaten unter dist/ und
git push. Die Befehle sind erfunden, decken aber die Schreibweisen ab, die in Sitzungen vorkommen (Git Bash,
PowerShell, absolute Windows-Pfade, Python-Einzeiler)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "schutz.py"
_spec = importlib.util.spec_from_file_location("schutz", SKRIPT)
schutz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schutz)

PROJEKT = str(schutz.PROJEKT)


def shell(befehl, werkzeug="Bash"):
    return schutz.pruefen({"tool_name": werkzeug, "tool_input": {"command": befehl}, "cwd": PROJEKT})


def datei(pfad, werkzeug="Edit", feld="file_path"):
    return schutz.pruefen({"tool_name": werkzeug, "tool_input": {feld: str(pfad)}, "cwd": PROJEKT})


class TestDateiwerkzeuge:
    @pytest.mark.parametrize("teil", ["Fertig/Beispiel - Erika Muster - 2020.md", "Prüfen/a.md", "Protokoll.csv",
                                      "Einstellungen.json", "neu.txt"])
    def test_schreiben_in_dist_ist_gesperrt(self, teil):
        assert datei(schutz.DIST / teil) is not None
        assert datei(schutz.DIST / teil, werkzeug="Write") is not None

    def test_relativer_pfad_und_andere_schreibweise(self):
        assert datei("dist/Prüfen/a.md") is not None
        assert datei(PROJEKT + "\\DIST\\fertig\\a.md") is not None

    def test_notebook_in_dist(self):
        assert datei(schutz.DIST / "x.ipynb", werkzeug="NotebookEdit", feld="notebook_path") is not None

    @pytest.mark.parametrize("pfad", ["tests/test_x.py", "docs/claude/tabellen.md", "distanz.py", "dist2/a.md"])
    def test_ausserhalb_von_dist_erlaubt(self, pfad):
        assert datei(Path(PROJEKT) / pfad) is None

    def test_lesen_ist_nie_betroffen(self):
        assert schutz.pruefen({"tool_name": "Read", "tool_input": {"file_path": str(schutz.DIST / "Protokoll.csv")}}) \
            is None


class TestGitPush:
    @pytest.mark.parametrize("befehl", [
        "git push",
        "git push origin main",
        'cd /c/Projekte/pdf2md && git push --tags',
        '"C:/Program Files/Git/cmd/git.exe" push origin main',
        "git -C /c/Projekte/pdf2md push",
        "git -c core.sshCommand=ssh push",
        "git --no-pager push",
        '"git" push',
    ])
    def test_push_gesperrt(self, befehl):
        assert shell(befehl) is not None

    def test_push_in_powershell(self):
        assert shell('& "C:\\Program Files\\Git\\cmd\\git.exe" push', werkzeug="PowerShell") is not None

    @pytest.mark.parametrize("befehl", ['git commit -m "push-Hinweis ergaenzt"', "git stash push", "git status",
                                        "git log --oneline -5", "git pull --dry-run",
                                        'git commit -m "Hook sperrt git push"', "echo 'git push'"])
    def test_andere_git_befehle_erlaubt(self, befehl):
        assert shell(befehl) is None


class TestShellInDist:
    @pytest.mark.parametrize("befehl", [
        "rm -rf dist/Fertig",
        "rm -rf dist",
        'rm "C:\\Projekte\\pdf2md\\dist\\Fertig\\a.md"',
        "mv dist/Eingang/a.pdf /tmp/",
        "echo x > dist/Protokoll.csv",
        "echo x >> dist/Sicherung/b.md",
        "cp -r /tmp/kopie dist/Fertig/",
        "sed -i 's/a/b/' dist/Fertig/a.md",
        "robocopy C:\\tmp\\x dist\\Fertig /E",
        "py werkzeuge/ui_vorschau.py C:/Projekte/pdf2md/dist 8765",
        "PDF2MD_ABLAGE=dist py ui_app.py",
        "py -c \"import shutil; shutil.rmtree('dist/Sicherung')\"",
        "py -c \"open('dist/Protokoll.csv', 'w').write('')\"",
    ])
    def test_veraendern_gesperrt(self, befehl):
        assert shell(befehl) is not None

    @pytest.mark.parametrize("befehl", [
        "Remove-Item -Recurse dist\\Prüfen",
        "Move-Item dist\\Eingang\\a.pdf C:\\tmp",
        "Set-Content dist\\Einstellungen.json '{}'",
        "Copy-Item -Path C:\\tmp\\a.md -Destination dist\\Fertig",
    ])
    def test_veraendern_in_powershell_gesperrt(self, befehl):
        assert shell(befehl, werkzeug="PowerShell") is not None

    @pytest.mark.parametrize("befehl", [
        "ls dist/Fertig | head",
        "cat dist/Protokoll.csv",
        "cp dist/Fertig/a.md /tmp/kopie/",
        "cp -r dist/Fertig dist/Prüfen /tmp/kopie",
        "robocopy dist\\Fertig C:\\tmp\\kopie /E",
        "rm dist/pdf2md.exe",
        "git status dist",
        "py werkzeuge/ui_vorschau.py C:/tmp/kopie 8765",
        "py -c \"print(open('dist/Protokoll.csv').read())\"",
        "head -5 dist/Protokoll.csv 2>/dev/null > /tmp/kopf.csv",
        "powershell -ExecutionPolicy Bypass -File build.ps1",
    ])
    def test_lesen_und_kopieren_aus_dist_erlaubt(self, befehl):
        assert shell(befehl) is None

    def test_kopieren_aus_dist_in_powershell_erlaubt(self):
        assert shell("Copy-Item -Path dist\\Fertig -Destination C:\\tmp\\kopie -Recurse", werkzeug="PowerShell") \
            is None


class TestAufruf:
    """So ruft Claude Code den Hook auf: JSON auf stdin, Entscheidung als JSON auf stdout, immer Exitcode 0."""

    def lauf(self, eingabe: bytes):
        return subprocess.run([sys.executable, str(SKRIPT)], input=eingabe, capture_output=True, timeout=30)

    def test_gesperrt_liefert_deny(self):
        e = {"tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": PROJEKT}
        r = self.lauf(json.dumps(e).encode("utf-8"))
        assert r.returncode == 0
        aus = json.loads(r.stdout)["hookSpecificOutput"]
        assert aus["hookEventName"] == "PreToolUse" and aus["permissionDecision"] == "deny"
        assert "Nutzer" in aus["permissionDecisionReason"]

    def test_umlaut_im_pfad_ueber_stdin(self):
        e = {"tool_name": "Edit", "tool_input": {"file_path": str(schutz.DIST / "Prüfen" / "ä.md")}, "cwd": PROJEKT}
        r = self.lauf(json.dumps(e, ensure_ascii=False).encode("utf-8"))
        assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bom_wie_aus_der_powershell_pipe(self):
        e = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
        r = self.lauf(b"\xef\xbb\xbf" + json.dumps(e).encode("utf-8"))
        assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_erlaubt_ohne_ausgabe(self):
        r = self.lauf(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}).encode("utf-8"))
        assert r.returncode == 0 and r.stdout.strip() == b""

    def test_kaputte_eingabe_blockiert_nichts(self):
        r = self.lauf(b"kein json")
        assert r.returncode == 0 and r.stdout.strip() == b""
