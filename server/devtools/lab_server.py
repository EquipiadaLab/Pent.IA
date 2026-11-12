"""Alvo de ENSAIO local com falhas propositais (so escuta em 127.0.0.1).

Serve para testar o Motor e para a demo nao depender da rede do evento.
    python devtools/lab_server.py            # vulneravel, porta 8000
    python devtools/lab_server.py --hardened # versao corrigida (para a "revanche")
"""

from __future__ import annotations

import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(hardened: bool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "lab"
        sys_version = ""

        def log_message(self, *args):  # silencioso
            pass

        def _send(self, status: int, body: str, ctype: str = "text/html", extra: list[tuple[str, str]] | None = None):
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            origin = self.headers.get("Origin")
            if hardened:
                for k, v in [
                    ("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'self'"),
                    ("X-Content-Type-Options", "nosniff"),
                    ("Referrer-Policy", "no-referrer"),
                    ("Permissions-Policy", "geolocation=()"),
                    ("Set-Cookie", "sid=abc123SESSION; HttpOnly; SameSite=Lax"),
                ]:
                    self.send_header(k, v)
            else:
                self.send_header("Server", "lab-nginx/1.14.0")
                self.send_header("X-Powered-By", "Express")
                self.send_header("X-XSS-Protection", "1; mode=block")
                self.send_header("Content-Security-Policy-Report-Only", "default-src 'self'")
                self.send_header("Set-Cookie", "sid=abc123SESSION")
                self.send_header("Set-Cookie", "theme=dark; SameSite=None")
                if origin:  # CORS refletindo qualquer origem, com credenciais
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Access-Control-Allow-Credentials", "true")
            for k, v in extra or []:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                return self._send(200, "<h1>lab</h1>")
            if not hardened and path == "/.git/HEAD":
                return self._send(200, "ref: refs/heads/main\n", "text/plain")
            if not hardened and path == "/.env":
                return self._send(200, "SECRET_KEY=s3cr3t\nDB_PASSWORD=hunter2\n", "text/plain")
            if hardened:
                return self._send(404, "Not found")
            return self._send(500, 'Traceback (most recent call last):\n  File "app.py", line 1, in <module>\n', "text/plain")

        def do_OPTIONS(self):
            allow = "GET, OPTIONS" if hardened else "GET, POST, PUT, DELETE, TRACE, OPTIONS"
            self._send(204, "", "text/plain", [("Allow", allow)])

    return Handler


def start(port: int = 0, hardened: bool = False) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(hardened))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--hardened", action="store_true")
    args = ap.parse_args()
    srv, url = start(args.port, args.hardened)
    print(f"Lab em {url} ({'corrigido' if args.hardened else 'vulneravel'}). Ctrl+C para sair.")
    threading.Event().wait()
