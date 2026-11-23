# AI-assisted GitHub deployments with WebOps and Jani

**Status:** The one-command CLI and a live read-only Jani/model preflight have been verified. The private `ifinsta/ifinsta` application **has not** yet been deployed and health-checked end to end. This is an operational guide, not a production-readiness certificate.

WebOps is the deployment controller. [Jani](https://github.com/ifinsta/jani) is an optional, read-only AI reviewer of a GitHub checkout. A WebOps-hosted model offers OpenAI-compatible chat completion endpoints. **Only WebOps, acting on an explicitly approved operator request, submits a deployment job.** Jani cannot widen its scope, edit files, run model-generated commands or approve deployments.

## 1. Install WebOps and its CLI

Choose a development machine or a disposable staging VPS before production. Do not run both installers interchangeably.

**Local development**, from a checkout of [DagiiM/webops](https://github.com/DagiiM/webops):

```bash
git clone https://github.com/DagiiM/webops.git
cd webops
make dev-install
make dev
```

`make dev-install` runs the [versioned development quickstart](https://github.com/DagiiM/webops/blob/main/provisioning/versions/v1.0.0/dev/quickstart.sh). It initializes the control panel, database and a local developer admin account. The development password is randomly generated and stored with restricted permissions in `control-panel/.dev_admin_password`. Never reuse development credentials in staging or production.

**VPS platform installation**, after reviewing the script and its privileges:

```bash
git clone https://github.com/DagiiM/webops.git
cd webops
less provisioning/versions/v1.0.0/lifecycle/install.sh
make install
```

The versioned installer modifies host services and configuration. Final health verification is required before installation success is recorded. Unverified partial system changes are never blindly replayed. See the [installation guide](../getting-started/installation.md) and [post-installation checks](https://github.com/DagiiM/webops/blob/main/POST_INSTALLATION.md).

Install the CLI with Python 3.11 or later from the checked-out repository:

```bash
python -m pip install -e ./cli
webops --help
webops deploy --help
```

## 2. Configure a least-privileged WebOps operator

Get an authorized WebOps API credential through your organization's normal procedure. Do not commit it, put it in screenshots or paste it into public logs.

```bash
# WEBOPS_CLI_TOKEN is supplied by an approved secret manager or secure session.
webops config --url https://panel.example.com --token "$WEBOPS_CLI_TOKEN" --role developer
```

Passing tokens in command-line arguments can expose them through process inspection or shell history. Use a trusted administration host and prefer an approved non-interactive credential-management mechanism when available. Protect `~/.webops/` and the local encryption key.

## 3. Verify a WebOps-managed AI model

The optional Jani review needs (a) a reachable OpenAI-compatible model endpoint, (b) a model name and (c) a separate model access key. WebOps' **experimental Runpod Ollama adapter** was demonstrated using `qwen3:1.7b` and `qwen3:8b`. It is not a production HA or persistence setup.

For the Runpod **development-only** path, see [Runpod WebOps model development](runpod-webops-development.md). For example, from the WebOps control-panel directory on a properly prepared GPU Pod:

```bash
WEBOPS_RUNPOD_MODE=1 /path/to/webops/.venv/bin/python manage.py \
  webops_runpod_ollama --action start --name jani-agent \
  --model qwen3:8b --port 8003 --upstream-port 8004

WEBOPS_RUNPOD_MODE=1 /path/to/webops/.venv/bin/python manage.py \
  webops_runpod_ollama --action status --name jani-agent
```

The model runs on the designated host. Retrieve its gateway key **privately** from `$WEBOPS_INSTALL_PATH/llm-deployments/jani-agent/access.key` (do not display it in CI logs) and provision it to the CLI securely as `WEBOPS_MODEL_API_KEY`. Verify that `/v1/models` requires that key, and do not publicly expose Ollama's native upstream port.

Install an approved Jani binary using the [Jani project's installation instructions](https://github.com/ifinsta/jani). Confirm the binary runs on the administration host; use `--jani-binary /approved/path/to/jani` if it is not on `PATH`.

## 4. Use the single deployment command

**Preflight only** — parse and validate the repository without submitting it to WebOps:

```bash
webops deploy your-org/your-repo --name staging-app \
  --branch main --domain staging.example.com \
  --dry-run --json-output
```

**Read-only Jani review** — uses the self-hosted model; absence of a valid model key or a failed review is an error, not implicit authorization:

```bash
webops deploy your-org/your-repo \
  --ai-assist --model qwen3:8b \
  --model-endpoint https://models.example.com/v1 \
  --dry-run --json-output
```

**Operator-approved deployment** — same CLI, no Jani-generated shell execution:

```bash
webops deploy your-org/your-repo \
  --ai-assist --model qwen3:8b \
  --model-endpoint https://models.example.com/v1 \
  --approve --wait --timeout 180
```

Use a model endpoint you control and trust. `--model-key-env` changes the name of the environment variable containing the model token; it does not accept the token's value. With `--worktree /secure/checkout`, WebOps verifies that the checkout's `origin` matches the requested GitHub repository before Jani reads it.

For **private GitHub repositories**, configure a short-lived, least-privileged checkout credential for the preflight process **and** authorized repository access for the backend deployment worker. The GitHub connector used to read a repository in ChatGPT is *not* a deployment credential. Avoid credential-bearing Git URLs and never weaken access controls just to make a demonstration succeed.

## 5. Verify the application, not just the queue

`--wait` waits for WebOps to report `running`; its structured result explicitly reports `http_health_verified=false` until a separate application check is performed. Do not confuse a queued or reported-running deployment with a healthy public service.

```bash
webops info staging-app
webops logs staging-app --tail 100 --follow

# Replace this with the actual application-specific HTTPS readiness endpoint.
curl --fail --show-error --silent https://staging.example.com/health/
```

Require evidence of successful checkout, actual build and start, expected environment variables, pending migrations, TLS certificate validity, job/worker processing, data persistence and useful application logs. Do not put passwords, API keys, private model keys or database connection strings directly into shell commands, public docs or repositories.

## 6. Resilience, rollback and release acceptance

Before advertising a production-ready deployment:

- Prove a **real** application build and reachable HTTPS endpoint from an external client.
- Verify schema migration, database isolation, backups and restore procedures using disposable test data.
- Exercise stop/start, failed builds, transient model/agent downtime, worker recovery and a documented rollback.
- Record request throughput, p95/p99 latency, errors, load, recovery time and resource constraints in a sustained staging run.
- Confirm host security boundaries, approved team permissions, required CI checks and the 100% CLI **statement** coverage gate. Statement coverage is not 100% branch coverage or a substitute for integration/security testing.

### Ifinsta acceptance

The live proof already covered the WebOps-managed Qwen model, authenticated gateway, Jani read-only repository inspection and one-command AI-assisted **dry run** against `DagiiM/webops`. It did **not** deploy the private `ifinsta/ifinsta` application. See the [evidence report](../testing/webops-resilience-jani-e2e-2026-11-22.md) and [acceptance issue #17](https://github.com/DagiiM/webops/issues/17) for the remaining private-checkout, staging execution, health and rollback checks.

## CLI test proof

At commit [`4fddf82`](https://github.com/DagiiM/webops/commit/4fddf8230fd6a3151dfd76003966befe91c88300), the CLI suite passed **3,173 tests plus 41 subtests** with **100.00% measured statement coverage**. To reproduce from a checked-out WebOps repository:

```bash
cd cli
python -m pip install -e . pytest pytest-cov pytest-asyncio
python -m pytest -q tests/
python -m coverage report --fail-under=100
```

See [CLI coverage verification](../testing/webops-cli-coverage-2026-11-22.md) for counted statements, known limits, and the CI gate.
