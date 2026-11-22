"""Authenticated OpenAI-compatible gateway for a private GPU LLM service.

Runpod development adapter only; use a production-grade API gateway before
serving third-party traffic. Models stay bound to 127.0.0.1.
"""
from __future__ import annotations

import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

MAX_BODY = 1024 * 1024
KEY_FILE = Path(os.environ["WEBOPS_LLM_KEY_FILE"])
UPSTREAM_PORT = int(os.environ.get("WEBOPS_LLM_UPSTREAM_PORT", "8002"))
PROXY_PORT = int(os.environ.get("WEBOPS_LLM_PROXY_PORT", "8001"))
BACKEND = os.environ.get("WEBOPS_LLM_BACKEND", "")
# Bound expensive model inferences even when many clients connect.
MAX_INFLIGHT = max(1, min(16, int(os.environ.get("WEBOPS_LLM_MAX_INFLIGHT", "2"))))
INFERENCE_SLOTS = threading.BoundedSemaphore(MAX_INFLIGHT)
ALLOWED_PATHS = ("/v1/models", "/v1/chat/completions", "/v1/completions",
                 "/v1/embeddings", "/health")


def normalized_tool_calls(calls):
    result = []
    for index, call in enumerate(calls or []):
        fn = call.get("function", {}) if isinstance(call, dict) else {}
        result.append({
            "id": "call_" + uuid4().hex[:16],
            "type": "function",
            "function": {
                "name": str(fn.get("name", "")),
                "arguments": (fn.get("arguments", "{}") if isinstance(fn.get("arguments"), str)
                              else json.dumps(fn.get("arguments", {}), separators=(",", ":"))),
            },
        })
    return result


def ollama_messages(messages):
    """Convert OpenAI tool history into Ollama-native tool arguments.

    OpenAI emits JSON-encoded function.arguments strings, while Ollama
    expects decoded JSON objects. Keep tool results intact, but remove
    the OpenAI-only tool_call_id for the native backend.
    """
    result = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Message must be an object")
        if message.get("role") not in ("system", "developer", "user", "assistant", "tool"):
            raise ValueError("Invalid message role")
        item = message.copy()
        if "tool_calls" in item:
            calls = item["tool_calls"]
            if not isinstance(calls, list) or len(calls) > 32:
                raise ValueError("Invalid tool call list")
            converted = []
            for call in calls:
                if not isinstance(call, dict):
                    raise ValueError("Invalid tool call")
                fn = call.get("function")
                if not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                    raise ValueError("Invalid tool function")
                arguments = fn.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError as exc:
                        raise ValueError("Invalid tool arguments") from exc
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be an object")
                converted.append({"function": {"name": fn["name"], "arguments": arguments}})
            item["tool_calls"] = converted
        if item["role"] == "tool":
            item.pop("tool_call_id", None)
        result.append(item)
    return result


def ollama_payload(data):
    """Translate a subset of OpenAI Chat Completions to native Ollama Chat."""
    if not isinstance(data, dict) or not isinstance(data.get("model"), str):
        raise ValueError("A model string is required")
    if not isinstance(data.get("messages"), list):
        raise ValueError("Messages must be an array")
    if len(data["messages"]) > 100:
        raise ValueError("Too many messages")
    request = {
        "model": data["model"], "messages": ollama_messages(data["messages"]),
        "stream": bool(data.get("stream", False)), "think": False,
    }
    options = {}
    for original, target in (("max_tokens", "num_predict"),
                             ("temperature", "temperature"),
                             ("top_p", "top_p")):
        val = data.get(original)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            options[target] = val
    if "num_predict" not in options:
        # Tool-call JSON can need more tokens than ordinary chat text.
        options["num_predict"] = 1024 if data.get("tools") else 384
    if options:
        request["options"] = options
    if isinstance(data.get("tools"), list):
        request["tools"] = data["tools"]
    return request


