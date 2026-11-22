"""Real Click entrypoints: successful API paths, failures, and protected actions."""

from unittest.mock import MagicMock
from types import SimpleNamespace
from contextlib import nullcontext
import click
from click.testing import CliRunner
import pytest
from webops_cli import cli as m

ORIGINAL_GET_API_CLIENT = m.get_api_client


@pytest.fixture
def cli(monkeypatch):
    api = MagicMock()
    api.list_deployments.return_value = {
        "deployments": [{"name": "app", "status": "running"}],
        "pagination": {"page": 1, "pages": 2},
    }
    api.get_deployment.return_value = {
        "name": "app",
        "status": "running",
        "project_type": "django",
        "repo_url": "https://github.com/owner/api.git",
        "branch": "main",
        "created_at": "now",
        "updated_at": "now",
        "domain": "",
        "port": 8000,
    }
    api.get_deployment_logs.return_value = {
        "logs": [
            {"created_at": "now", "level": "info", "message": "online"},
            {"created_at": "later", "level": "error", "message": "down"},
        ]
    }
    api.list_databases.return_value = {
        "databases": [
            {"name": "staging", "deployment": "app", "host": "localhost", "port": 5432}
        ]
    }
    api.get_database.return_value = {
        "name": "staging",
        "username": "user",
        "password": "mock-not-real",
        "host": "localhost",
        "port": 5432,
    }
    api.get_status.return_value = {"status": "ok", "version": "1.0", "timestamp": "now"}
    api.get_env_vars.return_value = {
        "env_vars": {
            "SECRET_KEY": "hidden-private-token-long",
            "API": "short",
            "DEBUG": "true",
            "EMPTY": "",
        }
    }
    api.validate_env.return_value = {"valid": True}
    api.validate_project.return_value = {"all_passed": True}
    fake_config = MagicMock()
    fake_config.is_configured.return_value = True
    fake_config.get_url.return_value = "https://panel.example.org"
    fake_config.get_token.return_value = "valid-long-token-12345"
    fake_config.get.return_value = "developer"
    monkeypatch.setattr(m, "config", fake_config)
    monkeypatch.setattr(m, "Config", lambda: fake_config)
    monkeypatch.setattr(m, "get_api_client", lambda: api)
    mock_console = MagicMock()
    mock_console.status.return_value = nullcontext()
    monkeypatch.setattr(m, "console", mock_console)
    monkeypatch.setattr(m, "display_deployment_table", MagicMock())
    logger = MagicMock()
    logger.get_user.return_value = "testoperator"
    monkeypatch.setattr(m, "get_security_logger", lambda: logger)
    monkeypatch.setattr(m, "error_handler", MagicMock())
    monkeypatch.setattr(m.time, "sleep", lambda *_: None)
    return SimpleNamespace(
        api=api,
        config=fake_config,
        console=mock_console,
        logger=logger,
        run=lambda *args, **kwargs: CliRunner().invoke(m.main, *args, **kwargs),
    )


@pytest.mark.parametrize(
    "cmd,api_method",
    [
        (["list"], "list_deployments"),
        (
            ["list", "--status", "running", "--page", "2", "--per-page", "10"],
            "list_deployments",
        ),
        (["info", "app"], "get_deployment"),
        (["logs", "app"], "get_deployment_logs"),
        (["logs", "app", "--tail", "2"], "get_deployment_logs"),
        (["start", "app"], "start_deployment"),
        (["stop", "app"], "stop_deployment"),
        (["restart", "app"], "restart_deployment"),
        (["delete", "app", "--yes"], "delete_deployment"),
        (["db:list"], "list_databases"),
        (["db:credentials", "staging"], "get_database"),
        (["status"], "get_status"),
        (["env:generate", "app"], "generate_env"),
        (
            [
                "env:generate",
                "app",
                "--debug",
                "--domain",
                "app.example.org",
                "--set",
                "MODE=staging",
                "--set",
                "PORT=8000",
            ],
            "generate_env",
        ),
        (["env:validate", "app"], "validate_env"),
        (["env:show", "app"], "get_env_vars"),
        (["env:show", "app", "--show-secrets"], "get_env_vars"),
        (["env:set", "app", "DEBUG", "true"], "set_env_var"),
        (["env:unset", "app", "DEBUG"], "unset_env_var"),
        (["project:validate", "app"], "validate_project"),
    ],
)
def test_cli_happy_path_methods_use_configured_api(cli, cmd, api_method):
    result = cli.run(cmd)
    assert result.exit_code == 0, (cmd, result.output, result.exception)
    getattr(cli.api, api_method).assert_called()


