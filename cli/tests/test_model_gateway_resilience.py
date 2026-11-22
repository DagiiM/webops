"""Gateway contract tests: authentication, overload rejection and tool-call interoperability."""
import importlib.util
import json
import threading
from pathlib import Path

import pytest


@pytest.fixture
def gateway(monkeypatch, tmp_path):
    key = tmp_path / "model.key"
    key.write_text("test-only-token")
    monkeypatch.setenv("WEBOPS_LLM_KEY_FILE", str(key))
    monkeypatch.setenv("WEBOPS_LLM_BACKEND", "ollama")
    monkeypatch.setenv("WEBOPS_LLM_MAX_INFLIGHT", "2")
    source = Path(__file__).resolve().parents[2] / "control-panel" / "apps" / "deployments" / "llm_gateway.py"
    spec = importlib.util.spec_from_file_location("webops_gateway_test_module", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gateway_token_required_before_capacity(gateway):
    handler = gateway.Handler.__new__(gateway.Handler)
    handler.path = "/v1/chat/completions"
    handler.headers = {"Authorization": "Bearer wrong-token"}
    errors = []
    forwards = []
    handler._json = lambda status, data: errors.append((status, data))
    handler._forward = lambda method: forwards.append(method)
    gateway.INFERENCE_SLOTS.acquire()
    gateway.INFERENCE_SLOTS.acquire()
    try:
        handler.do_POST()
        assert forwards == ["POST"]  # Auth is checked inside _forward.
        assert not errors
    finally:
        gateway.INFERENCE_SLOTS.release()
        gateway.INFERENCE_SLOTS.release()


def test_gateway_admission_429_when_capacity_exhausted(gateway):
    handler = gateway.Handler.__new__(gateway.Handler)
    handler.path = "/v1/chat/completions"
    handler.headers = {"Authorization": "Bearer test-only-token"}
    errors = []
    handler._json = lambda status, data: errors.append((status, data))
    handler._forward = lambda method: (_ for _ in ()).throw(AssertionError("must not forward"))
    gateway.INFERENCE_SLOTS.acquire()
    gateway.INFERENCE_SLOTS.acquire()
    try:
        handler.do_POST()
        assert errors == [(429, {"error": "model_capacity_exceeded"})]
    finally:
        gateway.INFERENCE_SLOTS.release()
        gateway.INFERENCE_SLOTS.release()


def test_gateway_releases_model_slot_after_upstream_failure(gateway):
    handler = gateway.Handler.__new__(gateway.Handler)
    handler.path = "/v1/chat/completions"
    handler.headers = {"Authorization": "Bearer test-only-token"}
    handler._forward = lambda method: (_ for _ in ()).throw(OSError("upstream down"))
    with pytest.raises(OSError):
        handler.do_POST()
    assert gateway.INFERENCE_SLOTS.acquire(blocking=False)
    assert gateway.INFERENCE_SLOTS.acquire(blocking=False)
    gateway.INFERENCE_SLOTS.release()
    gateway.INFERENCE_SLOTS.release()


def test_gateway_preserves_openai_tool_call_arguments(gateway):
    calls = [{"function": {"name": "read", "arguments": {"path": "README.md"}}}]
    formatted = gateway.normalized_tool_calls(calls)
    assert len(formatted) == 1
    assert formatted[0]["type"] == "function"
    assert json.loads(formatted[0]["function"]["arguments"]) == {"path": "README.md"}
    second = gateway.normalized_tool_calls([{"function": {
        "name": "read", "arguments": '{"path":"README.md"}'}}])
    assert json.loads(second[0]["function"]["arguments"]) == {"path": "README.md"}


@pytest.mark.parametrize("model", ["qwen3:1.7b", "qwen3:8b", "qwen2.5-coder:7b"])
def test_gateway_translates_valid_model_requests(gateway, model):
    payload = gateway.ollama_payload({
        "model": model, "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "function": {"name": "read",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}],
        "stream": True,
    })
    assert payload["model"] == model
    assert payload["stream"] is True
    assert payload["think"] is False
    assert payload["options"]["num_predict"] >= 1024
    assert len(payload["tools"]) == 1


@pytest.mark.parametrize("bad", [
    {}, "not-json", {"model": 12, "messages": []},
    {"model": "qwen3:8b", "messages": 7},
    {"model": "qwen3:8b", "messages": [{}] * 101},
])
def test_gateway_rejects_malformed_requests(gateway, bad):
    with pytest.raises(ValueError):
        gateway.ollama_payload(bad)


def test_gateway_declares_only_known_paths_and_bounds(gateway):
    assert gateway.MAX_BODY == 1024 * 1024
    assert gateway.MAX_INFLIGHT == 2
    assert "/v1/chat/completions" in gateway.ALLOWED_PATHS
    assert "/health" in gateway.ALLOWED_PATHS
    assert "/admin" not in gateway.ALLOWED_PATHS




def test_ollama_converts_prior_tool_history_for_multi_step_jani(gateway):
    history = [
        {"role": "user", "content": "Inspect README"},
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "call_abc", "type": "function",
            "function": {"name": "read", "arguments": '{"path":"README.md"}'},
        }]},
        {"role": "tool", "tool_call_id": "call_abc", "content": "# Project"},
    ]
    result = gateway.ollama_payload({"model": "qwen3:8b", "messages": history})
    assert result["messages"][1]["tool_calls"] == [{
        "function": {"name": "read", "arguments": {"path": "README.md"}}
    }]
    assert result["messages"][2] == {"role": "tool", "content": "# Project"}
    assert history[1]["tool_calls"][0]["function"]["arguments"] == '{"path":"README.md"}'


@pytest.mark.parametrize("arguments", ["{", "[]", "null", "3", '"text"', "[1,2]"])
def test_history_tool_argument_errors_fail_closed(gateway, arguments):
    with pytest.raises(ValueError):
        gateway.ollama_messages([{
            "role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "read", "arguments": arguments}}
            ]
        }])


def test_ollama_native_object_arguments_are_preserved(gateway):
    h = [{"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "read", "arguments": {"path": "README.md"}}}
    ]}]
    assert gateway.ollama_messages(h)[0]["tool_calls"][0]["function"]["arguments"]["path"] == "README.md"
