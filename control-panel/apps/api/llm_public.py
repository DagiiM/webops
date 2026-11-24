"""Public, key-authenticated inference API for the owner's own running reviewed CPU models.

Deliberately small: list models and run bounded text completions. A dedicated inference-only key
(LLMAccessKey, hashed, expiring, revocable) is the only credential accepted; it cannot manage
deployments. Model servers stay bound to 127.0.0.1; this view is the only public path to them.
"""
import hashlib
import json
import logging
import secrets
import time
import uuid

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from apps.deployments.models import BaseDeployment
from apps.services.runtime import portable_runtime
from .models import LLMAccessKey
from .rate_limiting import RateLimiter, get_client_ip

logger = logging.getLogger(__name__)

KEY_PREFIX = "wops_llm_"
MAX_BODY = 16 * 1024
MAX_PROMPT = 4096          # matches the model server's own limits
MAX_TOKENS = 128
MAX_ACTIVE_KEYS = 10
KEY_LIFETIME_DAYS = 30
# Limits apply before authentication (per client IP) and after it (per key).
IP_LIMIT = RateLimiter(max_requests=600, window_seconds=3600, burst_requests=60, burst_window=60, namespace="llm-public-ip")
KEY_LIMIT = RateLimiter(max_requests=300, window_seconds=3600, burst_requests=10, burst_window=60, namespace="llm-public-key")


def _error(message, status, kind="invalid_request_error", retry_after=None):
    response = JsonResponse({"error": {"message": message, "type": kind}}, status=status)
    if status == 401:
        response["WWW-Authenticate"] = 'Bearer realm="WebOps LLM"'
    if retry_after is not None:
        response["Retry-After"] = str(retry_after)
    return response


