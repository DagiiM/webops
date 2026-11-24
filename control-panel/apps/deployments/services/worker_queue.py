"""Remote build workers: tokens, the job queue, and the rules for what a worker may be given.

Rules that matter
-----------------
* A worker is trusted with exactly one thing: building approved jobs. Its token is hashed at rest, shown once,
  revocable, and only valid for the worker API.
* Jobs carry a *kind* from a fixed catalog (rust, node, python). The worker maps the kind to its own fixed
  commands; the panel never sends a command line, and neither a user nor an AI can add one.
* A job builds one exact commit, pinned when the operator approves, not a moving branch.
* The panel fetches the source (with the requester's GitHub token, which never leaves the panel) and streams it
  to the worker over the job's authenticated channel.
* Workers are process-isolated, not machine-isolated from each other's jobs, so only repositories owned by a
  trusted owner (the requester's own GitHub account or an operator-listed owner) are ever scheduled.
"""
import hashlib
import logging
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.common.utils.validators import parse_github_repo
from apps.services.runtime.policy import executable_block_reason

from ..models import BaseDeployment, BuildJob, DeploymentLog, WorkerNode

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "wops_wrk_"
API = "https://api.github.com"
MAX_SOURCE_BYTES = 200 * 1024 * 1024
LEASE_SLACK = 180
DEFAULT_LIMITS = {"wall_seconds": 1800, "cpu_seconds": 7200, "memory_mb": 24576, "file_mb": 4096, "procs": 2048, "disk_mb": 10240}
CATALOG = {"rust": "Cargo.toml", "node": "package.json", "python": "requirements.txt"}      # kind -> file that identifies it


class WorkerError(Exception):
    """A failure whose message is safe to show to the operator."""


# ───────────────────────────── tokens and workers ─────────────────────────────

def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_worker(name, user):
    name = (name or "").strip()
    if not 2 <= len(name) <= 60 or not all(c.isalnum() or c in "-_ ." for c in name):
        raise WorkerError("Use 2 to 60 characters: letters, digits, spaces, dots, hyphens or underscores.")
    if WorkerNode.objects.filter(name=name).exists():
        raise WorkerError("A worker with that name already exists.")
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    node = WorkerNode.objects.create(name=name, digest=_digest(token), created_by=user)
    return node, token


def authenticate(raw):
    """The active worker for a bearer token, or None."""
    if not raw or not raw.startswith(TOKEN_PREFIX) or len(raw) > 200:
        return None
    return WorkerNode.objects.filter(digest=_digest(raw), revoked_at__isnull=True).first()


def revoke(node):
    node.revoked_at = timezone.now()
    node.save(update_fields=["revoked_at"])
    # Anything it was holding goes back to the queue (counts as an attempt).
    for job in BuildJob.objects.filter(worker=node, status__in=(BuildJob.Status.CLAIMED, BuildJob.Status.BUILDING)):
        _requeue_or_fail(job, "The worker was revoked.")


def heartbeat(node, info):
    clean = {}
    for key, limit in (("agent", 40), ("os", 80), ("isolation", 80)):
        if isinstance(info.get(key), str):
            clean[key] = info[key][:limit]
    for key in ("cpus", "memory_gb", "free_disk_gb"):
        if isinstance(info.get(key), (int, float)) and not isinstance(info.get(key), bool):
            clean[key] = round(float(info[key]), 1)
    node.last_seen = timezone.now()
    node.info = {**node.info, **clean}
    node.save(update_fields=["last_seen", "info"])


def online_workers():
    cutoff = timezone.now() - timedelta(seconds=WorkerNode.ONLINE_SECONDS)
    return WorkerNode.objects.filter(revoked_at__isnull=True, last_seen__gte=cutoff)


def worker_ready():
    return online_workers().exists()


# ───────────────────────────── what a worker may be given ─────────────────────────────

def trusted_owners(user):
    configured = getattr(settings, "WEBOPS_WORKER_TRUSTED_OWNERS", "")
    owners = {o.strip().lower() for o in (configured.split(",") if isinstance(configured, str) else configured) if o.strip()}
    try:
        owners.add(user.github_connection.username.lower())
    except Exception:
        pass
    return owners


