"""Positive and failure-path coverage for every deployment wizard step.

All destructive operations, Git access and runtime delays are replaced by
controlled test doubles. This legacy wizard currently simulates deployment;
tests must not represent its success banner as live hosting evidence.
"""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from click.testing import CliRunner
import pytest
from webops_cli.wizards import deployment_wizard as deployment


@pytest.fixture
def wizard(monkeypatch):
    monkeypatch.setattr(deployment, "console", MagicMock())
    progress = MagicMock()
    progress.spinner.return_value = nullcontext()
    progress.progress_bar.return_value = nullcontext(MagicMock())
    monkeypatch.setattr(deployment, "progress_manager", progress)
    monkeypatch.setattr(deployment, "config", MagicMock())
    monkeypatch.setattr(deployment.time, "sleep", lambda _: None)
    monkeypatch.setattr(deployment.Prompt, "ask", MagicMock(return_value="value"))
    monkeypatch.setattr(deployment.IntPrompt, "ask", MagicMock(return_value=8000))
    monkeypatch.setattr(deployment.Confirm, "ask", MagicMock(return_value=False))
    instance = deployment.DeploymentWizard()
    instance.console = MagicMock()
    instance.deployment_config = {
        "name": "example", "source_type": "git",
        "repo_url": "https://github.com/team/repo.git",
        "branch": "main", "app_type": "python", "port": 8000,
        "cpu_limit": 1.0, "memory_limit": 512,
        "storage_size": 10, "env_vars": {"DEBUG": "false"},
    }
    return instance


@pytest.mark.parametrize("blocker", [
    "_check_api_config", "_step_application_source", "_step_application_config",
    "_step_environment_config", "_step_domain_config", "_step_resource_config",
    "_step_review_and_deploy", "_step_monitor_deployment", None,
])
def test_full_deployment_step_fail_fast(wizard, monkeypatch, blocker):
    seen = []
    names = ("_check_api_config", "_step_application_source",
             "_step_application_config", "_step_environment_config",
             "_step_domain_config", "_step_resource_config",
             "_step_review_and_deploy", "_step_monitor_deployment")
    for method in names:
        monkeypatch.setattr(wizard, method, lambda m=method:
                            seen.append(m) or m != blocker)
    monkeypatch.setattr(wizard, "_display_success", lambda: seen.append("success"))
    assert wizard.run() is (blocker is None)
    assert ("success" in seen) is (blocker is None)


@pytest.mark.parametrize("exception", [KeyboardInterrupt(), ValueError("bad project")])
def test_deployment_run_handles_user_cancel_and_exception(wizard, monkeypatch, exception):
    monkeypatch.setattr(wizard, "_check_api_config", MagicMock(side_effect=exception))
    errors = MagicMock()
    monkeypatch.setattr(deployment.error_handler, "display_error", errors)
    assert wizard.run() is False
    assert errors.called is isinstance(exception, ValueError)


@pytest.mark.parametrize("configured,have_url,have_token,client_error,expected", [
    (False, False, False, False, False),
    (True, False, True, False, False),
    (True, True, False, False, False),
    (True, True, True, False, True),
    (True, True, True, True, False),
])
def test_api_preflight_checks_real_configuration_and_constructor(
    wizard, monkeypatch, configured, have_url, have_token, client_error, expected
):
    deployment.config.is_configured.return_value = configured
    deployment.config.get_url.return_value = "https://panel.example" if have_url else ""
    deployment.config.get_token.return_value = "test-token" if have_token else ""
    connection = MagicMock(side_effect=ConnectionError("API refused")) if client_error else MagicMock()
    monkeypatch.setattr(deployment, "WebOpsAPIClient", connection)
    assert wizard._check_api_config() is expected
    if expected:
        assert wizard.api_client is not None


@pytest.mark.parametrize("source", ["git", "docker", "local"])
def test_source_selection_invokes_only_appropriate_adapter(wizard, monkeypatch, source):
    monkeypatch.setattr(deployment.Prompt, "ask", lambda *_a, **_k: source)
    for method in ("_configure_git_source", "_configure_docker_source", "_configure_local_source"):
        monkeypatch.setattr(wizard, method, MagicMock(return_value=True))
    assert wizard._step_application_source()
    selected = {
        "git": "_configure_git_source",
        "docker": "_configure_docker_source",
        "local": "_configure_local_source"
    }[source]
    getattr(wizard, selected).assert_called_once_with()
    assert wizard.deployment_config["source_type"] == source


