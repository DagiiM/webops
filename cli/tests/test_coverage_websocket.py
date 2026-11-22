"""WebSocket protocol, reconnection, and monitoring state tests with no live sockets."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from websockets.exceptions import ConnectionClosed
from webops_cli import websocket_client as m


@pytest.fixture
def socket(monkeypatch):
    cfg = MagicMock()
    cfg.get_url.return_value = "https://panel.example.org/"
    cfg.get_token.return_value = "token-123"
    c = m.WebSocketClient(cfg)
    c.console = MagicMock()
    return c


@pytest.mark.parametrize(
    "url,result",
    [
        ("https://panel.example.org/", "wss://panel.example.org/ws/events/"),
        ("http://localhost:8000", "ws://localhost:8000/ws/events/"),
    ],
)
def test_websocket_transport_scheme_and_path(socket, url, result):
    socket.config.get_url.return_value = url
    assert socket.get_websocket_url("/ws/events/") == result


def test_websocket_missing_configuration_rejected(socket):
    socket.config.get_url.return_value = None
    with pytest.raises(ValueError):
        socket.get_websocket_url("ws/events")


@pytest.mark.asyncio
async def test_websocket_connection_binds_bearer_only_to_socket(socket, monkeypatch):
    remote = AsyncMock()
    connect = AsyncMock(return_value=remote)
    monkeypatch.setattr(m.websockets, "connect", connect)
    assert await socket.connect("ws/events/")
    args = connect.call_args
    assert args.kwargs["additional_headers"] == {"Authorization": "Bearer token-123"}
    assert args.kwargs["ping_timeout"] == 10
    assert socket.is_connected and socket.reconnect_attempts == 0
    await socket.disconnect()
    remote.close.assert_awaited_once()
    assert socket.websocket is None and not socket.is_connected


@pytest.mark.asyncio
async def test_websocket_without_auth_token_omits_header(socket, monkeypatch):
    socket.config.get_token.return_value = ""
    connect = AsyncMock(return_value=AsyncMock())
    monkeypatch.setattr(m.websockets, "connect", connect)
    assert await socket.connect("ws/status")
    assert connect.call_args.kwargs["additional_headers"] == {}


@pytest.mark.asyncio
async def test_websocket_connect_error_returns_false(socket, monkeypatch):
    monkeypatch.setattr(
        m.websockets, "connect", AsyncMock(side_effect=OSError("gateway offline"))
    )
    assert not await socket.connect("ws/status")
    assert not socket.is_connected


@pytest.mark.asyncio
async def test_disconnected_send_rejected_and_receive_returns_none(socket):
    with pytest.raises(ConnectionError):
        await socket.send_message({"type": "ping"})
    assert await socket.receive_message() is None
    await socket.disconnect()
    assert not socket.is_connected


@pytest.mark.asyncio
async def test_socket_sends_json_and_receives_structured_message(socket):
    remote = AsyncMock()
    remote.recv.return_value = '{"type":"deployment_status","status":"running"}'
    socket.websocket = remote
    socket.is_connected = True
    await socket.send_message({"type": "ping", "timestamp": 1})
    remote.send.assert_awaited_once_with('{"type": "ping", "timestamp": 1}')
    assert await socket.receive_message() == {
        "type": "deployment_status",
        "status": "running",
    }


@pytest.mark.asyncio
async def test_malformed_socket_json_is_ignored(socket):
    socket.websocket = AsyncMock()
    socket.is_connected = True
    socket.websocket.recv.return_value = "INVALID JSON"
    assert await socket.receive_message() is None
    socket.console.print.assert_called()


@pytest.mark.asyncio
async def test_socket_remote_close_does_not_falsely_look_connected(socket):
    socket.websocket = AsyncMock()
    socket.is_connected = True
    socket.websocket.send.side_effect = ConnectionClosed(None, None)
    with pytest.raises(ConnectionClosed):
        await socket.send_message({"type": "ping"})
    assert not socket.is_connected
    socket.is_connected = True
    socket.websocket.recv.side_effect = ConnectionClosed(None, None)
    assert await socket.receive_message() is None
    assert not socket.is_connected


@pytest.mark.asyncio
@pytest.mark.parametrize("reconnect", [False, True])
async def test_failed_connect_retries_only_within_limit(socket, monkeypatch, reconnect):
    socket.max_reconnect_attempts = 2
    socket.connect = AsyncMock(return_value=False)
    socket.disconnect = AsyncMock()
    monkeypatch.setattr(m.asyncio, "sleep", AsyncMock())
    await socket.listen_for_updates("ws/", lambda msg: None, auto_reconnect=reconnect)
    assert socket.connect.await_count == (3 if reconnect else 1)
    socket.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_incoming_events_pass_to_handler_and_cancel_cleanly(socket):
    socket.is_connected = True
    socket.send_message = AsyncMock()
    messages = iter([{"type": "deployment_status", "status": "running"}, None])
    socket.receive_message = AsyncMock(side_effect=lambda: next(messages))

    # Stop after the first batch; next ping yields KeyboardInterrupt.
    async def ping(*args):
        if socket.send_message.await_count > 1:
            raise KeyboardInterrupt()

    socket.send_message.side_effect = ping
    socket.disconnect = AsyncMock()
    seen = []
    await socket.listen_for_updates("ws/", seen.append, auto_reconnect=False)
    assert seen == [{"type": "deployment_status", "status": "running"}]
    socket.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_listen_transport_exception_fails_closed_without_unbounded_retries(
    socket,
):
    socket.is_connected = True
    socket.send_message = AsyncMock(side_effect=OSError("connection died"))
    socket.disconnect = AsyncMock()
    await socket.listen_for_updates("ws/", lambda *_: None, auto_reconnect=False)
    assert not socket.is_connected
    socket.disconnect.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "deployment_status",
        "deployment_status_update",
        "deployment_logs",
        "pong",
        "unknown",
    ],
)
async def test_deployment_monitor_routes_live_events(kind):
    monitor = m.DeploymentStatusMonitor(MagicMock())
    monitor.console = MagicMock()
    monitor.client.disconnect = AsyncMock()
    updater = MagicMock()
    logs = MagicMock()
    monitor._display_status_update = updater
    monitor._display_logs = logs

    async def collect(endpoint, handler):
        assert endpoint == "ws/deployments/app-42/"
        handler(
            {
                "type": kind,
                "deployment": {"name": "app-42", "status": "building"},
                "status": "running",
                "message": "live",
                "logs": ["INFO online"],
            }
        )

    monitor.client.listen_for_updates = collect
    await monitor.monitor_deployment("app-42")
    if kind in ("deployment_status", "deployment_status_update"):
        updater.assert_called_once()
    if kind == "deployment_logs":
        logs.assert_called_once_with(["INFO online"])
    monitor.client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_deployment_monitor_gracefully_handles_operator_interrupt():
    monitor = m.DeploymentStatusMonitor(MagicMock())
    monitor.client.disconnect = AsyncMock()

    async def interrupted(*args):
        raise KeyboardInterrupt()

    monitor.client.listen_for_updates = interrupted
    await monitor.monitor_deployment("app-42")
    monitor.client.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "state",
    [
        "running",
        "stopped",
        "starting",
        "stopping",
        "error",
        "deploying",
        "unrecognized",
    ],
)
def test_deployment_status_display_all_states(state):
    monitor = m.DeploymentStatusMonitor(MagicMock())
    monitor.console = MagicMock()
    monitor.current_status = {
        "name": "app",
        "status": state,
        "message": "status changed",
    }
    monitor._display_status_update()
    monitor.console.print.assert_called_once()


def test_deployment_status_no_data_is_noop():
    monitor = m.DeploymentStatusMonitor(MagicMock())
    monitor.console = MagicMock()
    monitor._display_status_update()
    monitor.console.print.assert_not_called()
    monitor._display_logs([])
    monitor.console.print.assert_not_called()
    monitor._display_logs(["INFO started", "ERROR warning"])
    assert monitor.console.print.call_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["deployment_update", "deployment_status", "unknown"])
async def test_deployment_list_monitor_routes_events(kind):
    monitor = m.DeploymentListMonitor(MagicMock())
    monitor.client.disconnect = AsyncMock()
    monitor.console = MagicMock()
    update = MagicMock()
    change = MagicMock()
    monitor._display_deployment_update = update
    monitor._display_status_change = change

    async def source(endpoint, handler):
        assert endpoint == "ws/deployments/"
        handler(
            {
                "type": kind,
                "deployment": {"name": "webapp", "status": "running"},
                "deployment_id": "app-1",
                "status": "running",
                "message": "started",
            }
        )

    monitor.client.listen_for_updates = source
    await monitor.monitor_deployments()
    update.assert_called_once() if kind == "deployment_update" else update.assert_not_called()
    change.assert_called_once() if kind == "deployment_status" else change.assert_not_called()
    monitor.client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_deployment_list_monitor_user_interrupt():
    monitor = m.DeploymentListMonitor(MagicMock())
    monitor.client.disconnect = AsyncMock()

    async def cancel(*args):
        raise KeyboardInterrupt()

    monitor.client.listen_for_updates = cancel
    await monitor.monitor_deployments()
    monitor.client.disconnect.assert_awaited_once()


@pytest.mark.parametrize("message", [{"name": "web", "status": "running"}, {}])
def test_list_monitor_visualizations_and_change_notices(message):
    monitor = m.DeploymentListMonitor(MagicMock())
    monitor.console = MagicMock()
    monitor._display_deployment_update(message)
    monitor._display_status_change("app-1", "running", "")
    monitor._display_status_change("app-1", "failed", "rejected")
    assert monitor.console.print.call_count == 4


@pytest.mark.asyncio
async def test_listen_user_interrupt_releases_socket_without_retrying(socket):
    socket.is_connected = True
    socket.send_message = AsyncMock(side_effect=KeyboardInterrupt())
    socket.disconnect = AsyncMock()
    await socket.listen_for_updates("ws/", lambda msg: None, auto_reconnect=True)
    socket.disconnect.assert_awaited_once()
    assert socket.reconnect_attempts == 0


@pytest.mark.asyncio
async def test_socket_transport_error_reconnects_once_then_fails_closed(
    socket, monkeypatch
):
    socket.is_connected = True
    socket.max_reconnect_attempts = 1
    socket.send_message = AsyncMock(side_effect=OSError("network disconnected"))
    socket.connect = AsyncMock(return_value=False)
    socket.disconnect = AsyncMock()
    backoff = AsyncMock()
    monkeypatch.setattr(m.asyncio, "sleep", backoff)
    await socket.listen_for_updates(
        "ws/deployments/", lambda msg: None, auto_reconnect=True
    )
    assert socket.reconnect_attempts == 1
    backoff.assert_awaited_once_with(socket.reconnect_delay)
    socket.connect.assert_awaited_once()
    socket.disconnect.assert_awaited_once()
