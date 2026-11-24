"""
LLM deployment views for WebOps.

"Django App Structure" section
Handles LLM model deployment UI and management.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.utils import sanitize_deployment_name
from apps.core.integrations.services import HuggingFaceIntegrationService
from ..models import BaseDeployment, ApplicationDeployment, DeploymentLog, LLMDeployment


@login_required
def llm_create(request):
    """
    Create new LLM deployment.
    """
    # Check if user has Hugging Face connection
    hf_service = HuggingFaceIntegrationService()
    hf_connection = hf_service.get_connection(request.user)

    from apps.services.runtime import portable_runtime
    from ..services.llm_preflight import hardware, SUPPORTED, check_model
    from ..services.llm_cpu import queue_llm
    portable = portable_runtime() is not None
    if portable and request.method == "POST":
        name=request.POST.get("name","").strip()
        model=request.POST.get("model_name","").strip()
        check=check_model(model,"transformers","auto","")
        context={"portable":True,"hardware":hardware(),"supported_models":SUPPORTED,"preflight":check,"form_name":name,"form_model":model}
        if not check["success"]:
            return render(request,"deployments/llm_create.html",context,status=400)
        try:
            name=sanitize_deployment_name(name)
            if not name or BaseDeployment.objects.filter(name=name).exists():
                raise ValueError("Choose a unique deployment name.")
            d=LLMDeployment.objects.create(name=name,model_name=model,deployed_by=request.user,backend="transformers",dtype="auto")
        except (ValueError,TypeError) as exc:
            context["form_error"]=str(exc)
            return render(request,"deployments/llm_create.html",context,status=400)
        ok,message=queue_llm(d)
        (messages.success if ok else messages.error)(request,message)
        return redirect("deployments:llm_detail",pk=d.pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        model_name = request.POST.get('model_name', '').strip()
        tensor_parallel_size = int(request.POST.get('tensor_parallel_size', 1))
        gpu_memory_utilization = float(request.POST.get('gpu_memory_utilization', 0.9))
        max_model_len = request.POST.get('max_model_len', '').strip()
        quantization = request.POST.get('quantization', '')
        dtype = request.POST.get('dtype', 'auto')

        # Validation
        if not name:
            messages.error(request, "Deployment name is required.")
            return redirect('deployments:llm_create')

        if not model_name:
            messages.error(request, "Model name is required.")
            return redirect('deployments:llm_create')

        # Sanitize name
        try:
            sanitized_name = sanitize_deployment_name(name)
        except ValueError as e:
            messages.error(request, f"Invalid deployment name: {e}")
            return redirect('deployments:llm_create')

        # Check if name already exists
        if LLMDeployment.objects.filter(name=sanitized_name).exists():
            messages.error(request, f"Deployment '{sanitized_name}' already exists.")
            return redirect('deployments:llm_create')

        # Basic model name validation (detailed validation happens in LLMDeploymentService)
        import re
        if not re.match(r'^[a-zA-Z0-9\-_./]+$', model_name):
            messages.error(
                request,
                "Invalid model name. Use only letters, numbers, hyphens, underscores, dots, and slashes."
            )
            return redirect('deployments:llm_create')

        # Create LLM deployment
        try:
            from ..tasks.llm import deploy_llm_model

            deployment = LLMDeployment.objects.create(
                name=sanitized_name,
                model_name=model_name,
                tensor_parallel_size=tensor_parallel_size,
                gpu_memory_utilization=gpu_memory_utilization,
                max_model_len=int(max_model_len) if max_model_len else None,
                quantization=quantization if quantization else '',
                dtype=dtype,
                deployed_by=request.user,
            )

            # Ensure Celery worker is running (non-interactive)
            from ..shared.service_manager import ServiceManager
            ServiceManager().ensure_celery_running()

            # Queue LLM deployment task
            ok,message=queue_llm(deployment)
            if not ok:
                messages.error(request,message)
                return redirect("deployments:llm_detail",pk=deployment.pk)

            messages.success(
                request,
                f"LLM deployment '{sanitized_name}' created and queued successfully."
            )
            # Redirect directly to the dedicated LLM detail view
            return redirect('deployments:llm_detail', pk=deployment.id)

        except Exception as e:
            messages.error(request, f"Failed to create LLM deployment: {str(e)}")
            return redirect('deployments:llm_create')

    # GET request - show form
    context = {
        'portable': portable, 'hardware':hardware() if portable else None,'supported_models':SUPPORTED,
        'has_hf_connection': hf_connection is not None,
        'hf_username': hf_connection.username if hf_connection else None,
    }

    return render(request, 'deployments/llm_create.html', context)


@login_required
def llm_list(request):
    """
    List all LLM deployments.
    """
    llm_deployments = LLMDeployment.objects.filter(deployed_by=request.user, is_deleted=False).order_by('-created_at')

    # Calculate stats
    total = llm_deployments.count()
    running = llm_deployments.filter(status='running').count()
    building = llm_deployments.filter(status='building').count()
    failed = llm_deployments.filter(status='failed').count()

    context = {
        'llm_deployments': llm_deployments,
        'total': total,
        'running': running,
        'building': building,
        'failed': failed,
    }

    return render(request, 'deployments/llm_list.html', context)


@login_required
def llm_detail(request, pk):
    """
    LLM deployment detail view.
    """
    deployment = get_object_or_404(LLMDeployment, pk=pk, deployed_by=request.user, is_deleted=False)

    logs = deployment.logs.all()[:100]  # Last 100 logs

    # Get service status
    from ..shared.service_manager import ServiceManager
    service_manager = ServiceManager()
    service_status = service_manager.get_service_status(deployment)

    # Build API endpoint URL
    api_endpoint = None
    if deployment.status == 'running' and deployment.port:
        api_endpoint = f"http://localhost:{deployment.port}/v1"

    # Public gateway details for reviewed CPU models, built from the request so they are correct for
    # whatever host and scheme the panel is served on (never a hard-coded localhost).
    portable = __import__('apps.services.runtime', fromlist=['portable_runtime']).portable_runtime() is not None
    public_api = None
    if portable and deployment.status == 'running' and deployment.port:
        from django.urls import reverse
        from django.utils import timezone
        from apps.api.models import LLMAccessKey
        from ..services.llm_preflight import SUPPORTED
        if deployment.model_name in SUPPORTED:
            public_api = {
                'completions_url': request.build_absolute_uri(reverse('llm_public_completions')),
                'models_url': request.build_absolute_uri(reverse('llm_public_models')),
                'model_id': deployment.name,
                'keys_url': reverse('llm_keys'),
                'active_keys': LLMAccessKey.objects.filter(
                    user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()).count(),
            }

    context = {
        'public_api': public_api,
        'deployment': deployment,
        'logs': logs, 'latest_error':deployment.logs.filter(level='error').order_by('-created_at').first() if deployment.status=='failed' else None,
        'service_status': service_status,
        'api_endpoint': api_endpoint, 'portable': portable,
    }

    return render(request, 'deployments/llm_detail.html', context)


@login_required
@require_http_methods(["POST"])
def llm_test_endpoint(request, pk):
    """
    Test LLM endpoint with a simple prompt (AJAX).
    """
    import requests
    from django.http import JsonResponse

    deployment = get_object_or_404(LLMDeployment, pk=pk, deployed_by=request.user, is_deleted=False)

    if deployment.status != 'running':
        return JsonResponse({
            'success': False,
            'error': 'Deployment is not running'
        }, status=400)

    import json
    try:
        data=json.loads(request.body or b"{}")
        prompt=data.get("prompt","Hello, how are you?")
        tokens=int(data.get("max_tokens",32))
        temp=float(data.get("temperature",0.7))
        if not isinstance(prompt,str) or not 1 <= len(prompt) <= 4096 or not 1 <= tokens <= 128 or not 0 <= temp <= 2:
            raise ValueError()
    except (ValueError,TypeError,AttributeError):
        return JsonResponse({"success":False,"error":"Prompt must be 1–4096 characters; max tokens 1–128; temperature 0–2."},status=400)
    try:
        response=requests.post(f"http://127.0.0.1:{int(deployment.port)}/v1/completions",json={"model":deployment.model_name,"prompt":prompt,"max_tokens":tokens,"temperature":temp},timeout=60,allow_redirects=False)
        if response.status_code != 200:
            return JsonResponse({"success":False,"error":"Model busy or inference unavailable. Check status and retry."},status=response.status_code if response.status_code in (429,503) else 502)
        result=response.json()
        text=result["choices"][0]["text"]
        return JsonResponse({"success":True,"response":text,"choices":[{"text":text}],"model":deployment.model_name})
    except (requests.RequestException,ValueError,KeyError,IndexError,TypeError):
        return JsonResponse({"success":False,"error":"Model did not return a valid response. Check its runtime status and retry."},status=503)


@login_required
@require_http_methods(["POST"])
def llm_detect_model(request):
    """
    Auto-detect LLM model configuration (AJAX endpoint).
    Provides Railway-style detection preview.
    """
    model_name = request.POST.get('model_name', '').strip()

    if not model_name:
        return JsonResponse({
            'success': False,
            'error': 'Model name is required'
        }, status=400)

    from apps.services.runtime import portable_runtime
    if portable_runtime():
        from ..services.llm_preflight import check_model
        return JsonResponse(check_model(model_name))
    try:
        from ..shared.llm_detection import detect_model

        # Get Hugging Face token if available
        hf_service = HuggingFaceIntegrationService()
        hf_token = hf_service.get_access_token(request.user)

        # Run detection
        result = detect_model(
            model_name=model_name,
            hf_token=hf_token,
            available_gpu=False,  # Could be made dynamic
            available_vram_gb=0.0
        )

        if not result.detected:
            return JsonResponse({
                'success': False,
                'error': result.error_message or 'Failed to detect model'
            }, status=400)

        # Build response
        response_data = {
            'success': True,
            'model_info': {
                'name': model_name,
                'type': result.model_type,
                'architecture': result.architecture,
                'task_type': result.task_type,
                'parameter_count': result.parameter_count,
                'parameter_count_display': f"{result.parameter_count:,}" if result.parameter_count else "Unknown",
                'parameters_billions': f"{result.parameter_count / 1e9:.2f}B" if result.parameter_count else "Unknown",
                'model_size_gb': result.model_size_gb,
                'context_length': result.context_length,
                'author': result.author,
                'license': result.license,
                'downloads': result.downloads,
                'likes': result.likes,
                'tags': result.tags,
            },
            'recommended_config': {
                'backend': result.recommended_backend,
                'backend_confidence': int(result.backend_confidence * 100),
                'backend_reasoning': result.backend_reasoning,
                'dtype': result.suggested_dtype,
                'quantization': result.suggested_quantization or 'None',
                'max_model_len': result.suggested_max_model_len,
                'estimated_memory_gb': result.estimated_memory_gb,
                'requires_gpu': result.requires_gpu,
                'min_vram_gb': result.min_vram_gb,
                'min_ram_gb': result.min_ram_gb,
            },
            'confidence': int(result.confidence * 100),
            'warnings': result.warnings,
            'info_messages': result.info_messages,
        }

        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Detection failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def llm_search_models(request):
    """
    Search Hugging Face models (AJAX endpoint).
    """
    import requests
    from apps.api.rate_limiting import RateLimiter
    from ..services.llm_catalog import discover
    query = request.GET.get("q", "").strip()
    if len(query)>100 or (query and len(query)<2):
        return JsonResponse({"error":"Enter 2–100 characters to search."},status=400)
    allowed,_=RateLimiter(max_requests=60,window_seconds=3600,burst_requests=10,namespace="hf-model-discovery").is_allowed(str(request.user.pk))
    if not allowed:
        return JsonResponse({"error":"Model search rate limit reached. Try again later."},status=429)
    try:
        return JsonResponse(discover(query))
    except (requests.RequestException,RuntimeError,ValueError,TypeError,AttributeError):
        return JsonResponse({"error":"Hugging Face model catalog is temporarily unavailable. Retry or enter a model ID manually."},status=503)


@login_required
def llm_playground(request, pk):
    """
    Interactive playground for testing LLM models.
    """
    deployment = get_object_or_404(LLMDeployment, pk=pk, deployed_by=request.user, is_deleted=False)

    from apps.services.runtime import portable_runtime
    if portable_runtime():
        return redirect("deployments:llm_detail",pk=pk)

    context = {
        'deployment': deployment,
        'api_endpoint': f"http://localhost:{deployment.port}/v1" if deployment.port else None,
    }

    return render(request, 'deployments/llm_playground.html', context)


@login_required
@require_http_methods(["POST"])
def llm_update_backend(request, pk):
    """
    Update the LLM backend for a pending or failed deployment.
    """
    deployment = get_object_or_404(LLMDeployment, pk=pk, deployed_by=request.user, is_deleted=False)

    from apps.services.runtime import portable_runtime
    if portable_runtime():
        messages.error(request,"Only the reviewed CPU Transformers backend is supported on this host.")
        return redirect("deployments:llm_detail",pk=pk)
    # Only allow backend changes for pending or failed deployments
    if deployment.status not in ['pending', 'failed']:
        messages.error(request, 'Cannot change backend for a running or building deployment.')
        return redirect('deployments:llm_detail', pk=pk)

    backend = request.POST.get('backend', '').strip()

    # Validate backend choice
    valid_backends = [choice[0] for choice in LLMDeployment.Backend.choices]
    if backend not in valid_backends:
        messages.error(request, f'Invalid backend choice: {backend}')
        return redirect('deployments:llm_detail', pk=pk)

    # Update backend
    old_backend = deployment.backend
    deployment.backend = backend
    deployment.status = 'pending'  # Reset to pending
    deployment.save(update_fields=['backend', 'status'])

    # Log the change
    from ..models import DeploymentLog
    DeploymentLog.objects.create(
        deployment=deployment,
        level=DeploymentLog.Level.INFO,
        message=f'Backend changed from {old_backend} to {backend}'
    )

    messages.success(request, f'Backend updated to {deployment.get_backend_display()}. Click "Start Deployment" to begin.')
    return redirect('deployments:llm_detail', pk=pk)