@pytest.mark.parametrize("auth_method", ["ssh", "token", "username"])
def test_git_source_reprompts_invalid_and_collects_private_credentials(
    wizard, monkeypatch, auth_method
):
    answers = iter(["not-a-git-remote", "https://github.com/team/repo.git", "feature/test"])
    monkeypatch.setattr(deployment.Prompt, "ask", MagicMock(side_effect=lambda label, **kwargs:
                        auth_method if label == "Authentication method" else
                        "private-secret" if "token" in label.lower() or
                        "password" in label.lower() else
                        "gituser" if "username" in label.lower() else next(answers)))
    monkeypatch.setattr(wizard, "_check_git_access", lambda *_: True)
    monkeypatch.setattr(wizard, "_is_private_repo", lambda *_: True)
    monkeypatch.setattr(deployment.Confirm, "ask", lambda *_a, **_k: True)
    assert wizard._configure_git_source()
    assert wizard.deployment_config["branch"] == "feature/test"
    assert wizard.deployment_config["auth_method"] == auth_method
    if auth_method == "token":
        assert wizard.deployment_config["git_token"] == "private-secret"
    if auth_method == "username":
        assert wizard.deployment_config["git_username"] == "gituser"
        assert wizard.deployment_config["git_password"] == "private-secret"


@pytest.mark.parametrize("continue_anyway", [False, True])
def test_git_source_unreachable_remote_requires_approval(wizard, monkeypatch, continue_anyway):
    monkeypatch.setattr(deployment.Prompt, "ask", lambda label, **kw:
                        "main" if label == "Git branch" else
                        "https://github.com/team/repo.git")
    monkeypatch.setattr(wizard, "_check_git_access", lambda *_: False)
    monkeypatch.setattr(wizard, "_is_private_repo", lambda *_: False)
    monkeypatch.setattr(deployment.Confirm, "ask", lambda *_a, **_k: continue_anyway)
    assert wizard._configure_git_source() is continue_anyway


def test_public_git_repo_has_no_credentials(wizard, monkeypatch):
    monkeypatch.setattr(deployment.Prompt, "ask", lambda label, **kw:
                        "main" if label == "Git branch" else "https://github.com/team/repo.git")
    monkeypatch.setattr(wizard, "_check_git_access", lambda *_: True)
    monkeypatch.setattr(wizard, "_is_private_repo", lambda *_: False)
    assert wizard._configure_git_source()
    assert "git_password" not in wizard.deployment_config


@pytest.mark.parametrize("private,authorize", [
    (False, False), (True, False), (True, True),
])
def test_docker_source_invalid_then_valid_and_registry_auth(
    wizard, monkeypatch, private, authorize
):
    def ask(prompt, **kwargs):
        if prompt.startswith("Docker image"):
            ask.count += 1
            return "$bad-image" if ask.count == 1 else "team/repo:v1"
        return "registry-password" if "password" in prompt.lower() else "registry-user"
    ask.count = 0
    monkeypatch.setattr(deployment.Prompt, "ask", ask)
    monkeypatch.setattr(wizard, "_is_private_registry", lambda *_: private)
    monkeypatch.setattr(deployment.Confirm, "ask", lambda *_a, **_k: authorize)
    assert wizard._configure_docker_source()
    assert wizard.deployment_config["docker_image"] == "team/repo:v1"
    assert ("registry_password" in wizard.deployment_config) is (private and authorize)


def test_local_source_rejects_nonexistent_directory_then_accepts_existing(
    wizard, monkeypatch, tmp_path
):
    attempts = iter([str(tmp_path / "absent"), str(tmp_path)])
    monkeypatch.setattr(deployment.Prompt, "ask", lambda *_a, **_k: next(attempts))
    assert wizard._configure_local_source()
    assert wizard.deployment_config["local_path"] == str(tmp_path)


@pytest.mark.parametrize("detected,accept_detected,build", [
    (None, True, False),
    ("python", True, True),
    ("python", False, False),
    ("static", True, True),
])
def test_application_configuration_detection_and_build_commands(
    wizard, monkeypatch, detected, accept_detected, build
):
    names = iter(["BAD Name", "webapp"])
    def ask(label, **kwargs):
        if label == "Application name":
            return next(names)
        if label == "Application type":
            return "nodejs"
        return kwargs.get("default", "npm start")
    monkeypatch.setattr(deployment.Prompt, "ask", ask)
    monkeypatch.setattr(deployment.IntPrompt, "ask", lambda *_a, **kw: kw["default"])
    monkeypatch.setattr(wizard, "_detect_application_type", lambda: detected)
    def confirm(label, **kwargs):
        if label == "Is this correct?":
            return accept_detected
        return build
    monkeypatch.setattr(deployment.Confirm, "ask", confirm)
    assert wizard._step_application_config()
    kind = detected if (detected and accept_detected) else "nodejs"
    assert wizard.deployment_config["app_type"] == kind
    assert wizard.deployment_config["port"] == wizard._get_default_port(kind)
    if kind in {"nodejs", "python", "ruby"} and build:
        assert "build_command" in wizard.deployment_config