def completion_from_ollama(data, response):
    message = response.get("message", {})
    tool_calls = normalized_tool_calls(message.get("tool_calls", []))
    msg = {"role": "assistant", "content": message.get("content", "")}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    finish = "tool_calls" if tool_calls else ("length" if response.get("done_reason") == "length" else "stop")
    return {
        "id": "chatcmpl-" + uuid4().hex, "object": "chat.completion",
        "created": int(time.time()), "model": data["model"],
        "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": response.get("prompt_eval_count", 0),
            "completion_tokens": response.get("eval_count", 0),
            "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "WebOpsLLM/1.1"
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        # Never log bearer credentials, prompts or responses.
        pass

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        if urlsplit(self.path).path != "/v1/chat/completions":
            return self._forward("POST")
        # Reject unauthenticated callers before consuming scarce model slots.
        actual = self.headers.get("Authorization", "")
        expected = "Bearer " + KEY_FILE.read_text(encoding="utf-8").strip()
        if not hmac.compare_digest(actual, expected):
            return self._forward("POST")
        if not INFERENCE_SLOTS.acquire(blocking=False):
            return self._json(429, {"error": "model_capacity_exceeded"})
        try:
            return self._forward("POST")
        finally:
            INFERENCE_SLOTS.release()

    def _json(self, status, obj):
        data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _forward(self, method):
        path = urlsplit(self.path)
        if path.path not in ALLOWED_PATHS or len(self.path) > 2048:
            return self._json(404, {"error": "not_found"})
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
            return self._json(400, {"error": "invalid_content_length"})
        if size < 0 or size > MAX_BODY:
            return self._json(413, {"error": "request_too_large"})
        data = self.rfile.read(size) if method == "POST" else None
        if BACKEND == "ollama" and path.path == "/health" and method == "GET":
            try:
                with urlopen(f"http://127.0.0.1:{UPSTREAM_PORT}/api/tags", timeout=4) as upstream:
                    models = json.load(upstream).get("models", [])
                if not models:
                    return self._json(503, {"status": "model_loading"})
                return self._json(200, {"status": "ready", "model_count": len(models)})
            except (OSError, URLError, ValueError):
                return self._json(503, {"status": "unavailable"})
        if BACKEND == "ollama" and path.path == "/v1/chat/completions" and method == "POST":
            return self._ollama_chat(data)
        uri = f"http://127.0.0.1:{UPSTREAM_PORT}{self.path}"
        upstream = Request(uri, method=method, data=data,
                           headers={"Content-Type": "application/json"})
        try:
            response = urlopen(upstream, timeout=95)
        except HTTPError as exc:
            response = exc
        except (OSError, URLError):
            return self._json(503, {"error": "model_unavailable"})
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

    def _ollama_chat(self, data):
        try:
            original = json.loads(data or b"{}")
            payload = ollama_payload(original)
        except (json.JSONDecodeError, ValueError) as exc:
            return self._json(400, {"error": "invalid_request", "message": str(exc)})
        is_stream = payload["stream"]
        upstream = Request(
            f"http://127.0.0.1:{UPSTREAM_PORT}/api/chat",
            method="POST", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urlopen(upstream, timeout=95)
        except HTTPError as exc:
            try:
                error = json.loads(exc.read(8192))
            except (ValueError, OSError):
                error = {"error": "model_request_failed"}
            return self._json(exc.code, error)
        except (OSError, URLError):
            return self._json(503, {"error": "model_unavailable"})
        with response:
            if not is_stream:
                try:
                    result = json.load(response)
                    return self._json(200, completion_from_ollama(payload, result))
                except (ValueError, OSError):
                    return self._json(502, {"error": "invalid_model_response"})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            identifier = "chatcmpl-" + uuid4().hex
            created = int(time.time())

            def chunk(delta, finish=None):
                item = {
                    "id": identifier, "object": "chat.completion.chunk",
                    "created": created, "model": payload["model"],
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(("data: " + json.dumps(item, separators=(",", ":")) + "\n\n").encode())
                self.wfile.flush()

            try:
                chunk({"role": "assistant"})
                saw_tool_calls = False
                for line in response:
                    parsed = json.loads(line)
                    message = parsed.get("message", {})
                    if message.get("content"):
                        chunk({"content": message["content"]})
                    for index, call in enumerate(message.get("tool_calls", []) or []):
                        if not isinstance(call, dict):
                            continue
                        fn = call.get("function", {})
                        if not isinstance(fn, dict):
                            continue
                        args = fn.get("arguments", {})
                        if not isinstance(args, str):
                            args = json.dumps(args, separators=(",", ":"))
                        saw_tool_calls = True
                        chunk({"tool_calls": [{
                            "index": index,
                            "id": "call_" + uuid4().hex[:16],
                            "type": "function",
                            "function": {"name": str(fn.get("name", "")),
                                         "arguments": args},
                        }]})
                    if parsed.get("done"):
                        chunk({}, finish="tool_calls" if saw_tool_calls else "stop")
                        break
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ValueError):
                return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), Handler).serve_forever()
