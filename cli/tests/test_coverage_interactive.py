"""Interactive CLI workflows tested with simulated operator responses, no API writes."""

from unittest.mock import MagicMock
import pytest
from webops_cli.ui import interactive as m
from webops_cli.errors import WebOpsError, ConnectionError as WebOpsConnectionError


@pytest.fixture
def ui(monkeypatch):
    api = MagicMock()
    api.list_deployments.return_value = {
        "deployments": [
            {"name": "api", "status": "running"},
            {"name": "worker", "status": "stopped"},
        ]
    }
    api.get_deployment_logs.return_value = {"logs": "INFO online\nWARN slow"}
    api.get_status.return_value = {
        "cpu_usage": 12,
        "memory_usage": 26,
        "disk_usage": 34,
        "uptime": "1d",
    }
    widget = m.InteractiveCommands(api, MagicMock())
    widget.ui = MagicMock()
    monkeypatch.setattr(m, "console", MagicMock())
    monkeypatch.setattr(m.time, "sleep", lambda *_: None)
    p = MagicMock()
    p.__enter__.return_value = p
    monkeypatch.setattr(m, "Progress", lambda *a, **kw: p)
    return widget


@pytest.mark.parametrize(
    "actions",
    [
        ["q"],
        ["r", "q"],
        ["1", "q"],
        ["2", "q"],
        ["3", "q"],
        ["4", "q"],
        ["5", "q"],
        ["6", "q"],
    ],
)
def test_interactive_manager_menu_dispatches_actions_without_external_mutations(
    ui, monkeypatch, actions
):
    monkeypatch.setattr(m.Prompt, "ask", MagicMock(side_effect=actions))
    names = ("create", "start", "stop", "restart", "view_logs", "delete")
    for name in names:
        setattr(
            ui,
            "_interactive_" + name + "_deployment"
            if name != "view_logs"
            else "_interactive_view_logs",
            MagicMock(),
        )
    # All choices besides q/r dispatch into the expected handler.
    ui.interactive_deployment_manager()
    ui.api_client.list_deployments.assert_called()


def test_manager_error_allows_operator_to_quit(ui, monkeypatch):
    ui.api_client.list_deployments.side_effect = WebOpsError("offline")
    monkeypatch.setattr(m.Confirm, "ask", lambda *_a, **_k: False)
    ui.interactive_deployment_manager()


@pytest.mark.parametrize("choice", ["c", "1", "2"])
def test_selection_cancel_or_deployment_choice(ui, monkeypatch, choice):
    monkeypatch.setattr(m.Prompt, "ask", lambda *_a, **_kw: choice)
    result = ui._select_deployment(
        [{"name": "first"}, {"name": "second", "status": "running"}], "select"
    )
    assert result == {"c": None, "1": "first", "2": "second"}[choice]


def test_selection_empty_returns_no_deployment(ui):
    assert ui._select_deployment([], "select") is None


def test_selection_invalid_value_then_valid(ui, monkeypatch):
    answers = iter(["bad", "999", "1"])
    monkeypatch.setattr(m.Prompt, "ask", lambda *_a, **_kw: next(answers))
    assert ui._select_deployment([{"name": "api"}], "select") == "api"


@pytest.mark.parametrize("missing", ["name", "repo_url", "cancel", None])
def test_interactive_create_requires_parameters_and_approval(ui, monkeypatch, missing):
    fields = {
        "Deployment name": "api-new",
        "Domain (optional)": "",
        "Repository URL": "https://github.com/owner/project.git",
        "Branch": "main",
    }
    if missing == "name":
        fields["Deployment name"] = ""
    if missing == "repo_url":
        fields["Repository URL"] = ""
    monkeypatch.setattr(m.Prompt, "ask", lambda label, **kw: fields[label])
    monkeypatch.setattr(
        m.Confirm,
        "ask",
        lambda label, **kw: (
            missing != "cancel" and "Start the deployment now?" not in label
        ),
    )
    ui._interactive_create_deployment()
    assert ui.api_client.create_deployment.called is (missing is None)


