"""
LLM deployment views for WebOps.

Reference: CLAUDE.md "Django App Structure" section
Handles LLM model deployment UI and management.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.utils import sanitize_deployment_name
from apps.core.integration_services import HuggingFaceIntegrationService
from .models import Deployment, DeploymentLog


@login_required
def llm_create(request):
    """
    Create new LLM deployment.
    """
    # Check if user has Hugging Face connection
    hf_service = HuggingFaceIntegrationService()
    hf_connection = hf_service.get_connection(request.user)

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
        if Deployment.objects.filter(name=sanitized_name).exists():
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
            from .tasks import deploy_llm_model

            deployment = Deployment.objects.create(
                name=sanitized_name,
                project_type=Deployment.ProjectType.LLM,
                model_name=model_name,
                tensor_parallel_size=tensor_parallel_size,
                gpu_memory_utilization=gpu_memory_utilization,
                max_model_len=int(max_model_len) if max_model_len else None,
                quantization=quantization if quantization else '',
                dtype=dtype,
                deployed_by=request.user,
                repo_url='',  # Not needed for LLM deployments
            )

            # Ensure Celery worker is running (non-interactive)
            from .service_manager import ServiceManager
            ServiceManager().ensure_celery_running()

            # Queue LLM deployment task
            deploy_llm_model.delay(deployment.id)

            messages.success(
                request,
                f"LLM deployment '{sanitized_name}' created and queued successfully."
            )
            return redirect('deployments:deployment_detail', pk=deployment.id)

        except Exception as e:
            messages.error(request, f"Failed to create LLM deployment: {str(e)}")
            return redirect('deployments:llm_create')

    # GET request - show form
    context = {
        'has_hf_connection': hf_connection is not None,
        'hf_username': hf_connection.username if hf_connection else None,
    }

    return render(request, 'deployments/llm_create.html', context)


@login_required
def llm_list(request):
    """
    List all LLM deployments.
    """
    llm_deployments = Deployment.objects.filter(
        project_type=Deployment.ProjectType.LLM
    ).order_by('-created_at')

    # Calculate stats
    total = llm_deployments.count()
    running = llm_deployments.filter(status=Deployment.Status.RUNNING).count()
    building = llm_deployments.filter(status=Deployment.Status.BUILDING).count()
    failed = llm_deployments.filter(status=Deployment.Status.FAILED).count()

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
    deployment = get_object_or_404(
        Deployment,
        pk=pk,
        project_type=Deployment.ProjectType.LLM
    )

    logs = deployment.logs.all()[:100]  # Last 100 logs

    # Get service status
    from .service_manager import ServiceManager
    service_manager = ServiceManager()
    service_status = service_manager.get_service_status(deployment)

    # Build API endpoint URL
    api_endpoint = None
    if deployment.status == Deployment.Status.RUNNING and deployment.port:
        api_endpoint = f"http://localhost:{deployment.port}/v1"

    context = {
        'deployment': deployment,
        'logs': logs,
        'service_status': service_status,
        'api_endpoint': api_endpoint,
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

    deployment = get_object_or_404(
        Deployment,
        pk=pk,
        project_type=Deployment.ProjectType.LLM
    )

    if deployment.status != Deployment.Status.RUNNING:
        return JsonResponse({
            'success': False,
            'error': 'Deployment is not running'
        }, status=400)

    try:
        # Send test request to vLLM
        test_prompt = "Hello, how are you?"
        api_url = f"http://localhost:{deployment.port}/v1/completions"

        response = requests.post(
            api_url,
            json={
                "model": deployment.model_name,
                "prompt": test_prompt,
                "max_tokens": 50,
                "temperature": 0.7
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            generated_text = result['choices'][0]['text']

            return JsonResponse({
                'success': True,
                'prompt': test_prompt,
                'response': generated_text,
                'model': deployment.model_name
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'API returned status {response.status_code}: {response.text}'
            }, status=response.status_code)

    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Request timeout - model may be loading or overloaded'
        }, status=504)
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'success': False,
            'error': 'Cannot connect to model server - check if service is running'
        }, status=503)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def llm_search_models(request):
    """
    Search Hugging Face models (AJAX endpoint).
    """
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({
            'models': []
        })

    # Popular LLM models to suggest
    popular_models = [
        {
            'id': 'meta-llama/Llama-2-7b-chat-hf',
            'name': 'Llama 2 7B Chat',
            'size': '7B',
            'description': 'Meta\'s Llama 2 7B chat model',
            'vram': '~14GB'
        },
        {
            'id': 'meta-llama/Llama-2-13b-chat-hf',
            'name': 'Llama 2 13B Chat',
            'size': '13B',
            'description': 'Meta\'s Llama 2 13B chat model',
            'vram': '~26GB'
        },
        {
            'id': 'mistralai/Mistral-7B-Instruct-v0.2',
            'name': 'Mistral 7B Instruct',
            'size': '7B',
            'description': 'Mistral AI\'s 7B instruction-tuned model',
            'vram': '~14GB'
        },
        {
            'id': 'microsoft/phi-2',
            'name': 'Phi-2',
            'size': '2.7B',
            'description': 'Microsoft\'s small but powerful model',
            'vram': '~6GB'
        },
        {
            'id': 'TheBloke/Llama-2-7B-Chat-AWQ',
            'name': 'Llama 2 7B Chat (AWQ)',
            'size': '7B',
            'description': 'Quantized version - reduced VRAM usage',
            'vram': '~7GB'
        },
        {
            'id': 'gpt2',
            'name': 'GPT-2',
            'size': '124M',
            'description': 'OpenAI GPT-2 (good for testing)',
            'vram': '~1GB'
        },
    ]

    # Filter based on query
    query_lower = query.lower()
    filtered_models = [
        m for m in popular_models
        if query_lower in m['id'].lower() or query_lower in m['name'].lower()
    ]

    return JsonResponse({
        'models': filtered_models,
        'query': query
    })


@login_required
def llm_playground(request, pk):
    """
    Interactive playground for testing LLM models.
    """
    deployment = get_object_or_404(
        Deployment,
        pk=pk,
        project_type=Deployment.ProjectType.LLM
    )

    context = {
        'deployment': deployment,
        'api_endpoint': f"http://localhost:{deployment.port}/v1" if deployment.port else None,
    }

    return render(request, 'deployments/llm_playground.html', context)
