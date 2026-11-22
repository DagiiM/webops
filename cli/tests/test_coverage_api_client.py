"""Authenticated API method and transport failure contracts."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
import requests
from webops_cli import api as m


@pytest.fixture(params=[False, True], ids=["plain", "secured"])
def client(request, monkeypatch):
    logger = MagicMock()
    logger.get_user.return_value = "operator"
    monkeypatch.setattr(m, "get_security_logger", lambda: logger)
    api = m.WebOpsAPIClient(
        "https://panel.example.org",
        "valid-api-token-12345",
        user_role=m.Role.ADMIN,
        enable_security=request.param,
    )
    api.session.request = MagicMock()
    response = MagicMock()
    response.content = b'{"ok":true}'
    response.json.return_value = {"ok": True}
    api.session.request.return_value = response
    yield api
    api.close()


def test_roles_and_permissions_are_explicit():
    assert m.Role.is_valid_role("admin")
    assert not m.Role.is_valid_role("owner")
    assert "admin" in m.Role.all_roles()
    assert m.Permission.DEPLOYMENT_CREATE in m.Permission.all_permissions()
    assert m.RBACManager("admin").check_permission(m.Permission.SYSTEM_ADMIN)
    assert not m.RBACManager("viewer").check_permission(m.Permission.DEPLOYMENT_CREATE)
    assert m.Permission.DEPLOYMENT_READ in m.RBACManager("viewer").get_permissions()
    with pytest.raises(m.RBACError):
        m.RBACManager("unknown")
    with pytest.raises(m.RBACError):
        m.RBACManager("viewer").require_permission(m.Permission.DEPLOYMENT_DELETE)


@pytest.mark.parametrize(
    "method,args",
    [
        ("get_status", ()),
        ("list_deployments", ()),
        ("get_deployment", ("app",)),
        ("create_deployment", ("app", "https://github.com/org/app.git")),
        ("start_deployment", ("app",)),
        ("stop_deployment", ("app",)),
        ("restart_deployment", ("app",)),
        ("delete_deployment", ("app",)),
        ("get_deployment_logs", ("app",)),
        ("list_databases", ()),
        ("get_database", ("maindb",)),
        ("generate_env", ("app",)),
        ("validate_env", ("app",)),
        ("validate_project", ("app",)),
        ("get_env_vars", ("app",)),
        ("set_env_var", ("app", "DEBUG", "false")),
        ("unset_env_var", ("app", "DEBUG")),
    ],
)
def test_client_methods_route_to_expected_endpoints_and_auth(client, method, args):
    assert getattr(client, method)(*args) == {"ok": True}
    client.session.request.assert_called_once()
    assert client.session.request.call_args.args[1].startswith(
        "https://panel.example.org/api/"
    )


def test_api_context_manager_closes_connections(client):
    original = client.session.close
    client.session.close = MagicMock()
    with client as same:
        assert same is client
    client.session.close.assert_called_once()
    client.session.close = original


def test_paginated_api_filter_and_log_tail(client):
    client.list_deployments(2, 50, "running")
    assert client.session.request.call_args.kwargs["params"] == {
        "page": 2,
        "per_page": 50,
        "status": "running",
    }
    client.get_deployment_logs("app", tail=100)
    assert client.session.request.call_args.kwargs["params"] == {"tail": 100}
    client.get_deployment_logs("app", tail=None)
    assert client.session.request.call_args.kwargs["params"] == {}


def test_deployment_create_env_payload_and_configuration(client):
    client.create_deployment(
        "app",
        "https://github.com/o/r.git",
        branch="staging",
        domain="app.example.org",
        env_vars={"MODE": "staging"},
    )
    payload = client.session.request.call_args.kwargs["json"]
    assert payload["env_vars"] == {"MODE": "staging"}
    client.generate_env(
        "app", debug=True, domain="app.example.org", custom_vars={"MODE": "staging"}
    )
    assert client.session.request.call_args.kwargs["json"] == {
        "debug": True,
        "domain": "app.example.org",
        "custom_vars": {"MODE": "staging"},
    }


def test_empty_body_api_response_is_valid(client):
    response = MagicMock()
    response.content = b""
    client.session.request.return_value = response
    assert client.get_status() == {}


@pytest.mark.parametrize(
    "exception,message",
    [
        (requests.Timeout("waited too long"), "Request timeout"),
        (requests.ConnectionError("offline"), "Connection error"),
        (ValueError("unhandled issue"), "Unexpected error"),
    ],
)
def test_transport_error_wrapped_and_logged(client, exception, message):
    client.session.request.side_effect = exception
    with pytest.raises(m.WebOpsAPIError, match=message):
        client.get_status()


@pytest.mark.parametrize(
    "status,payload",
    [
        (400, {"error": "bad branch"}),
        (401, {"error": "expired token"}),
        (403, {"error": "denied"}),
        (503, {"error": "backend down"}),
    ],
)
def test_http_response_errors_remain_actionable(client, status, payload):
    response = MagicMock(status_code=status, text="upstream failed")
    response.json.return_value = payload
    exc = requests.HTTPError("HTTP failure", response=response)
    client.session.request.return_value = response
    response.raise_for_status.side_effect = exc
    with pytest.raises(m.WebOpsAPIError, match=payload["error"]):
        client.get_status()


def test_http_unparseable_error_uses_response_text(client):
    response = MagicMock(status_code=502, text="bad gateway")
    response.json.side_effect = ValueError("invalid JSON")
    response.raise_for_status.side_effect = requests.HTTPError(
        "oops", response=response
    )
    client.session.request.return_value = response
    with pytest.raises(m.WebOpsAPIError, match="bad gateway"):
        client.get_status()


def test_viewer_role_cannot_mutate_deployments(monkeypatch):
    monkeypatch.setattr(
        m, "get_security_logger", lambda: MagicMock(get_user=lambda: "viewer")
    )
    api = m.WebOpsAPIClient(
        "https://panel.example.org",
        "valid-token-12345",
        user_role=m.Role.VIEWER,
        enable_security=True,
    )
    api.session.request = MagicMock()
    try:
        with pytest.raises(m.RBACError):
            api.create_deployment("app", "https://github.com/o/r.git")
        api.session.request.assert_not_called()
    finally:
        api.close()


def test_token_refresh_with_existing_refresh_key_and_rotation(client):
    client.refresh_token = "refresh-token"
    post = MagicMock()
    post.json.return_value = {
        "access_token": "new-token-12345678",
        "expires_in": 3600,
        "refresh_token": "rotated-refresh",
    }
    client.session.post = MagicMock(return_value=post)
    client.token_expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
    client.get_status()
    if not client.enable_security:
        assert client.token == "valid-api-token-12345"
        return
    assert client.token == "new-token-12345678"
    assert client.refresh_token == "rotated-refresh"
    assert client.token_expiry > datetime.now(timezone.utc)
    client.session.post.assert_called_once()


def test_token_exchange_creates_refresh_credential(client):
    client.token_expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
    exchange = MagicMock()
    exchange.json.return_value = {"refresh_token": "new-refresh"}
    rotate = MagicMock()
    rotate.json.return_value = {"access_token": "new-access"}
    client.session.post = MagicMock(side_effect=[exchange, rotate])
    client.get_status()
    if not client.enable_security:
        client.session.post.assert_not_called()
        return
    assert client.refresh_token == "new-refresh"
    assert client.token == "new-access"
    assert client.session.post.call_count == 2


def test_unexpired_token_does_not_refresh(client):
    client.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    client.session.post = MagicMock()
    client.get_status()
    client.session.post.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    ["exchange_request", "exchange_missing", "refresh_request", "refresh_missing"],
)
def test_token_refresh_fails_closed_without_usable_credentials(client, failure):
    client.token_expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
    client.refresh_token = None if failure.startswith("exchange") else "refresh-token"
    if failure == "exchange_request":
        client.session.post = MagicMock(side_effect=requests.Timeout("auth offline"))
    elif failure == "exchange_missing":
        exchange = MagicMock()
        exchange.json.return_value = {}
        client.session.post = MagicMock(return_value=exchange)
    elif failure == "refresh_request":
        client.session.post = MagicMock(
            side_effect=requests.ConnectionError("auth unreachable")
        )
    else:
        response = MagicMock()
        response.json.return_value = {}
        client.session.post = MagicMock(return_value=response)
    if client.enable_security:
        with pytest.raises(m.TokenExpiredError):
            client.get_status()
        client.session.request.assert_not_called()
    else:
        assert client.get_status() == {"ok": True}
        client.session.post.assert_not_called()


def test_optional_no_token_expiry_skips_refresh(client):
    client._validate_token()
    client.token_expiry = None
    client._validate_token()


def test_authorization_logging_has_no_live_http(client):
    if client.enable_security:
        client.security_logger.log_data_access.assert_not_called()
        client.get_status()
        client.security_logger.log_data_access.assert_called_once()


@pytest.mark.parametrize("bad_name", ["bad/name", "name with spaces"])
def test_secured_client_validates_mutating_deployment_names(monkeypatch, bad_name):
    monkeypatch.setattr(
        m, "get_security_logger", lambda: MagicMock(get_user=lambda: "admin")
    )
    client = m.WebOpsAPIClient(
        "https://panel.example.org",
        "valid-token-123456",
        user_role=m.Role.ADMIN,
        enable_security=True,
    )
    client.session.request = MagicMock()
    try:
        with pytest.raises(m.ValidationError):
            client.start_deployment(bad_name)
        client.session.request.assert_not_called()
    finally:
        client.close()


def test_refresh_token_exchange_failure_never_reuses_expired_bearer(client):
    client.token_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
    client.session.post = MagicMock(side_effect=requests.HTTPError("401"))
    if client.enable_security:
        with pytest.raises(m.TokenExpiredError):
            client.list_deployments()
        client.session.request.assert_not_called()
    else:
        assert client.list_deployments() == {"ok": True}
        client.session.post.assert_not_called()
