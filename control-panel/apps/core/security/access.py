"""Authorization policy for user-owned resources and host-wide operations."""
from django.conf import settings
from django.http import HttpResponseForbidden
from django.urls import Resolver404, resolve

def requires_review(user):
    import os
    return not user.is_staff and getattr(settings, "WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL",
        getattr(settings, "WEBOPS_RUNTIME", os.getenv("WEBOPS_RUNTIME", "systemd")) == "supervisor")

def queue_deployment(deployment):
    from apps.services.runtime.policy import application_allowed, executable_block_reason, restricted, sandbox_ready
    if not application_allowed(deployment):
        raise ValueError(executable_block_reason())
    if restricted() and not sandbox_ready():
        raise ValueError("Restricted workload sandbox unavailable; contact an operator.")
    from apps.deployments.shared import ServiceManager
    from apps.services.background import get_background_processor
    ServiceManager().ensure_celery_running()
    return get_background_processor().submit("apps.deployments.tasks.application.deploy_application", deployment.pk)

# These operations change the host, not a user's own resources.
HOST_NAMES = {
    "restart_core_service", "enable_health_monitoring", "disable_health_monitoring", "set_service_auto_restart",
    "configuration_list", "configuration_update", "configuration_reset", "configuration_reset_all",
    "api_configuration", "background_management", "background_restart", "celery_status", "celery_restart_workers",
    "api_celery_status", "api_celery_inspect", "install_dependencies_ajax", "branding_settings", "reset_branding",
    "deployment_approve",
}
# These require an isolated worker or a trusted operator in a single-UID preview.
REVIEW_NAMES = {
    "llm_create", "llm_update_backend", "llm_detect", "llm_test", "llm_playground",
    "deployment_env_update", "deployment_env_wizard", "api_deployment_env_generate",
    "api_deployment_env_set", "api_deployment_env_unset", "api_deployment_file_write",
    "ssl_toggle", "ssl_upload_certificate", "ssl_update_configuration", "ssl_configure", "ssl_validate",
    "notification_test", "notification_toggle", "notification_create", "webhook_handler", "webhook_test",
    "workflow_execute", "retry_execution", "webhook_trigger",
    "database_check_dependencies", "check_dependencies",
}

def deny_for_user(request, user, match=None):
    if not user.is_authenticated or user.is_staff:
        return None
    match = match or getattr(request, "resolver_match", None)
    if match is None:
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
    name = match.url_name
    if name in HOST_NAMES or match.namespace == "compliance" or (match.namespace == "addons" and name not in ("addons_list","addon_detail")):
        return HttpResponseForbidden("This action manages shared host infrastructure. Operator access is required.")
    if requires_review(user):
        from apps.services.runtime import portable_runtime
        if portable_runtime() and name in ("llm_create","llm_detect","llm_test","llm_playground"):
            return None  # Reviewed CPU models only; views enforce preflight and ownership.
        # Code and environment edits can turn a previously reviewed process into arbitrary code.
        if name in REVIEW_NAMES and (request.method not in ("GET","HEAD") or name in ("llm_playground","llm_test","workflow_execute","retry_execution","webhook_trigger","check_dependencies","database_check_dependencies")):
            return HttpResponseForbidden("This operation requires a trusted operator or isolated execution worker.")
        if name == "deployment_env_manage" and request.method not in ("GET","HEAD"):
            return HttpResponseForbidden("Environment changes require operator review in the shared runtime.")
        if name == "deployment_files" and request.method not in ("GET","HEAD"):
            return HttpResponseForbidden("Executable file changes require operator review.")
    return None

class ResourceAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        return deny_for_user(request, request.user)
