# One-command WebOps deployments and Jani proof — 2026-11-22

## What was actually demonstrated

Runpod CPU: **2,042 CLI tests passed**, including **1,415 resilience cases**,
**537 AI deployment-contract cases** and **21 model-gateway tests**, plus
the pre-existing CLI tests. A concurrent probe exercised 4,096 requests across
64 workers. These are isolated, fast, deterministic workload and fault-injection
tests rather than a sustained public-hosting load test.

Runpod GPU: fresh WebOps installed with SQLite migrations, Redis, Python 3.11,
an unprivileged `webops` operating-system account and WebOps administrator.
Ollama 0.40.17 installed, and WebOps' Runpod development adapter deployed
`qwen3:1.7b` as `jani-small` and `qwen3:8b` as `jani-agent`. Both
model records reached `running`; the authenticated gateway listed the model
and the 1.7B model answered a real Chat Completions request (HTTP 200).
Jani 0.1.2 was built from `ifinsta/jani`, and `jani doctor` confirmed its
model and default-deny read-only authority.

**Live Jani integration verified:** The initial gateway returned HTTP 400
when Jani sent multi-step tool-call history. The fix translates OpenAI tool
arguments from JSON strings into native Ollama objects and forwards streaming
tool calls correctly. After upgrading and restarting the actual model gateways,
Jani `--print` completed a read-only inspection of the `ifinsta/jani`
repository using the WebOps-hosted `qwen3:8b` model (exit 0).

**One-command preflight verified:** On the GPU Pod, the published CLI executed
`webops deploy DagiiM/webops --ai-assist --model qwen3:8b
--model-endpoint http://127.0.0.1:8003/v1 --jani-binary /opt/jani/bin/jani
--worktree /work/webops --dry-run --json-output` (exit 0, Jani 3,682 ms).
The output included the validated repository, branch, a deterministic
idempotency key, a Jani evidence digest and a no-write dry-run status.
Authenticated gateway `/health` also responded HTTP 200 with `ready`
and an installed model count. The CLI refused an intentionally mismatched
`--worktree` for `ifinsta/ifinsta` before invoking Jani (exit 1).
**This was an actual AI-assisted dry run, not a real application deployment.**

**Bounded live gateway load:** Against the GPU Pod's loopback interface,
128 authenticated `/health` requests at concurrency 16 all returned HTTP 200
(observed p95 18.5 ms). A simultaneous 12-request inference burst returned
two HTTP 200 responses and ten HTTP 429 overload rejections, consistent with
the explicit two-request model concurrency limit; maximum observed response
duration was 483 ms. An unauthenticated `/health` request returned HTTP 401.
These are local short bursts, **not** multi-day soak or public-network SLO
evidence.

**Historical published code verification (before the 100% coverage programme):** A fresh detached checkout of `main` at
`b2dd67f6eb21ba656240527dd1d6bcfb4e7a6ad2` passed all **2,042 CLI
tests and 41 subtests** in 1.94 seconds.

**Not yet proven:** cloning and deploying the private `ifinsta/ifinsta`
repository, a public site health check, application rollback/restore, or
multi-day traffic soak. Private GitHub credentials were not supplied to the
Runpod test environment; a connected GitHub repository reader is not a
deployment credential. Do not call this production-ready or a passing complete
E2E proof.

## One command to deploy a GitHub project

For a step-by-step, maintained installation and Jani walkthrough, see the [AI-assisted deployment guide](../deployment/ai-assisted-github-deployments.md).

After installing WebOps (`make dev-install` for a development instance or the
documented production installer) and configuring the CLI once with a
least-privileged WebOps token, run:

```bash
webops config --url https://panel.example.com --token "$WEBOPS_CLI_TOKEN" --role developer

# Validate an exact deployment specification with no external changes.
webops deploy ifinsta/ifinsta --dry-run --json-output

# Optional: a self-hosted, OpenAI-compatible model deployed by WebOps.
# Access token stays local; do not commit the credential or print it.
export WEBOPS_MODEL_API_KEY="$(cat /secure/path/to/model/access.key)"
# Supply a short-lived, read-only GITHUB_TOKEN through your approved secret manager;
# do not use an uninstalled example helper or embed the token in shell history.

# One approved deployment command, with bounded read-only Jani review.
webops deploy ifinsta/ifinsta --ai-assist \
  --model qwen3:8b \
  --model-endpoint https://models.example.com/v1 \
  --approve --wait --timeout 180
```

The same CLI supports `--repo`, `--name`, `--branch`, `--domain`,
`--worktree`, `--model-key-env` and `--json-output`. If the repository
is already checked out securely, use `--worktree /path/to/checkout`, avoiding
a second clone and eliminating the need to hand Git credentials to this process.

`--ai-assist` is **read-only**; Jani cannot execute arbitrary model-generated
shell commands, widen its scopes, edit the repository or approve deployments.
The operator must explicitly approve the WebOps API submission. The AI review
is fail-closed if the model is missing, unauthorized, times out or cannot
complete. GitHub credentials are not exported to Jani, and the model key
must not be embedded in a repository. The checked-out repository is untrusted.

WebOps `create_deployment` queues an application deployment in the
background processor; it is **not** itself proof of a healthy live service.
`--wait` only waits for the WebOps-reported `running` state and explicitly
reports `http_health_verified=false`. Perform a real endpoint probe and
rollback rehearsal before release.

## Reproduce tests

```bash
cd cli
python -m pip install -e . pytest pytest-cov pytest-asyncio
python -m pytest -q tests/
python -m coverage report --fail-under=100
```

**Historical snapshot:** This guide originally recorded 2,042 CLI tests and
32.15% statement coverage before the CLI coverage expansion. That is not
the current release gate or current measurement. At commit
[`4fddf82`](https://github.com/DagiiM/webops/commit/4fddf8230fd6a3151dfd76003966befe91c88300),
the full CLI suite passed **3,173 tests and 41 subtests** with **100.00%
statement coverage (5,083/5,083 statements)**. The CLI pytest and GitHub
Actions gates require **100% statement coverage**. This does not establish
100% branch coverage or production readiness. See the
[CLI verification report](webops-cli-coverage-2026-11-22.md).

## Production acceptance criteria

- Repeat Jani tool-call review after Pod/model restarts; test model upgrades
  and API outage recovery across host boundaries.
- Provide an authorized short-lived GitHub token for private repository
  checkout; avoid embedding it in command arguments or Git remote URLs.
- Deploy `ifinsta/ifinsta` in an isolated staging environment with Docker,
  its services, migrations and approved secrets, then verify a public health
  endpoint, application logs, data persistence and rollback.
- Execute sustained concurrency and failure-injection tests against
  running HTTP services; capture request rates, p95/p99, error rate,
  memory/cpu and recovery-time objectives.
- Verify that required CI quality/security gates and the 100% CLI statement coverage gate pass on the target commit. Preserve
  audit records, minimum privileges and explicit operator approval.