@pytest.mark.parametrize(
    "cmd",
    [
        ["list", "--status", "invalid"],
        ["list", "--page", "0"],
        ["list", "--per-page", "110"],
        ["info", "bad/name"],
        ["logs", "bad/name"],
        ["logs", "app", "--tail", "-1"],
        ["start", "bad/name"],
        ["stop", "bad/name"],
        ["restart", "bad/name"],
        ["delete", "bad/name", "--yes"],
        ["env:generate", "app", "--set", "MALFORMED"],
    ],
)
def test_bad_user_input_never_invokes_mutating_api(cli, cmd):
    result = cli.run(cmd)
    assert result.exit_code != 0
    assert not any(
        getattr(cli.api, n).called
        for n in (
            "start_deployment",
            "stop_deployment",
            "restart_deployment",
            "delete_deployment",
            "generate_env",
            "get_deployment",
        )
    )


@pytest.mark.parametrize(
    "action,argv",
    [
        ("start_deployment", ["start", "app"]),
        ("stop_deployment", ["stop", "app"]),
        ("restart_deployment", ["restart", "app"]),
        ("delete_deployment", ["delete", "app", "--yes"]),
        ("get_deployment", ["info", "app"]),
        ("get_deployment_logs", ["logs", "app"]),
        ("list_deployments", ["list"]),
        ("list_databases", ["db:list"]),
        ("get_database", ["db:credentials", "staging"]),
        ("get_status", ["status"]),
        ("generate_env", ["env:generate", "app"]),
        ("validate_env", ["env:validate", "app"]),
        ("get_env_vars", ["env:show", "app"]),
        ("set_env_var", ["env:set", "app", "DEBUG", "true"]),
        ("unset_env_var", ["env:unset", "app", "DEBUG"]),
        ("validate_project", ["project:validate", "app"]),
    ],
)
def test_cli_api_error_exits_without_misreporting_success(cli, action, argv):
    getattr(cli.api, action).side_effect = m.WebOpsAPIError("API offline")
    result = cli.run(argv)
    assert result.exit_code != 0, (argv, result.output)


@pytest.mark.parametrize(
    "failure",
    [
        m.RBACError("not allowed"),
        m.TokenExpiredError("expired"),
        m.WebOpsAPIError("offline"),
    ],
)
def test_deployment_list_distinguishes_security_and_connection_errors(cli, failure):
    cli.api.list_deployments.side_effect = failure
    assert cli.run(["list"]).exit_code != 0


@pytest.mark.parametrize(
    "stored",
    [
        ("https://panel.example.org", "valid-token-12345", "developer"),
        (None, None, "viewer"),
        ("https://panel.example.org", None, "developer"),
    ],
)
def test_cli_config_view_masks_token_or_reports_missing(cli, stored):
    url, token, role = stored
    cli.config.get_url.return_value = url
    cli.config.get_token.return_value = token
    cli.config.get.return_value = role
    assert cli.run(["config"]).exit_code == 0
    cli.logger.log_configuration_change.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        ["--url", "https://panel.example.org"],
        ["--token", "valid-long-token-1234"],
        ["--role", "viewer"],
        [
            "--url",
            "https://panel.example.org",
            "--token",
            "valid-long-token-1234",
            "--role",
            "developer",
        ],
    ],
)
def test_cli_config_updates_log_changes_without_disclosing_secrets(cli, options):
    result = cli.run(["config", *options])
    assert result.exit_code == 0, result.exception
    assert cli.config.set.called
    assert cli.logger.log_configuration_change.call_count >= 1