def detect_kind(root):
    """The catalog kind for a repository, from its root file names. Deterministic; None when unsupported."""
    names = set(root or ())
    for kind, marker in CATALOG.items():
        if marker in names:
            return kind
    if "pyproject.toml" in names:
        return "python"
    return None


def _github(path, token):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "webops-worker-queue"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        return requests.get(API + path, headers=headers, timeout=(5, 15), allow_redirects=False)
    except requests.RequestException:
        raise WorkerError("GitHub could not be reached.")


def assess(deployment):
    """Can this approved request be built on a worker? Returns (ok, reason, kind, commit)."""
    from .ai_assist import AssistError, fetch_repo
    from apps.core.integrations.services import GitHubIntegrationService
    if not worker_ready():
        return False, executable_block_reason() + " No worker is online.", None, None
    parsed = parse_github_repo(deployment.repo_url)
    if not parsed or parsed.get("ssh"):
        return False, "Only GitHub HTTPS repositories can be built on a worker.", None, None
    owners = trusted_owners(deployment.deployed_by)
    if parsed["owner"].lower() not in owners:
        return False, (f"Workers only build repositories from trusted owners. '{parsed['owner']}' is not one of: "
                       f"{', '.join(sorted(owners)) or 'none configured'}. An operator can add it to WEBOPS_WORKER_TRUSTED_OWNERS."), None, None
    token = GitHubIntegrationService().get_access_token(deployment.deployed_by)
    try:
        facts = fetch_repo(parsed["owner"], parsed["repo"], deployment.branch, token)
    except AssistError as exc:
        return False, str(exc), None, None
    kind = detect_kind(facts["root"])
    if kind is None:
        return False, "This project type is not supported on workers yet (Rust, Node and Python are).", None, None
    response = _github(f"/repos/{parsed['owner']}/{parsed['repo']}/commits/{facts['ref']}", token)
    sha = (response.json() or {}).get("sha", "") if response.status_code == 200 else ""
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        return False, "The branch's latest commit could not be determined.", None, None
    return True, "", kind, sha


# ───────────────────────────── queue ─────────────────────────────

def enqueue(deployment, kind, commit):
    if kind not in CATALOG:
        raise WorkerError("Unsupported project type.")
    job = BuildJob.objects.create(deployment=deployment, kind=kind, commit=commit, limits=dict(DEFAULT_LIMITS))
    BaseDeployment.objects.filter(pk=deployment.pk).update(status=BaseDeployment.Status.BUILDING)
    DeploymentLog.objects.create(deployment=deployment, level="info", message=f"Queued {kind} build of {commit[:10]} for a worker.")
    return job


def _log(job, level, message):
    DeploymentLog.objects.create(deployment=job.deployment, level=level, message=message[:500])


def _requeue_or_fail(job, why):
    if job.attempts >= BuildJob.MAX_ATTEMPTS:
        job.status, job.finished_at, job.result = BuildJob.Status.FAILED, timezone.now(), {"error": f"{why} Giving up after {job.attempts} attempts."}
        job.save(update_fields=["status", "finished_at", "result"])
        BaseDeployment.objects.filter(pk=job.deployment_id).update(status=BaseDeployment.Status.FAILED)
        _log(job, "error", job.result["error"])
    else:
        job.status, job.worker, job.lease_expires_at = BuildJob.Status.QUEUED, None, None
        job.save(update_fields=["status", "worker", "lease_expires_at"])
        _log(job, "warning", f"{why} Re-queued.")


def _expire_leases():
    now = timezone.now()
    for job in BuildJob.objects.filter(status__in=(BuildJob.Status.CLAIMED, BuildJob.Status.BUILDING), lease_expires_at__lt=now):
        _requeue_or_fail(job, "The worker stopped reporting.")


def claim(node):
    """Hand the oldest queued job to this worker, or None."""
    _expire_leases()
    with transaction.atomic():
        job = (BuildJob.objects.select_for_update(skip_locked=True).filter(status=BuildJob.Status.QUEUED).order_by("created_at").first())
        if job is None:
            return None
        wall = int(job.limits.get("wall_seconds", DEFAULT_LIMITS["wall_seconds"]))
        job.status, job.worker, job.attempts = BuildJob.Status.CLAIMED, node, job.attempts + 1
        job.claimed_at, job.lease_expires_at = timezone.now(), timezone.now() + timedelta(seconds=wall + LEASE_SLACK)
        job.save(update_fields=["status", "worker", "attempts", "claimed_at", "lease_expires_at"])
    return {"id": job.pk, "kind": job.kind, "commit": job.commit, "limits": job.limits, "attempt": job.attempts}


