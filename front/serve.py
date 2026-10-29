"""Sirve el panel estático y publica la URL de la API en ``/config.js``.

Uso:

    API_URL=http://localhost:8000 python3 front/serve.py

Variables de entorno:
    API_URL  URL base de la API (por defecto http://localhost:8000).
    PORT     Puerto en el que se sirve el panel (por defecto 5173).
"""

import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
PORT = int(os.environ.get("PORT", "5173"))


class PanelHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/config.js":
            body = f"window.API_URL = {json.dumps(API_URL)};\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(PanelHandler, directory=ROOT))
    print(f"Panel en http://localhost:{PORT} (API: {API_URL})")
    server.serve_forever()
