# Production readiness: evidence-based release gates

The Runpod deployment is a restricted shared-UID preview, not production-certified. Existing features are not certified by the presence of a UI or a passing unit test suite alone.

| Gate | Acceptance evidence |
|---|---|
| Background reliability | Durable queue across web/worker restart; interrupted work visibly failed; no unsafe replay; worker readiness; migrate remaining direct Celery callers |
| Security and isolation | Separate control plane/workload identities; tenant isolation tests; credential and logging review; least privilege; threat model; rate-limit review |
| Persistence and recovery | Persistent volume, PostgreSQL/Redis where appropriate, backup retention and tested restore; full container restart and replacement |
| Networking | Authenticated management plane; per-app origin, domain routing, TLS renewal, DNS and request limits |
| Application runtime | Real static, Django, Node, Go, Rust and other claimed framework deployments; negative tests; rollbacks and updates |
| LLM | GPU/CPU scheduling, memory/disk admission, isolation, model and backend compatibility; authenticated inference |
| Databases | Real provision/connect/backup/restore/delete for supported engines; scoped credentials |
| Automation and addons | Real workflow execution, bounded retries, webhooks, notifications, addon lifecycle; permission enforcement |
| MCP | OAuth authorization, client compatibility, schema and protocol conformance, consent and audit |
| Monitoring | Durable event delivery, actionable alerts, recovery and incident runbooks |
| Quality | Browser/mobile accessibility, security scanning, CI, load and soak tests; no unjustified feature claims |

## Single-host durable deployment queue

Set WEBOPS_BG_PROCESSOR=sqlite in both the web process and the separately supervised process running:

    python manage.py run_background_worker

The SQLite queue resides at WEBOPS_INSTALL_PATH/queue/jobs.sqlite3 by default; optionally set WEBOPS_QUEUE_PATH in Django settings. Put it on a persistent local disk. One worker at a time holds an exclusive OS lock. Pending jobs survive web and worker restarts, duplicate active submissions for the same operation are deduplicated, and jobs interrupted mid-execution are marked failed with a reconciliation message (not replayed). Only registered deployment/service tasks with a single deployment ID are accepted. The queue is not a distributed worker system. Keep production workloads on isolated workers; use Celery/Redis for distributed operation after integration testing.

Readiness is heartbeat-based. A stopped worker does not erase queued jobs. Job history is pruned after 30 days at worker startup. The shared-UID preview still uses local process management and in-memory channel layers; refresh or poll the status page if worker events do not reach the browser. The durable queue does not imply durable container storage.

## Release discipline

For each gate: audit source and live behavior, implement changes on a branch, add regression and adversarial tests, test real integration on isolated resources, merge only verified changes, deploy the matching commit, verify live health and document remaining gaps. Never advertise production readiness until the gates have objective evidence.
