"""Executable contract coverage for the interactive setup wizard.

No installer, network call, sudo command, or host service is started.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
import builtins
import io

from click.testing import CliRunner
import pytest

from webops_cli.wizards import wizards as wmodule
from webops_cli import wizards as lazy_wizards


@pytest.fixture
def setup_env(monkeypatch):
    monkeypatch.setattr(wmodule, "console", MagicMock())
    progress = MagicMock()
    progress.spinner.return_value = nullcontext()
    progress.progress_bar.return_value = nullcontext(MagicMock())
    monkeypatch.setattr(wmodule, "progress_manager", progress)
    monkeypatch.setattr(wmodule.time, "sleep", lambda _: None)
    monkeypatch.setattr(wmodule.Confirm, "ask", MagicMock(return_value=True))
    monkeypatch.setattr(wmodule.Prompt, "ask", MagicMock(return_value="admin"))
    monkeypatch.setattr(wmodule.IntPrompt, "ask", MagicMock(return_value=5432))
    return wmodule.SetupWizard()


def test_lazy_wizard_exports_and_unknown_attribute():
    assert lazy_wizards.SetupWizard is wmodule.SetupWizard
    assert lazy_wizards.InteractiveWizard is wmodule.InteractiveWizard
    assert lazy_wizards.DeploymentWizard.__name__ == "DeploymentWizard"
    assert lazy_wizards.TroubleshootingWizard.__name__ == "TroubleshootingWizard"
    with pytest.raises(AttributeError):
        getattr(lazy_wizards, "destructive_or_unknown_tool")


def test_setup_headers_and_success_message(setup_env):
    wiz = setup_env
    wiz.config.update(admin_username="operator", database="sqlite")
    wiz.display_header()
    wiz.display_step(2, 5, "Configuration")
    wiz._display_success()
    assert wiz.console.print.call_count >= 5


@pytest.mark.parametrize("failing_check", [None, "_check_os", "_check_sudo",
                                          "_check_internet", "_check_python", "_check_git"])
def test_welcome_all_prerequisites_and_each_failure(setup_env, monkeypatch, failing_check):
    wiz = setup_env
    for name in ("_check_os", "_check_sudo", "_check_internet", "_check_python", "_check_git"):
        monkeypatch.setattr(wiz, name, lambda: True)
    if failing_check:
        monkeypatch.setattr(wiz, failing_check, lambda: False)
    result = wiz._step_welcome()
    assert result is (failing_check is None)


@pytest.mark.parametrize("answer", [True, False])
def test_welcome_confirmation_controls_proceed(setup_env, monkeypatch, answer):
    for name in ("_check_os", "_check_sudo", "_check_internet", "_check_python", "_check_git"):
        monkeypatch.setattr(setup_env, name, lambda: True)
    wmodule.Confirm.ask.return_value = answer
    assert setup_env._step_welcome() is answer


@pytest.mark.parametrize("bad_ports", [[], [80], [80, 443], [8000]])
@pytest.mark.parametrize("proceed", [True, False])
def test_system_check_port_failures_require_explicit_approval(setup_env, monkeypatch,
                                                             bad_ports, proceed):
    monkeypatch.setattr(setup_env, "_check_port", lambda port: port not in bad_ports)
    wmodule.Confirm.ask.return_value = proceed
    assert setup_env._step_system_check() is (True if not bad_ports else proceed)


def test_config_collection_retries_passwords_and_supports_postgresql(setup_env, monkeypatch):
    wiz = setup_env
    def ask(prompt, **kwargs):
        if prompt == "Admin username":
            return "testadmin"
        if prompt == "Admin password":
            ask.n += 1
            return "short" if ask.n == 1 else "strongpassword"
        if prompt == "Confirm password":
            return "short" if ask.n == 1 else "strongpassword"
        if prompt == "Database type":
            return "postgresql"
        return {
            "Domain name (e.g., webops.example.com)": "panel.example.org",
            "PostgreSQL host": "db.example.internal",
            "Database name": "webops_stage",
            "Database user": "webops_user",
            "Database password": "secret-not-shown",
        }.get(prompt, "value")
    ask.n = 0
    monkeypatch.setattr(wmodule.Prompt, "ask", ask)
    monkeypatch.setattr(wmodule.IntPrompt, "ask", lambda *a, **k: 5433)
    monkeypatch.setattr(wmodule.Confirm, "ask", lambda prompt, **kwargs: True)
    assert wiz._step_collect_config()
    assert wiz.config["admin_password"] == "strongpassword"
    assert wiz.config["ssl"] is True
    assert wiz.config["database"] == "postgresql"
    assert wiz.config["db_port"] == 5433
    assert wiz.config["db_host"] == "db.example.internal"


def test_password_mismatch_and_sqlite_without_domain(setup_env, monkeypatch):
    answers = iter(["badpassword", "different", "anothergood", "anothergood"])
    def ask(prompt, **kwargs):
        if "password" in prompt.lower():
            return next(answers)
        if prompt == "Database type":
            return "sqlite"
        return "admin"
    monkeypatch.setattr(wmodule.Prompt, "ask", ask)
    monkeypatch.setattr(wmodule.Confirm, "ask", lambda prompt, **kwargs:
                        False if "custom domain" in prompt else True)
    assert setup_env._step_collect_config()
    assert setup_env.config["database"] == "sqlite"
    assert setup_env.config["domain"] is None
    assert setup_env.config["ssl"] is False


@pytest.mark.parametrize("fail_install", [False, True])
def test_installation_progress_and_failure_handling(setup_env, monkeypatch, fail_install):
    fake_progress = MagicMock()
    if fail_install:
        fake_progress.update.side_effect = OSError("unavailable installation target")
    monkeypatch.setattr(wmodule.progress_manager, "progress_bar",
                        lambda *a, **kw: nullcontext(fake_progress))
    errors = MagicMock()
    monkeypatch.setattr(wmodule.error_handler, "display_error", errors)
    assert setup_env._step_install() is (not fail_install)
    if fail_install:
        errors.assert_called_once()


def test_installation_verification_status_table(setup_env):
    assert setup_env._step_verify() is True


@pytest.mark.parametrize("blocker", ["_step_welcome", "_step_system_check", "_step_collect_config",
                                      "_step_install", "_step_verify", None])
def test_setup_run_stops_at_each_failed_stage_or_succeeds(setup_env, monkeypatch, blocker):
    calls = []
    for method in ("_step_welcome", "_step_system_check", "_step_collect_config",
                   "_step_install", "_step_verify"):
        monkeypatch.setattr(setup_env, method, lambda m=method:
                            calls.append(m) or m != blocker)
    monkeypatch.setattr(setup_env, "_display_success", lambda: calls.append("success"))
    assert setup_env.run() is (blocker is None)
    assert ("success" in calls) is (blocker is None)


@pytest.mark.parametrize("error", [KeyboardInterrupt(), RuntimeError("simulated step failure")])
def test_setup_run_catches_interruption_and_error(setup_env, monkeypatch, error):
    monkeypatch.setattr(setup_env, "_step_welcome", MagicMock(side_effect=error))
    errors = MagicMock()
    monkeypatch.setattr(wmodule.error_handler, "display_error", errors)
    assert not setup_env.run()
    if isinstance(error, RuntimeError):
        errors.assert_called_once()


@pytest.mark.parametrize("command,result", [
    (["sudo", "-n", "true"], 0),
    (["ping", "-c", "1", "8.8.8.8"], 0),
    (["python3", "--version"], 0),
    (["git", "--version"], 0),
    (["netstat", "-tuln"], 0),
])
def test_prerequisite_checks_success(setup_env, monkeypatch, command, result):
    def fake_run(args, **kwargs):
        assert args == command
        return SimpleNamespace(returncode=result, stdout=(
            "Python 3.13.1" if args[0] == "python3" else
            "Active Internet connections" if args[0] == "netstat" else "git version 2.4"
        ))
    monkeypatch.setattr(wmodule.subprocess, "run", fake_run)
    lookup = {"sudo": "_check_sudo", "ping": "_check_internet",
              "python3": "_check_python", "git": "_check_git", "netstat": "_check_port"}
    method = getattr(setup_env, lookup[command[0]])
    assert (method(80) if command[0] == "netstat" else method()) is True


@pytest.mark.parametrize("method,argv", [
    ("_check_sudo", "sudo"), ("_check_internet", "ping"),
    ("_check_python", "python3"), ("_check_git", "git"),
    ("_check_port", "netstat"),
])
def test_prerequisite_failure_survives_unavailable_binaries(setup_env, monkeypatch,
                                                             method, argv):
    monkeypatch.setattr(wmodule.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError(argv)))
    check = getattr(setup_env, method)
    assert (check(443) if method == "_check_port" else check()) is (method == "_check_port")


@pytest.mark.parametrize("version,expected", [
    ("Python 3.10.15", False), ("Python 2.13.0", False),
    ("Python 3.13.0", True), ("Python 4.0.0", True),
    ("broken", False),
])
def test_python_version_gate(setup_env, monkeypatch, version, expected):
    monkeypatch.setattr(wmodule.subprocess, "run",
                        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=version))
    assert setup_env._check_python() is expected


def test_nonzero_prerequisite_commands_and_occupied_port(setup_env, monkeypatch):
    monkeypatch.setattr(wmodule.subprocess, "run",
                        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="tcp :80 open"))
    assert not setup_env._check_sudo()
    assert not setup_env._check_internet()
    assert not setup_env._check_python()
    assert not setup_env._check_git()
    assert not setup_env._check_port(80)


def test_os_detection_supported_unsupported_and_io_error(setup_env, monkeypatch):
    monkeypatch.setattr(builtins, "open", lambda *a, **kw: io.StringIO("ID=ubuntu"))
    assert setup_env._check_os()
    monkeypatch.setattr(builtins, "open", lambda *a, **kw: io.StringIO("ID=fedora"))
    assert not setup_env._check_os()
    monkeypatch.setattr(builtins, "open",
                        lambda *a, **kw: (_ for _ in ()).throw(OSError("unreadable")))
    assert not setup_env._check_os()


@pytest.mark.parametrize("successful", [True, False])
def test_setup_click_entrypoint_propagates_result(monkeypatch, successful):
    monkeypatch.setattr(wmodule.SetupWizard, "run", lambda *_: successful)
    result = CliRunner().invoke(wmodule.wizard, ["setup"])
    assert result.exit_code == (0 if successful else 1)

