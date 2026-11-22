"""Regression tests for the authenticated Runpod loopback LLM gateway."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.deployments import llm_gateway as gateway


class FakeModel(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"object":"list","data":[]}')
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"object":"chat.completion","choices":[]}')
    def log_message(self, *_):
        pass


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.keyfile = Path(cls.folder.name) / "key"
        cls.keyfile.write_text("test-only-key")
        gateway.KEY_FILE = cls.keyfile
        cls.model = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
        gateway.UPSTREAM_PORT = cls.model.server_address[1]
        cls.proxy = ThreadingHTTPServer(("127.0.0.1", 0), gateway.Handler)
        cls.url = f"http://127.0.0.1:{cls.proxy.server_address[1]}"
        for server in (cls.model, cls.proxy):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.proxy.shutdown()
        cls.model.shutdown()
        cls.folder.cleanup()

    def test_rejects_missing_bearer(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url + "/v1/models", timeout=3)
        self.assertEqual(ctx.exception.code, 401)

    def test_rejects_disallowed_path(self):
        request = Request(self.url + "/admin", headers={"Authorization": "Bearer test-only-key"})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 404)

    def test_forwards_authorized_models(self):
        request = Request(self.url + "/v1/models", headers={"Authorization": "Bearer test-only-key"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(json.load(response)["object"], "list")

    def test_forwards_chat_json(self):
        request = Request(self.url + "/v1/chat/completions",
                          data=b'{"messages":[]}', method="POST",
                          headers={"Authorization": "Bearer test-only-key",
                                   "Content-Type": "application/json"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(json.load(response)["object"], "chat.completion")

    def test_rejects_body_over_limit(self):
        request = Request(self.url + "/v1/chat/completions",
                          data=b"x", method="POST",
                          headers={"Authorization": "Bearer test-only-key",
                                   "Content-Length": str(gateway.MAX_BODY + 1)})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 413)


if __name__ == "__main__":
    unittest.main()
