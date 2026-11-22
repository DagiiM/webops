# Runpod development: WebOps control panel + private vLLM API

**Scope:** supervised development only. WebOps' production installer manages host
systemd, SSH, firewall, and Nginx and must **not** be run inside a Runpod Pod
container. The native WebOps vLLM service is CPU-oriented; this adapter is an
isolated GPU-compatible development path.

## Pod setup

1. Use an NVIDIA GPU with enough VRAM for the selected model.
2. Choose a CUDA/PyTorch container image compatible with the GPU host driver.
3. Allocate at least 40 GB container disk; remember it is **ephemeral** on
   Pod restart or stop. Move persistent data to an appropriately located volume
   for non-experimental use.
4. Do **not** expose WebOps port 8009. Initially expose no ports.
5. Clone the `feat/runpod-llm-safe-dev` branch into `/workspace/webops`.
6. Create a Python 3.11 virtual environment and install
   `control-panel/requirements.txt`; inspect and upgrade obsolete dependencies
   before production. Generate unique `SECRET_KEY` and `ENCRYPTION_KEY`
   and set `WEBOPS_INSTALL_PATH` to a dedicated writable location.
7. Run `manage.py check`, `manage.py migrate --noinput`; create a
   **strong** administrator account with a generated password. Never use
   the documented default `admin123`.
8. Create an unprivileged Linux user named `webops`.
9. Install a **GPU-capable** version of vLLM into the Python interpreter named
   by `WEBOPS_LLM_PYTHON`. Verify GPU availability with `nvidia-smi`
   and `torch.cuda.is_available()`.

## Start model through WebOps

From `control-panel/`:

```bash
export WEBOPS_RUNPOD_MODE=1
export WEBOPS_LLM_PYTHON=/usr/local/bin/python3
/path/to/webops/.venv/bin/python manage.py webops_runpod_llm \
  --action start --name jani-small --model Qwen/Qwen3-1.7B \
  --port 8001 --upstream-port 8002 --max-model-len 2048
```

Status:

```bash
WEBOPS_RUNPOD_MODE=1 /path/to/webops/.venv/bin/python manage.py \
  webops_runpod_llm --action status --name jani-small
```

Stop:

```bash
WEBOPS_RUNPOD_MODE=1 /path/to/webops/.venv/bin/python manage.py \
  webops_runpod_llm --action stop --name jani-small
```

This command registers a real `LLMDeployment` record, starts GPU vLLM
bound to `127.0.0.1:8002`, and starts an authenticated proxy on port 8001,
with a random Bearer secret held at:

```
$WEBOPS_INSTALL_PATH/llm-deployments/jani-small/access.key
```

Never expose, print, commit, or share the secret. The gateway includes
`GET /v1/models` and `POST /v1/chat/completions` among its allowed paths.
Successful startup only proves that the processes were launched; **status
must report running** and real model inference must succeed.

## Private verification

```bash
KEY=$(cat "$WEBOPS_INSTALL_PATH/llm-deployments/jani-small/access.key")
curl -i http://127.0.0.1:8001/v1/models
# Expected: 401 without Authorization

curl -sS -H "Authorization: Bearer $KEY" \
  http://127.0.0.1:8001/v1/models

curl -sS -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"jani-small","messages":[{"role":"user","content":"Say READY."}],"max_tokens":24}' \
  http://127.0.0.1:8001/v1/chat/completions
```

Do not expose port 8001 until unauthorized and authorized checks pass.
A Runpod HTTPS proxy URL, when port 8001 is exposed, follows
`https://POD_ID-8001.proxy.runpod.net/v1`. Such URLs are public, so
the gateway requires Bearer authentication. The proxy has a 100-second
request timeout. Preserve a copy of code and credentials outside ephemeral
container storage **before** any Pod restart.

## Safety and operational boundaries

- Control panel serves on `127.0.0.1:8009` for local evaluation.
- This minimal gateway lacks production-grade rate limiting, tenant
  isolation, audit streaming, observability and high availability.
- WebOps' native systemd-based production LLM deployment is not used here.
- Pod stops/restarts wipe container disk. Use a persistent volume,
  reproducible startup scripts, TLS, credential management, backups,
  metrics, and lifecycle supervision before promoting the system.
- Review the WebOps baseline test suite, dependency security, and
  site security before publication.
- GPU Pods charge while running, even if the model is idle.