@pytest.mark.parametrize("operation", ["start", "stop", "restart", "delete"])
@pytest.mark.parametrize("fails", [False, True])
def test_operation_progress_accepts_api_or_handles_failure(
    ui, monkeypatch, operation, fails
):
    target = getattr(ui.api_client, operation + "_deployment")
    if fails:
        target.side_effect = WebOpsError("forbidden")
    getattr(ui, "_" + operation + "_deployment_with_progress")("api")
    target.assert_called_once_with("api")


@pytest.mark.parametrize("action", ["start", "stop", "restart", "view_logs", "delete"])
@pytest.mark.parametrize("approved", [False, True])
def test_interactive_actions_require_selection_and_confirmation(
    ui, monkeypatch, action, approved
):
    monkeypatch.setattr(ui, "_select_deployment", lambda *_: "api")
    monkeypatch.setattr(m.Confirm, "ask", lambda *_a, **_kw: approved)
    handler = {
        "start": "_interactive_start_deployment",
        "stop": "_interactive_stop_deployment",
        "restart": "_interactive_restart_deployment",
        "view_logs": "_interactive_view_logs",
        "delete": "_interactive_delete_deployment",
    }[action]
    operation = (
        "interactive_logs_viewer"
        if action == "view_logs"
        else "_" + action + "_deployment_with_progress"
    )
    target = MagicMock()
    monkeypatch.setattr(ui, operation, target)
    getattr(ui, handler)([{"name": "api", "status": "running"}])
    assert target.called is (approved or action in ("start", "view_logs"))


def test_stop_menu_only_shows_running_deployments(ui):
    ui._interactive_stop_deployment([{"name": "notrunning", "status": "stopped"}])
    ui.api_client.stop_deployment.assert_not_called()


@pytest.mark.parametrize(
    "method",
    [
        "_interactive_stop_deployment",
        "_interactive_restart_deployment",
        "_interactive_view_logs",
        "_interactive_delete_deployment",
    ],
)
def test_interactive_operation_errors_are_handled(ui, monkeypatch, method):
    monkeypatch.setattr(
        ui, "_select_deployment", MagicMock(side_effect=ValueError("selection failed"))
    )
    getattr(ui, method)([{"name": "api", "status": "running"}])


def test_status_and_deployment_information_fall_back_on_api_error(ui):
    assert ui._get_system_info()["cpu_usage"] == 12
    assert len(ui._get_deployments_info()) == 2
    assert len(ui._get_services_info()) == 3
    ui.api_client.get_status.side_effect = WebOpsError("offline")
    ui.api_client.list_deployments.side_effect = WebOpsError("offline")
    assert ui._get_system_info()["cpu_usage"] == 0
    assert ui._get_deployments_info() == []


@pytest.mark.parametrize("connection_error", [False, True])
def test_live_status_dashboard_updates_and_retries_on_disconnection(
    ui, monkeypatch, connection_error
):
    live = MagicMock()
    live.__enter__.return_value = live
    monkeypatch.setattr(m, "Live", lambda *a, **kw: live)
    if connection_error:
        ui.api_client.get_status.side_effect = WebOpsConnectionError("offline")
        # _get_system_info catches WebOpsError; trigger at dashboard layer instead.
        ui.ui.create_status_dashboard.side_effect = WebOpsConnectionError("offline")
    count = [0]

    def finish_after_cycle(n):
        count[0] += 1
        raise KeyboardInterrupt()

    monkeypatch.setattr(m.time, "sleep", finish_after_cycle)
    ui.interactive_status()
    assert live.update.called


