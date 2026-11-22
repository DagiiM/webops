"""Previously untested edge branches with real failure and authorization assertions."""

import os
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from webops_cli import admin as adm
from webops_cli import config as config_module
from webops_cli import project_setup as project_module
from webops_cli import system as system_module
from webops_cli.errors import WebOpsError


def test_git_clone_non_github_ssh_remote_requires_https(monkeypatch, tmp_path):
    workflow = project_module.ProjectSetupWorkflow(MagicMock())
    workflow.temp_dir = tmp_path
    clone = MagicMock()
    monkeypatch.setattr(project_module.Repo, "clone_from", clone)
    ok, message, _ = workflow.clone_project("git@gitlab.com:team/project.git", "app")
    assert not ok
    assert "Only HTTPS" in message
    clone.assert_not_called()


def test_admin_uses_repo_scripts_fallback_when_install_dir_absent(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("WEBOPS_INSTALL_PATH", str(tmp_path))
    monkeypatch.delenv("WEBOPS_SCRIPTS_PATH", raising=False)
    source = Path(adm.__file__).resolve().parents[2] / "scripts"
    original = Path.exists

    def exists(path):
        if path == source:
            return True
        return original(path)

    monkeypatch.setattr(Path, "exists", exists)
    assert adm.AdminManager().scripts_dir == source


def test_disk_subdirectory_failure_does_not_hide_other_usage(monkeypatch, tmp_path):
    monitor = system_module.SystemMonitor()
    monitor.webops_dir = tmp_path
    (tmp_path / "backups").mkdir()

    def runner(args, **kwargs):
        if args[:1] == ["df"]:
            return SimpleNamespace(
                stdout="Filesystem Size Used Avail Use% Mounted\n/dev/root 100G 30G 70G 30% /\n"
            )
        if args[0] == "du" and args[-1].endswith("backups"):
            raise system_module.subprocess.CalledProcessError(1, args)
        return SimpleNamespace(stdout="1G /path")

    monkeypatch.setattr(system_module.subprocess, "run", runner)
    data = monitor.check_disk_usage()
    assert data["system"]["usage_percent"] == "30%"
    assert data["subdirectories"]["backups"] == "unknown"


def test_config_backup_skips_when_no_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    c = config_module.Config()
    assert not c.config_file.exists()
    assert c._create_backup() is None
    assert c.list_backups() == []


def test_config_backup_retention_deletes_oldest_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    c = config_module.Config()
    c.save({"backup_count": 2, "role": "viewer"}, create_backup=False)
    files = []
    for n in range(6):
        path = c.backup_dir / f"config_20261122_{n:06d}.json"
        path.write_text("{}")
        os.utime(path, (100 + n, 100 + n))
        files.append(path)
    c._cleanup_old_backups()
    assert [path.name for path in c.backup_dir.glob("config_*.json")] == [
        files[-2].name,
        files[-1].name,
    ]


def test_quick_logs_reports_authorization_failure_without_leaking_data(monkeypatch):
    import webops_cli.command_shortcuts as module

    monkeypatch.setattr(module, "console", MagicMock())
    api = MagicMock()
    api.get_deployment_logs.side_effect = WebOpsError("denied")
    cmd = module.CommandShortcuts(api, MagicMock())
    cmd.quick_logs("staging")
    assert module.console.print.called


def test_package_module_main_dispatches_to_real_click_entrypoint(monkeypatch):
    import webops_cli.cli as module

    runner = MagicMock()
    monkeypatch.setattr(module, "main", runner)
    runpy.run_module("webops_cli.__main__", run_name="__main__")
    runner.assert_called_once()
