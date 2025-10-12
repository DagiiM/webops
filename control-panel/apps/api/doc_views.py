"""
API Documentation Views.

Provides dynamic API documentation with live examples.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .documentation import APIDocumentationGenerator


@require_http_methods(["GET"])
def api_documentation(request):
    """Render API documentation page."""
    return render(request, 'api/docs.html', {
        'page_title': 'API Documentation'
    })


@require_http_methods(["GET"])
def api_documentation_data(request) -> JsonResponse:
    """Return API documentation data as JSON."""
    generator = APIDocumentationGenerator()
    return JsonResponse(generator.to_dict())
