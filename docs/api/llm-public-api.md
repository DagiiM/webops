# Public LLM API

Call your own running, reviewed CPU models from outside WebOps with an inference-only key.

- **Base URL:** `https://<your-panel-host>/api/llm/v1`
- **Auth:** `Authorization: Bearer wops_llm_...` (create keys at **LLM models → API keys**, `/api/llm/keys/`)
- **Endpoints:** `GET /models`, `POST /completions`

```bash
curl https://<your-panel-host>/api/llm/v1/completions \
  -H "Authorization: Bearer $WEBOPS_LLM_KEY" -H "Content-Type: application/json" \
  -d '{"model":"my-deployment","prompt":"Hello","max_tokens":32}'
```

## What a key can and cannot do

A key runs completions on **your own** deployments that are running and use a reviewed model. It is
a separate credential from API tokens and MCP tokens: it is not accepted by the REST API, MCP or the
panel, and those credentials are not accepted here, so a leaked key cannot manage deployments.

Keys are stored as a SHA-256 digest and shown once. They expire after 30 days, can be revoked at any
time, and each user may hold at most 10 active keys.

## Limits

| | |
|---|---|
| Prompt | 1 to 4096 characters |
| `max_tokens` | 1 to 128 (default 16) |
| `temperature` | 0 to 2 (default 0.7) |
| Request body | 16 KiB; `Content-Type: application/json` |
| Streaming | not supported (`stream: true` returns 400) |
| Concurrency | the model server handles one request at a time; a busy model returns 429 with `Retry-After` |
| Rate | per key: 10 per minute burst, 300 per hour; per client IP: 60 per minute, 600 per hour |

HTTPS is required outside DEBUG. Only `prompt`, `max_tokens` and `temperature` are forwarded; other
OpenAI fields are ignored. There is no chat-completions endpoint: the reviewed CPU servers expose
text completions only.

## Errors

Errors use `{"error": {"message": "...", "type": "..."}}` and never include internal paths, ports or
upstream messages: 400 invalid input, 401 missing/invalid/expired/revoked key, 404 unknown or
not-ready model, 413 body too large, 415 wrong content type, 429 rate limited or model busy,
502/503 model returned an invalid response / is unavailable.

## Exposure

The model servers stay bound to `127.0.0.1`. This endpoint is the only public path to them, and it is
served by the control panel on its existing public port. Anyone with a valid key can use your model's
compute, so treat keys as secrets and revoke any you do not recognise.