@pytest.mark.parametrize(
    "options",
    [
        ["--url", "ftp://unsafe.example.org"],
        ["--token", "short"],
    ],
)
def test_cli_config_validation_rejects_bad_details(cli, options):
    assert cli.run(["config", *options]).exit_code != 0
    cli.logger.log_security_violation.assert_called_once()


def test_cli_config_encryption_error_is_reported(cli):
    cli.config.set.side_effect = m.EncryptionError("encryption key unreadable")
    assert cli.run(["config", "--role", "admin"]).exit_code != 0
    cli.logger.log_error.assert_called_once()


@pytest.mark.parametrize("configured", [True, False])
def test_api_client_constructor_checks_configuration(cli, monkeypatch, configured):
    cli.config.is_configured.return_value = configured
    monkeypatch.setattr(m, "get_api_client", ORIGINAL_GET_API_CLIENT)
    monkeypatch.setattr(m, "WebOpsAPIClient", MagicMock(return_value=cli.api))
    if configured:
        assert m.get_api_client() is cli.api
    else:
        with pytest.raises(SystemExit):
            m.get_api_client()
        m.WebOpsAPIClient.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        m.ValidationError("malformed URL"),
        m.EncryptionError("key corrupted"),
        m.RBACError("unauthorized role"),
    ],
)
def test_get_api_client_security_configuration_failures(cli, monkeypatch, failure):
    monkeypatch.setattr(m, "get_api_client", ORIGINAL_GET_API_CLIENT)
    monkeypatch.setattr(m, "WebOpsAPIClient", MagicMock(side_effect=failure))
    with pytest.raises(SystemExit):
        m.get_api_client()


def test_decorator_does_not_swallow_success_or_unexpected_error(cli):
    @m.handle_api_errors
    def operation(n):
        if n < 0:
            raise RuntimeError("failure")
        return n + 1

    assert operation(4) == 5
    assert operation(-1) is None
    m.error_handler.display_error.assert_called_once()


@pytest.mark.parametrize("ready", [True, False])
def test_configuration_required_decorator_fails_closed(cli, ready):
    cli.config.is_configured.return_value = ready
    wrapped = m.require_config(lambda text: text.upper())
    assert wrapped("hello") == ("HELLO" if ready else None)


@pytest.mark.parametrize(
    "force,confirmed", [(True, False), (False, False), (False, True)]
)
def test_destructive_action_confirmation(cli, monkeypatch, force, confirmed):
    monkeypatch.setattr(m.Confirm, "ask", lambda *_a, **_kw: confirmed)
    assert m.confirm_destructive_action("delete", "app", force) == (force or confirmed)


@pytest.mark.parametrize(
    "lines",
    [
        [],
        [
            "ERROR failure",
            "CRITICAL outage",
            "WARN overload",
            "WARNING disk",
            "INFO started",
            "DEBUG step",
            "plain",
        ],
    ],
)
def test_log_formatting_emits_all_level_variants(cli, lines):
    m.display_logs_with_formatting(lines, "app")
    assert cli.console.print.called


@pytest.mark.parametrize("approve", [True, False])
def test_deletion_without_force_honors_explicit_confirmation(cli, monkeypatch, approve):
    monkeypatch.setattr(m, "confirm_destructive_action", lambda *a: approve)
    result = cli.run(["delete", "app"])
    assert result.exit_code == 0
    assert cli.api.delete_deployment.called is approve


