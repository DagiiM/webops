"""Security audit routing, file protections, and event provenance."""

import json
import getpass
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from webops_cli import security_logging as m


@pytest.fixture
def logger(tmp_path):
    obj = m.SecurityLogger(log_dir=tmp_path / "logs")
    yield obj
    # Release file handlers, do not leak temporary log descriptors.
    for child in (obj.security_logger, obj.audit_logger):
        for h in list(child.handlers):
            child.removeHandler(h)
            h.close()


def test_default_secure_audit_log_location(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    log = m.SecurityLogger()
    assert log.log_dir == tmp_path / ".webops" / "logs"
    assert (log.log_dir.stat().st_mode & 0o777) == 0o700
    assert (log.security_log_file.stat().st_mode & 0o777) == 0o600


def test_audit_entry_with_optional_client_address(logger):
    entry = logger._create_log_entry(
        m.SecurityEventType.SYSTEM_ACCESS,
        "server login",
        user="staff",
        ip_address="127.0.0.1",
        resource="cluster",
        action="inspect",
        result="SUCCESS",
        severity="INFO",
        details={"tenant": "team"},
    )
    assert entry["ip_address"] == "127.0.0.1"
    assert entry["resource"] == "cluster"
    logger._write_entry(entry)
    rows = [json.loads(x) for x in logger.security_log_file.read_text().splitlines()]
    assert rows[-1]["details"]["tenant"] == "team"
    assert logger.audit_log_file.read_text()


@pytest.mark.parametrize(
    "method,args",
    [
        (
            "log_deployment_operation",
            {
                "user": "alice",
                "operation": "start",
                "deployment": "staging",
                "success": True,
            },
        ),
        (
            "log_deployment_operation",
            {
                "user": "alice",
                "operation": "stop",
                "deployment": "staging",
                "success": False,
            },
        ),
        (
            "log_error",
            {"user": "alice", "error_type": "outage", "error_message": "down"},
        ),
    ],
)
def test_failure_and_successful_operations_always_audited(logger, method, args):
    getattr(logger, method)(**args)
    rows = [json.loads(x) for x in logger.security_log_file.read_text().splitlines()]
    assert rows
    assert rows[-1]["user"] == "alice"


def test_get_user_prefers_environment_and_handles_unavailable_system_login(
    logger, monkeypatch
):
    monkeypatch.setenv("USER", "engineer")
    assert logger.get_user() == "engineer"
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(getpass, "getuser", lambda: "runpod")
    assert logger.get_user() == "runpod"
    monkeypatch.setattr(
        getpass, "getuser", MagicMock(side_effect=RuntimeError("no login"))
    )
    assert logger.get_user() == "unknown"
    assert logger.get_ip_address() is None


@pytest.mark.parametrize(
    "event,target",
    [
        (m.SecurityEventType.AUTHENTICATION, "log_authentication"),
        (m.SecurityEventType.AUTHORIZATION, "log_authorization"),
        (m.SecurityEventType.CONFIGURATION_CHANGE, "log_configuration_change"),
        (m.SecurityEventType.DEPLOYMENT_OPERATION, "log_deployment_operation"),
        (m.SecurityEventType.DATA_ACCESS, "log_data_access"),
        (m.SecurityEventType.SECURITY_VIOLATION, "log_security_violation"),
        (m.SecurityEventType.ERROR, "log_error"),
        (m.SecurityEventType.SYSTEM_ACCESS, "_write_entry"),
    ],
)
def test_security_event_dispatch_covers_all_event_types(monkeypatch, event, target):
    stub = MagicMock()
    stub._create_log_entry.return_value = {"event_type": "system_access"}
    monkeypatch.setattr(m, "get_security_logger", lambda: stub)
    m.log_security_event(event, "test event", user="operator", action="check")
    getattr(stub, target).assert_called_once()


def test_singleton_reuses_current_location_but_switches_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(m, "_security_logger", None)
    first = m.get_security_logger()
    assert m.get_security_logger() is first
    new_root = tmp_path / "other"
    monkeypatch.setattr(Path, "home", lambda: new_root)
    second = m.get_security_logger()
    assert second is not first
    assert second.log_dir == new_root / ".webops" / "logs"
