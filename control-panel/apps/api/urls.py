"""URL configuration for API app."""

from django.urls import path
from . import views, token_views, doc_views

urlpatterns = [
    # API Documentation
    path('docs/', doc_views.api_documentation, name='api_docs'),
    path('docs/data/', doc_views.api_documentation_data, name='api_docs_data'),

    # Status
    path('status/', views.api_status, name='api_status'),

    # API Token Management (UI)
    path('tokens/', token_views.token_list, name='token_list'),
    path('tokens/create/', token_views.token_create, name='token_create'),
    path('tokens/<int:pk>/', token_views.token_detail, name='token_detail'),
    path('tokens/<int:pk>/toggle/', token_views.token_toggle, name='token_toggle'),
    path('tokens/<int:pk>/delete/', token_views.token_delete, name='token_delete'),

    # Deployments
    path('deployments/', views.deployment_list, name='api_deployment_list'),
    path('deployments/create/', views.deployment_create, name='api_deployment_create'),

    # File Editor (must come before <str:name> patterns)
    path('deployments/<int:deployment_id>/files/tree/', views.deployment_files_tree, name='api_deployment_files_tree'),
    path('deployments/<int:deployment_id>/files/read/', views.deployment_file_read, name='api_deployment_file_read'),
    path('deployments/<int:deployment_id>/files/write/', views.deployment_file_write, name='api_deployment_file_write'),

    # Deployment details by name (must come after specific paths)
    path('deployments/<str:name>/', views.deployment_detail, name='api_deployment_detail'),
    path('deployments/<str:name>/start/', views.deployment_start, name='api_deployment_start'),
    path('deployments/<str:name>/stop/', views.deployment_stop, name='api_deployment_stop'),
    path('deployments/<str:name>/restart/', views.deployment_restart, name='api_deployment_restart'),
    path('deployments/<str:name>/delete/', views.deployment_delete, name='api_deployment_delete'),
    path('deployments/<str:name>/logs/', views.deployment_logs, name='api_deployment_logs'),

    # Environment Variables (must come before database routes)
    path('deployments/<str:name>/env/', views.deployment_env_vars, name='api_deployment_env_vars'),
    path('deployments/<str:name>/env/generate/', views.deployment_env_generate, name='api_deployment_env_generate'),
    path('deployments/<str:name>/env/validate/', views.deployment_env_validate, name='api_deployment_env_validate'),
    path('deployments/<str:name>/env/set/', views.deployment_env_set, name='api_deployment_env_set'),
    path('deployments/<str:name>/env/unset/', views.deployment_env_unset, name='api_deployment_env_unset'),

    # Databases
    path('databases/', views.database_list, name='api_database_list'),
    path('databases/<str:name>/', views.database_detail, name='api_database_detail'),
]