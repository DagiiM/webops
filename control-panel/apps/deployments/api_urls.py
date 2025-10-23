"""API URL configuration for Deployments app."""

from django.urls import path
from .api import (
    api_status,
    list_deployments,
    get_deployment,
    create_deployment,
    get_deployment_logs,
    start_deployment_api,
    stop_deployment_api,
    restart_deployment_api,
    delete_deployment_api,
    generate_env_api,
    validate_project_api,
    validate_env_api,
    get_env_vars_api,
    set_env_var_api,
    unset_env_var_api,
)

app_name = 'deployments_api'

urlpatterns = [
    # Status
    path('status/', api_status, name='api_status'),

    # Deployments
    path('deployments/', list_deployments, name='list_deployments'),
    path('deployments/create/', create_deployment, name='create_deployment'),
    path('deployments/<str:name>/', get_deployment, name='get_deployment'),
    path('deployments/<str:name>/logs/', get_deployment_logs, name='get_deployment_logs'),
    path('deployments/<str:name>/start/', start_deployment_api, name='start_deployment'),
    path('deployments/<str:name>/stop/', stop_deployment_api, name='stop_deployment'),
    path('deployments/<str:name>/restart/', restart_deployment_api, name='restart_deployment'),
    path('deployments/<str:name>/delete/', delete_deployment_api, name='delete_deployment'),

    # Project Validation
    path('deployments/<str:name>/project/validate/', validate_project_api, name='validate_project'),

    # Environment Variables
    path('deployments/<str:name>/env/', get_env_vars_api, name='get_env_vars'),
    path('deployments/<str:name>/env/generate/', generate_env_api, name='generate_env'),
    path('deployments/<str:name>/env/validate/', validate_env_api, name='validate_env'),
    path('deployments/<str:name>/env/set/', set_env_var_api, name='set_env_var'),
    path('deployments/<str:name>/env/unset/', unset_env_var_api, name='unset_env_var'),
]
