"""High-cardinality, deterministic WebOps installation failure and cleanup tests.

Each parametrized case uses an independent temporary fake system root. No tests
install packages or touch real host services. The cross-product deliberately
varies baseline types, installed types, administrator changes and protected data
paths; distinct pytest node IDs make failure triage reproducible.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import sys

import pytest

LIFECYCLE = Path(__file__).resolve().parents[1] / "lifecycle"
sys.path.insert(0, str(LIFECYCLE))
import installation_inventory as inv
import installation_recovery as recovery
sys.path.remove(str(LIFECYCLE))

PATHS = inv.CONFIG_PATHS[:30]
BASELINES = ("absent", "file", "directory", "symlink")
INSTALLED = ("absent", "file", "directory", "symlink")
LATER = ("unchanged", "file", "directory", "symlink")


def delete_path(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def materialize(path, kind, tag, external):
    delete_path(path)
    if kind == "absent":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "file":
        path.write_bytes((tag + "-payload\\n").encode())
        path.chmod(0o640)
    elif kind == "directory":
        path.mkdir()
        (path / "config.ini").write_text(tag + "=value\\n")
        (path / "secret.data").write_bytes((tag * 3).encode())
    elif kind == "symlink":
        destination = external / (tag + "-target")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("DO NOT ALTER " + tag)
        path.symlink_to(destination)
    else:
        raise AssertionError(kind)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / "app" / "webops"
    root.mkdir(parents=True)
    (root / inv.MARKER).write_text("v1.0.0")
    platform = root / "provisioning" / "bin"
    platform.mkdir(parents=True)
    (platform / "webops").write_text("installed binary")
    system = tmp_path / "fake-system"
    state = tmp_path / "inventory"
    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.setattr(inv, "command", lambda *args: "nginx\\n" if args[0] == "dpkg-query" else "")
    return root, system, state, external


# 30 independently tracked system paths × 4 original shapes × 4 installed
# shapes × 4 subsequent administrator edits = 1,920 distinct cases.
@pytest.mark.parametrize("config", PATHS, ids=lambda x: x.replace("/", "_"))
@pytest.mark.parametrize("original", BASELINES)
@pytest.mark.parametrize("installed", INSTALLED)
@pytest.mark.parametrize("later", LATER)
def test_configuration_restoration_crossproduct(sandbox, config, original, installed, later):
    root, system, state, external = sandbox
    path = inv.system_path(config, system)
    materialize(path, original, "original", external)
    original_signature = inv.signature(path)
    inv.capture(state, root, system)
    materialize(path, installed, "webops", external)
    installed_signature = inv.signature(path)
    inv.seal(state, system)
    if later != "unchanged":
        materialize(path, later, "operator", external)
    current_signature = inv.signature(path)
    preview = inv.plan_or_uninstall(state, system, apply=False)
    assert inv.signature(path) == current_signature
    inv.plan_or_uninstall(state, system, apply=True)
    if current_signature == installed_signature:
        assert inv.signature(path) == original_signature
    else:
        assert inv.signature(path) == current_signature
        assert any(config in entry for entry in preview["preserved"])


# 14 protected data directory names × 8 mutation patterns × 2 purge modes
# = 224 additional scenarios. No alias may reach external user data.
DATA_VARIANTS = ("plain", "nested", "new-after-seal", "modified-after-seal",
                 "link", "replaced-with-link", "empty", "nested-modified")


@pytest.mark.parametrize("name", sorted(inv.PRESERVE_DIRS))
@pytest.mark.parametrize("variant", DATA_VARIANTS)
@pytest.mark.parametrize("purge", [False, True], ids=["keep-data", "purge-data"])
def test_protected_data_matrix(sandbox, name, variant, purge):
    root, system, state, external = sandbox
    protected = root / name
    outsider = external / "other-app"
    outsider.mkdir()
    sentinel = outsider / "do-not-delete"
    sentinel.write_text("unrelated software data")
    if variant != "replaced-with-link" and variant != "link":
        protected.mkdir()
        if variant != "empty":
            base = protected / "nested" if variant.startswith("nested") else protected
            base.mkdir(exist_ok=True)
            (base / "database.sql").write_text("important original data")
    elif variant == "link":
        protected.symlink_to(outsider, target_is_directory=True)
    else:
        protected.mkdir()
        (protected / "temp.txt").write_text("before")
    inv.capture(state, root, system)
    inv.seal(state, system)
    if variant == "replaced-with-link":
        shutil.rmtree(protected)
        protected.symlink_to(outsider, target_is_directory=True)
    elif variant == "new-after-seal":
        (protected / "new").write_text("added after installation")
    elif variant == "modified-after-seal":
        (protected / "database.sql").write_text("operator modification")
    elif variant == "nested-modified":
        (protected / "nested" / "database.sql").write_text("operator modification")
    inv.plan_or_uninstall(state, system, apply=True, purge_data=purge)
    assert sentinel.read_text() == "unrelated software data"
    if purge and not protected.is_symlink():
        assert not protected.exists()
    elif variant in ("link", "replaced-with-link"):
        assert protected.is_symlink()
    else:
        assert protected.is_dir()


# A destroyed or corrupted backup must never permit a partially destructive
# uninstall. Pick different system components and different corruption styles.
@pytest.mark.parametrize("config", inv.CONFIG_PATHS[:24])
@pytest.mark.parametrize("damage", ["missing", "rewritten", "mode", "symlink"])
def test_corrupt_baseline_backup_fail_closed(sandbox, config, damage):
    root, system, state, external = sandbox
    path = inv.system_path(config, system)
    materialize(path, "file", "original", external)
    inv.capture(state, root, system)
    materialize(path, "file", "webops", external)
    inv.seal(state, system)
    saved = state / "originals" / inv.load(state)["config"][config]["backup"]
    if damage == "missing":
        saved.unlink()
    elif damage == "rewritten":
        saved.write_text("garbage")
    elif damage == "mode":
        saved.chmod(0o600)
    else:
        saved.unlink()
        saved.symlink_to(external / "unrelated")
    with pytest.raises(ValueError, match="corrupted"):
        inv.plan_or_uninstall(state, system, apply=True)
    assert inv.signature(path) == inv.load(state)["config"][config]["after"]
    assert (root / "provisioning" / "bin" / "webops").exists()


RECOVERY_CASES = [
    ("fresh", "fresh"),
    ("staged", "staged"),
    ("captured", "resume"),
    ("started", "repair"),
    ("sealed", "installed"),
    ("sealed-no-proof", "repair"),
    ("removed", "manual"),
    ("invalid-marker", "manual"),
    ("missing-installer", "manual"),
    ("broken-stage", "manual"),
    ("invalid-journal", "manual"),
]


@pytest.mark.parametrize("state,expected", RECOVERY_CASES)
@pytest.mark.parametrize("unrelated", range(8), ids=lambda n: "other-file-" + str(n))
def test_recovery_classifier_with_unrelated_host_changes(sandbox, state, expected, unrelated):
    root, system, inventory_dir, external = sandbox
    installer = root / "provisioning/versions/v1.0.0/lifecycle/install.sh"
    installer.parent.mkdir(parents=True)
    installer.write_text("#!/bin/sh\\nexit 0\\n")
    (root / ("unrelated-file-%02d" % unrelated)).write_text("never overwrite")
    if state == "fresh":
        shutil.rmtree(root)
    if state == "staged":
        recovery.write_stage(root)
    if state in ("captured", "started", "sealed", "sealed-no-proof", "removed"):
        inv.capture(inventory_dir, root, system)
        if state == "started":
            inv.begin_system_changes(inventory_dir)
        if state.startswith("sealed"):
            inv.seal(inventory_dir, system)
            if state == "sealed-no-proof":
                journal = inv.load(inventory_dir)
                journal.pop("health_verified_at", None)
                inv.atomic_save(inventory_dir, journal)
        if state == "removed":
            journal = inv.load(inventory_dir)
            journal["status"] = "removed"
            inv.atomic_save(inventory_dir, journal)
    if state == "invalid-marker":
        (root / inv.MARKER).write_text("unknown-version")
    if state == "missing-installer":
        installer.unlink()
    if state == "broken-stage":
        (root / recovery.STAGE).write_text("bad-json")
    if state == "invalid-journal":
        inventory_dir.mkdir()
        (inventory_dir / "inventory.json").write_text("not-json")
    found = recovery.inspect(root, inventory_dir)
    assert found["action"] == expected, found
    if root.exists():
        assert (root / ("unrelated-file-%02d" % unrelated)).read_text() == "never overwrite"


@pytest.mark.parametrize("relative", [
    "../../etc", "../etc", "/etc/passwd", "/root/secret", "safe/../../escape",
    "a/../b", "..", "../../", "x/y/../../../escape", "/",
    *["/etc/" + ("x" * n) for n in range(1, 31)],
])
def test_uninstall_rejects_malicious_manifest_paths_before_mutation(sandbox, relative):
    root, system, state, external = sandbox
    inv.capture(state, root, system)
    inv.seal(state, system)
    journal = inv.load(state)
    journal["tracked_files"][relative] = "file:deadbeef:0o600"
    inv.atomic_save(state, journal)
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        with pytest.raises(ValueError, match="Unsafe"):
            inv.plan_or_uninstall(state, system, apply=True)
    else:
        inv.plan_or_uninstall(state, system, apply=True)
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        assert (root / inv.MARKER).is_file()
        assert inv.load(state)["status"] == "sealed"
    else:
        assert inv.load(state)["status"] == "removed"


# Symlink substitution is a particularly dangerous uninstall failure: an
# attacker or operator can replace /etc/foo with a link to another directory.
# Even identical content must not allow deleting the link target's files.
SYMLINK_CONFIGS = [
    "/etc/ssh/sshd_config", "/etc/sysctl.d/99-webops-base.conf",
    "/etc/sudoers.d/webops", "/etc/systemd/journald.conf.d/99-webops.conf",
    "/etc/logrotate.d/webops", "/etc/apt/apt.conf.d/50unattended-upgrades",
    "/etc/chrony/chrony.conf", "/etc/redis/redis.conf",
    "/etc/nginx/sites-available/webops", "/etc/systemd/system/webops-web.service",
    "/etc/apt/sources.list.d/kubernetes.list",
    "/etc/apt/keyrings/kubernetes-apt-keyring.gpg",
    "/etc/yum.repos.d/kubernetes.repo", "/etc/modules-load.d/k8s.conf",
    "/etc/containerd/config.toml", "/usr/local/bin/webops-k8s-status",
]


@pytest.mark.parametrize("config", SYMLINK_CONFIGS)
@pytest.mark.parametrize("baseline", ["absent", "file"])
@pytest.mark.parametrize("foreign", ["matching", "different", "empty"])
def test_symlinked_config_parent_never_touches_third_party(sandbox, config, baseline, foreign):
    root, system, state, external = sandbox
    target = inv.system_path(config, system)
    materialize(target, baseline, "original", external)
    inv.capture(state, root, system)
    materialize(target, "file", "installed", external)
    inv.seal(state, system)
    foreign_dir = external / "another-system-" / ("matching" if foreign == "matching" else foreign)
    foreign_dir.mkdir(parents=True)
    other = foreign_dir / target.name
    if foreign != "empty":
        other.write_bytes(("installed-payload\\n" if foreign == "matching" else "CUSTOM DATA").encode())
        other.chmod(0o640)
    before_other = inv.signature(other)
    # Move, don't remove: the operator can still access the old directory.
    target.parent.rename(target.parent.with_name(target.parent.name + ".moved"))
    target.parent.symlink_to(foreign_dir, target_is_directory=True)
    report = inv.plan_or_uninstall(state, system, apply=True)
    assert inv.signature(other) == before_other
    assert target.parent.is_symlink()
    assert any(config in msg for msg in report["preserved"])


CRITICAL_ROOTS = [
    "/", "/etc", "/etc/webops", "/etc/ssh/sshd_config", "/proc", "/proc/self",
    "/sys", "/sys/kernel", "/dev", "/dev/null", "/boot", "/boot/grub",
    "/bin", "/bin/webops", "/sbin", "/sbin/init", "/usr", "/usr/local",
    "/usr/local/bin", "/var", "/var/backups", "/var/lib", "/var/log",
    "/run", "/run/systemd", "/root", "/root/webops", "/lib", "/lib64",
    "/opt", "/tmp", "/home", "/mnt",
]


@pytest.mark.parametrize("root_name", CRITICAL_ROOTS)
def test_critical_system_root_never_accepted(root_name):
    with pytest.raises(ValueError, match="Unsafe"):
        inv.valid_install_root(root_name)


@pytest.mark.parametrize("config", inv.CONFIG_PATHS[:28])
@pytest.mark.parametrize("forged", ["../other", "../../escape", "/etc/passwd", "9999", "not-an-index"])
def test_corrupted_journal_backup_refuses_operation(sandbox, config, forged):
    root, system, state, external = sandbox
    inv.capture(state, root, system)
    inv.seal(state, system)
    journal = inv.load(state)
    journal["config"][config]["backup"] = forged
    inv.atomic_save(state, journal)
    with pytest.raises(ValueError, match="backup"):
        inv.plan_or_uninstall(state, system, apply=True)
    assert (root / inv.MARKER).is_file()


@pytest.mark.parametrize("marker", ["missing", "wrong-version", "symlink", "empty",
                                     "whitespace", "unreadable", "correct"])
@pytest.mark.parametrize("when", ["before-capture", "before-seal", "before-cleanup"])
def test_ownership_marker_lifecycle_matrix(sandbox, marker, when):
    root, system, state, external = sandbox
    marker_path = root / inv.MARKER

    def modify():
        if marker_path.is_symlink() or marker_path.exists():
            marker_path.unlink()
        if marker == "wrong-version":
            marker_path.write_text("v1.9.9")
        elif marker == "symlink":
            source = external / "other-owner"
            source.write_text("v1.0.0")
            marker_path.symlink_to(source)
        elif marker == "empty":
            marker_path.touch()
        elif marker == "whitespace":
            marker_path.write_text(" v1.0.0 ")
        elif marker == "unreadable":
            marker_path.write_text("v1.0.0")
            marker_path.chmod(0o000)
        elif marker == "correct":
            marker_path.write_text("v1.0.0")
    if when == "before-capture":
        modify()
    inv.capture(state, root, system)
    if when == "before-seal":
        modify()
    if when == "before-seal" and marker not in ("correct", "whitespace", "unreadable"):
        # A captured valid marker may no longer be present; sealing must refuse.
        with pytest.raises(ValueError, match="marker"):
            inv.seal(state, system)
        return
    inv.seal(state, system)
    if when == "before-cleanup":
        modify()
    if when == "before-cleanup" and marker not in ("correct", "whitespace", "unreadable"):
        with pytest.raises(ValueError, match="marker"):
            inv.plan_or_uninstall(state, system, apply=True)
        return
    if when == "before-capture" and not inv.load(state)["owned_root"]:
        inv.plan_or_uninstall(state, system, apply=True)
        assert (root / "provisioning" / "bin" / "webops").exists()
    else:
        inv.plan_or_uninstall(state, system, apply=True)
    # Never follow a marker symlink into an external file.
    if marker == "symlink":
        assert (external / "other-owner").read_text() == "v1.0.0"


FAIL_STAGES = (
    "preflight", "copy", "network", "dns", "apt-update", "apt-install",
    "ssh-config", "firewall", "kernel", "postgresql", "redis", "nginx",
    "django", "celery", "readiness", "control-panel",
)
FAIL_KINDS = (
    "timeout", "permission-denied", "not-found", "exit-one",
    "read-only-fs", "disk-full", "process-killed", "invalid-state",
)


@pytest.mark.parametrize("stage", FAIL_STAGES)
@pytest.mark.parametrize("kind", FAIL_KINDS)
@pytest.mark.parametrize("phase", ["baseline-captured", "system-changes-started"])
def test_failure_journal_keeps_original_state(sandbox, stage, kind, phase):
    root, system, state, external = sandbox
    original = root / "deployments" / "user-db"
    original.parent.mkdir()
    original.write_text("valuable")
    inv.capture(state, root, system)
    if phase == "system-changes-started":
        inv.begin_system_changes(state)
    text = stage + ":" + kind
    info = inv.record_failure(state, text)
    journal = inv.load(state)
    assert info["status"] == journal["status"] == "captured"
    assert journal["failure_reason"] == text
    assert journal["phase"] == phase
    assert journal["failure_recorded_at"]
    assert original.read_text() == "valuable"
    with pytest.raises(ValueError, match="incomplete"):
        inv.plan_or_uninstall(state, system, apply=True)


@pytest.mark.parametrize("phase", ["captured", "sealed", "removed"])
@pytest.mark.parametrize("reason", ["timeout", "operator-cancel", "permission-denied"])
def test_error_journal_fails_closed_after_success(sandbox, phase, reason):
    root, system, state, external = sandbox
    inv.capture(state, root, system)
    if phase in ("sealed", "removed"):
        inv.seal(state, system)
    if phase == "removed":
        journal = inv.load(state)
        journal["status"] = "removed"
        inv.atomic_save(state, journal)
    if phase == "captured":
        inv.record_failure(state, reason)
    else:
        with pytest.raises(ValueError, match="incomplete"):
            inv.record_failure(state, reason)


def test_failed_install_rollback_preserves_new_user_data(sandbox):
    """Real shell function, but never invokes systemctl or modifies real OS."""
    import subprocess
    root, system, state, external = sandbox
    user_file = root / "deployments" / "late-upload.txt"
    user_file.parent.mkdir()
    user_file.write_text("created after installer snapshot")
    source = (LIFECYCLE / "install.sh").read_text()
    source = source[:source.rindex('main "$@"')]
    source += 'rollback_installation && exit 8 || exit 2\n'
    script = root / "test-simulated-rollback.sh"
    script.write_text(source)
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert user_file.read_text() == "created after installer snapshot"
    assert "destructive rollback disabled" in result.stdout


MALFORMED_JOURNALS = [
    ("version", 0), ("version", 2), ("version", "1"), ("version", None),
    ("version", []), ("version", True), ("version", {}),
    ("status", None), ("status", []), ("status", {}), ("status", "unknown"),
    ("status", "installed"), ("status", ""), ("status", 1),
    ("install_root", None), ("install_root", ""), ("install_root", 123),
    ("install_root", "/"), ("install_root", "/etc"), ("install_root", "/root/webops"),
    ("install_root", "relative"), ("install_root", "/tmp/x/../y"),
    ("owned_root", None), ("owned_root", "true"), ("owned_root", 1),
    ("owned_root", 0), ("owned_root", {}), ("owned_root", []),
    ("tracked_files", None), ("tracked_files", "files"),
    ("tracked_files", ["foo"]), ("tracked_files", 5),
    ("config", None), ("config", "files"), ("config", []),
    ("config", {}), ("config", 45),
]


@pytest.mark.parametrize("field,value", MALFORMED_JOURNALS)
def test_malformed_journal_does_not_allow_uninstall(sandbox, field, value):
    root, system, state, external = sandbox
    inv.capture(state, root, system)
    inv.seal(state, system)
    journal = inv.load(state)
    journal[field] = value
    inv.atomic_save(state, journal)
    with pytest.raises(ValueError):
        inv.plan_or_uninstall(state, system, apply=True)
    assert (root / "provisioning" / "bin" / "webops").exists()


INVALID_HEALTH_PROOFS = [
    "", "fake", "success", "never", "yesterday", "2026", "2026-99-23",
    "2026-11-23", "2026-11-23T10:00:00", "0", 0, 123, None, {},
    [], False, True, "2026-11-23T25:00:00+00:00",
]


@pytest.mark.parametrize("health", INVALID_HEALTH_PROOFS)
def test_unverifiable_success_timestamp_requires_repair(sandbox, health):
    root, system, state, external = sandbox
    entrypoint = root / "provisioning/versions/v1.0.0/lifecycle/install.sh"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("#!/bin/sh\\nexit 0\\n")
    inv.capture(state, root, system)
    inv.seal(state, system)
    journal = inv.load(state)
    journal["health_verified_at"] = health
    inv.atomic_save(state, journal)
    result = recovery.inspect(root, state)
    assert result["action"] == "repair"

@pytest.mark.parametrize("invalid_bytes", [bytes([255]), bytes([254, 255]), bytes([0, 255])])
def test_non_unicode_ownership_marker_fails_closed(sandbox, invalid_bytes):
    root, system, state, external = sandbox
    marker = root / inv.MARKER
    marker.write_bytes(invalid_bytes)
    assert not inv.valid_ownership_marker(root)
    inv.capture(state, root, system)
    inv.seal(state, system)
    inv.plan_or_uninstall(state, system, apply=True)
    assert (root / "provisioning" / "bin" / "webops").exists()
