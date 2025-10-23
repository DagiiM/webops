"""
URL configuration for automation app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # =========================================================================
    # WORKFLOW MANAGEMENT
    # =========================================================================
    path('', views.workflow_list, name='workflow_list'),
    path('create/', views.workflow_create, name='workflow_create'),
    path('<int:workflow_id>/builder/', views.workflow_builder, name='workflow_builder'),
    path('<int:workflow_id>/save/', views.workflow_save, name='workflow_save'),
    path('<int:workflow_id>/execute/', views.workflow_execute, name='workflow_execute'),
    path('<int:workflow_id>/delete/', views.workflow_delete, name='workflow_delete'),

    # =========================================================================
    # EXECUTION MONITORING
    # =========================================================================
    path('<int:workflow_id>/executions/', views.execution_list, name='execution_list'),
    path('execution/<int:execution_id>/', views.execution_detail, name='execution_detail'),
    path('execution/<int:execution_id>/retry/', views.retry_execution, name='retry_execution'),

    # =========================================================================
    # WEBHOOKS
    # =========================================================================
    path('webhook/<int:workflow_id>/', views.webhook_trigger, name='webhook_trigger'),

    # =========================================================================
    # TEMPLATES
    # =========================================================================
    path('templates/', views.template_list, name='template_list'),
    path('templates/<int:template_id>/preview/', views.template_preview, name='template_preview'),
    path('template/<int:template_id>/create/', views.workflow_create_from_template, name='workflow_create_from_template'),

    # =========================================================================
    # API ENDPOINTS
    # =========================================================================
    path('api/<int:workflow_id>/status/', views.api_workflow_status, name='api_workflow_status'),
    path('api/execution/<int:execution_id>/status/', views.api_execution_status, name='api_execution_status'),
    path('api/node-types/', views.api_node_types, name='api_node_types'),
]
