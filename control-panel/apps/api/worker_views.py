"""Worker API: the only surface a remote build worker can reach.

Bearer-token authenticated (WorkerNode, hashed, revocable). A worker can claim a queued job, fetch that job's
source, append to its log, and report the outcome. It cannot read or change anything else.
"""
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from apps.deployments.models import BuildJob
from apps.deployments.services import worker_queue as wq
from .rate_limiting import RateLimiter, get_client_ip

logger = logging.getLogger(__name__)
MAX_BODY = 64 * 1024
IP_LIMIT = RateLimiter(max_requests=3000, window_seconds=3600, burst_requests=120, burst_window=60, namespace="worker-ip")
NODE_LIMIT = RateLimiter(max_requests=6000, window_seconds=3600, burst_requests=120, burst_window=60, namespace="worker-node")


def _error(message, status):
    response = JsonResponse({"error": message}, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _bearer(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    return header[7:].strip() if header[:7].lower() == "bearer " else ""


def _gate(request, method):
    """Returns (node, None) or (None, error response)."""
    if request.method != method:
        response = _error("Method not allowed.", 405)
        response["Allow"] = method
        return None, response
    if not request.is_secure() and not settings.DEBUG:
        return None, _error("HTTPS required.", 403)
    allowed, _ = IP_LIMIT.is_allowed(get_client_ip(request))
    if not allowed:
        return None, _error("Rate limited.", 429)
    node = wq.authenticate(_bearer(request))
    if node is None:
        return None, _error("A valid worker token is required.", 401)
    allowed, _ = NODE_LIMIT.is_allowed(str(node.pk))
    if not allowed:
        return None, _error("Rate limited.", 429)
    return node, None


def _body(request):
    if len(request.body) > MAX_BODY:
        return None
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


@csrf_exempt
@never_cache
def heartbeat(request):
    node, denied = _gate(request, "POST")
    if denied:
        return denied
    data = _body(request)
    if data is None:
        return _error("Invalid request.", 400)
    wq.heartbeat(node, data)
    return JsonResponse({"ok": True})


@csrf_exempt
@never_cache
def claim(request):
    node, denied = _gate(request, "POST")
    if denied:
        return denied
    wq.heartbeat(node, {})
    job = wq.claim(node)
    if job is None:
        return HttpResponse(status=204)
    logger.info("Worker %s claimed job %s", node.pk, job["id"])
    return JsonResponse(job)


@csrf_exempt
@never_cache
def source(request, job_id):
    node, denied = _gate(request, "GET")
    if denied:
        return denied
    job = BuildJob.objects.filter(pk=job_id, worker=node, status__in=(BuildJob.Status.CLAIMED, BuildJob.Status.BUILDING)).select_related("deployment").first()
    if job is None:
        return _error("Not your job.", 404)
    try:
        stream = wq.open_source(job)
    except wq.WorkerError as exc:
        return _error(str(exc), 502)
    response = StreamingHttpResponse(stream, content_type="application/zip")
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@never_cache
def log(request, job_id):
    node, denied = _gate(request, "POST")
    if denied:
        return denied
    data = _body(request)
    if data is None or not isinstance(data.get("text"), str):
        return _error("Invalid request.", 400)
    try:
        wq.append_log(job_id, node, data["text"])
    except wq.WorkerError as exc:
        return _error(str(exc), 409)
    return JsonResponse({"ok": True})


@csrf_exempt
@never_cache
def complete(request, job_id):
    node, denied = _gate(request, "POST")
    if denied:
        return denied
    data = _body(request)
    if data is None or not isinstance(data.get("ok"), bool):
        return _error("Invalid request.", 400)
    try:
        wq.complete(job_id, node, ok=data["ok"], exit_code=data.get("exit_code"), summary=str(data.get("summary", "")),
                    artifacts=data.get("artifacts") if isinstance(data.get("artifacts"), list) else [])
    except wq.WorkerError as exc:
        return _error(str(exc), 409)
    return JsonResponse({"ok": True})
