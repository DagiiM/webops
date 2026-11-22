"""Adversarial and recovery tests for the one-command GitHub/Jani deployment path."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from click.testing import CliRunner
import pytest

import webops_cli.deployment_flow as flow
from webops_cli.one_deploy_command import one_deploy


@pytest.mark.parametrize("seed", range(128))
def test_github_plan_normalized_and_identified(seed):
    owner = f"team{seed%19}"
    project = f"service{seed}"
    a = flow.DeploymentPlan.from_input(f"{owner}/{project}")
    b = flow.DeploymentPlan.from_input(f"https://github.com/{owner}/{project}.git")
    assert a == b
    assert a.repo_url == f"https://github.com/{owner}/{project}.git"
    assert a.name == project
    assert a.digest == b.digest
    assert a.display()["idempotency_key"] == a.digest[:32]


@pytest.mark.parametrize("repo", [
    "", "org", "org//repo", "org/../repo", "../repo", "org/repo/extra",
    "https://evil.com/org/repo", "http://github.com/org/repo",
    "https://github.com@evil.com/a/b", "https://github.com/org/r?token=a",
    "org/r;rm -rf x", "org/r&&echo", "org/r\nother", "-owner/r",
    "a/-repo", "a/repo#main", "git@github.com:owner/repo",
    "https://github.com/org/r@branch", "https://github.com/org/r%2e.git"
])
def test_reject_untrusted_repository_urls(repo):
    with pytest.raises(flow.DeploymentPreflightError):
        flow.DeploymentPlan.from_input(repo)


@pytest.mark.parametrize("seed", range(128))
def test_plan_rejects_malformed_branch_name_and_domain(seed):
    bad_branch = ["../main", "-bad", "main//../bad", "main\nbranch", "main/.."][seed % 5]
    with pytest.raises(flow.DeploymentPreflightError):
        flow.DeploymentPlan.from_input("team/app", branch=bad_branch)
    bad_domain = ["../dev", "http://example.com", "team_domain", ".org", "example..com"][seed % 5]
    with pytest.raises(flow.DeploymentPreflightError):
        flow.DeploymentPlan.from_input("team/app", domain=bad_domain)


class StubResponse:
    def __init__(self, model="qwen3:1.7b", status=200):
        self.model = model
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise flow.requests.HTTPError("gateway unavailable")

    def json(self):
        return {"data": [{"id": self.model}]}


class StubSession:
    def __init__(self, model="qwen3:1.7b", status=200):
        self.url = None
        self.kwargs = None
        self.response = StubResponse(model, status)

    def get(self, url, **kwargs):
        self.url, self.kwargs = url, kwargs
        return self.response


@pytest.mark.parametrize("seed", range(128))
def test_model_preflight_auth_protocol_and_model_matching(seed):
    session = StubSession()
    uri = "http://127.0.0.1:8001/v1" if seed % 2 else "https://models.example.com/v1"
    flow.validate_model_gateway(uri, "qwen3:1.7b", "not-a-real-token", session)
    assert session.url == uri + "/models"
    assert session.kwargs["timeout"] <= 10
    assert session.kwargs["headers"]["Authorization"] == "Bearer not-a-real-token"
    with pytest.raises(flow.DeploymentPreflightError):
        flow.validate_model_gateway("http://models.example.com/v1",
                                    "qwen3:1.7b", "token", session)
    with pytest.raises(flow.DeploymentPreflightError):
        flow.validate_model_gateway(uri, "different-model", "token", session)


@pytest.mark.parametrize("seed", range(128))
def test_bounded_polling_success_failure_and_timeout(seed):
    status_count = seed % 12 + 1
    outcomes = [{"status": "building"} for _ in range(status_count)]
    outcomes.append({"status": "running"} if seed % 3 else {"status": "failed"})
    progress = iter(outcomes)
    clock = [0.0]
    def wait(delay):
        clock[0] += delay
    def fetch():
        return next(progress)
    if seed % 3:
        result = flow.wait_for_deployment(fetch, timeout=60, poll=1,
                                          clock=lambda: clock[0], sleep=wait)
        assert result["status"] == "running"
        assert clock[0] == status_count
    else:
        with pytest.raises(flow.DeploymentPreflightError, match="terminal"):
            flow.wait_for_deployment(fetch, timeout=60, poll=1,
                                     clock=lambda: clock[0], sleep=wait)


def test_jani_has_no_mutation_authority_and_no_secrets(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret-never-pass")
    monkeypatch.setenv("WEBOPS_API_KEY", "webops-secret-never-pass")
    monkeypatch.setattr(flow, "validate_model_gateway", lambda *args: None)
    seen = {}
    def runner(command, **kwargs):
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, "Review only: do not deploy.", "")
    plan = flow.DeploymentPlan.from_input("ifinsta/ifinsta")
    evidence = flow.read_only_jani_review(plan, tmp_path, "qwen3:1.7b",
                                          "http://127.0.0.1:8001/v1",
                                          "model-local-key", run=runner)
    assert seen["command"][0] == "jani"
    assert "--print" in seen["command"]
    assert "--allow-write" not in seen["command"]
    assert "--allow-exec" not in seen["command"]
    assert seen["cwd"] == tmp_path
    assert seen["env"]["JANI_MODEL"] == "qwen3:1.7b"
    assert seen["env"]["JANI_API_KEY"] == "model-local-key"
    assert "GITHUB_TOKEN" not in seen["env"]
    assert "WEBOPS_API_KEY" not in seen["env"]
    assert evidence.digest == hashlib.sha256(b"Review only: do not deploy.").hexdigest()


def test_agent_fails_closed_when_unavailable_or_empty(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(flow, "validate_model_gateway", lambda *args: None)
    plan = flow.DeploymentPlan.from_input("ifinsta/ifinsta")
    def fail(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "failed")
    with pytest.raises(flow.DeploymentPreflightError, match="failed"):
        flow.read_only_jani_review(plan, tmp_path, "model", "https://host/v1", "key", run=fail)
    def empty(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "", "")
    with pytest.raises(flow.DeploymentPreflightError, match="empty"):
        flow.read_only_jani_review(plan, tmp_path, "model", "https://host/v1", "key", run=empty)


def test_private_checkout_does_not_embed_token_in_argv(tmp_path):
    plan = flow.DeploymentPlan.from_input("ifinsta/ifinsta")
    observed = {}
    def runner(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"].copy()
        assert Path(observed["env"]["GIT_ASKPASS"]).is_file()
        assert "top-secret" not in repr(command)
        assert "top-secret" not in Path(observed["env"]["GIT_ASKPASS"]).read_text()
        return subprocess.CompletedProcess(command, 0, "", "")
    flow.safe_checkout(plan, tmp_path / "clone", "top-secret", runner)
    assert observed["env"]["WEBOPS_GIT_TOKEN"] == "top-secret"
    assert observed["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert "--depth" in observed["command"]


def test_one_command_dry_run_ifinsta_does_not_contact_api():
    runner = CliRunner()
    result = runner.invoke(one_deploy, ["ifinsta/ifinsta", "--dry-run", "--json-output"])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["spec"]["name"] == "ifinsta"
    assert info["status"] == "validated"


def test_one_command_needs_approval_before_api_call(monkeypatch):
    called = []
    class FakeClient:
        def create_deployment(self, **kwargs):
            called.append(kwargs)
            return {"id": "1"}
        def close(self):
            pass
    from webops_cli import cli
    monkeypatch.setattr(cli, "get_api_client", lambda: FakeClient())
    runner = CliRunner()
    denied = runner.invoke(one_deploy, ["ifinsta/ifinsta"], input="n\n")
    assert denied.exit_code != 0
    assert not called
    approved = runner.invoke(one_deploy, ["ifinsta/ifinsta", "--approve", "--json-output"])
    assert approved.exit_code == 0, approved.output
    assert called == [dict(name="ifinsta", repo_url="https://github.com/ifinsta/ifinsta.git",
                           branch="main", domain="")]

