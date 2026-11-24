"""One-click managed databases: deploy, start/stop/restart, status and permanent removal."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from . import provisioner as pv
from .decorators import database_write_rate_limit
from .models import Database
from .views import _databases_visible_to

logger = logging.getLogger(__name__)
ACTIONS = {"start": pv.start, "stop": pv.stop, "restart": pv.restart}


def remove_row(db):
    """Permanently remove a managed database's record (its data is gone, so there is nothing to restore)."""
    db.required_addons.clear()
    Database.objects.filter(pk=db.pk)._raw_delete(Database.objects.db)


def _deploy_context(request, **extra):
    engines = pv.engine_info()
    ok, why = pv.can_deploy(request.user)
    ctx = {"engines": [{"key": k, **engines[k]} for k in pv.ENGINES], "can_deploy": ok, "limit_reason": why,
           "values": {}, "errors": []}
    ctx.update(extra)
    return ctx


@login_required
@database_write_rate_limit
@never_cache
@require_http_methods(["GET", "POST"])
def database_deploy(request):
    if request.method == "GET":
        return render(request, "databases/deploy.html", _deploy_context(request))

    engine = request.POST.get("engine", "")
    raw_name = request.POST.get("name", "").strip()
    values = {"engine": engine, "name": raw_name}
    errors = []
    if engine not in pv.ENGINES:
        errors.append("Choose a database type.")
    name = ""
    try:
        name = pv.slug(raw_name)
    except pv.ProvisionError as exc:
        errors.append(str(exc))
    if name and Database.objects.filter(name=name).exists():
        errors.append("A database with that name already exists. Choose another name.")
    ok, why = pv.can_deploy(request.user)
    if not ok:
        errors.append(why)
    if engine in pv.ENGINES and not pv.engine_info()[engine]["available"]:
        errors.append(pv.engine_info()[engine]["hint"])
    if errors:
        return render(request, "databases/deploy.html", _deploy_context(request, errors=errors, values=values), status=400)

    with transaction.atomic():
        db = Database.objects.create(name=name, db_type=engine, managed=True, created_by=request.user,
                                     port=None if engine == "sqlite" else pv.allocate_port())
    try:
        pv.provision(db)
    except pv.ProvisionError as exc:
        remove_row(db)
        return render(request, "databases/deploy.html", _deploy_context(request, errors=[str(exc)], values=values), status=502)
    except Exception:
        logger.exception("Managed database provisioning crashed for %s", name)
        remove_row(db)
        return render(request, "databases/deploy.html",
                      _deploy_context(request, errors=["The database could not be deployed. Check the server log."], values=values), status=500)
    logger.info("Managed database deployed", extra={"database_id": db.pk, "db_type": engine, "user_id": request.user.id})
    messages.success(request, f"{name} is running.")
    return redirect("database_detail", pk=db.pk)


@login_required
@database_write_rate_limit
@require_POST
@never_cache
def database_action(request, pk, action):
    db = get_object_or_404(_databases_visible_to(request.user), pk=pk, managed=True)
    if action == "check":
        ok, text = pv.check(db)
        (messages.success if ok else messages.error)(request, text)
        return redirect("database_detail", pk=db.pk)
    fn = ACTIONS.get(action)
    if fn is None:
        return JsonResponse({"error": "Unknown action"}, status=404)
    try:
        fn(db)
        messages.success(request, f"{db.name}: {action} done.")
    except pv.ProvisionError as exc:
        messages.error(request, f"{db.name}: {exc}")
    return redirect("database_detail", pk=db.pk)


@login_required
@never_cache
def database_status(request, pk):
    db = get_object_or_404(_databases_visible_to(request.user), pk=pk, managed=True)
    return JsonResponse({"status": pv.status(db)})
