# Runpod development: WebOps control panel + private vLLM API

**Scope:** supervised development only. WebOps' production installer manages host
systemd, SSH, firewall, and Nginx and must **not** be run inside a Runpod Pod
container. The native WebOps vLLM service is CPU-oriented; this adapter is an
isolated GPU-compatible development path.

## Verified low-VRAM path: Ollama on RTX 3070

For affordable 8 GiB GPU Pods, **use the WebOps Ollama adapter**, not
the native CPU-first vLLM installer. It registers a real WebOps
`LLMDeployment` record, downloads an Ollama model, and starts a
loopback-only model backend with an authenticated HTTPS-facing gateway.

### Install Ollama and local Redis

Run inside a Runpod Pod using a compatible NVIDIA/CUDA image:

```bash
apt-get update
apt-get install -y zstd redis-server
redis-server --daemonize yes --bind 127.0.0.1 --port 6379 --protected-mode yes
curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst -o /tmp/ollama.tar.zst
tar --use-compress-program=unzstd -xf /tmp/ollama.tar.zst -C /usr/local
/usr/local/bin/ollama --version
```

Validate the archive's origin and approved version/checksum in a release
pipeline. Do not run unreviewed installers with administrative privileges.

Prepare WebOps using the normal development environment, **not** the host
provisioning installer. Create the `webops` unprivileged Unix user and an
administrator account with a generated password. Configure a private
`WEBOPS_INSTALL_PATH`, strong secrets, and database migrations.

From `control-panel/`:

```bash
WEBOPS_RUNPOD_MODE=1 /path/to/webops/.venv/bin/python manage.py \
  webops_runpod_ollama --action start --name jani-small \
  --model qwen3:1.7b --port 8001 --upstream-port 8002
```

Model download starts asynchronously and is recorded under a private model
directory. Confirm actual model installation and process health:

```bash
WEBOPS_RUNPOD_MODE=1 /path/to/webops/.venv/bin/python manage.py \
  webops_runpod_ollama --action status --name jani-small
```

Only a status of `running` indicates that Ollama, the gateway, and the
configured model were all detected.

Set the Pod's `8001/http` exposed port **at Pod creation time**. Editing
ports on an existing Pod resets its container and can erase an ephemeral
installation. Never expose the private model port 8002 or the Django
control-panel development port.

Use OpenAI-compatible client configuration:

```text
base_url = https://POD_ID-8001.proxy.runpod.net/v1
model = qwen3:1.7b
api_key = <secret obtained securely from the Pod>
```

Read the Bearer secret from
`$WEBOPS_INSTALL_PATH/llm-deployments/jani-small/access.key`; store it in
your application's secret manager, not in browser JavaScript. The gateway
translates Ollama-native chat into OpenAI-compatible nonstreaming JSON and
streaming SSE, disabling extended thinking by default for useful answers.
`/v1/models` requires authentication.

### Live development validation (22 November 2026)

On a Community RTX 3070 (8 GiB), Qwen3 1.7B Q4 was downloaded from
Ollama, detected on the GPU, and successfully served via the authenticated
Runpod HTTPS endpoint. HTTP 401 without a key, HTTP 200 with the key, an
actual generated chat response, and SSE streaming were verified. The
Django login redirect and authenticated dashboard page also worked
locally.

**Not production-ready:** In this tested configuration the 40 GB container
disk is ephemeral and the Pod startup command is temporary; there is no
persistent model volume, automatic recovery, production rate limiting,
external monitoring, or durable WebOps service provisioning. At this historical checkpoint, some repository test suites had failures;
the current CLI statement-coverage suite later reached 100% but production
integration/security gates still require independent verification. Do not expose the WebOps
control panel publicly in this state.

---

## Pod setup

1. Use an NVIDIA GPU with enough VRAM for the selected model.
2. Choose a CUDA/PyTorch container image compatible with the GPU host driver.
3. Allocate at least 40 GB container disk; remember it is **ephemeral** on
   Pod restart or stop. Move persistent data to an appropriately located volume
   for non-experimental use.
4. Do **not** expose WebOps port 8009. Initially expose no ports.
5. Clone the current reviewed `main` branch of `DagiiM/webops` into `/workspace/webops`; pin a tested commit SHA for reproducibility.
6. Create a Python 3.11 virtual environment and install
   `control-panel/requirements.txt`; inspect and upgrade obsolete dependencies
   before production. Generate unique `SECRET_KEY` and `ENCRYPTION_KEY`
   and set `WEBOPS_INSTALL_PATH` to a dedicated writable location.
7. Run `manage.py check`, `manage.py migrate --noinput`; create a
   **strong** administrator account with a generated password. Never use any fixed sample credential.
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