@pytest.mark.parametrize("add_common,add_custom", [(False, False), (True, False),
                                                    (True, True), (False, True)])
def test_environment_variables_required_and_secret_masking(wizard, monkeypatch,
                                                            add_common, add_custom):
    wizard.deployment_config["app_type"] = "python"
    custom = iter(["bad-name", "LONG_SECRET", ""])
    def ask(label, **kwargs):
        if label == "Variable name":
            return next(custom)
        return "this-is-a-private-value-longer-than-20-characters"
    monkeypatch.setattr(deployment.Prompt, "ask", ask)
    def confirm(label, **kwargs):
        if label.startswith("Set "):
            return add_common
        if label == "Add custom environment variables?":
            return add_custom
        return True
    monkeypatch.setattr(deployment.Confirm, "ask", confirm)
    assert wizard._step_environment_config()
    variables = wizard.deployment_config["env_vars"]
    assert ("PYTHONPATH" in variables) is add_common
    assert ("LONG_SECRET" in variables) is add_custom
    assert "bad-name" not in variables


@pytest.mark.parametrize("domain_enabled,ssl_enabled,method", [
    (False, False, ""),
    (True, False, ""),
    (True, True, "custom"),
    (True, True, "cloudflare"),
    (True, True, "letsencrypt"),
])
def test_domain_and_certificate_modes(wizard, monkeypatch, domain_enabled,
                                      ssl_enabled, method):
    attempts = iter(["invalid_domain", "app.example.org"])
    monkeypatch.setattr(deployment.Prompt, "ask", lambda label, **kwargs:
                        method if label == "SSL certificate method" else
                        "/private/cert.pem" if "certificate file" in label else
                        "/private/key.pem" if "private key" in label else next(attempts))
    monkeypatch.setattr(deployment.Confirm, "ask", lambda label, **kwargs:
                        domain_enabled if label == "Use a custom domain?" else ssl_enabled)
    assert wizard._step_domain_config()
    assert wizard.deployment_config["ssl_enabled"] is (ssl_enabled if domain_enabled else False)
    if domain_enabled:
        assert wizard.deployment_config["domain"] == "app.example.org"
    else:
        assert wizard.deployment_config["domain"] is None
    if method == "custom":
        assert wizard.deployment_config["ssl_cert_path"] == "/private/cert.pem"


@pytest.mark.parametrize("autoscale", [True, False])
def test_resource_config_capacity_and_scaling(wizard, monkeypatch, autoscale):
    monkeypatch.setattr(deployment.Prompt, "ask", lambda label, **kwargs:
                        {"CPU limit (cores)": "1.5", "Memory limit (MB)": "1536",
                         "Storage size (GB)": "30"}[label])
    monkeypatch.setattr(deployment.IntPrompt, "ask", lambda label, **kwargs: 2 if label.startswith("Minimum") else 4)
    monkeypatch.setattr(deployment.Confirm, "ask", lambda *_a, **_k: autoscale)
    assert wizard._step_resource_config()
    assert wizard.deployment_config["cpu_limit"] == 1.5
    assert wizard.deployment_config["memory_limit"] == 1536
    assert wizard.deployment_config["storage_size"] == 30
    assert wizard.deployment_config["auto_scaling"] is autoscale
    if autoscale:
        assert wizard.deployment_config["min_instances"] == 2
        assert wizard.deployment_config["max_instances"] == 4
    else:
        assert wizard.deployment_config["instances"] == 4


@pytest.mark.parametrize("approved,fails", [(False, False), (True, False), (True, True)])
def test_deployment_review_requires_approval_and_handles_progress_failure(
    wizard, monkeypatch, approved, fails
):
    monkeypatch.setattr(deployment.Confirm, "ask", lambda *_a, **_k: approved)
    progress = MagicMock()
    if fails:
        progress.update.side_effect = OSError("deployment unavailable")
    monkeypatch.setattr(deployment.progress_manager, "progress_bar",
                        lambda *_a, **_k: nullcontext(progress))
    error_handler = MagicMock()
    monkeypatch.setattr(deployment.error_handler, "display_error", error_handler)
    assert wizard._step_review_and_deploy() is (approved and not fails)
    assert ("deployment_id" in wizard.deployment_config) is (approved and not fails)