@pytest.mark.parametrize(
    "logs",
    [
        {"logs": []},
        {
            "logs": [
                {"level": "debug", "created_at": "now", "message": "trace"},
                {"level": "warning", "created_at": "now", "message": "delay"},
            ]
        },
    ],
)
def test_log_display_empty_or_structured_messages(cli, logs):
    cli.api.get_deployment_logs.return_value = logs
    assert cli.run(["logs", "app"]).exit_code == 0


@pytest.mark.parametrize(
    "status,detail",
    [
        ("pending", None),
        ("building", "Building"),
        ("running", "OK"),
        ("failed", "Startup failed"),
        ("unknown", None),
    ],
)
def test_cli_info_handles_all_deployment_states(cli, status, detail):
    cli.api.get_deployment.return_value = {
        **cli.api.get_deployment.return_value,
        "status": status,
        "domain": detail,
        "port": None,
    }
    assert cli.run(["info", "app"]).exit_code == 0


def test_follow_logs_deduplicates_events_then_cancels(cli, monkeypatch):
    events = [
        {"created_at": "now", "level": "info", "message": "started"},
        {"created_at": "later", "level": "warning", "message": "slow"},
    ]
    cli.api.get_deployment_logs.side_effect = [
        {"logs": events[:1]},
        {"logs": events},
        {"logs": events},
    ]
    steps = [0]

    def interrupt_after(ignored):
        steps[0] += 1
        if steps[0] >= 3:
            raise KeyboardInterrupt()

    monkeypatch.setattr(m.time, "sleep", interrupt_after)
    assert cli.run(["logs", "app", "--follow"]).exit_code == 0
    assert cli.api.get_deployment_logs.call_count == 3


def test_follow_logs_api_error_causes_failure(cli):
    cli.api.get_deployment_logs.side_effect = m.WebOpsAPIError("offline")
    assert cli.run(["logs", "app", "--follow"]).exit_code != 0


@pytest.mark.parametrize("status", [True, False])
def test_env_validation_status_and_missing_vars(cli, status):
    cli.api.validate_env.return_value = {
        "valid": status,
        "missing": ["DATABASE_URL", "SECRET_KEY"],
    }
    result = cli.run(["env:validate", "app"])
    assert result.exit_code == (0 if status else 1)


@pytest.mark.parametrize(
    "vars",
    [
        {},
        {"PUBLIC": "hello"},
        {"TOKEN": "short", "API_KEY": "long-super-private-value"},
        {"BLANK": "", "SECRET_KEY": "private", "DEBUG": "false"},
    ],
)
@pytest.mark.parametrize("show", [False, True])
def test_env_display_masking_and_empty_values(cli, vars, show):
    cli.api.get_env_vars.return_value = {"env_vars": vars}
    argv = ["env:show", "app"] + (["--show-secrets"] if show else [])
    assert cli.run(argv).exit_code == 0


@pytest.mark.parametrize("operation", ["env:set", "env:unset"])
def test_env_restart_calls_correct_deployment_name_and_masks_secrets(cli, operation):
    cmd = (
        ["env:set", "app", "API_KEY", "classified-secret", "--restart"]
        if operation == "env:set"
        else ["env:unset", "app", "API_KEY", "--restart"]
    )
    result = cli.run(cmd)
    assert result.exit_code == 0, (cmd, result.exception, result.output)
    cli.api.restart_deployment.assert_called_once_with("app")
    if operation == "env:set":
        logged = " ".join(str(call) for call in cli.console.print.call_args_list)
        assert "classified-secret" not in logged


def test_env_unset_without_restart_keeps_running_process(cli):
    assert cli.run(["env:unset", "app", "DEBUG"]).exit_code == 0
    cli.api.restart_deployment.assert_not_called()


