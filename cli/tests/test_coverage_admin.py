"""Admin CLI commands and least-privilege host operations; all writes mocked."""

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import subprocess
from click.testing import CliRunner
import pytest
from webops_cli import admin as m


@pytest.fixture
def manager(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBOPS_INSTALL_PATH", str(tmp_path))
    monkeypatch.setenv("WEBOPS_USER", "webops")
    monkeypatch.setattr(m, "console", MagicMock())
    monkeypatch.setattr(m, "show_progress", lambda *a, **kw: nullcontext(MagicMock()))
    monkeypatch.setattr(m.error_handler, "display_error", MagicMock())
    monkeypatch.setattr(m.error_handler, "handle_system_error", MagicMock())
    return m.AdminManager()


@pytest.mark.parametrize("uid", [0, 1000])
def test_root_check_follows_effective_identity(manager, monkeypatch, uid):
    monkeypatch.setattr(m.os, "geteuid", lambda: uid)
    assert manager.check_root_privileges() is (uid == 0)


def test_root_check_os_failure_returns_false(manager, monkeypatch):
    monkeypatch.setattr(m.os, "geteuid", MagicMock(side_effect=OSError("no euid")))
    assert not manager.check_root_privileges()
    m.error_handler.display_error.assert_called_once()


@pytest.mark.parametrize("failure", [False, True])
def test_user_command_runs_with_explicit_user_argv_no_shell_interpolation(
    manager, monkeypatch, failure
):
    def runner(argv, **kw):
        assert argv[:5] == ["sudo", "-u", "webops", "bash", "-c"]
        assert kw["check"]
        if failure:
            raise subprocess.CalledProcessError(8, argv)
        return SimpleNamespace(stdout="OK", stderr="", returncode=0)

    monkeypatch.setattr(m.subprocess, "run", runner)
    if failure:
        with pytest.raises(subprocess.CalledProcessError):
            manager.run_as_webops_user("true")
    else:
        assert manager.run_as_webops_user("true").stdout == "OK"


def test_user_command_other_os_error_is_reported(manager, monkeypatch):
    monkeypatch.setattr(
        m.subprocess, "run", MagicMock(side_effect=OSError("sudo unavailable"))
    )
    with pytest.raises(OSError):
        manager.run_as_webops_user("true")
    m.error_handler.display_error.assert_called()


@pytest.mark.parametrize("fail", [False, True])
def test_admin_status_collects_process_count_and_system_information(
    manager, monkeypatch, fail
):
    (manager.webops_dir / "deployments").mkdir()

    def runner(argv, **kw):
        if fail:
            raise subprocess.CalledProcessError(1, argv)
        if argv[0] == "id":
            return SimpleNamespace(stdout="uid=1001(webops)\n")
        if argv[0] == "ps":
            return SimpleNamespace(
                stdout="webops 123 nginx\nroot 5 python\nwebops 456 worker\n"
            )
        if argv[0] == "du":
            return SimpleNamespace(stdout="5G /opt/webops\n")
        return SimpleNamespace(stdout="active (running)\nservice ok\n")

    monkeypatch.setattr(m.subprocess, "run", runner)
    status = manager.get_system_status()
    if fail:
        assert status == {}
    else:
        assert status["process_count"] == 2
        assert len(status["processes"]) == 2
        assert status["disk_usage"]
        assert status["services"]


@pytest.mark.parametrize("state", ["running", "stopped", "no service", "unknown"])
def test_deployment_directory_listing_maps_real_service_state(
    manager, monkeypatch, state
):
    deployments = manager.webops_dir / "deployments"
    deployments.mkdir()
    (deployments / "api").mkdir()
    (deployments / "worker.log").touch()

    def runner(argv, **kw):
        if argv[0] == "du":
            return SimpleNamespace(stdout="100M  /path")
        if argv[1] == "is-active":
            if state == "unknown":
                raise subprocess.CalledProcessError(3, argv)
            return SimpleNamespace(returncode=0 if state == "running" else 3, stdout="")
        return SimpleNamespace(
            returncode=0, stdout=("app-api.service" if state == "stopped" else "")
        )

    monkeypatch.setattr(m.subprocess, "run", runner)
    found = manager.get_deployment_list()
    assert len(found) == 1
    assert found[0]["status"] == state


def test_directory_listing_handles_missing_deployment_root(manager):
    assert manager.get_deployment_list() == []


def test_deployment_size_probe_error_uses_unknown_without_abort(manager, monkeypatch):
    folder = manager.webops_dir / "deployments"
    folder.mkdir()
    (folder / "api").mkdir()

    def runner(argv, **kw):
        if argv[0] == "du":
            raise subprocess.CalledProcessError(1, argv)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(m.subprocess, "run", runner)
    found = manager.get_deployment_list()
    assert found[0]["size"] == "unknown"


def test_permission_fix_refuses_non_root_before_any_command(manager, monkeypatch):
    monkeypatch.setattr(manager, "check_root_privileges", lambda: False)
    run = MagicMock()
    monkeypatch.setattr(m.subprocess, "run", run)
    with pytest.raises(SystemExit):
        manager.fix_permissions()
    run.assert_not_called()


def test_permission_fix_limits_writes_to_webops_install_prefix(manager, monkeypatch):
    for name in ("control-panel", "deployments", "backups", ".secrets"):
        (manager.webops_dir / name).mkdir()
    (manager.webops_dir / "control-panel" / "tmp").mkdir()
    monkeypatch.setattr(manager, "check_root_privileges", lambda: True)
    invoked = []
    monkeypatch.setattr(m.subprocess, "run", lambda args, **kw: invoked.append(args))
    manager.fix_permissions()
    assert invoked[0][:2] == ["chown", "-R"]
    assert all(
        str(manager.webops_dir) in " ".join(args)
        for args in invoked
        if args[0] in ("chown", "find", "chmod")
    )
    assert any(args[0] == "chmod" and args[1] == "1777" for args in invoked)


@pytest.fixture
def cmd_manager(manager, monkeypatch):
    monkeypatch.setattr(m, "AdminManager", lambda: manager)
    monkeypatch.setattr(m, "require_root_privileges", lambda *_: None)
    monkeypatch.setattr(m, "handle_exception", MagicMock())
    return manager


@pytest.mark.parametrize("status", ["active", "inactive", "unknown"])
def test_admin_status_click_renders_service_states(cmd_manager, monkeypatch, status):
    monkeypatch.setattr(
        cmd_manager,
        "get_system_status",
        lambda: {"web": {"status": status}, "processes": {"status": "running"}},
    )
    r = CliRunner().invoke(m.admin, ["status"])
    assert r.exit_code == 0, r.output


def test_admin_status_error_handler_is_used(cmd_manager, monkeypatch):
    monkeypatch.setattr(
        cmd_manager,
        "get_system_status",
        MagicMock(side_effect=OSError("status unavailable")),
    )
    assert CliRunner().invoke(m.admin, ["status"]).exit_code == 0
    m.handle_exception.assert_called_once()


@pytest.mark.parametrize("root", [False, True])
def test_admin_shell_requires_root_and_never_runs_real_shell(
    cmd_manager, monkeypatch, root
):
    monkeypatch.setattr(cmd_manager, "check_root_privileges", lambda: root)
    system = MagicMock()
    monkeypatch.setattr(m.os, "system", system)
    result = CliRunner().invoke(m.admin, ["shell"])
    if root:
        assert result.exit_code == 0
        system.assert_called_once()
    else:
        assert result.exit_code != 0
        system.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(stdout="ok", stderr="", returncode=0),
        SimpleNamespace(stdout="", stderr="warning", returncode=0),
    ],
)
def test_admin_run_outputs_both_result_streams(cmd_manager, monkeypatch, response):
    monkeypatch.setattr(cmd_manager, "run_as_webops_user", lambda _: response)
    assert CliRunner().invoke(m.admin, ["run", "echo ok"]).exit_code == 0