@pytest.mark.parametrize("ssl,domain", [(False, None), (True, "app.example.com")])
def test_monitor_summary_and_success_views(wizard, ssl, domain):
    wizard.deployment_config.update(domain=domain, ssl_enabled=ssl, deployment_id="dep-1")
    assert wizard._step_monitor_deployment()
    wizard._display_deployment_summary()
    wizard._display_success()
    assert wizard.console.print.call_count > 3


@pytest.mark.parametrize("source", ["docker", "local", "git"])
def test_summary_supports_all_sources(wizard, source):
    wizard.deployment_config.update(source_type=source, docker_image="team/app:v1")
    wizard._display_deployment_summary()


@pytest.mark.parametrize("kind,expected", [
    ("nodejs", 3000), ("python", 8000), ("php", 80), ("ruby", 3000),
    ("java", 8080), ("go", 8080), ("static", 80), ("docker", 80),
    ("unknown", 8000)
])
def test_default_port_contract(wizard, kind, expected):
    assert wizard._get_default_port(kind) == expected


@pytest.mark.parametrize("kind", ["nodejs", "python", "php", "ruby", "java",
                                  "go", "static", "docker", "unknown"])
def test_build_start_and_common_environment_defaults(wizard, kind):
    assert isinstance(wizard._get_default_build_command(kind), str)
    assert isinstance(wizard._get_default_start_command(kind), str)
    assert isinstance(wizard._get_common_env_vars(kind), dict)
    assert wizard._detect_application_type() is None


@pytest.mark.parametrize("name,valid", [
    ("webapp", True), ("dev-env", True), ("a" * 50, True),
    ("a" * 51, False), ("BAD", False), ("a/b", False), ("", False),
])
def test_application_name_validation(wizard, name, valid):
    assert wizard._validate_app_name(name) is valid


@pytest.mark.parametrize("url,valid", [
    ("https://github.com/owner/repo.git", True),
    ("git@github.com:owner/repo.git", True),
    ("https://gitlab.com/team/project.git", True),
    ("git@gitlab.com:team/project.git", True),
    ("https://bitbucket.org/team/repo.git", True),
    ("git@bitbucket.org:team/repo.git", True),
    ("http://github.com/owner/repo.git", False),
    ("https://evil.example.com/a/b.git", False), ("bad", False),
])
def test_git_url_rules(wizard, url, valid):
    assert wizard._validate_git_url(url) is valid


@pytest.mark.parametrize("image,valid", [
    ("nginx", True), ("team/app:v1", True), ("registry/app_latest", True),
    ("NGINX", False), ("bad image", False), ("team//app", False),
])
def test_docker_image_validation(wizard, image, valid):
    assert wizard._validate_docker_image(image) is valid


@pytest.mark.parametrize("value,valid", [
    ("app.example.com", True), ("a.example.com", True),
    ("example.org", True), ("app_underscore.org", False),
    ("localhost", False), ("https://app.example.org", False),
])
def test_domain_validation(wizard, value, valid):
    assert wizard._validate_domain(value) is valid


@pytest.mark.parametrize("name,valid", [
    ("DEBUG", True), ("_INTERNAL", True), ("PORT_2", True),
    ("9PORT", False), ("lowercase", False), ("A-B", False),
])
def test_environment_variable_name_validation(wizard, name, valid):
    assert wizard._validate_env_var_name(name) is valid


@pytest.mark.parametrize("repo,private", [
    ("https://github.com/a/b", True), ("https://gitlab.com/a/b", True),
    ("https://bitbucket.org/a/b", True), ("https://example.org/a/b", False),
])
def test_private_source_heuristics(wizard, repo, private):
    assert wizard._is_private_repo(repo) is private


@pytest.mark.parametrize("image,private", [
    ("my-registry.example.com/app", True), ("team/app", True),
    ("docker.io/library/nginx", False), ("nginx", False),
])
def test_private_registry_heuristics(wizard, image, private):
    assert wizard._is_private_registry(image) is private


@pytest.mark.parametrize("code,throws,expected", [
    (0, False, True), (1, False, False), (1, True, False),
])
def test_git_remote_access_error_paths(wizard, monkeypatch, code, throws, expected):
    def run(args, **kwargs):
        assert args[:3] == ["git", "ls-remote", "--heads"]
        if throws:
            raise OSError("Git binary missing")
        return SimpleNamespace(returncode=code)
    monkeypatch.setattr(deployment.subprocess, "run", run)
    assert wizard._check_git_access("https://github.com/a/b.git", "main") is expected


@pytest.mark.parametrize("succeeded", [True, False])
def test_click_deployment_wizard_entrypoint(monkeypatch, succeeded):
    monkeypatch.setattr(deployment.DeploymentWizard, "run", lambda self: succeeded)
    result = CliRunner().invoke(deployment.deploy)
    assert result.exit_code == 0