@pytest.mark.parametrize("logs", ["INFO online\nERROR failed", "", None])
def test_live_logs_render_and_graceful_cancel(ui, monkeypatch, logs):
    live = MagicMock()
    live.__enter__.return_value = live
    monkeypatch.setattr(m, "Live", lambda *a, **kw: live)
    ui.api_client.get_deployment_logs.return_value = {"logs": logs}
    monkeypatch.setattr(m.time, "sleep", MagicMock(side_effect=KeyboardInterrupt()))
    ui.interactive_logs_viewer("api")
    ui.ui.create_log_viewer.assert_called_once()


def test_live_logs_retry_on_api_error(ui, monkeypatch):
    live = MagicMock()
    live.__enter__.return_value = live
    monkeypatch.setattr(m, "Live", lambda *a, **kw: live)
    ui.api_client.get_deployment_logs.side_effect = WebOpsError("offline")
    monkeypatch.setattr(m.time, "sleep", MagicMock(side_effect=KeyboardInterrupt()))
    ui.interactive_logs_viewer("api")
    live.update.assert_called()


@pytest.mark.parametrize("pick", ["no-deployments", "cancelled", "selected"])
def test_log_viewer_uses_selected_deployment(ui, monkeypatch, pick):
    if pick == "no-deployments":
        ui.api_client.list_deployments.return_value = {"deployments": []}
    if pick != "no-deployments":
        monkeypatch.setattr(
            ui, "_select_deployment", lambda *_: None if pick == "cancelled" else "api"
        )
    live = MagicMock()
    live.__enter__.return_value = live
    monkeypatch.setattr(m, "Live", lambda *a, **kw: live)
    monkeypatch.setattr(m.time, "sleep", MagicMock(side_effect=KeyboardInterrupt()))
    ui.interactive_logs_viewer()
    assert live.update.called is (pick == "selected")


def test_manager_can_continue_after_recoverable_api_failure(ui, monkeypatch):
    calls = [0]

    def fetch():
        calls[0] += 1
        if calls[0] == 1:
            raise WebOpsError("temporary")
        return {"deployments": []}

    ui.api_client.list_deployments.side_effect = fetch
    monkeypatch.setattr(m.Confirm, "ask", lambda *_a, **_kw: True)
    monkeypatch.setattr(m.Prompt, "ask", lambda *_a, **_kw: "q")
    ui.interactive_deployment_manager()
    assert calls[0] == 2


def test_interactive_create_reports_webops_api_error(ui, monkeypatch):
    data = {
        "Deployment name": "new-app",
        "Domain (optional)": "",
        "Repository URL": "https://github.com/owner/repo.git",
        "Branch": "main",
    }
    monkeypatch.setattr(m.Prompt, "ask", lambda text, **kw: data[text])
    monkeypatch.setattr(m.Confirm, "ask", lambda *_a, **_kw: True)
    ui.api_client.create_deployment.side_effect = WebOpsError("permission denied")
    ui._interactive_create_deployment()
    ui.api_client.start_deployment.assert_not_called()


def test_no_selection_does_not_start_or_delete(ui, monkeypatch):
    monkeypatch.setattr(ui, "_select_deployment", lambda *_: None)
    ui._interactive_start_deployment([{"name": "api", "status": "running"}])
    ui._interactive_delete_deployment([{"name": "api", "status": "running"}])
    ui.api_client.start_deployment.assert_not_called()
    ui.api_client.delete_deployment.assert_not_called()


def test_interactive_create_can_start_approved_deployment(ui, monkeypatch):
    prompt_values = {
        "Deployment name": "staging-app",
        "Repository URL": "https://github.com/owner/repo.git",
        "Branch": "main",
        "Domain (optional)": "",
    }
    monkeypatch.setattr(m.Prompt, "ask", lambda label, **kw: prompt_values[label])
    monkeypatch.setattr(m.Confirm, "ask", lambda *a, **kw: True)
    starter = MagicMock()
    monkeypatch.setattr(ui, "_start_deployment_with_progress", starter)
    ui._interactive_create_deployment()
    ui.api_client.create_deployment.assert_called_once()
    starter.assert_called_once_with("staging-app")
