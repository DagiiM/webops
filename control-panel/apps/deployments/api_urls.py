"""API URL configuration for Deployments app."""

from django.urls import path
from . import api_views

app_name = 'deployments_api'

urlpatterns = [
    # Status
    path('status/', api_views.api_status, name='api_status'),

    # Deployments
    path('deployments/', api_views.list_deployments, name='list_deployments'),
    path('deployments/create/', api_views.create_deployment, name='create_deployment'),
    path('deployments/<str:name>/', api_views.get_deployment, name='get_deployment'),
    path('deployments/<str:name>/logs/', api_views.get_deployment_logs, name='get_deployment_logs'),
    path('deployments/<str:name>/start/', api_views.start_deployment_api, name='start_deployment'),
    path('deployments/<str:name>/stop/', api_views.stop_deployment_api, name='stop_deployment'),
    path('deployments/<str:name>/restart/', api_views.restart_deployment_api, name='restart_deployment'),
    path('deployments/<str:name>/delete/', api_views.delete_deployment_api, name='delete_deployment'),

    # Environment Variables
    path('deployments/<str:name>/env/', api_views.get_env_vars_api, name='get_env_vars'),
    path('deployments/<str:name>/env/generate/', api_views.generate_env_api, name='generate_env'),
    path('deployments/<str:name>/env/validate/', api_views.validate_env_api, name='validate_env'),
    path('deployments/<str:name>/env/set/', api_views.set_env_var_api, name='set_env_var'),
    path('deployments/<str:name>/env/unset/', api_views.unset_env_var_api, name='unset_env_var'),
]