def test_admin_run_displays_process_exit_status(cmd_manager, monkeypatch):
    exc = subprocess.CalledProcessError(5, "test", output="partial", stderr="failed")
    monkeypatch.setattr(cmd_manager, "run_as_webops_user", MagicMock(side_effect=exc))
    assert CliRunner().invoke(m.admin, ["run", "false"]).exit_code == 0


def test_admin_run_unexpected_error_routes_through_handler(cmd_manager, monkeypatch):
    monkeypatch.setattr(
        cmd_manager,
        "run_as_webops_user",
        MagicMock(side_effect=PermissionError("not allowed")),
    )
    assert CliRunner().invoke(m.admin, ["run", "true"]).exit_code == 0
    m.handle_exception.assert_called_once()


def test_admin_permissions_cli_calls_manager_only(cmd_manager, monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(cmd_manager, "fix_permissions", mock)
    assert CliRunner().invoke(m.admin, ["fix-permissions"]).exit_code == 0
    mock.assert_called_once()


@pytest.mark.parametrize(
    "deployments",
    [
        [],
        [{"name": "api", "path": "/tmp/api", "size": "1G", "status": "running"}],
        [
            {"name": "api", "path": "/tmp/api", "size": "1G", "status": "stopped"},
            {
                "name": "build",
                "path": "/tmp/build",
                "size": "2G",
                "status": "no service",
            },
            {
                "name": "unknown",
                "path": "/tmp/unknown",
                "size": "?",
                "status": "unknown",
            },
        ],
    ],
)
def test_admin_deployment_list_cli_display_states(
    cmd_manager, monkeypatch, deployments
):
    monkeypatch.setattr(cmd_manager, "get_deployment_list", lambda: deployments)
    assert CliRunner().invoke(m.admin, ["deployments"]).exit_code == 0


@pytest.mark.parametrize("exists,failed", [(False, False), (True, False), (True, True)])
def test_admin_validation_script_missing_success_and_error(
    cmd_manager, monkeypatch, tmp_path, exists, failed
):
    cmd_manager.scripts_dir = tmp_path
    if exists:
        (tmp_path / "validate-user-setup.sh").write_text("echo OK")
    run = MagicMock()
    if failed:
        run.side_effect = subprocess.CalledProcessError(17, ["bash", "validate"])
    monkeypatch.setattr(m.subprocess, "run", run)
    result = CliRunner().invoke(m.admin, ["validate"])
    if exists and not failed:
        assert result.exit_code == 0
    else:
        assert result.exit_code == (17 if failed else 1)


def test_admin_scripts_env_override_and_default_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBOPS_INSTALL_PATH", str(tmp_path))
    monkeypatch.setenv("WEBOPS_SCRIPTS_PATH", str(tmp_path / "scripts"))
    assert m.AdminManager().scripts_dir == tmp_path / "scripts"
    monkeypatch.delenv("WEBOPS_SCRIPTS_PATH")
    assert m.AdminManager().scripts_dir == tmp_path / "scripts"


def test_admin_scripts_recovered_from_broken_path_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBOPS_INSTALL_PATH", str(tmp_path))
    original = Path.exists

    def check(path):
        if path == tmp_path / "scripts":
            raise OSError("filesystem failure")
        return original(path)

    monkeypatch.setattr(Path, "exists", check)
    assert m.AdminManager().scripts_dir == tmp_path / "scripts"


def test_admin_status_inactive_is_red_not_false_positive_green(
    cmd_manager, monkeypatch
):
    monkeypatch.setattr(
        cmd_manager,
        "get_system_status",
        lambda: {"webops-web": "inactive", "worker": {"status": "stopped"}},
    )
    assert CliRunner().invoke(m.admin, ["status"]).exit_code == 0
    tables = [
        c.args[0]
        for c in m.console.print.call_args_list
        if isinstance(c.args[0], m.Table)
    ]
    assert len(tables) == 1
    styles = tables[0].columns[1]._cells
    assert all("[red]" in status for status in styles)
