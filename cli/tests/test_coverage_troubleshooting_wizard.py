"""End-to-end diagnostic decision coverage for the legacy troubleshooting wizard.

Host-level service, file-removal, network, and privileged repair operations are
fully mocked. No test restarts services, deletes files or changes host settings.
"""
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from click.testing import CliRunner
import pytest

from webops_cli.wizards import troubleshooting_wizard as m


@pytest.fixture
def wiz(monkeypatch):
    mock_console = MagicMock()
    monkeypatch.setattr(m, "console", mock_console)
    p = MagicMock()
    p.spinner.return_value = nullcontext()
    p.progress_bar.return_value = nullcontext(MagicMock())
    monkeypatch.setattr(m, "progress_manager", p)
    monkeypatch.setattr(m.time, "sleep", lambda *_: None)
    monkeypatch.setattr(m.Prompt, "ask", MagicMock(return_value=""))
    monkeypatch.setattr(m.Confirm, "ask", MagicMock(return_value=False))
    instance = m.TroubleshootingWizard()
    instance.console = mock_console
    instance.diagnostics = {
        "problem_type": "performance", "app_name": "staging-app",
        "cpu_usage": 10.0, "memory_usage": 20.0,
        "disk_usage": 30.0, "load_average": 0.5,
        "internet_connectivity": True,
    }
    return instance


@pytest.mark.parametrize("blocker", [
    "_step_identify_problem", "_step_system_diagnostics", "_step_service_diagnostics",
    "_step_network_diagnostics", "_step_application_diagnostics",
    "_step_analyze_issues", "_step_apply_fixes", "_step_verify_fixes", None,
])
def test_diagnostic_run_short_circuits_failed_phase(wiz, monkeypatch, blocker):
    visited = []
    methods = [
        "_step_identify_problem", "_step_system_diagnostics", "_step_service_diagnostics",
        "_step_network_diagnostics", "_step_application_diagnostics",
        "_step_analyze_issues", "_step_apply_fixes", "_step_verify_fixes",
    ]
    for method in methods:
        monkeypatch.setattr(wiz, method, lambda name=method:
                            visited.append(name) or name != blocker)
    monkeypatch.setattr(wiz, "_display_summary", lambda: visited.append("summary"))
    assert wiz.run() is (blocker is None)
    assert ("summary" in visited) is (blocker is None)


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), OSError("monitor inaccessible")])
def test_diagnostic_run_reports_interruption_and_error(wiz, monkeypatch, failure):
    errors = MagicMock()
    monkeypatch.setattr(m.error_handler, "display_error", errors)
    monkeypatch.setattr(wiz, "_step_identify_problem", MagicMock(side_effect=failure))
    assert wiz.run() is False
    assert errors.called is isinstance(failure, OSError)


@pytest.mark.parametrize("number,category", [
    ("1", "deployment"), ("2", "performance"), ("3", "connectivity"),
    ("4", "services"), ("5", "ssl"), ("6", "database"),
    ("7", "logs"), ("8", "other"),
])
def test_problem_selection_all_categories_and_optional_application(
    wiz, monkeypatch, number, category
):
    responses = iter(["non-numeric", "10", "0", number, "text description", "app-001"])
    monkeypatch.setattr(m.Prompt, "ask", lambda *_a, **_k: next(responses))
    assert wiz._step_identify_problem()
    assert wiz.diagnostics["problem_type"] == category
    assert wiz.diagnostics["problem_description"] == "text description"
    assert ("app_name" in wiz.diagnostics) or category not in {
        "deployment", "performance", "connectivity", "logs"
    }


def test_problem_selection_allows_blank_application(wiz, monkeypatch):
    responses = iter(["1", "issue", ""])
    monkeypatch.setattr(m.Prompt, "ask", lambda *_a, **_k: next(responses))
    wiz.diagnostics.pop("app_name")
    assert wiz._step_identify_problem()
    assert "app_name" not in wiz.diagnostics


