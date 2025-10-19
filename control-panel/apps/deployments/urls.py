"""URL configuration for Deployments app."""

from django.urls import path, include
from . import views, llm_views

urlpatterns = [
    # Standard Deployments
    path('', views.deployment_list, name='deployment_list'),
    path('create/', views.deployment_create, name='deployment_create'),
    path('github/branches/', views.github_repo_branches, name='github_repo_branches'),
    path('<int:pk>/', views.deployment_detail, name='deployment_detail'),
    path('<int:pk>/start/', views.deployment_start, name='deployment_start'),
    path('<int:pk>/stop/', views.deployment_stop, name='deployment_stop'),
    path('<int:pk>/restart/', views.deployment_restart, name='deployment_restart'),
    path('<int:pk>/env/', views.deployment_env_manage, name='deployment_env_manage'),
    path('<int:pk>/env/update/', views.deployment_env_update, name='deployment_env_update'),
    path('<int:pk>/delete/', views.deployment_delete, name='deployment_delete'),
    path('<int:pk>/validate/', views.deployment_validate, name='deployment_validate'),
    path('<int:pk>/env-wizard/', views.deployment_env_wizard, name='deployment_env_wizard'),
    path('<int:pk>/files/', views.deployment_files, name='deployment_files'),
    path('<int:pk>/editor/', views.deployment_editor, name='deployment_editor'),
    path('<int:pk>/monitoring/', views.deployment_monitoring, name='deployment_monitoring'),
    path('<int:pk>/health-check/', views.deployment_health_check, name='deployment_health_check'),
    path('<int:pk>/health-history/', views.deployment_health_history, name='deployment_health_history'),

    # LLM Deployments
    path('llm/', llm_views.llm_list, name='llm_list'),
    path('llm/create/', llm_views.llm_create, name='llm_create'),
    path('llm/<int:pk>/', llm_views.llm_detail, name='llm_detail'),
    path('llm/<int:pk>/test/', llm_views.llm_test_endpoint, name='llm_test'),
    path('llm/<int:pk>/playground/', llm_views.llm_playground, name='llm_playground'),
    path('llm/search/', llm_views.llm_search_models, name='llm_search'),

    # Configuration Management

    # Celery Management (disabled in tests; URLConf not present)
]