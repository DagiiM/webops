"""Manage AI providers: OpenAI-compatible models (local or external) used by WebOps' AI features."""
import re

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .ai_client import ProviderError, complete, validate_base_url
from .llm_public import _ready_models
from .models import AIProvider
from .rate_limiting import RateLimiter

MAX_PROVIDERS = 10
TEST_LIMIT = RateLimiter(max_requests=30, window_seconds=3600, burst_requests=5, burst_window=60, namespace="ai-provider-test")
PRESETS = [
    ("OpenAI", "https://api.openai.com/v1"),
    ("OpenRouter", "https://openrouter.ai/api/v1"),
    ("Groq", "https://api.groq.com/openai/v1"),
    ("Together AI", "https://api.together.xyz/v1"),
    ("Mistral", "https://api.mistral.ai/v1"),
    ("Google Gemini (OpenAI mode)", "https://generativelanguage.googleapis.com/v1beta/openai"),
]
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _context(request, **extra):
    ctx = {"providers": AIProvider.objects.filter(user=request.user), "presets": PRESETS,
           "local_models": list(_ready_models(request.user)), "max_providers": MAX_PROVIDERS,
           "values": {}, "errors": [], "result": None}
    ctx.update(extra)
    return ctx


def _render(request, status=200, **extra):
    response = render(request, "api/ai_providers.html", _context(request, **extra), status=status)
    response["Referrer-Policy"] = "same-origin"
    return response


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def providers_view(request):
    if request.method == "GET":
        return _render(request)

    post = request.POST
    values = {"kind": post.get("kind", ""), "name": post.get("name", "").strip(), "base_url": post.get("base_url", "").strip(),
              "model": (post.get("local_model") if post.get("kind") == AIProvider.LOCAL else post.get("model", "")) or "", "allow_private": post.get("allow_private") == "on"}
    values["model"] = values["model"].strip()
    errors = []
    kind = values["kind"]
    if kind not in (AIProvider.LOCAL, AIProvider.EXTERNAL):
        errors.append("Choose a provider type.")
    if not 1 <= len(values["name"]) <= 100 or _CONTROL.search(values["name"]):
        errors.append("Enter a name of 1 to 100 characters.")
    elif AIProvider.objects.filter(user=request.user, name=values["name"]).exists():
        errors.append("You already have a provider with that name.")
    if AIProvider.objects.filter(user=request.user).count() >= MAX_PROVIDERS:
        errors.append(f"You can keep up to {MAX_PROVIDERS} providers. Delete one first.")
    base_url, key = "", ""
    if kind == AIProvider.LOCAL:
        if values["model"] not in _ready_models(request.user):
            errors.append("Choose one of your running local models. Start one from LLM models if none is listed.")
    elif kind == AIProvider.EXTERNAL:
        try:
            base_url = validate_base_url(values["base_url"])
        except ProviderError as exc:
            errors.append(str(exc))
        if not 1 <= len(values["model"]) <= 200 or _CONTROL.search(values["model"]):
            errors.append("Enter the model name your provider expects, for example gpt-4o-mini.")
        key = post.get("api_key", "").strip()
        if len(key) > 400 or _CONTROL.search(key):
            errors.append("That API key does not look valid.")
    if errors:
        return _render(request, status=400, errors=errors, values=values)

    provider = AIProvider(user=request.user, name=values["name"], kind=kind, model=values["model"],
                          base_url=base_url, allow_private_repos=values["allow_private"] and kind == AIProvider.EXTERNAL)
    provider.set_api_key(key)
    provider.is_default = post.get("make_default") == "on" or not AIProvider.objects.filter(user=request.user).exists()
    if provider.is_default:
        AIProvider.objects.filter(user=request.user, is_default=True).update(is_default=False)
    provider.save()
    return _render(request, result={"ok": True, "text": f"Added {provider.name}. Use Test to check it works."})


@login_required
@require_POST
@never_cache
def provider_test(request, pk):
    provider = get_object_or_404(AIProvider, pk=pk, user=request.user)
    allowed, info = TEST_LIMIT.is_allowed(str(request.user.pk))
    if not allowed:
        return _render(request, status=429, result={"ok": False, "text": f"Too many tests. Try again in {info.get('retry_after', 60)} seconds."})
    try:
        reply = complete(provider, [{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=16, temperature=0)
    except ProviderError as exc:
        return _render(request, result={"ok": False, "text": f"{provider.name}: {exc}"})
    return _render(request, result={"ok": True, "text": f"{provider.name} answered: {re.sub(r'[\x00-\x1f]+', ' ', reply).strip()[:80]}"})


@login_required
@require_POST
@never_cache
def provider_default(request, pk):
    provider = get_object_or_404(AIProvider, pk=pk, user=request.user)
    AIProvider.objects.filter(user=request.user, is_default=True).update(is_default=False)
    provider.is_default = True
    provider.save(update_fields=["is_default"])
    return redirect("ai_providers")


@login_required
@require_POST
@never_cache
def provider_delete(request, pk):
    provider = get_object_or_404(AIProvider, pk=pk, user=request.user)
    was_default = provider.is_default
    provider.delete()
    if was_default:
        nxt = AIProvider.objects.filter(user=request.user).first()
        if nxt:
            nxt.is_default = True
            nxt.save(update_fields=["is_default"])
    return redirect("ai_providers")


@login_required
@require_POST
@never_cache
def provider_key(request, pk):
    """Replace (or clear) an external provider's API key. The old key is never shown."""
    provider = get_object_or_404(AIProvider, pk=pk, user=request.user, kind=AIProvider.EXTERNAL)
    key = request.POST.get("api_key", "").strip()
    if len(key) > 400 or _CONTROL.search(key):
        return _render(request, status=400, errors=["That API key does not look valid."])
    provider.set_api_key(key)
    provider.last_ok, provider.last_error = None, ""
    provider.save(update_fields=["api_key_enc", "key_hint", "last_ok", "last_error"])
    return _render(request, result={"ok": True, "text": f"Key updated for {provider.name}."})
