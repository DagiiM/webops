"""Regression tests for the authenticated Runpod loopback LLM gateway."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

os.environ.setdefault('WEBOPS_LLM_KEY_FILE', '/dev/null')
from apps.deployments import llm_gateway as gateway


class FakeModel(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"object":"list","data":[]}')
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        request = json.loads(raw)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.path == "/api/chat":
            if request.get("stream"):
                self.wfile.write(b'{"message":{"content":"READY"},"done":false}' + bytes([10]))
                self.wfile.write(b'{"message":{"content":""},"done":true}' + bytes([10]))
            else:
                self.wfile.write(b'{"message":{"content":"READY"},"done":true,"prompt_eval_count":3,"eval_count":1}')
        else:
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


    def test_ollama_payload_disables_thinking(self):
        payload = gateway.ollama_payload({"model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "READY"}],
            "max_tokens": 60})
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 60)

    def test_ollama_chat_produces_answer(self):
        previous = gateway.BACKEND
        gateway.BACKEND = "ollama"
        try:
            request = Request(self.url + "/v1/chat/completions",
                data=b'{"model":"qwen3:1.7b","messages":[{"role":"user","content":"READY"}]}',
                headers={"Authorization": "Bearer test-only-key", "Content-Type": "application/json"},
                method="POST")
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
            self.assertEqual(result["choices"][0]["message"]["content"], "READY")
        finally:
            gateway.BACKEND = previous

    def test_ollama_chat_streaming_sse(self):
        previous = gateway.BACKEND
        gateway.BACKEND = "ollama"
        try:
            request = Request(self.url + "/v1/chat/completions",
                data=b'{"model":"qwen3:1.7b","messages":[],"stream":true}',
                headers={"Authorization": "Bearer test-only-key", "Content-Type": "application/json"},
                method="POST")
            with urlopen(request, timeout=5) as response:
                data = response.read().decode()
            self.assertIn("READY", data)
            self.assertIn("data: [DONE]", data)
        finally:
            gateway.BACKEND = previous

if __name__ == "__main__":
    unittest.main()
