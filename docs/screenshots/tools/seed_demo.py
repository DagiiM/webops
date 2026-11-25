"""Seed a throw-away database with made-up demo data for the README screenshots.

Run against an EMPTY, migrated database only (never a real one):
    DATABASE_URL=postgresql://... python manage.py shell < docs/screenshots/tools/seed_demo.py
Everything here is fictional: the 'acme' organisation, repositories and names do not exist.
Managed databases are deployed for real by capture.js, so their status badges are genuine.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.api.models import AIProvider, APIToken, LLMAccessKey
from apps.deployments.models import ApplicationDeployment as App, BuildJob, DeploymentLog, LLMDeployment, WorkerNode

User = get_user_model()
assert User.objects.count() == 0, "Refusing to seed a database that already has users."
now = timezone.now()

admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
dev = User.objects.create_user("maya", "maya@example.com", "demo-pass-123")


def app(name, repo, status, project="python", static=False, port=None, domain="", report=None, ago=60, user=None):
    d = App.objects.create(name=name, repo_url=f"https://github.com/acme/{repo}", branch="main", status=status, project_type=project,
                           static_only=static, port=port, domain=domain, deployed_by=user or admin, safety_report=report or {})
    App.objects.filter(pk=d.pk).update(created_at=now - timedelta(minutes=ago))
    return d


def report(decision, findings, ai=("ran", "A small project with no network surprises.")):
    return {"verdict": "pass" if decision == "auto_approved" else "review", "decision": decision, "reviewed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "approved_by": "automatic review" if decision == "auto_approved" else "", "findings": findings, "stats": {},
            "ai": {"status": ai[0], "summary": ai[1], "provider": "OpenAI"}}


site = app("marketing-site", "marketing-site", "running", "react", static=True, port=8101, domain="www.acme.example", ago=1500,
           report=report("auto_approved", [{"id": "external-scripts", "severity": "info", "title": "Loads scripts from other sites", "detail": "Hosts: cdn.jsdelivr.net", "path": "", "source": "rule"}]))
api = app("billing-api", "billing-api", "running", "python", port=8102, domain="billing.acme.example", ago=4300)
docs = app("docs-portal", "docs-portal", "pending", "vue", static=True, port=8103, ago=2,
           report=report("auto_approved", []))
care = app("care-platform", "care", "requested", "python", ago=35,
           report=report("needs_operator", [
               {"id": "executes-code", "severity": "review", "title": "Runs repository code", "detail": "This project would build and run code, so a person must approve it and it needs an isolated worker.", "path": "", "source": "rule"},
               {"id": "secret-file", "severity": "warn", "title": "Secret-looking file in the repository", "detail": ".env.local is committed. Treat it as exposed.", "path": ".env.local", "source": "rule"}],
               ai=("ran", "A Rust workspace with an HTTP API, a CLI and background workers.")))
legacy = app("legacy-importer", "legacy-importer", "failed", "python", port=8104, ago=700)
for text, level in (("Starting deployment process", "info"), ("Cloning repository", "info"), ("Installing dependencies", "info"),
                    ("Build failed: requirements.txt pins a package that no longer exists", "error")):
    DeploymentLog.objects.create(deployment=legacy, level=level, message=text)
for text, level in (("Safety review passed. Publishing automatically.", "success"), ("Static site published on port 8101", "success")):
    DeploymentLog.objects.create(deployment=site, level=level, message=text)

llm = LLMDeployment.objects.create(name="smollm2-135m-instruct", model_name="HuggingFaceTB/SmolLM2-135M-Instruct", status="running", port=9371,
                                   deployed_by=admin, backend="transformers", dtype="auto", download_completed=True)
LLMDeployment.objects.filter(pk=llm.pk).update(created_at=now - timedelta(hours=9))

import hashlib, secrets
LLMAccessKey.objects.create(user=admin, name="notebook", digest=hashlib.sha256(secrets.token_bytes(16)).hexdigest(), expires_at=now + timedelta(days=21), last_used=now - timedelta(hours=3))
LLMAccessKey.objects.create(user=admin, name="staging-app", digest=hashlib.sha256(secrets.token_bytes(16)).hexdigest(), expires_at=now + timedelta(days=6))
APIToken.objects.create(user=admin, name="ci-deploy", token=secrets.token_hex(32), expires_at=now + timedelta(days=60), last_used=now - timedelta(days=1))

p = AIProvider(user=admin, name="OpenAI", kind="external", model="gpt-4o-mini", base_url="https://api.openai.com/v1", is_default=True, last_ok=True, last_used=now - timedelta(minutes=20))
p.set_api_key("sk-demo-0000000000000000000000000000AB12")
p.save()

node = WorkerNode.objects.create(name="build-1", digest=hashlib.sha256(b"demo").hexdigest(), created_by=admin, last_seen=now,
                                 info={"agent": "webops-worker/1.0", "os": "Linux 6.8.0", "cpus": 8, "memory_gb": 32,
                                       "isolation": "process: unprivileged user, rlimits, no_new_privs; no network isolation"})
WorkerNode.objects.create(name="build-2", digest=hashlib.sha256(b"demo2").hexdigest(), created_by=admin, last_seen=now - timedelta(hours=5), info={"cpus": 4, "memory_gb": 16})
LOG = """== job 1: rust build of commit e94a54ab34 (attempt 1)

$ [1/1] cargo build --release --locked
   Compiling serde v1.0.228
   Compiling tokio v1.48.0
   Compiling sqlx v0.8.6
   Compiling axum v0.8.9
   Compiling care-core v0.1.0
   Compiling care-identity v0.1.0
   Compiling care-server v0.1.0
    Finished `release` profile [optimized] target(s) in 47.83s
"""
ok = BuildJob.objects.create(deployment=care, kind="rust", commit="e94a54ab34ca003b63ebf063907c91176945de15", status="succeeded", worker=node, attempts=1,
                             log=LOG, result={"ok": True, "exit_code": 0, "summary": "1 step(s) succeeded.", "artifacts": ["target/release/care-api", "target/release/care-migrate", "target/release/care-worker"]},
                             finished_at=now - timedelta(minutes=3), claimed_at=now - timedelta(minutes=4))
BuildJob.objects.create(deployment=legacy, kind="python", commit="b" * 40, status="failed", worker=node, attempts=1,
                        log="== job 2: python build\n\n$ [2/2] .venv/bin/pip install -r requirements.txt\nERROR: No matching distribution found for oldpkg==0.3\n",
                        result={"ok": False, "exit_code": 1, "summary": "Step 2 (.venv/bin/pip) exited with 1.", "artifacts": []}, finished_at=now - timedelta(hours=11))
print("seeded:", App.objects.count(), "apps,", LLMDeployment.objects.count(), "llm,", BuildJob.objects.count(), "jobs; first job id", ok.pk)