@pytest.mark.parametrize("cpu,mem,disk,internet", [
    (12.5, 23, 42, True), (91, 94, 96, False),
    (99, 12, 11, True), (1, 99, 40, True),
])
def test_system_diagnostics_collects_and_identifies_actual_resource_breaches(
    wiz, monkeypatch, cpu, mem, disk, internet
):
    monkeypatch.setattr(m.psutil, "cpu_percent", lambda **kwargs: cpu)
    monkeypatch.setattr(m.psutil, "virtual_memory",
                        lambda: SimpleNamespace(percent=mem, available=9 * 1024 ** 3))
    monkeypatch.setattr(m.psutil, "disk_usage", lambda path:
                        SimpleNamespace(total=1000, used=10 * disk, free=9 * 1024 ** 3))
    monkeypatch.setattr(m.os, "getloadavg", lambda: (2.5, 1, 1))
    monkeypatch.setattr(wiz, "_check_internet_connectivity", lambda: internet)
    assert wiz._step_system_diagnostics()
    assert wiz.diagnostics["cpu_usage"] == cpu
    assert wiz.diagnostics["memory_available"] == 9
    assert wiz.diagnostics["disk_free"] == 9
    assert wiz.diagnostics["disk_usage"] == pytest.approx(disk)
    assert len(wiz.issues_found) == sum((cpu > 90, mem > 90, disk > 95))


def test_service_diagnostics_uses_all_expected_webops_services(wiz, monkeypatch):
    def status(service):
        return {"active": service == "webops-web", "error": "not running"}
    monkeypatch.setattr(wiz, "_check_service_status", status)
    assert wiz._step_service_diagnostics()
    assert set(wiz.diagnostics["service_status"]) == {
        "webops-web", "webops-celery", "webops-celerybeat"
    }
    assert len(wiz.issues_found) == 2


@pytest.mark.parametrize("all_working", [True, False])
def test_network_diagnostics_all_probes_and_incident_analysis(
    wiz, monkeypatch, all_working
):
    for name in ("_test_localhost_connection", "_test_nginx_config",
                 "_test_ssl_certificates", "_test_dns_resolution"):
        monkeypatch.setattr(wiz, name, lambda status=all_working: {"success": status})
    assert wiz._step_network_diagnostics()
    assert len(wiz.diagnostics["network_tests"]) == 4
    assert len(wiz.issues_found) == (0 if all_working else 2)


@pytest.mark.parametrize("run_app,healthy,errors", [
    (False, True, 0), (True, True, 0), (True, False, 3),
    (True, True, 7),
])
def test_application_diagnostics_skip_or_analyze_real_result_shapes(
    wiz, monkeypatch, run_app, healthy, errors
):
    if not run_app:
        wiz.diagnostics.pop("app_name", None)
        assert wiz._step_application_diagnostics()
        assert "application" not in wiz.diagnostics
        return
    monkeypatch.setattr(wiz, "_check_application_logs", lambda _: {
        "errors_found": errors, "warnings_found": 2
    })
    monkeypatch.setattr(wiz, "_check_application_health",
                        lambda _: {"healthy": healthy, "response_time": 0.2})
    monkeypatch.setattr(wiz, "_check_application_config",
                        lambda _: {"config_valid": True, "missing_vars": []})
    monkeypatch.setattr(wiz, "_check_application_dependencies",
                        lambda _: {"dependencies_ok": True, "missing_dependencies": []})
    assert wiz._step_application_diagnostics()
    assert len(wiz.diagnostics["application"]) == 4
    assert len(wiz.issues_found) == sum((not healthy, errors > 0))


@pytest.mark.parametrize("priorities", [[], ["high"], ["medium", "low", "high"]])
def test_issue_analysis_presentations(wiz, priorities):
    wiz.issues_found = [
        {"priority": p, "category": "Network", "description": "service down",
         "impact": "site unavailable", "fix_available": True,
         "fix_description": "restart"} for p in priorities
    ]
    assert wiz._step_analyze_issues()
    wiz._display_summary()


def example_issue(*, fixable=True, function="restart_services", priority="high"):
    return {
        "priority": priority, "category": "Services",
        "description": f"service {function} is down", "impact": "downtime",
        "fix_available": fixable, "fix_description": "restart if approved",
        "fix_function": function,
        "manual_fix": "Review the logs",
    }


@pytest.mark.parametrize("mode", ["no-issues", "manual-only", "all", "selective-none",
                                  "selective-one", "all-with-failed-fix"])
def test_fix_workflow_never_executes_unapproved_host_changes(
    wiz, monkeypatch, mode
):
    if mode == "no-issues":
        assert wiz._step_apply_fixes()
        return
    wiz.issues_found = [example_issue(fixable=mode != "manual-only")]
    if mode == "manual-only":
        assert wiz._step_apply_fixes()
        return
    monkeypatch.setattr(m.Confirm, "ask", lambda prompt, **kwargs: (
        False if mode.startswith("selective") and
        prompt.startswith("Apply all available") else
        mode != "selective-none"))
    do_fix = MagicMock(return_value=mode != "all-with-failed-fix")
    monkeypatch.setattr(wiz, "_apply_fix", do_fix)
    assert wiz._step_apply_fixes()
    assert len(wiz.fixes_applied) == (0 if mode in ("selective-none", "all-with-failed-fix") else 1)
    assert do_fix.call_count == (0 if mode == "selective-none" else 1)


