"""Project provisioning workflow coverage using disposable repository trees."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from webops_cli import project_setup as m


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    client = MagicMock()
    w = m.ProjectSetupWorkflow(client)
    w.temp_dir = tmp_path / "sources"
    w.temp_dir.mkdir()
    monkeypatch.setattr(m, "console", MagicMock())
    mock_progress = MagicMock()
    mock_progress.__enter__.return_value = mock_progress
    monkeypatch.setattr(m, "Progress", lambda *a, **kw: mock_progress)
    monkeypatch.setattr(m.time, "sleep", lambda *_: None)
    return w


def test_project_result_has_independent_default_step_list():
    first = m.ProjectSetupResult(False, "a", "repo", "", "")
    second = m.ProjectSetupResult(False, "b", "repo", "", "")
    first.setup_steps.append({"step": "attempt"})
    assert second.setup_steps == []


@pytest.mark.parametrize("failure", [False, True])
def test_cleanup_of_disposable_clone_and_failure_reporting(
    workflow, monkeypatch, failure
):
    temp_dir = workflow.temp_dir
    if failure:
        import shutil

        monkeypatch.setattr(
            shutil,
            "rmtree",
            lambda path: (_ for _ in ()).throw(PermissionError("locked")),
        )
    workflow.cleanup()
    assert temp_dir.exists() is failure


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/team/repo.git",
        "https://github.com/team/repo",
    ],
)
def test_clone_github_repository_https_with_shallow_depth(workflow, monkeypatch, url):
    clone = MagicMock()
    monkeypatch.setattr(m.Repo, "clone_from", clone)
    out = workflow.clone_project(url, "webapp")
    assert out[0] is True
    assert out[2] == workflow.temp_dir / "webapp"
    assert clone.call_args.kwargs["depth"] == 1
    assert clone.call_args.args[0] == "https://github.com/team/repo.git"


def test_clone_overwrites_only_existing_temp_project(workflow, monkeypatch):
    prior = workflow.temp_dir / "example"
    prior.mkdir()
    (prior / "old.txt").write_text("obsolete")
    clone = MagicMock()
    monkeypatch.setattr(m.Repo, "clone_from", clone)
    assert workflow.clone_project("https://github.com/a/repo", "example")[0] is True
    assert not (prior / "old.txt").exists()


@pytest.mark.parametrize(
    "url,reason",
    [
        ("git@external.example.com:team/repo", "HTTPS"),
        ("not-a-url", "Invalid repository"),
    ],
)
def test_clone_rejects_invalid_or_non_https_origin(workflow, url, reason):
    result = workflow.clone_project(url, "example")
    assert not result[0]
    assert reason in result[1]


@pytest.mark.parametrize(
    "stderr,expected",
    [
        ("not found", "not found"),
        ("permission denied", "Permission denied"),
        ("other git failure", "Git error"),
    ],
)
def test_clone_git_error_categories_never_leak_access_token(
    workflow, monkeypatch, stderr, expected
):
    failure = m.GitCommandError("git clone", 128, stderr)
    monkeypatch.setattr(m.Repo, "clone_from", MagicMock(side_effect=failure))
    result = workflow.clone_project("https://github.com/a/repo", "example")
    assert not result[0]
    assert expected in result[1]


def test_clone_unexpected_error_is_returned_not_raised(workflow, monkeypatch):
    monkeypatch.setattr(
        m.Repo, "clone_from", MagicMock(side_effect=OSError("volume unavailable"))
    )
    assert (
        "Unexpected error"
        in workflow.clone_project("https://github.com/team/repo", "example")[1]
    )


@pytest.mark.parametrize(
    "layout,expected",
    [
        ("root", "settings"),
        ("config", "config.settings"),
        ("core", "core.settings"),
        ("deep", "project.core.settings"),
        ("excluded", "settings"),
    ],
)
def test_django_detection_config_priority_and_ignored_folders(
    workflow, tmp_path, layout, expected
):
    source = tmp_path / "django-src"
    source.mkdir()
    (source / "manage.py").write_text("# manage")
    if layout == "root":
        path = source / "settings.py"
    elif layout == "config":
        path = source / "config" / "settings.py"
    elif layout == "core":
        path = source / "core" / "settings.py"
    elif layout == "deep":
        path = source / "project" / "core" / "settings.py"
    else:
        path = source / "tests" / "settings.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# config")
    if layout == "config":
        (path.parent / "__init__.py").write_text("# module")
        (path.parent / "asgi.py").write_text("# ASGI")
    kind, entry, details = workflow.detect_project_type_and_entry_point(source)
    assert kind == "django"
    assert entry == expected
    assert details["manage_py"]
    assert details["asgi"] is (layout == "config")


def test_django_detection_prefers_valid_config_over_test_settings(workflow, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "manage.py").touch()
    for directory in ("tests", "config", "core"):
        p = root / directory
        p.mkdir()
        (p / "settings.py").touch()
    (root / "config" / "__init__.py").touch()
    assert workflow.detect_project_type_and_entry_point(root)[1] == "config.settings"


@pytest.mark.parametrize(
    "static_path",
    [
        "index.html",
        "index.htm",
        "public/index.html",
        "dist/index.html",
        "build/index.html",
    ],
)
def test_static_site_fallback_detection(workflow, tmp_path, static_path):
    base = tmp_path / "static-repo"
    base.mkdir()
    target = base / static_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("<p>hello</p>")
    kind, entry, details = workflow.detect_project_type_and_entry_point(base)
    assert kind == "static" and entry == static_path
    assert details["static_file"] == static_path


@pytest.mark.parametrize(
    "manifest,entry",
    [
        ('{"scripts":{"start":"node app.js"}}', "npm start"),
        ('{"scripts":{"dev":"vite"}}', "npm run dev"),
        ('{"scripts":{"test":"vitest"}}', "npm install"),
        ("{invalid-json", "package.json"),
    ],
)
def test_node_entry_point_detected_without_installing_dependencies(
    workflow, tmp_path, manifest, entry
):
    root = tmp_path / "node-repo"
    root.mkdir()
    (root / "package.json").write_text(manifest)
    assert workflow.detect_project_type_and_entry_point(root)[1] == entry


def test_no_detection_hints_defaults_to_static(workflow, tmp_path):
    kind, entry, details = workflow.detect_project_type_and_entry_point(tmp_path)
    assert kind == "static" and details["default_assumption"] is True


@pytest.mark.parametrize(
    "response,expected",
    [
        ({"success": True, "id": 42, "name": "app", "message": "queued"}, True),
        ({"id": 42}, True),
        ({"success": False, "error": "invalid app"}, False),
    ],
)
def test_deployment_submission_accepts_and_rejects_api_response(
    workflow, response, expected
):
    workflow.api_client.create_deployment.return_value = response
    success, info = workflow.create_webops_deployment(
        "app", "https://github.com/a/b", "django"
    )
    assert success is expected
    workflow.api_client.create_deployment.assert_called_once()


@pytest.mark.parametrize(
    "exc", [m.WebOpsAPIError("offline"), OSError("HTTP unreachable")]
)
def test_deployment_submission_api_errors_are_bounded(workflow, exc):
    workflow.api_client.create_deployment.side_effect = exc
    assert not workflow.create_webops_deployment(
        "app", "https://github.com/a/b", "static"
    )[0]


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["building", "running"], True),
        (["pending", "failed"], False),
        (["building", "building", "building"], False),
    ],
)
def test_wait_deployment_status_and_deadline(workflow, monkeypatch, statuses, expected):
    times = [0.0]
    steps = iter(statuses)

    def fetch(*a):
        try:
            return {"status": next(steps), "port": 8080}
        except StopIteration:
            return {"status": "building"}

    monkeypatch.setattr(workflow.api_client, "get_deployment", fetch)
    monkeypatch.setattr(m.time, "time", lambda: times[0])
    monkeypatch.setattr(
        m.time, "sleep", lambda duration: times.__setitem__(0, times[0] + duration)
    )
    outcome, info = workflow.wait_for_deployment_setup("app", timeout=13)
    assert outcome is expected
    if expected:
        assert info["port"] == 8080
    elif info.get("status") == "timeout":
        assert times[0] >= 13


@pytest.mark.parametrize(
    "failure",
    [m.WebOpsAPIError("temporary offline"), ValueError("unexpected API format")],
)
def test_wait_deployment_retries_provider_failures_then_times_out(
    workflow, monkeypatch, failure
):
    current = [0.0]
    monkeypatch.setattr(m.time, "time", lambda: current[0])
    monkeypatch.setattr(
        m.time, "sleep", lambda amount: current.__setitem__(0, current[0] + amount)
    )
    workflow.api_client.get_deployment.side_effect = failure
    result = workflow.wait_for_deployment_setup("webapp", timeout=12)
    assert result[0] is False
    assert result[1]["status"] == "timeout"


@pytest.mark.parametrize(
    "http_code,ok",
    [
        (200, True),
        (301, True),
        (302, True),
        (307, True),
        (308, True),
        (401, False),
        (503, False),
    ],
)
def test_http_access_probe_accepts_ok_and_redirect_codes(
    workflow, monkeypatch, http_code, ok
):
    monkeypatch.setattr(
        m.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=http_code)
    )
    result, message = workflow.verify_web_access(8080, "app", timeout=5)
    assert result is ok


@pytest.mark.parametrize(
    "exc",
    [
        m.requests.exceptions.ConnectionError("refused"),
        m.requests.exceptions.Timeout("backend timeout"),
        ValueError("bad HTTP response"),
    ],
)
def test_http_access_probe_handles_transport_failures(workflow, monkeypatch, exc):
    monkeypatch.setattr(m.requests, "get", lambda *a, **kw: (_ for _ in ()).throw(exc))
    status, message = workflow.verify_web_access(8080, "app", timeout=5)
    assert not status and "Could not access" in message


def test_http_probe_zero_timeout_is_immediate_failure(workflow):
    assert not workflow.verify_web_access(8080, "app", timeout=0)[0]


@pytest.mark.parametrize(
    "stage", ["clone", "detect", "deploy", "wait", "verify", "happy", "no-deploy"]
)
def test_complete_workflow_respects_stage_failures_and_optional_verification(
    workflow, monkeypatch, tmp_path, stage
):
    root = tmp_path / "cloned"
    root.mkdir()
    monkeypatch.setattr(
        workflow,
        "clone_project",
        lambda *a: (
            (False, "denied", Path()) if stage == "clone" else (True, "cloned", root)
        ),
    )

    def detect(*a):
        if stage == "detect":
            raise OSError("cannot read tree")
        return "nodejs", "npm start", {"package_json": True, "manage_py": False}

    monkeypatch.setattr(workflow, "detect_project_type_and_entry_point", detect)
    monkeypatch.setattr(
        workflow,
        "create_webops_deployment",
        lambda *a: (
            (False, {"error": "cannot queue"})
            if stage == "deploy"
            else (True, {"deployment_id": 14, "message": "queued"})
        ),
    )
    monkeypatch.setattr(
        workflow,
        "wait_for_deployment_setup",
        lambda *a: (
            (False, {"error": "timeout", "status": "timeout"})
            if stage == "wait"
            else (True, {"port": 8001, "status": "running"})
        ),
    )
    monkeypatch.setattr(
        workflow,
        "verify_web_access",
        lambda *a: (False, "port closed") if stage == "verify" else (True, "responded"),
    )
    clean = MagicMock()
    monkeypatch.setattr(workflow, "cleanup", clean)
    result = workflow.run_complete_workflow(
        "https://github.com/org/app", "app", create_deployment=stage != "no-deploy"
    )
    assert result.success is (stage not in {"clone", "detect", "deploy", "wait"})
    assert len(result.setup_steps) >= 1
    if stage == "verify":
        assert result.success and result.web_url is None
    if stage == "happy":
        assert result.web_url == "http://localhost:8001"
    clean.assert_called_once()


def test_complete_workflow_can_skip_optional_http_probe(
    workflow, monkeypatch, tmp_path
):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(workflow, "clone_project", lambda *a: (True, "cloned", root))
    monkeypatch.setattr(
        workflow,
        "detect_project_type_and_entry_point",
        lambda *a: ("static", "index.html", {}),
    )
    monkeypatch.setattr(
        workflow, "create_webops_deployment", lambda *a: (True, {"deployment_id": 9})
    )
    monkeypatch.setattr(
        workflow,
        "wait_for_deployment_setup",
        lambda *a: (True, {"status": "running", "port": None}),
    )
    verify = MagicMock()
    monkeypatch.setattr(workflow, "verify_web_access", verify)
    monkeypatch.setattr(workflow, "cleanup", lambda: None)
    result = workflow.run_complete_workflow(
        "https://github.com/org/app", "app", verify_access=False
    )
    assert result.success and result.port is None
    verify.assert_not_called()


@pytest.mark.parametrize(
    "success,with_url", [(True, True), (True, False), (False, False)]
)
def test_result_summary_reports_failure_and_success_with_optional_fields(
    workflow, success, with_url
):
    result = m.ProjectSetupResult(
        success,
        "example",
        "https://github.com/org/app",
        "npm start",
        "nodejs",
        port=8000 if with_url else None,
        web_url="http://localhost:8000" if with_url else None,
        deployment_id=22 if with_url else None,
        setup_steps=[
            {"step": "clone", "success": True, "message": "cloned"},
            {"step": "deploy", "success": False, "message": "not authorized"},
        ],
        error_message="not authorized" if not success else None,
    )
    workflow.display_result_summary(result)
    assert m.console.print.called


@pytest.mark.parametrize(
    "remote",
    [
        "git@github.com:team/repo.git",
        "ssh://git@github.com/team/repo.git",
        "git://github.com/team/repo.git",
    ],
)
def test_github_ssh_and_git_remotes_normalize_to_exact_https_without_shell(
    workflow, monkeypatch, remote
):
    clone = MagicMock()
    monkeypatch.setattr(m.Repo, "clone_from", clone)
    ok, _, destination = workflow.clone_project(remote, "app")
    assert ok
    assert clone.call_args.args[0] == "https://github.com/team/repo.git"
    assert clone.call_args.kwargs["depth"] == 1


def test_django_generic_single_directory_settings_priority(workflow, tmp_path):
    root = tmp_path / "generic-django"
    root.mkdir()
    (root / "manage.py").touch()
    (root / "backend").mkdir()
    (root / "backend" / "settings.py").touch()
    kind, entry, details = workflow.detect_project_type_and_entry_point(root)
    assert kind == "django"
    assert entry == "backend.settings"
    assert details["settings_file"] == "backend/settings.py"
