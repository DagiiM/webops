"""Shortcut command and WebOps API invocation contracts."""

from unittest.mock import MagicMock
from click.testing import CliRunner
import click
import pytest
from webops_cli import command_shortcuts as m
from webops_cli.errors import WebOpsError


@pytest.fixture
def shortcuts(monkeypatch):
    monkeypatch.setattr(m, "console", MagicMock())
    monkeypatch.setattr(m, "display_deployment_table", MagicMock())
    client = MagicMock()
    client.get_deployment.return_value = {
        "status": "running",
        "health": "healthy",
        "domain": "example.org",
    }
    client.list_deployments.return_value = {
        "deployments": [{"name": "app", "status": "running"}]
    }
    client.get_deployment_logs.return_value = {
        "logs": "INFO startup\nERROR fail\nINFO ok"
    }
    client.get_env_vars.return_value = {"TOKEN": "private-key", "DEBUG": "true"}
    client.get_status.return_value = {"cpu_usage": 12, "memory_usage": 25}
    return m.CommandShortcuts(client, MagicMock())


@pytest.mark.parametrize(
    "auto_start,domain", [(True, None), (False, None), (True, "app.example.org")]
)
def test_shortcut_creation_uses_api_schema_and_explicit_start(
    shortcuts, auto_start, domain
):
    shortcuts.quick_deploy(
        "app",
        "https://github.com/owner/repo.git",
        branch="develop",
        domain=domain,
        auto_start=auto_start,
    )
    shortcuts.api_client.create_deployment.assert_called_once_with(
        name="app",
        repo_url="https://github.com/owner/repo.git",
        branch="develop",
        domain=domain or "",
    )
    assert shortcuts.api_client.start_deployment.called is auto_start


@pytest.mark.parametrize(
    "operation", ["quick_restart", "quick_stop", "quick_status", "quick_deploy"]
)
def test_shortcut_api_failure_is_visible_not_raised(shortcuts, operation):
    for name in (
        "restart_deployment",
        "stop_deployment",
        "get_deployment",
        "create_deployment",
    ):
        getattr(shortcuts.api_client, name).side_effect = WebOpsError("not authorized")
    if operation == "quick_deploy":
        getattr(shortcuts, operation)("app", "https://github.com/o/p.git")
    else:
        getattr(shortcuts, operation)("app")
    assert m.console.print.called


@pytest.mark.parametrize("operation", ["quick_restart", "quick_stop"])
def test_shortcut_lifecycle_dispatches_expected_api_method(shortcuts, operation):
    getattr(shortcuts, operation)("app")
    getattr(
        shortcuts.api_client, operation.replace("quick_", "") + "_deployment"
    ).assert_called_once_with("app")


@pytest.mark.parametrize("kind", ["all", "one"])
def test_shortcut_status_shows_deployment_records_not_dict_keys(shortcuts, kind):
    shortcuts.quick_status("app" if kind == "one" else None)
    if kind == "all":
        m.display_deployment_table.assert_called_once_with(
            [{"name": "app", "status": "running"}]
        )
    else:
        shortcuts.api_client.get_deployment.assert_called_once_with("app")


@pytest.mark.parametrize(
    "logs",
    [
        {"logs": "one\n\nthree"},
        {"logs": "\n".join(f"line {n}" for n in range(125))},
        {},
        None,
    ],
)
def test_shortcut_log_display_ignores_blank_and_missing_logs(shortcuts, logs):
    shortcuts.api_client.get_deployment_logs.return_value = logs
    shortcuts.quick_logs("app", lines=2)
    assert m.console.print.called


def test_shortcut_log_missing_client_fails_closed(shortcuts):
    shortcuts.api_client = None
    shortcuts.quick_logs("app")
    shortcuts.quick_env_get("app", "TOKEN")
    shortcuts.quick_env_set("app", "TOKEN", "redacted")
    shortcuts.quick_health_check()


@pytest.mark.parametrize("mode", ["all", "found", "missing", "empty", "error"])
def test_shortcut_environment_get_and_missing_key(shortcuts, mode):
    if mode == "empty":
        shortcuts.api_client.get_env_vars.return_value = {}
    if mode == "error":
        shortcuts.api_client.get_env_vars.side_effect = WebOpsError("offline")
    key = "TOKEN" if mode == "found" else "UNKNOWN" if mode == "missing" else None
    shortcuts.quick_env_get("app", key)
    assert m.console.print.called


@pytest.mark.parametrize("error", [True, False])
def test_environment_set_errors_and_success(shortcuts, error):
    if error:
        shortcuts.api_client.set_env_var.side_effect = WebOpsError("forbidden")
    shortcuts.quick_env_set("app", "DEBUG", "true")
    shortcuts.api_client.set_env_var.assert_called_once_with("app", "DEBUG", "true")


@pytest.mark.parametrize("status,high_load", [("running", False), ("stopped", True)])
def test_health_check_uses_api_returned_deployments(shortcuts, status, high_load):
    shortcuts.api_client.list_deployments.return_value = {
        "deployments": [{"name": "web", "status": status}]
    }
    shortcuts.api_client.get_status.return_value = {
        "cpu_usage": 91 if high_load else 10,
        "memory_usage": 95 if high_load else 20,
    }
    shortcuts.quick_health_check()
    assert m.console.print.called


def test_health_check_bounded_on_backend_failure(shortcuts):
    shortcuts.api_client.get_status.side_effect = WebOpsError("unreachable")
    shortcuts.quick_health_check()
    assert m.console.print.called


def test_shortcuts_help_renders_all_supported_aliases(shortcuts):
    shortcuts.list_shortcuts()
    assert m.console.print.call_count > 10


@pytest.mark.parametrize(
    "argv,called",
    [
        (["quick-deploy", "app", "https://github.com/o/p.git"], "quick_deploy"),
        (["quick-restart", "app"], "quick_restart"),
        (["quick-stop", "app"], "quick_stop"),
        (["quick-status", "app"], "quick_status"),
        (["quick-logs", "app", "--lines", "12"], "quick_logs"),
        (["quick-env-set", "app", "DEBUG", "true"], "quick_env_set"),
        (["quick-env-get", "app", "DEBUG"], "quick_env_get"),
        (["health-check"], "quick_health_check"),
        (["shortcuts"], "list_shortcuts"),
    ],
)
def test_click_shortcut_command_wrappers_preserve_intent(monkeypatch, argv, called):
    from webops_cli import cli

    api = MagicMock()
    monkeypatch.setattr(cli, "get_api_client", lambda: api)
    monkeypatch.setattr(m, "Config", lambda: MagicMock())
    method = MagicMock()
    monkeypatch.setattr(m.CommandShortcuts, called, method)
    group = click.Group()
    m.create_shortcut_commands(group)
    result = CliRunner().invoke(group, argv)
    assert result.exit_code == 0, result.output
    method.assert_called_once()
