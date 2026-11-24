"""Operator pages for remote build workers: register, revoke, watch jobs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from ..models import BuildJob, WorkerNode
from ..services import worker_queue as wq


def _staff_only(request):
    return None if request.user.is_staff else HttpResponseForbidden("Operator access required.")


def _context(request, **extra):
    ctx = {"workers": WorkerNode.objects.all(), "jobs": BuildJob.objects.select_related("deployment", "worker")[:15],
           "panel_url": request.build_absolute_uri("/").rstrip("/"), "issued": "", "error": "", "name": ""}
    ctx.update(extra)
    return ctx


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def workers(request):
    denied = _staff_only(request)
    if denied:
        return denied
    if request.method == "GET":
        return render(request, "deployments/workers.html", _context(request))
    name = request.POST.get("name", "")
    try:
        node, token = wq.create_worker(name, request.user)
    except wq.WorkerError as exc:
        return render(request, "deployments/workers.html", _context(request, error=str(exc), name=name), status=400)
    response = render(request, "deployments/workers.html", _context(request, issued=token, name=node.name))
    response["Referrer-Policy"] = "same-origin"
    return response


@login_required
@require_POST
def worker_revoke(request, pk):
    denied = _staff_only(request)
    if denied:
        return denied
    node = get_object_or_404(WorkerNode, pk=pk, revoked_at__isnull=True)
    wq.revoke(node)
    messages.success(request, f"Worker {node.name} revoked. Its token no longer works.")
    return redirect("deployments:workers")


@login_required
@never_cache
def job_detail(request, pk):
    job = get_object_or_404(BuildJob.objects.select_related("deployment", "worker"), pk=pk)
    if not request.user.is_staff and job.deployment.deployed_by_id != request.user.pk:
        return HttpResponseForbidden("Not your job.")
    return render(request, "deployments/worker_job.html", {"job": job, "can_cancel": request.user.is_staff and job.status in BuildJob.ACTIVE})


@login_required
@require_POST
def job_cancel(request, pk):
    denied = _staff_only(request)
    if denied:
        return denied
    job = get_object_or_404(BuildJob, pk=pk)
    wq.cancel(job)
    messages.success(request, "Job cancelled. The request is back with the operator.")
    return redirect("deployments:job_detail", pk=job.pk)
