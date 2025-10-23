"""URL configuration for Deployments app."""

from django.urls import path, include
from .views import (
    # Legacy/Application views
    deployment_list,
    deployment_create,
    deployment_detail,
    deployment_start,
    deployment_stop,
    deployment_restart,
    deployment_delete,
    deployment_env_update,
    deployment_validate,
    deployment_env_wizard,
    deployment_env_manage,
    deployment_files,
    deployment_editor,
    deployment_health_check,
    deployment_health_history,
    deployment_monitoring,
    github_repo_branches,
    # Core service management
    restart_core_service,
    get_core_services_status_detailed,
    enable_service_health_monitoring,
    disable_service_health_monitoring,
    set_service_auto_restart,
    get_service_health_history,
    # LLM views
    llm_create,
    llm_list,
    llm_detail,
    llm_test_endpoint,
    llm_search_models,
    llm_playground,
)

urlpatterns = [
    # Standard Deployments
    path('', deployment_list, name='deployment_list'),
    path('create/', deployment_create, name='deployment_create'),
    path('github/branches/', github_repo_branches, name='github_repo_branches'),
    path('<int:pk>/', deployment_detail, name='deployment_detail'),
    path('<int:pk>/start/', deployment_start, name='deployment_start'),
    path('<int:pk>/stop/', deployment_stop, name='deployment_stop'),
    path('<int:pk>/restart/', deployment_restart, name='deployment_restart'),
    path('<int:pk>/env/', deployment_env_manage, name='deployment_env_manage'),
    path('<int:pk>/env/update/', deployment_env_update, name='deployment_env_update'),
    path('<int:pk>/delete/', deployment_delete, name='deployment_delete'),
    path('<int:pk>/validate/', deployment_validate, name='deployment_validate'),
    path('<int:pk>/env-wizard/', deployment_env_wizard, name='deployment_env_wizard'),
    path('<int:pk>/files/', deployment_files, name='deployment_files'),
    path('<int:pk>/editor/', deployment_editor, name='deployment_editor'),
    path('<int:pk>/monitoring/', deployment_monitoring, name='deployment_monitoring'),
    path('<int:pk>/health-check/', deployment_health_check, name='deployment_health_check'),
    path('<int:pk>/health-history/', deployment_health_history, name='deployment_health_history'),

    # Core Service Management
    path('core-services/status/', get_core_services_status_detailed, name='core_services_status_detailed'),
    path('core-services/restart/<str:service_name>/', restart_core_service, name='restart_core_service'),
    path('core-services/health-monitor/enable/', enable_service_health_monitoring, name='enable_health_monitoring'),
    path('core-services/health-monitor/disable/', disable_service_health_monitoring, name='disable_health_monitoring'),
    path('core-services/auto-restart/<str:service_name>/', set_service_auto_restart, name='set_service_auto_restart'),
    path('core-services/health-history/<str:service_name>/', get_service_health_history, name='get_service_health_history'),

    # LLM Deployments
    path('llm/', llm_list, name='llm_list'),
    path('llm/create/', llm_create, name='llm_create'),
    path('llm/<int:pk>/', llm_detail, name='llm_detail'),
    path('llm/<int:pk>/test/', llm_test_endpoint, name='llm_test'),
    path('llm/<int:pk>/playground/', llm_playground, name='llm_playground'),
    path('llm/search/', llm_search_models, name='llm_search'),
]