@pytest.mark.parametrize(
    "data",
    [
        {"all_passed": False, "results": []},
        {
            "all_passed": False,
            "results": [
                {
                    "level": "error",
                    "passed": False,
                    "message": "Missing requirement",
                    "details": {f"problem_{i}": "x" * 200 for i in range(8)},
                },
                {
                    "level": "warning",
                    "passed": False,
                    "message": "Possible risk",
                    "details": {"disk": "slow"},
                },
                {"level": "info", "passed": True, "message": "Ready"},
                {"level": "unclassified", "passed": True, "message": "Unknown check"},
            ],
        },
    ],
)
def test_project_validator_reports_all_levels_and_truncates_long_fields(cli, data):
    cli.api.validate_project.return_value = data
    result = cli.run(["project:validate", "app"])
    assert result.exit_code == 1
    assert cli.api.validate_project.called


def test_empty_database_list_is_not_misreported_as_error(cli):
    cli.api.list_databases.return_value = {"databases": []}
    assert cli.run(["db:list"]).exit_code == 0
    cli.console.print.assert_called()


@pytest.mark.parametrize("kind", [True, False])
@pytest.mark.parametrize("command", ["setup", "deploy-wizard", "troubleshoot"])
def test_wizard_click_command_displays_real_completion_status(
    cli, monkeypatch, command, kind
):
    from webops_cli import wizards

    cls = {
        "setup": "SetupWizard",
        "deploy-wizard": "DeploymentWizard",
        "troubleshoot": "TroubleshootingWizard",
    }[command]
    obj = MagicMock()
    obj.run.return_value = kind
    monkeypatch.setattr(wizards, cls, lambda: obj)
    result = cli.run([command])
    assert result.exit_code == 0, result.exception
    obj.run.assert_called_once()


@pytest.mark.parametrize(
    "command,method",
    [
        ("interactive-status", "interactive_status"),
        ("manage", "interactive_deployment_manager"),
        ("interactive-logs", "interactive_logs_viewer"),
    ],
)
def test_interactive_click_commands_dispatch_without_opening_live_terminal(
    cli, monkeypatch, command, method
):
    interface = MagicMock()
    monkeypatch.setattr(m, "InteractiveCommands", lambda *a, **kw: interface)
    argv = [command] + (["app"] if command == "interactive-logs" else [])
    result = cli.run(argv)
    assert result.exit_code == 0, result.exception
    getattr(interface, method).assert_called_once()


@pytest.mark.parametrize("mode", ["success", "failure", "interrupt", "error"])
def test_project_setup_reports_outcomes_and_releases_temp_checkout(
    cli, monkeypatch, mode
):
    workflow = MagicMock()
    if mode == "interrupt":
        workflow.run_complete_workflow.side_effect = KeyboardInterrupt()
    elif mode == "error":
        workflow.run_complete_workflow.side_effect = OSError("git unavailable")
    else:
        workflow.run_complete_workflow.return_value = SimpleNamespace(
            success=mode == "success",
            error_message="access denied" if mode == "failure" else None,
        )
    monkeypatch.setattr(m, "ProjectSetupWorkflow", lambda *a: workflow)
    result = cli.run(["project:setup", "--repo", "https://github.com/team/repo.git"])
    assert (
        result.exit_code
        == {"success": 0, "failure": 1, "interrupt": 130, "error": 1}[mode]
    )
    if mode in ("success", "failure"):
        workflow.display_result_summary.assert_called_once()
        cli.logger.log_deployment_operation.assert_called_once()
        assert cli.logger.log_deployment_operation.call_args.kwargs["success"] is (
            mode == "success"
        )
    else:
        workflow.cleanup.assert_called_once()


@pytest.mark.parametrize(
    "name,expected", [(None, "repo"), ("custom-app", "custom-app")]
)
def test_project_setup_accepts_explicit_or_derived_project_name(
    cli, monkeypatch, name, expected
):
    task = MagicMock()
    task.run_complete_workflow.return_value = SimpleNamespace(
        success=True, error_message=None
    )
    monkeypatch.setattr(m, "ProjectSetupWorkflow", lambda *a: task)
    args = [
        "project:setup",
        "--repo",
        "https://github.com/team/repo.git",
        "--no-deploy",
        "--no-verify",
    ]
    if name:
        args += ["--name", name]
    assert cli.run(args).exit_code == 0
    assert task.run_complete_workflow.call_args.kwargs["project_name"] == expected
    assert task.run_complete_workflow.call_args.kwargs["create_deployment"] is False
    assert task.run_complete_workflow.call_args.kwargs["verify_access"] is False


