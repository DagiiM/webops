"""POST /deployments/ai-assist/: analyse a repository and optionally ask an AI provider for a plan."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.api.models import AIProvider
from apps.api.rate_limiting import RateLimiter
from apps.deployments.services.ai_assist import AssistError, assist

LIMIT = RateLimiter(max_requests=40, window_seconds=3600, burst_requests=5, burst_window=60, namespace="deploy-ai-assist")


@login_required
@require_POST
@never_cache
def ai_assist(request):
    allowed, info = LIMIT.is_allowed(str(request.user.pk))
    if not allowed:
        return JsonResponse({"ok": False, "error": f"Too many requests. Try again in {info.get('retry_after', 60)} seconds."}, status=429)
    try:
        body = json.loads(request.body[:4096] or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)
    repo_url = body.get("repo_url") if isinstance(body.get("repo_url"), str) else ""
    branch = body.get("branch") if isinstance(body.get("branch"), str) else ""
    provider = None
    if body.get("use_ai", True):
        pid = body.get("provider")
        qs = AIProvider.objects.filter(user=request.user)
        provider = qs.filter(pk=pid).first() if isinstance(pid, int) and not isinstance(pid, bool) else qs.filter(is_default=True).first()
    try:
        result = assist(request.user, repo_url.strip()[:300], branch.strip()[:200], provider=provider)
    except AssistError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    result["ok"] = True
    return JsonResponse(result)