def _key_for(request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer " + KEY_PREFIX) or len(auth) > 160:
        return None
    digest = hashlib.sha256(auth[7:].encode()).hexdigest()
    key = (LLMAccessKey.objects.select_related("user")
           .filter(digest=digest, revoked_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True)
           .first())
    if key:
        LLMAccessKey.objects.filter(pk=key.pk).update(last_used=timezone.now())
    return key


def _ready_models(user):
    """Running reviewed CPU models owned by the user, keyed by deployment name."""
    from apps.deployments.services.llm_preflight import SUPPORTED
    runtime = portable_runtime()
    models = {}
    if not runtime:
        return models
    qs = BaseDeployment.objects.filter(deployed_by=user, is_deleted=False, status="running").select_related("llmdeployment")
    for d in qs:
        llm = getattr(d, "llmdeployment", None)
        if llm is None or not d.port or llm.model_name not in SUPPORTED:
            continue
        try:
            if not runtime.status(d)["active"]:
                continue
        except Exception:  # a broken runtime must not break listing
            continue
        models[d.name] = d
    return models


def _gate(request, method):
    """Shared checks. Returns (key, None) or (None, error response)."""
    if request.method != method:
        response = _error("Method not allowed.", 405)
        response["Allow"] = method
        return None, response
    if not request.is_secure() and not settings.DEBUG:
        return None, _error("HTTPS required.", 403)
    allowed, info = IP_LIMIT.is_allowed(get_client_ip(request))
    if not allowed:
        return None, _error("Rate limited. Retry later.", 429, "rate_limit_error", info.get("retry_after", 60))
    key = _key_for(request)
    if key is None:
        return None, _error("A valid LLM API key is required (Authorization: Bearer wops_llm_...).", 401, "authentication_error")
    allowed, info = KEY_LIMIT.is_allowed(str(key.pk))
    if not allowed:
        return None, _error("Rate limited. Retry later.", 429, "rate_limit_error", info.get("retry_after", 60))
    return key, None


@csrf_exempt
@never_cache
def models_view(request):
    key, denied = _gate(request, "GET")
    if denied:
        return denied
    data = [{"id": name, "object": "model", "created": int(d.created_at.timestamp()), "owned_by": "webops"}
            for name, d in _ready_models(key.user).items()]
    return JsonResponse({"object": "list", "data": data})


@csrf_exempt
@never_cache
def completions_view(request):
    key, denied = _gate(request, "POST")
    if denied:
        return denied
    if request.content_type != "application/json":
        return _error("Content-Type must be application/json.", 415)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_BODY or len(request.body) > MAX_BODY:
            return _error("Request too large.", 413)
        body = json.loads(request.body or b"{}", parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(body, dict):
            raise ValueError
        prompt = body.get("prompt")
        tokens = body.get("max_tokens", 16)
        temperature = body.get("temperature", 0.7)
        if (not isinstance(prompt, str) or not 1 <= len(prompt) <= MAX_PROMPT
                or type(tokens) is not int or not 1 <= tokens <= MAX_TOKENS
                or isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2
                or body.get("stream") not in (None, False)
                or not isinstance(body.get("model", ""), str)):
            raise ValueError
    except (ValueError, UnicodeDecodeError, TypeError):
        return _error(f"Send JSON with a prompt of 1-{MAX_PROMPT} characters, max_tokens 1-{MAX_TOKENS}, "
                      "temperature 0-2. Streaming is not supported.", 400)

    models = _ready_models(key.user)
    name = body.get("model") or (next(iter(models)) if len(models) == 1 else "")
    deployment = models.get(name)
    if deployment is None:
        return _error("Unknown or not-ready model. GET /api/llm/v1/models lists the models you can use.", 404, "not_found_error")

    try:
        upstream = requests.post(f"http://127.0.0.1:{int(deployment.port)}/v1/completions",
                                 json={"prompt": prompt, "max_tokens": tokens, "temperature": temperature},
                                 timeout=60, allow_redirects=False)
    except requests.RequestException:
        logger.warning("LLM public API upstream unavailable key_id=%s model=%s", key.pk, name)
        return _error("Model unavailable. Retry shortly.", 503, "server_error")
    if upstream.status_code == 429:
        return _error("Model busy; try again shortly.", 429, "rate_limit_error", 2)
    try:
        if upstream.status_code != 200:
            raise ValueError
        text = upstream.json()["choices"][0]["text"]
        if not isinstance(text, str):
            raise ValueError
    except (ValueError, KeyError, IndexError, TypeError):
        return _error("Model did not return a valid response.", 502, "server_error")
    logger.info("LLM public API completion key_id=%s model=%s", key.pk, name)
    return JsonResponse({"id": "cmpl-" + uuid.uuid4().hex[:24], "object": "text_completion",
                         "created": int(time.time()), "model": name,
                         "choices": [{"index": 0, "text": text, "finish_reason": "stop"}]})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def keys_view(request):
    """Create (shown once) and list the signed-in user's LLM API keys."""
    keys = LLMAccessKey.objects.filter(user=request.user).order_by("-created_at")
    issued, error = None, None
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        active = LLMAccessKey.objects.filter(user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()).count()
        if not 1 <= len(name) <= 100:
            error = "Enter a name of 1-100 characters."
        elif active >= MAX_ACTIVE_KEYS:
            error = "Revoke an existing key before creating another."
        else:
            issued = KEY_PREFIX + secrets.token_urlsafe(32)
            LLMAccessKey.objects.create(user=request.user, name=name, digest=hashlib.sha256(issued.encode()).hexdigest(),
                                        expires_at=timezone.now() + timezone.timedelta(days=KEY_LIFETIME_DAYS))
            keys = LLMAccessKey.objects.filter(user=request.user).order_by("-created_at")
    response = render(request, "api/llm_keys.html", {
        "keys": keys, "issued": issued, "error": error, "days": KEY_LIFETIME_DAYS,
        "base_url": request.build_absolute_uri("/api/llm/v1"),
        "models": list(_ready_models(request.user)),
    }, status=400 if error else 200)
    # same-origin, not no-referrer: with no-referrer browsers send "Origin: null" on this page's own
    # form posts, which Django's CSRF check rejects. The key is never in a URL, so nothing leaks.
    response["Referrer-Policy"] = "same-origin"
    return response


@login_required
@require_POST
@never_cache
def key_revoke(request, pk):
    key = get_object_or_404(LLMAccessKey, pk=pk, user=request.user)
    key.revoked_at = timezone.now()
    key.save(update_fields=["revoked_at"])
    return redirect("llm_keys")
