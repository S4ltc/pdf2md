"""Entwicklungsserver fuer die Oberflaeche: liefert ui/web aus und beantwortet POST /api/<methode> mit ui_app.Api.

So laeuft dieselbe Oberflaeche wie im Fenster auch im Browser (Screenshots in mehreren Breiten, hell/dunkel,
Tastaturtest), auf einer beliebigen Ablage, zum Beispiel einer Kopie von dist im Scratchpad. Nie auf dist selbst
zeigen lassen: "Starten" und die Werkzeuge veraendern die Ablage wirklich. Nur 127.0.0.1, nur oeffentliche Methoden.
Ohne Fenster gibt es keinen Dateidialog und kein Ablegen per Ziehen.

Aufruf:  python werkzeuge/ui_vorschau.py <ablage> [port]     (Thema erzwingen: ...?thema=hell bzw. ?thema=dunkel)"""
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import ui_app  # noqa: E402

MODUS = '<head>\n<meta name="pdf2md-modus" content="http">'


def handler_fuer(api: ui_app.Api):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ui_app.web_ordner()), **kwargs)

        def log_message(self, *args):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _senden(self, code: int, daten: bytes, art: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", art)
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)

        def do_GET(self):
            if self.path.split("?")[0] in ("/", "/index.html"):
                html = (ui_app.web_ordner() / "index.html").read_text(encoding="utf-8").replace("<head>", MODUS, 1)
                return self._senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return super().do_GET()

        def do_POST(self):
            name = self.path[len("/api/"):] if self.path.startswith("/api/") else ""
            methode = getattr(api, name, None) if name and not name.startswith("_") else None
            if not callable(methode):
                return self._senden(404, b'{"fehler": "unbekannt"}', "application/json")
            laenge = int(self.headers.get("Content-Length") or 0)
            try:
                args = json.loads(self.rfile.read(laenge) or b"[]")
                ergebnis = methode(*args)
            except Exception as e:
                return self._senden(500, json.dumps({"fehler": str(e)}).encode("utf-8"), "application/json")
            self._senden(200, json.dumps(ergebnis, ensure_ascii=False).encode("utf-8"), "application/json")

    return Handler


def server(ablage: Path, port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), handler_fuer(ui_app.Api(Path(ablage))))


def main() -> None:
    ablage = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    s = server(ablage, port)
    print(f"http://127.0.0.1:{s.server_port}/   Ablage: {ablage}", flush=True)
    s.serve_forever()


if __name__ == "__main__":
    main()
