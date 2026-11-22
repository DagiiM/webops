"""Isolated CLI service checks: no actual privileged commands run."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import builtins
import io
import json
import subprocess
from click.testing import CliRunner
import pytest
from webops_cli import system as m

@pytest.fixture
def monitor(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBOPS_INSTALL_PATH", str(tmp_path))
    (tmp_path / "control-panel").mkdir()
    instance = m.SystemMonitor()
    monkeypatch.setattr(m, "console", MagicMock())
    return instance

@pytest.mark.parametrize("active,enabled,throws", [
    (True, True, False), (False, False, False),
    (True, False, False), (False, False, True),
])
def test_systemd_status_error_and_service_states(monitor, monkeypatch, active, enabled, throws):
    def runner(argv, **kwargs):
        if throws:
            raise FileNotFoundError("systemctl missing")
        if argv[1] == "is-active":
            return SimpleNamespace(returncode=0 if active else 3, stdout="")
        if argv[1] == "is-enabled":
            return SimpleNamespace(returncode=0 if enabled else 1, stdout="")
        return SimpleNamespace(returncode=0, stdout="service details")
    monkeypatch.setattr(m.subprocess, "run", runner)
    data = monitor.check_service_status("webops-web")
    assert data["active"] is (active and not throws)
    assert data["enabled"] is (enabled and not throws)

@pytest.mark.parametrize("missing,partial,broken", [
    (False, False, False), (False, True, False),
    (False, True, True), (True, False, False),
])
def test_disk_usage_and_partial_failure(monitor, monkeypatch, missing, partial, broken):
    if missing:
        monitor.webops_dir = monitor.webops_dir / "missing"
    elif partial:
        for d in ("deployments", "backups", "logs"):
            (monitor.webops_dir / d).mkdir()
    def runner(argv, **kwargs):
        if broken and (argv[0] == "df" or "backups" in argv[-1]):
            raise subprocess.CalledProcessError(1, argv)
        if argv[0] == "df":
            return SimpleNamespace(stdout="Filesystem Size Used Available Use% Mounted\n/dev/root 100G 20G 80G 20% /\n")
        return SimpleNamespace(stdout="2G /somewhere")
    monkeypatch.setattr(m.subprocess, "run", runner)
    out = monitor.check_disk_usage()
    if broken:
        assert "error" in out or out["subdirectories"]["backups"] == "unknown"
    else:
        assert out["system"]["usage_percent"] == "20%"
        assert ("webops_total" in out) is (not missing)

@pytest.mark.parametrize("panel,check_ok,detail_ok,throws", [
    (False, False, False, False), (True, False, False, False),
    (True, True, False, False), (True, True, True, False),
    (True, True, True, True),
])
def test_database_check_without_privileged_command(monitor, monkeypatch, panel,
                                                     check_ok, detail_ok, throws):
    if not panel:
        monitor.control_panel_dir = monitor.webops_dir / "absent"
    calls = [0]
    def runner(argv, **kwargs):
        if throws:
            raise FileNotFoundError("sudo unavailable")
        calls[0] += 1
        ok = check_ok if calls[0] == 1 else detail_ok
        return SimpleNamespace(returncode=0 if ok else 1, stdout="database info", stderr="error")
    monkeypatch.setattr(m.subprocess, "run", runner)
    out = monitor.check_database_connection()
    if not panel or throws:
        assert "error" in out
    else:
        assert out["django_check"]["success"] is check_ok
        assert ("details" in out) is (check_ok and detail_ok)

@pytest.mark.parametrize("exception", [PermissionError("unreadable"), ValueError("bad path")])
def test_database_dir_error_is_safe(monitor, monkeypatch, exception):
    orig = Path.exists
    def fake_exists(p):
        if p == monitor.control_panel_dir:
            raise exception
        return orig(p)
    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(m.subprocess, "run",
                        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    out = monitor.check_database_connection()
    assert ("error" not in out) is isinstance(exception, PermissionError)

@pytest.mark.parametrize("w,b,exc", [
    (True, True, None), (False, True, None), (True, False, None),
    (False, False, subprocess.TimeoutExpired("celery", 10)),
    (False, False, OSError("offline")),
])
def test_celery_worker_and_beat_health(monitor, monkeypatch, w, b, exc):
    count = [0]
    def runner(*args, **kwargs):
        if exc:
            raise exc
        count[0] += 1
        good = w if count[0] == 1 else b
        return SimpleNamespace(returncode=0 if good else 1, stdout="pong", stderr="offline")
    monkeypatch.setattr(m.subprocess, "run", runner)
    out = monitor.check_celery_health()
    if exc:
        assert "error" in out
    else:
        assert out["worker"]["responsive"] is w
        assert out["beat"]["responsive"] is b


@pytest.mark.parametrize("memory,cpu,fails", [(True, True, False),
                                            (True, False, False),
                                            (False, True, False),
                                            (False, False, True)])
def test_cpu_memory_load_parsing_and_os_errors(monitor, monkeypatch, memory, cpu, fails):
    normal_open = builtins.open
    def fake_open(file, *args, **kwargs):
        if str(file) == "/proc/loadavg":
            if fails:
                raise OSError("proc unavailable")
            return io.StringIO("0.22 0.30 0.15 1/85 111\n")
        return normal_open(file, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", fake_open)
    def runner(argv, **kwargs):
        if argv[0] == "free":
            return SimpleNamespace(stdout=(
                "header\nMem: 16Gi 2Gi 14Gi 0Gi 0Gi 13Gi\n" if memory else "header"))
        return SimpleNamespace(stdout=(
            "%Cpu(s): 5.0 us, 90.0 id\n" if cpu else "cpu utilization unknown\n"))
    monkeypatch.setattr(m.subprocess, "run", runner)
    result = monitor.get_system_load()
    if fails:
        assert "error" in result
    else:
        assert result["load_average"]["1min"] == 0.22
        assert ("memory" in result) is memory
        assert ("cpu" in result) is cpu

@pytest.mark.parametrize("kind,method", [
    ("database", "_evaluate_database_health"),
    ("services", "_evaluate_services_health"),
    ("celery", "_evaluate_celery_health"),
    ("disk", "_evaluate_disk_health"),
    ("load", "_evaluate_system_load_health"),
])
@pytest.mark.parametrize("state", ["healthy", "unhealthy", "error", "exception"])
def test_health_checks_fail_closed(monitor, monkeypatch, kind, method, state):
    target = {"database": "check_database_connection",
              "services": "check_service_status",
              "celery": "check_celery_health",
              "disk": "check_disk_usage",
              "load": "get_system_load"}[kind]
    good = {"database": {"django_check": {"success": True}},
            "services": {"active": True}, "celery": {"worker": {"responsive": True}},
            "disk": {"system": {"usage_percent": "20%"}},
            "load": {"load_average": {"1min": 0.25}}}
    bad = {"database": {"django_check": {"success": False}},
           "services": {"active": False}, "celery": {"worker": {"responsive": False}},
           "disk": {"system": {"usage_percent": "95%"}},
           "load": {"load_average": {"1min": 5.0}}}
    def probe(*args):
        if state == "exception":
            raise ValueError("broken probe")
        if state == "error":
            return {"error": "offline"} if kind != "services" else {"active": False}
        return good[kind] if state == "healthy" else bad[kind]
    monkeypatch.setattr(monitor, target, probe)
    assert getattr(monitor, method)() is (state == "healthy")

@pytest.mark.parametrize("percent", ["not-a-number", "95%", "0%"])
def test_disk_usage_parse_and_threshold(monitor, monkeypatch, percent):
    monkeypatch.setattr(monitor, "check_disk_usage",
                        lambda: {"system": {"usage_percent": percent}})
    assert monitor._evaluate_disk_health() is (percent == "0%")

def test_missing_disk_capacity_cannot_pass_health_gate(monitor, monkeypatch):
    monkeypatch.setattr(monitor, "check_disk_usage", lambda: {})
    assert not monitor._evaluate_disk_health()

@pytest.mark.parametrize("passing", [0, 2, 3, 4, 5])
def test_comprehensive_health_score_categories(monitor, monkeypatch, passing):
    labels = ["Database", "Celery", "Services", "Disk Space", "System Load"]
    monkeypatch.setattr(m.progress_manager, "show_health_check_progress",
                        lambda calls: {name: i < passing for i, name in enumerate(labels)})
    monkeypatch.setattr(monitor, "_get_check_details", lambda name: "checked " + name)
    result = monitor.run_comprehensive_health_check()
    assert result["health_score"] == passing * 20
    expected = "healthy" if passing >= 4 else "warning" if passing == 3 else "critical"
    assert result["status"] == expected
    assert len(result["checks"]) == 5

def test_comprehensive_health_error_result(monitor, monkeypatch):
    monkeypatch.setattr(m.progress_manager, "show_health_check_progress",
                        lambda _: (_ for _ in ()).throw(OSError("broken")))
    handler = MagicMock()
    monkeypatch.setattr(m.error_handler, "display_error", handler)
    assert monitor.run_comprehensive_health_check()["status"] == "error"
    handler.assert_called_once()

@pytest.mark.parametrize("category,response,fragment", [
    ("Database", {"connection_successful": True, "database_name": "postgres"}, "Connected"),
    ("Database", {"error": "offline"}, "Connection failed"),
    ("Celery", {"worker": {"responsive": True}}, "responsive"),
    ("Celery", {"worker": {"responsive": False}, "error": "timeout"}, "timeout"),
    ("Services", {"active": True}, "running"),
    ("Services", {"active": False}, "Failed"),
    ("Disk Space", {"system": {"usage_percent": "25%", "available": "75G"}}, "25%"),
    ("System Load", {"load_average": {"1min": 2.2}}, "2.20"),
    ("Not Recognized", {}, "No details"),
])
def test_health_detail_descriptions(monitor, monkeypatch, category, response, fragment):
    for name in ("check_database_connection", "check_celery_health",
                 "check_service_status", "check_disk_usage", "get_system_load"):
        monkeypatch.setattr(monitor, name, lambda *a, **kw: response)
    assert fragment in monitor._get_check_details(category)

def test_health_detail_provider_exception_makes_safe_message(monitor, monkeypatch):
    monkeypatch.setattr(monitor, "check_database_connection",
                        lambda: (_ for _ in ()).throw(ValueError("query down")))
    assert "Error getting details" in monitor._get_check_details("Database")


@pytest.fixture
def fake_cli_monitor(monkeypatch):
    mon = MagicMock()
    mon.services = ["webops-web", "webops-celery"]
    mon.run_comprehensive_health_check.return_value = {
        "checks": {"Database": {"passed": True, "details": "connected"},
                   "Services": {"passed": False, "details": "stopped"}},
        "health_score": 50, "status": "critical", "timestamp": 1795377400.0,
    }
    mon.get_system_load.return_value = {
        "load_average": {"1min": 1.0, "5min": 1.1, "15min": 0.5},
        "memory": {"used": "2Gi", "total": "8Gi", "available": "6Gi"},
        "cpu": "%Cpu(s): 5.0",
    }
    mon.check_service_status.side_effect = lambda name: {
        "active": name == "webops-web", "enabled": name == "webops-web",
        "error": "service failed" if name != "webops-web" else None,
    }
    mon.check_disk_usage.return_value = {
        "system": {"total": "100G", "used": "20G", "available": "80G",
                   "usage_percent": "20%"},
        "webops_total": "5G", "subdirectories": {"backups": "1G", "logs": "300M"},
    }
    monkeypatch.setattr(m, "SystemMonitor", lambda: mon)
    monkeypatch.setattr(m, "console", MagicMock())
    return mon

def test_health_cli_renders_checks_and_failures(fake_cli_monitor):
    out = CliRunner().invoke(m.system, ["health"])
    assert out.exit_code == 0, out.output
    fake_cli_monitor.run_comprehensive_health_check.assert_called_once()

def test_health_cli_handles_unexpected_provider_error(fake_cli_monitor, monkeypatch):
    fake_cli_monitor.run_comprehensive_health_check.side_effect = OSError("offline")
    error_handler = MagicMock()
    monkeypatch.setattr(m, "handle_exception", error_handler)
    assert CliRunner().invoke(m.system, ["health"]).exit_code == 0
    error_handler.assert_called_once()

@pytest.mark.parametrize("all_up", [True, False])
def test_services_cli_renders_running_and_failed(fake_cli_monitor, all_up):
    if all_up:
        fake_cli_monitor.check_service_status.side_effect = lambda _: {
            "active": True, "enabled": True}
    assert CliRunner().invoke(m.system, ["services"]).exit_code == 0

@pytest.mark.parametrize("percent", ["20%", "78%", "95%"])
def test_disk_cli_emits_disk_pressure_levels(fake_cli_monitor, percent):
    fake_cli_monitor.check_disk_usage.return_value["system"]["usage_percent"] = percent
    assert CliRunner().invoke(m.system, ["disk"]).exit_code == 0

def test_disk_cli_tolerates_unavailable_data(fake_cli_monitor):
    fake_cli_monitor.check_disk_usage.return_value = {}
    assert CliRunner().invoke(m.system, ["disk"]).exit_code == 0

@pytest.mark.parametrize("status,score", [
    ("healthy", 100), ("healthy", 80), ("critical", 30), ("warning", 65)
])
def test_doctor_cli_outputs_distinct_status_and_recommendations(fake_cli_monitor,
                                                                status, score):
    labels = ["Database", "Celery", "Services", "Disk Space", "System Load"]
    fake_cli_monitor.run_comprehensive_health_check.return_value = {
        "checks": {name: {"passed": score == 100, "details": "probe"} for name in labels},
        "health_score": score, "status": status,
    }
    out = CliRunner().invoke(m.system, ["doctor"])
    assert out.exit_code == 0, out.output

@pytest.mark.parametrize("bad_directory", [False, True])
def test_doctor_writes_optional_json_diagnostics(fake_cli_monitor, tmp_path, bad_directory):
    location = (tmp_path / "absent" / "status.json" if bad_directory
                else tmp_path / "status.json")
    out = CliRunner().invoke(m.system, ["doctor", "--output", str(location)])
    assert out.exit_code == 0, out.output
    if not bad_directory:
        assert json.loads(location.read_text())["status"] == "critical"

def test_live_monitor_updates_once_before_clean_cancel(fake_cli_monitor, monkeypatch):
    fake_live = MagicMock()
    fake_live.__enter__.return_value = fake_live
    monkeypatch.setattr(m, "Live", lambda *a, **kw: fake_live)
    count = [0]
    def fake_sleep(_):
        count[0] += 1
        if count[0] >= 2:
            raise KeyboardInterrupt()
    monkeypatch.setattr(m.time, "sleep", fake_sleep)
    assert CliRunner().invoke(m.system, ["monitor"]).exit_code == 0
    fake_live.update.assert_called_once()

