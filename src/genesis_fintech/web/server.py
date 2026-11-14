"""Loopback-only UI with a small same-origin API for trusted demo policies."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from genesis_fintech import __version__
from genesis_fintech.domain.models import integer
from genesis_fintech.generation.storage import parse_json
from .app import run_view

STATIC = Path(__file__).parent / "static"
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/styles.css": ("styles.css", "text/css; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/samples.js": ("samples.js", "text/javascript; charset=utf-8"),
          "/sculpture.svg": ("sculpture.svg", "image/svg+xml"),
          "/favicon.svg": ("favicon.svg", "image/svg+xml")}


def response(method, path, headers, body, port):
    """Pure request routing, shared by HTTP adapter and transport-independent tests."""
    allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if headers.get("Host") not in allowed:
        return 403, "application/json", b'{"error":"host_not_allowed"}'
    if method == "GET" and path == "/api/status":
        return 200, "application/json", json.dumps({"ok": True, "version": __version__,
                                                     "mode": "local_demo"}).encode()
    if method == "GET" and path in ASSETS:
        filename, content_type = ASSETS[path]
        return 200, content_type, (STATIC / filename).read_bytes()
    if method == "POST" and path == "/api/run":
        if headers.get("Origin") not in {"http://" + host for host in allowed}:
            return 403, "application/json", b'{"error":"origin_not_allowed"}'
        if headers.get("Content-Type", "").split(";")[0] != "application/json":
            return 415, "application/json", b'{"error":"json_required"}'
        if len(body) > 4096:
            return 413, "application/json", b'{"error":"request_too_large"}'
        try:
            result = run_view(parse_json(body.decode("utf-8")))
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return 400, "application/json", b'{"error":"invalid_parameters"}'
        return 200, "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
    return 404, "application/json", b'{"error":"not_found"}'


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, content_type, payload):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def _handle(self, method):
        self.connection.settimeout(5)
        length = self.headers.get("Content-Length", "0")
        if not length.isdecimal() or len(length) > 5 or int(length) > 4096:
            self._send(413, "application/json", b'{"error":"request_too_large"}')
            return
        body = self.rfile.read(int(length))
        if not self.server.capacity.acquire(blocking=False):
            self._send(429, "application/json", b'{"error":"busy"}')
            return
        try:
            self._send(*response(method, self.path, self.headers, body, self.server.server_port))
        finally:
            self.server.capacity.release()

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port):
        integer(port, "port", 0, 65535)
        self.capacity = threading.BoundedSemaphore(2)
        super().__init__(("127.0.0.1", port), Handler)


def serve(port=8765):
    integer(port, "port", 1024, 65535)
    with LocalServer(port) as server:
        print(f"Genesis UI: http://127.0.0.1:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
