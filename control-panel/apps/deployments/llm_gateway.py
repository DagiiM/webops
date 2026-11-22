"""Authenticated, minimal HTTP proxy for a loopback-only OpenAI-compatible LLM.

This is a Runpod development adapter, not a replacement for a hardened reverse
proxy or a production API gateway. No model access is possible without a key.
"""
from __future__ import annotations

import hmac
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_BODY = 1024 * 1024
KEY_FILE = Path(os.environ["WEBOPS_LLM_KEY_FILE"])
UPSTREAM_PORT = int(os.environ.get("WEBOPS_LLM_UPSTREAM_PORT", "8002"))
PROXY_PORT = int(os.environ.get("WEBOPS_LLM_PROXY_PORT", "8001"))
ALLOWED_PATHS = ("/v1/models", "/v1/chat/completions", "/v1/completions",
                 "/v1/embeddings", "/health")


class Handler(BaseHTTPRequestHandler):
    server_version = "WebOpsLLM/1.0"
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        # Do not log prompts or authorization headers.
        pass

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def _error(self, status: int, message: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(message)))
        self.end_headers()
        self.wfile.write(message)

    def _forward(self, method: str):
        path = urlsplit(self.path)
        if path.path not in ALLOWED_PATHS or len(self.path) > 2048:
            return self._error(404, b'{"error":"not_found"}')
        actual = self.headers.get("Authorization", "")
        expected = "Bearer " + KEY_FILE.read_text(encoding="utf-8").strip()
        if not hmac.compare_digest(actual, expected):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "Bearer")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._error(400, b'{"error":"invalid_content_length"}')
        if size < 0 or size > MAX_BODY:
            return self._error(413, b'{"error":"request_too_large"}')
        data = self.rfile.read(size) if method == "POST" else None
        uri = f"http://127.0.0.1:{UPSTREAM_PORT}{self.path}"
        upstream = Request(uri, method=method, data=data,
                           headers={"Content-Type": "application/json"})
        try:
            response = urlopen(upstream, timeout=95)
        except HTTPError as exc:
            response = exc
        except (OSError, URLError):
            return self._error(503, b'{"error":"model_unavailable"}')
        with response:
            self.send_response(response.status)
            self.send_header("Content-Type",
                             response.headers.get("Content-Type", "application/json"))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    chunk = response.read1(8192) if hasattr(response, "read1") else response.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), Handler).serve_forever()