@pytest.mark.parametrize("bad_url", ["not-a-url", "https://example.com/../../repo.git"])
def test_project_setup_invalid_remote_rejected_before_clone(cli, bad_url):
    result = cli.run(["project:setup", "--repo", bad_url])
    assert result.exit_code != 0
    cli.api.create_deployment.assert_not_called()


@pytest.mark.parametrize(
    "args,expected",
    [
        (["watch", "app"], "status"),
        (["watch"], "all"),
        (["watch", "--all"], "all"),
        (["watch", "app", "--all"], "all"),
    ],
)
def test_watch_cli_starts_only_requested_websocket_monitor(
    cli, monkeypatch, args, expected
):
    all_mon = MagicMock()
    all_mon.monitor_deployments = MagicMock(return_value=None)
    status_mon = MagicMock()
    status_mon.monitor_deployment = MagicMock(return_value=None)

    async def nothing(*a, **kw):
        return None

    all_mon.monitor_deployments = nothing
    status_mon.monitor_deployment = nothing
    all_factory = MagicMock(return_value=all_mon)
    status_factory = MagicMock(return_value=status_mon)
    monkeypatch.setattr(m, "DeploymentListMonitor", all_factory)
    monkeypatch.setattr(m, "DeploymentStatusMonitor", status_factory)
    result = cli.run(args)
    assert result.exit_code == 0, result.exception
    if expected == "all":
        all_factory.assert_called_once()
    else:
        status_factory.assert_called_once()


def test_watch_requires_configured_cli_before_opening_socket(cli):
    cli.config.is_configured.return_value = False
    assert cli.run(["watch", "app"]).exit_code == 1


@pytest.mark.parametrize("kind", ["all", "single"])
def test_watch_graceful_operator_interruption(cli, monkeypatch, kind):
    monkeypatch.setattr(m.asyncio, "run", MagicMock(side_effect=KeyboardInterrupt()))
    argv = ["watch", "--all"] if kind == "all" else ["watch", "app"]
    assert cli.run(argv).exit_code == 0


def test_enhanced_cli_empty_and_mixed_status_tables(cli):
    enhanced = m.EnhancedCLI(cli.api, cli.config)
    enhanced.console = cli.console
    enhanced.display_deployment_table([])
    enhanced.display_deployment_table(
        [
            {
                "name": "api",
                "status": "running",
                "health": "healthy",
                "repo_url": "https://github.com/owner/long-name" + "x" * 90,
            },
            {"name": "worker", "status": "stopped", "health": "unhealthy"},
            {"name": "builder", "status": "deploying", "health": "degraded"},
            {"name": "faulted", "status": "error", "health": "unknown"},
            {"name": "legacy", "status": "other", "health": "other"},
            "not-a-dictionary",
        ]
    )
    assert enhanced.console.print.call_count == 2


@pytest.mark.parametrize("confirmed", [True, False])
def test_enhanced_cli_confirms_privileged_action(cli, monkeypatch, confirmed):
    monkeypatch.setattr(m.Confirm, "ask", lambda *a, **kw: confirmed)
    enhanced = m.EnhancedCLI(cli.api, cli.config)
    assert enhanced.confirm_destructive_action("delete", "staging") is confirmed


def test_cli_main_exposes_only_unified_deploy_command():
    assert m.main.commands["deploy"].name == "deploy"
    assert "ai-assist" in str(
        m.main.commands["deploy"].get_help(click.Context(m.main.commands["deploy"]))
    )