def _own(job_id, node, *, active=True):
    job = BuildJob.objects.filter(pk=job_id, worker=node).first()
    if job is None or (active and job.status not in (BuildJob.Status.CLAIMED, BuildJob.Status.BUILDING)):
        raise WorkerError("That job is not yours or is no longer active.")
    return job


def append_log(job_id, node, text):
    job = _own(job_id, node)
    text = text.replace("\x00", "")[:20_000]
    room = BuildJob.MAX_LOG - len(job.log)
    if room > 0:
        job.log += text[:room]
        if len(text) > room:
            job.log += "\n[log truncated]\n"
    wall = int(job.limits.get("wall_seconds", DEFAULT_LIMITS["wall_seconds"]))
    job.status = BuildJob.Status.BUILDING
    job.lease_expires_at = timezone.now() + timedelta(seconds=wall + LEASE_SLACK)
    job.save(update_fields=["log", "status", "lease_expires_at"])


def complete(job_id, node, *, ok, exit_code=None, summary="", artifacts=None):
    job = _own(job_id, node)
    summary = (summary or "")[:300]
    job.status = BuildJob.Status.SUCCEEDED if ok else BuildJob.Status.FAILED
    job.finished_at = timezone.now()
    job.result = {"ok": bool(ok), "exit_code": exit_code if isinstance(exit_code, int) else None, "summary": summary,
                  "artifacts": [str(a)[:120] for a in (artifacts or [])[:20]]}
    job.save(update_fields=["status", "finished_at", "result"])
    if ok:
        BaseDeployment.objects.filter(pk=job.deployment_id).update(status=BaseDeployment.Status.STOPPED)
        _log(job, "success", f"Built on worker {node.name}. {summary} Serving applications from workers is not enabled yet.")
    else:
        BaseDeployment.objects.filter(pk=job.deployment_id).update(status=BaseDeployment.Status.FAILED)
        _log(job, "error", f"Build failed on worker {node.name}. {summary}")
    return job


def cancel(job):
    if job.status in BuildJob.ACTIVE:
        job.status, job.finished_at = BuildJob.Status.CANCELLED, timezone.now()
        job.save(update_fields=["status", "finished_at"])
        BaseDeployment.objects.filter(pk=job.deployment_id, status=BaseDeployment.Status.BUILDING).update(status=BaseDeployment.Status.REQUESTED)


# ───────────────────────────── source ─────────────────────────────

def open_source(job):
    """A generator streaming the job's exact commit as a zip, fetched with the requester's own GitHub token."""
    from apps.core.integrations.services import GitHubIntegrationService
    parsed = parse_github_repo(job.deployment.repo_url)
    if not parsed or parsed.get("ssh") or len(job.commit) != 40:
        raise WorkerError("This job has no fetchable source.")
    token = GitHubIntegrationService().get_access_token(job.deployment.deployed_by)
    first = _github(f"/repos/{parsed['owner']}/{parsed['repo']}/zipball/{job.commit}", token)
    if first.status_code not in (301, 302, 307):
        raise WorkerError("GitHub did not provide the source archive.")
    location = first.headers.get("Location", "")
    if not location.startswith("https://codeload.github.com/"):
        raise WorkerError("GitHub redirected to an unexpected host.")
    try:
        response = requests.get(location, stream=True, timeout=(5, 20), allow_redirects=False)   # no Authorization header on this hop
    except requests.RequestException:
        raise WorkerError("The source archive could not be downloaded.")
    if response.status_code != 200:
        raise WorkerError("The source archive could not be downloaded.")

    def stream():
        sent = 0
        try:
            for chunk in response.iter_content(65536):
                sent += len(chunk)
                if sent > MAX_SOURCE_BYTES:
                    logger.warning("Worker source for job %s exceeded the size limit", job.pk)
                    return
                yield chunk
        finally:
            response.close()
    return stream()