@pytest.mark.parametrize("fixes", [[], ["restart app"], ["reload nginx", "restart worker"]])
def test_fix_verification_and_summary(wiz, monkeypatch, fixes):
    wiz.fixes_applied = fixes
    monkeypatch.setattr(wiz, "_verify_fix", lambda desc: {
        "success": desc != "reload nginx",
        "notes": "verified" if desc != "reload nginx" else "still unavailable",
    })
    assert wiz._step_verify_fixes()
    wiz._display_summary()


@pytest.mark.parametrize("ok,error", [(True, False), (False, False), (False, True)])
def test_internet_probe_success_failed_and_transport_error(wiz, monkeypatch, ok, error):
    def fake_get(url, **kwargs):
        assert kwargs["timeout"] == 5
        if error:
            raise m.requests.Timeout("offline")
        return SimpleNamespace(status_code=200 if ok else 503)
    monkeypatch.setattr(m.requests, "get", fake_get)
    assert wiz._check_internet_connectivity() is (ok and not error)


@pytest.mark.parametrize("active,throws", [(True, False), (False, False), (False, True)])
def test_systemd_status_validates_failure_and_diagnostic_error(
    wiz, monkeypatch, active, throws
):
    def fake_run(args, **kwargs):
        if throws:
            raise FileNotFoundError("systemctl missing")
        return SimpleNamespace(stdout="active\n" if active else "inactive\n", stderr="")
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    result = wiz._check_service_status("webops-web")
    assert result["active"] is (active and not throws)
    assert ("error" in result) is throws


@pytest.mark.parametrize("reachable", [True, False])
def test_localhost_http_probe_has_bounded_timeout(wiz, monkeypatch, reachable):
    def fake_get(*args, **kwargs):
        assert kwargs["timeout"] == 5
        if not reachable:
            raise m.requests.ConnectionError("connection refused")
        return SimpleNamespace(status_code=200,
                               elapsed=timedelta(milliseconds=42))
    monkeypatch.setattr(m.requests, "get", fake_get)
    response = wiz._test_localhost_connection()
    assert response["success"] is reachable
    if reachable:
        assert response["response_time"] == pytest.approx(0.042)


@pytest.mark.parametrize("valid,throws", [(True, False), (False, False), (False, True)])
def test_nginx_config_probe_handles_status_and_spawn_error(wiz, monkeypatch, valid, throws):
    def runner(*args, **kwargs):
        if throws:
            raise OSError("missing executable")
        return SimpleNamespace(returncode=0 if valid else 1, stderr="configuration error")
    monkeypatch.setattr(m.subprocess, "run", runner)
    result = wiz._test_nginx_config()
    assert result["success"] is (valid and not throws)
    assert ("error" in result and result["error"] is not None) is (not valid or throws)


@pytest.mark.parametrize("dns", [True, False])
def test_dns_resolution_probe(wiz, monkeypatch, dns):
    import socket
    def resolve(host):
        if dns:
            return "8.8.8.8"
        raise socket.gaierror("DNS unavailable")
    monkeypatch.setattr(socket, "gethostbyname", resolve)
    assert wiz._test_dns_resolution()["success"] is dns


def test_placeholder_diagnostics_shapes_document_current_limitations(wiz):
    assert wiz._test_ssl_certificates()["certificates_found"] == 0
    assert wiz._check_application_logs("staging")["errors_found"] == 0
    assert wiz._check_application_health("staging")["healthy"] is True
    assert wiz._check_application_config("staging")["config_valid"] is True
    assert wiz._check_application_dependencies("staging")["dependencies_ok"] is True
    assert wiz._verify_fix("restart process")["success"] is True


@pytest.mark.parametrize("overloaded", [False, True])
def test_resource_status_presentation_both_slo_sides(wiz, overloaded):
    wiz.diagnostics.update(cpu_usage=95 if overloaded else 10,
                           memory_usage=95 if overloaded else 10,
                           disk_usage=98 if overloaded else 10,
                           load_average=6 if overloaded else 0.2,
                           internet_connectivity=not overloaded)
    wiz._display_system_status()
    wiz._display_service_status({
        "active": {"active": True},
        "inactive": {"active": False, "error": "crashed"},
        "no-error": {"active": False},
    })
    wiz._display_network_status({
        "localhost_8000": {"success": not overloaded, "error": "offline"},
        "unknown_probe": {"success": overloaded},
    })


