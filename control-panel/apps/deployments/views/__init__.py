"""
Deployment views module.

Exports all view functions.
"""

from .application_deployment import (
    deployment_list,
    deployment_detail,
    deployment_create,
    dashboard,
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
)

from .llm import (
    llm_create,
    llm_list,
    llm_detail,
    llm_test_endpoint,
    llm_search_models,
    llm_playground,
    llm_update_backend,
)

__all__ = [
    # Legacy/Application views
    'deployment_list',
    'deployment_detail',
    'deployment_create',
    'dashboard',
    'deployment_start',
    'deployment_stop',
    'deployment_restart',
    'deployment_delete',
    'deployment_env_update',
    'deployment_validate',
    'deployment_env_wizard',
    'deployment_env_manage',
    'deployment_files',
    'deployment_editor',
    'deployment_health_check',
    'deployment_health_history',
    'deployment_monitoring',
    'github_repo_branches',
    # Core service management
    'restart_core_service',
    'get_core_services_status_detailed',
    'enable_service_health_monitoring',
    'disable_service_health_monitoring',
    'set_service_auto_restart',
    'get_service_health_history',
    # LLM views
    'llm_create',
    'llm_list',
    'llm_detail',
    'llm_test_endpoint',
    'llm_search_models',
    'llm_playground',
    'llm_update_backend',
]
