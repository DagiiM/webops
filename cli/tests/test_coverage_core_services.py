"""Security-focused boundary and failure tests for the deployment core."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import subprocess

from click.testing import CliRunner
import pytest

from webops_cli import resilience as r
from webops_cli import deployment_flow as flow
from webops_cli import one_deploy_command as command
from webops_cli.ui import display


@pytest.mark.parametrize("capacity,refill", [
    (0, 1), (-3, 1), (5, -1), (5, float("nan")), (5, float("inf"))
])
def test_token_bucket_rejects_invalid_resource_limits(capacity, refill):
    with pytest.raises(ValueError):
        r.TokenBucket(capacity, refill)


def test_rate_limiter_refuses_backwards_clock():
    now = [100.0]
    b = r.TokenBucket(1, 1, lambda: now[0])
    now[0] = 99.0
    with pytest.raises(ValueError, match="backwards"):
        b.consume()


@pytest.mark.parametrize("threshold,reset", [(0, 1), (3, 0), (3, float("nan")),
                                              (3, float("inf"))])
def test_circuit_breaker_rejects_bad_policy(threshold, reset):
    with pytest.raises(ValueError):
        r.CircuitBreaker(threshold, reset)


@pytest.mark.parametrize("policy", [
    {"attempts": 0}, {"attempts": 17},
    {"base_delay": float("inf")}, {"base_delay": -1},
    {"max_delay": 0.01, "base_delay": 0.02}
])
def test_bounded_retry_configuration_errors(policy):
    with pytest.raises(ValueError):
        r.RetryPolicy(**policy)


def test_retry_delay_rejects_negative_index():
    with pytest.raises(ValueError):
        r.RetryPolicy().delay(-1)


def test_negative_concurrency_limit_fails():
    with pytest.raises(ValueError):
        r.ConcurrencyLimiter(0)


@pytest.mark.parametrize("event", ["", "e" * 129])
def test_invalid_event_identifiers_never_mutate_deployment_state(event):
    machine = r.DeploymentState()
    with pytest.raises(ValueError):
        machine.advance("validated", event)
    assert machine.state == "planned"


@pytest.mark.parametrize("kw", [
    {"capacity": 0}, {"capacity": 2, "min_samples": 3},
    {"min_samples": 0}, {"max_error_rate": -0.5},
    {"max_error_rate": 1.3}, {"max_p95_ms": 0}
])
def test_health_rolling_window_policy_rejects_invalid_values(kw):
    with pytest.raises(ValueError):
        r.HealthWindow(**kw)


@pytest.mark.parametrize("value", [float("nan"), -1, float("inf")])
def test_health_window_rejects_invalid_latency(value):
    window = r.HealthWindow()
    with pytest.raises(ValueError):
        window.record(True, value)


def test_no_health_samples_means_not_healthy():
    assert r.HealthWindow().snapshot() == {
        "samples": 0, "error_rate": None, "p95_ms": None, "healthy": False
    }


def test_singleflight_rejects_invalid_cache_size_or_blank_request_key():
    with pytest.raises(ValueError):
        r.SingleFlight(0)
    with pytest.raises(ValueError):
        r.SingleFlight().run("", lambda: "not allowed")


def test_singleflight_evicts_oldest_completed_idempotency_key():
    cache = r.SingleFlight(max_cached=2)
    assert cache.run("a", lambda: "old") == "old"
    assert cache.run("b", lambda: "stable") == "stable"
    assert cache.run("a", lambda: "should not execute") == "old"
    assert cache.run("c", lambda: "fresh") == "fresh"
    assert len(cache._succeeded) == 2
    assert "b" not in cache._succeeded
    assert cache.run("b", lambda: "retry") == "retry"


@pytest.mark.parametrize("coordinates", [
    ("", "main", "app"), ("org/repo", "", "app"),
    ("org/repo", "main", "")
])
def test_deployment_key_rejects_missing_dimensions(coordinates):
    with pytest.raises(ValueError):
        r.deployment_key(*coordinates)


@pytest.mark.parametrize("status,style", [
    ("running", "green"), ("stopped", "red"), ("building", "yellow"),
    ("failed", "bold red"), ("pending", "blue"), ("unknown", "white"),
    ("RUNNING", "green"),
])
def test_shared_cli_status_formatting(status, style):
    assert display._get_status_style(status) == style


def test_empty_and_complete_deployment_table(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr(display, "console", log)
    display.display_deployment_table([])
    log.print.assert_called()
    display.display_deployment_table([
        {"name": "api", "status": "running", "domain": "api.example.org",
         "branch": "main", "created_at": "2026-11-22"},
        {"name": "worker", "status": "failed"},
    ], title="Staging deployments")
    assert log.print.call_count == 2


@pytest.mark.parametrize("repo,name", [
    ("owner/project", "BAD name"), ("owner/project", "app--double"),
    ("owner/project", "a" * 65),
])
def test_deployment_preflight_rejects_invalid_app_names(repo, name):
    with pytest.raises(flow.DeploymentPreflightError):
        flow.DeploymentPlan.from_input(repo, name=name)


@pytest.mark.parametrize("base", [
    "https://user:password@models.example.com/v1",
    "https://models.example.com/v1?token=secret",
    "https://models.example.com/v1#fragment",
])
def test_model_gateway_never_accepts_credential_in_url(base):
    with pytest.raises(flow.DeploymentPreflightError):
        flow.validate_model_gateway(base, "model", "token")


@pytest.mark.parametrize("model,key", [("", "token"), ("model", "")])
def test_model_gateway_requires_selected_model_and_auth(model, key):
    with pytest.raises(flow.DeploymentPreflightError):
        flow.validate_model_gateway("https://models.example.com/v1", model, key)


@pytest.mark.parametrize("error", [ValueError("bad model list"),
                                   flow.requests.Timeout("model unavailable"),
                                   KeyError("missing data")])
def test_model_gateway_errors_are_safe_and_fail_closed(error):
    session = MagicMock()
    session.get.side_effect = error
    with pytest.raises(flow.DeploymentPreflightError, match="unavailable"):
        flow.validate_model_gateway("https://models.example.com/v1", "model",
                                    "secret", session)


def test_missing_jani_worktree_is_not_allowed(tmp_path):
    plan = flow.DeploymentPlan.from_input("team/repo")
    with pytest.raises(flow.DeploymentPreflightError, match="Git worktree"):
        flow.read_only_jani_review(plan, tmp_path, "model", "https://model", "key")


@pytest.mark.parametrize("timeout", [0, -1, 601])
def test_jani_execution_timeout_limit(tmp_path, monkeypatch, timeout):
    (tmp_path / ".git").mkdir()
    plan = flow.DeploymentPlan.from_input("team/repo")
    with pytest.raises(flow.DeploymentPreflightError, match="timeout"):
        flow.read_only_jani_review(plan, tmp_path, "model", "https://model",
                                   "key", timeout=timeout)


@pytest.mark.parametrize("throw", [OSError("binary unavailable"),
                                  subprocess.TimeoutExpired("jani", 3)])
def test_jani_runtime_failures_do_not_authorize_deploy(tmp_path, monkeypatch, throw):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(flow, "validate_model_gateway", lambda *a: None)
    plan = flow.DeploymentPlan.from_input("team/repo")
    with pytest.raises(flow.DeploymentPreflightError, match="unavailable"):
        flow.read_only_jani_review(plan, tmp_path, "model", "https://model",
                                   "key", run=lambda *a, **k: (_ for _ in ()).throw(throw))


def test_clone_wont_replace_existing_checkout(tmp_path):
    plan = flow.DeploymentPlan.from_input("team/repo")
    with pytest.raises(flow.DeploymentPreflightError, match="already exists"):
        flow.safe_checkout(plan, tmp_path)


@pytest.mark.parametrize("problem", [
    subprocess.TimeoutExpired("git", 150),
    OSError("git unavailable"), None,
])
def test_private_git_checkout_errors_never_print_credentials(tmp_path, problem):
    plan = flow.DeploymentPlan.from_input("team/repo")
    def fake_run(*args, **kwargs):
        if problem:
            raise problem
        return subprocess.CompletedProcess(args[0], 128, "", "secret-should-not-leak")
    with pytest.raises(flow.DeploymentPreflightError) as result:
        flow.safe_checkout(plan, tmp_path / "working", "token-secret", fake_run)
    assert "token-secret" not in str(result.value)
    assert "secret-should-not-leak" not in str(result.value)


def test_bounded_deployment_polling_requires_finite_budget():
    for timeout, poll in ((0, 1), (4, 0), (4, 5)):
        with pytest.raises(ValueError):
            flow.wait_for_deployment(lambda: {"status": "running"},
                                     timeout=timeout, poll=poll)


def test_transient_polling_errors_eventually_timeout():
    now = [0.0]
    def wait(delay):
        now[0] += delay
    def fetch():
        raise r.RetryableError("temporarily unavailable")
    with pytest.raises(flow.DeploymentPreflightError, match="timeout"):
        flow.wait_for_deployment(fetch, timeout=1, poll=0.4,
                                 clock=lambda: now[0], sleep=wait)


def test_wrong_git_remote_or_git_spawn_error_rejects_existing_checkout():
    plan = flow.DeploymentPlan.from_input("team/repo")
    def bad(*args, **kwargs):
        raise OSError("missing Git")
    with pytest.raises(flow.DeploymentPreflightError, match="Cannot verify"):
        flow.verify_worktree_matches_plan(plan, Path("/tmp/placeholder"), run=bad)
    def unsupported(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, "https://evil.example/repo\n", "")
    with pytest.raises(flow.DeploymentPreflightError, match="supported GitHub"):
        flow.verify_worktree_matches_plan(plan, Path("/tmp/placeholder"), run=unsupported)


@pytest.mark.parametrize("argv", [
    [], ["ifinsta/ifinsta", "--repo", "team/other"],
    ["team/app", "--ai-assist", "--dry-run"],
    ["not-a-repo", "--dry-run"],
])
def test_one_command_rejects_invalid_operator_input_before_credentials(argv):
    result = CliRunner().invoke(command.one_deploy, argv)
    assert result.exit_code != 0
    assert "Error" in result.output


def test_one_command_renders_read_only_jani_review_without_secret(monkeypatch, tmp_path):
    repo = flow.DeploymentPlan.from_input("team/app")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    monkeypatch.setenv("WEBOPS_MODEL_API_KEY", "model-token-not-output")
    monkeypatch.setattr(command, "verify_worktree_matches_plan", lambda *a: None)
    monkeypatch.setattr(command, "read_only_jani_review", lambda *a:
                        flow.AgentEvidence("model", "sha-evidence", "No deploy without approval.", 17))
    output = CliRunner().invoke(command.one_deploy, [
        "team/app", "--ai-assist", "--model", "model",
        "--model-endpoint", "https://models.example.com/v1",
        "--worktree", str(checkout), "--dry-run",
    ])
    assert output.exit_code == 0, output.output
    assert "No deploy without approval" in output.output
    assert "model-token-not-output" not in output.output


def test_one_command_clones_repo_for_ai_preflight_and_waits(monkeypatch, tmp_path):
    imported_cli = __import__("webops_cli.cli", fromlist=["get_api_client"])
    client = MagicMock()
    client.create_deployment.return_value = {"id": 17}
    client.get_deployment.return_value = {"status": "running"}
    monkeypatch.setattr(imported_cli, "get_api_client", lambda: client)
    monkeypatch.setenv("WEBOPS_MODEL_API_KEY", "local-model-key")
    monkeypatch.setenv("WEBOPS_MODEL", "qwen3:8b")
    monkeypatch.setenv("WEBOPS_MODEL_ENDPOINT", "https://models.example.com/v1")
    monkeypatch.setenv("GITHUB_TOKEN", "never-log-private-token")
    clone = MagicMock()
    monkeypatch.setattr(command, "safe_checkout", clone)
    review = MagicMock(return_value=flow.AgentEvidence("qwen3:8b", "digest", "Reviewed", 3))
    monkeypatch.setattr(command, "read_only_jani_review", review)
    output = CliRunner().invoke(command.one_deploy,
                                ["ifinsta/ifinsta", "--ai-assist",
                                 "--approve", "--wait", "--json-output"])
    assert output.exit_code == 0, output.output
    assert '"provider_reported_running": true' in output.output
    assert '"http_health_verified": false' in output.output
    assert "never-log-private-token" not in output.output
    clone.assert_called_once()
    assert clone.call_args.args[2] == "never-log-private-token"
    client.create_deployment.assert_called_once()
    client.close.assert_called_once()


def test_one_command_wait_error_still_closes_api_client(monkeypatch):
    imported_cli = __import__("webops_cli.cli", fromlist=["get_api_client"])
    client = MagicMock()
    client.create_deployment.return_value = {"id": 25}
    monkeypatch.setattr(imported_cli, "get_api_client", lambda: client)
    monkeypatch.setattr(command, "wait_for_deployment",
                        MagicMock(side_effect=flow.DeploymentPreflightError("health timed out")))
    output = CliRunner().invoke(command.one_deploy,
                                ["team/app", "--approve", "--wait"])
    assert output.exit_code != 0
    client.close.assert_called_once()


def test_one_command_without_ai_supports_legacy_options(monkeypatch):
    imported_cli = __import__("webops_cli.cli", fromlist=["get_api_client"])
    client = MagicMock()
    client.create_deployment.return_value = {"id": 3}
    monkeypatch.setattr(imported_cli, "get_api_client", lambda: client)
    result = CliRunner().invoke(command.one_deploy,
                                ["--repo", "team/app", "--name", "app-1",
                                 "--branch", "dev", "--domain", "app.example.com",
                                 "--approve"])
    assert result.exit_code == 0, result.output
    assert "WebOps deployment app-1" in result.output
    assert client.create_deployment.call_args.kwargs["branch"] == "dev"
    assert client.create_deployment.call_args.kwargs["domain"] == "app.example.com"