@pytest.mark.parametrize("failing", [True, False])
def test_application_status_combinations(wiz, failing):
    wiz._display_application_status({
        "logs": {"errors_found": 4 if failing else 0, "warnings_found": 2},
        "health": {"healthy": not failing, "response_time": 1.25},
        "config": {"config_valid": not failing, "missing_vars": ["API_KEY"] if failing else []},
        "dependencies": {"dependencies_ok": not failing,
                         "missing_dependencies": ["redis"] if failing else []},
    })


@pytest.mark.parametrize("critical", [False, True])
def test_system_service_network_and_application_issue_priority_analysis(wiz, critical):
    wiz.diagnostics.update(cpu_usage=97 if critical else 15,
                           memory_usage=96 if critical else 20,
                           disk_usage=99 if critical else 35)
    wiz._analyze_system_issues()
    wiz._analyze_service_issues({"a": {"active": not critical}})
    wiz._analyze_network_issues({
        "localhost_8000": {"success": not critical},
        "nginx_config": {"success": not critical},
    })
    wiz._analyze_application_issues({
        "logs": {"errors_found": 3 if critical else 0},
        "health": {"healthy": not critical},
    })
    assert len(wiz.issues_found) == (8 if critical else 0)


@pytest.mark.parametrize("function", [
    "restart_services", "clear_memory", "cleanup_disk", "restart_service",
    "fix_web_access", "fix_nginx_config", "restart_application",
])
def test_fix_routing_requires_identified_function_and_never_guesses(
    wiz, monkeypatch, function
):
    mapping = {
        "restart_services": "_fix_restart_services", "clear_memory": "_fix_clear_memory",
        "cleanup_disk": "_fix_cleanup_disk", "restart_service": "_fix_restart_service",
        "fix_web_access": "_fix_web_access", "fix_nginx_config": "_fix_nginx_config",
        "restart_application": "_fix_restart_application",
    }
    for method in mapping.values():
        monkeypatch.setattr(wiz, method, MagicMock(return_value=True))
    assert wiz._apply_fix({"fix_function": function,
                           "fix_params": {"service": "webops-web"}})
    getattr(wiz, mapping[function]).assert_called_once()


def test_fix_routing_unknown_and_exception_fails_closed(wiz, monkeypatch):
    assert not wiz._apply_fix({"fix_function": "arbitrary_shell_command"})
    monkeypatch.setattr(wiz, "_fix_restart_services",
                        MagicMock(side_effect=OSError("insufficient permissions")))
    assert not wiz._apply_fix({"fix_function": "restart_services"})


@pytest.mark.parametrize("function", [
    "_fix_restart_services", "_fix_clear_memory", "_fix_cleanup_disk",
    "_fix_restart_service", "_fix_web_access", "_fix_nginx_config",
    "_fix_restart_application",
])
@pytest.mark.parametrize("fail", [False, True])
def test_host_fixes_are_bounded_by_subprocess_failure(
    wiz, monkeypatch, function, fail
):
    wiz.diagnostics["app_name"] = "staging-app"
    called = []
    def fake_run(argv, **kw):
        called.append((argv, kw))
        if fail:
            raise PermissionError("permission denied")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    result = (wiz._fix_restart_service("webops-web") if function == "_fix_restart_service"
              else getattr(wiz, function)())
    assert result is (not fail)
    assert len(called) >= 1


def test_restart_app_requires_application_identity(wiz, monkeypatch):
    wiz.diagnostics.pop("app_name", None)
    run = MagicMock()
    monkeypatch.setattr(m.subprocess, "run", run)
    assert not wiz._fix_restart_application()
    run.assert_not_called()


def test_nginx_config_repair_refuses_invalid_syntax(wiz, monkeypatch):
    called = []
    def fake_run(args, **kwargs):
        called.append(args)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    assert not wiz._fix_nginx_config()
    assert called == [["nginx", "-t"]]


def test_manual_fix_display_for_fixable_and_manual_only(wiz):
    wiz.issues_found = [example_issue(), example_issue(fixable=False)]
    wiz._display_manual_fixes()
    assert wiz.console.print.called
    wiz.issues_found = [example_issue()]
    wiz._display_manual_fixes()


@pytest.mark.parametrize("success", [True, False])
def test_troubleshooting_click_entrypoint(monkeypatch, success):
    monkeypatch.setattr(m.TroubleshootingWizard, "run", lambda *_: success)
    response = CliRunner().invoke(m.troubleshoot)
    assert response.exit_code == 0

