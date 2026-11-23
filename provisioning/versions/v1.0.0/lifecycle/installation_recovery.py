#!/usr/bin/env python3
"""Read-only WebOps install recovery classifier; never guesses missing history."""
from __future__ import annotations
import argparse
import json
import os
import pwd
import shutil
import subprocess
import tempfile
from pathlib import Path
from installation_inventory import load, valid_install_root, MARKER

STAGE = ".webops-install-stage.json"
VERSION = 1

def inspect(target: Path, state_dir: Path) -> dict:
    try:
        root = valid_install_root(str(target))
    except ValueError as e:
        return {"action": "unsafe", "reason": str(e)}
    if root.is_symlink():
        return {"action": "unsafe", "reason": "Installation root is a symlink"}
    if not root.exists():
        # A missing installation directory does NOT mean a fresh server when
        # inventory still records previous host/package/service changes.
        if (state_dir / "inventory.json").exists():
            return {"action": "repair",
                    "reason": "Install root is missing but previous installation history exists; "
                              "cannot safely start fresh or overwrite the original baseline"}
        return {"action": "fresh", "reason": "No install root or prior inventory exists"}
    if not root.is_dir():
        return {"action": "unsafe", "reason": "Install root is not a directory"}
    script = root / "provisioning/versions/v1.0.0/lifecycle/install.sh"
    if not script.is_file() or script.is_symlink():
        return {"action": "manual", "reason": "Existing directory has no trusted installer"}
    marker = root / MARKER
    if not marker.is_file() or marker.is_symlink() or marker.read_text().strip() != "v1.0.0":
        return {"action": "manual", "reason": "No valid WebOps ownership marker"}
    if (state_dir / "inventory.json").exists():
        try:
            state = load(state_dir)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            return {"action": "manual", "reason": "Invalid inventory; manual recovery required"}
        if Path(state["install_root"]) != root:
            return {"action": "manual", "reason": "Inventory belongs to another installation root"}
        if state["status"] == "sealed":
            # A nonempty string is not evidence; malformed/naive timestamps
            # must not let a corrupted journal declare success.
            from datetime import datetime
            timestamp = state.get("health_verified_at")
            try:
                checked = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else None
            except ValueError:
                checked = None
            if checked is None or checked.tzinfo is None or checked.utcoffset() is None:
                return {"action": "repair", "reason": "Existing installation has no valid recorded health verification"}
            return {"action": "installed", "reason": "Previous installation completed and passed recorded health verification",
                    "health_verified_at": timestamp}
        if state["status"] == "removed":
            return {"action": "manual", "reason": "Previously uninstalled root must be reviewed"}
        if state["status"] == "captured":
            if state.get("phase") == "baseline-captured":
                return {"action": "resume", "reason": "Verified baseline; no host modifications started"}
            if state.get("phase") == "setup-completed":
                return {"action": "finalize",
                        "reason": "Platform setup finished; verify health and seal without rerunning setup"}
            return {"action": "repair",
                    "reason": "Host modifications may be partial; unsafe to replay package/configuration operations",
                    "failure_reason": state.get("failure_reason")}
        return {"action": "manual", "reason": "Unrecognized inventory state"}
    stage = root / STAGE
    if stage.is_file() and not stage.is_symlink():
        try:
            data = json.loads(stage.read_text())
            if data == {"version": VERSION, "phase": "copied", "target": str(root)}:
                return {"action": "staged", "reason": "Copied files, no host modifications started"}
        except (OSError, ValueError):
            pass
        return {"action": "manual", "reason": "Unknown/corrupted installation stage"}
    return {"action": "manual", "reason": "Older/untracked staged root; no proof of safe replay"}

def write_stage(target: Path) -> None:
    root = valid_install_root(str(target))
    if not root.is_dir() or not (root / MARKER).is_file():
        raise ValueError("Staging requires a WebOps-owned directory")
    stage = root / STAGE
    if stage.exists() or stage.is_symlink():
        raise ValueError("Stage already exists")
    temp = root / (STAGE + ".tmp")
    with temp.open("x", encoding="utf-8") as f:
        json.dump({"version": VERSION, "phase": "copied", "target": str(root)}, f)
    temp.chmod(0o600)
    temp.rename(stage)

def advance_stage(target: Path) -> None:
    root = valid_install_root(str(target))
    stage = root / STAGE
    if not stage.is_file() or stage.is_symlink():
        return
    data = json.loads(stage.read_text())
    if data != {"version": VERSION, "phase": "copied", "target": str(root)}:
        raise ValueError("Unexpected stage; refusing installation changes")
    # The state barrier is recorded before any change to system settings.
    tmp = root / (STAGE + ".tmp")
    with tmp.open("x", encoding="utf-8") as f:
        json.dump({"version": VERSION, "phase": "changes-started", "target": str(root)}, f)
    tmp.chmod(0o600)
    tmp.replace(stage)

def legacy_preflight_check(target: Path, state_dir: Path, system_root: Path = Path("/")) -> None:
    """Conservative eligibility test; operator confirmation remains mandatory."""
    root = valid_install_root(str(target))
    status = inspect(root, state_dir)
    if status != {"action": "manual",
                  "reason": "Older/untracked staged root; no proof of safe replay"}:
        raise ValueError("Not an eligible untracked preflight copy: " + status["reason"])
    evidence = (
        "etc/systemd/system/webops-web.service",
        "etc/systemd/system/webops-worker.service",
        "etc/systemd/system/webops-beat.service",
        "etc/systemd/system/webops-channels.service",
        "etc/sudoers.d/webops",
        "etc/sysctl.d/99-webops-base.conf",
        "etc/logrotate.d/webops",
        "var/lib/webops",
    )
    for relative in evidence:
        path = system_root / relative
        if path.exists() or path.is_symlink():
            raise ValueError("Possible previous system modifications: /" + relative)
    for name in ("deployments", "data", "postgresql", "backups", ".secrets",
                 ".install_state", "provisioning/.install_state"):
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError("Existing managed state requires manual recovery: " + name)
    config = root / "config.env"
    if config.is_symlink():
        raise ValueError("Symlinked installation config is unsafe to adopt")
    if config.is_file():
        roots = [
            line.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
            for line in config.read_text().splitlines()
            if line.startswith("WEBOPS_ROOT=")
        ]
        if roots and any(value != str(root) for value in roots):
            raise ValueError("Configuration points to a different installation root")
    if system_root == Path("/"):
        # A platform user from an earlier run invalidates the "preflight only" assumption.
        try:
            pwd.getpwnam("webops")
        except KeyError:
            pass
        else:
            raise ValueError("Existing WebOps system account suggests prior host modifications")
        for service in ("webops-web", "webops-worker", "webops-beat", "webops-channels"):
            try:
                state = subprocess.run(["systemctl", "is-active", service],
                                       capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ValueError("Could not verify WebOps service state") from error
            if state.returncode not in (0, 3, 4) or "System has not been booted" in state.stderr:
                raise ValueError("Cannot trust current service status for " + service)
            if state.stdout.strip() in ("active", "activating", "reloading"):
                raise ValueError("Existing WebOps service is running: " + service)


def adopt_staged(target: Path, state_dir: Path, source_dir: Path,
                 system_root: Path = Path("/")) -> dict:
    """Opt-in recovery of a preflight-only copy; never overwrite user data."""
    legacy_preflight_check(target, state_dir, system_root)
    root = valid_install_root(str(target))
    installed_dir = root / "provisioning/versions/v1.0.0/lifecycle"
    source_dir = source_dir.resolve()
    names = ("install.sh", "installation_inventory.py", "installation_recovery.py")
    for name in names:
        src = source_dir / name
        dest = installed_dir / name
        if not src.is_file() or src.is_symlink() or dest.is_symlink():
            raise ValueError("Unsafe or missing recovery script: " + name)
    state_dir.parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="staged-recovery-", dir=state_dir.parent))
    backup.chmod(0o700)
    for name in names:
        src = source_dir / name
        dest = installed_dir / name
        if dest.is_file():
            shutil.copy2(dest, backup / name, follow_symlinks=False)
        fd, temporary_name = tempfile.mkstemp(prefix=name + ".recovery-", dir=installed_dir)
        temporary = Path(temporary_name)
        try:
            with src.open("rb") as inp, os.fdopen(fd, "wb") as out:
                shutil.copyfileobj(inp, out)
            temporary.chmod(0o755 if name.endswith(".sh") else 0o644)
            os.replace(temporary, dest)
        finally:
            temporary.unlink(missing_ok=True)
    # Mark replayability only after scripts are safely refreshed.
    write_stage(root)
    return {"status": "staged", "backup": str(backup), "root": str(root)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inspect", "stage", "advance", "legacy-check", "adopt"))
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--system-root", type=Path, default=Path("/"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--state-dir", type=Path, default=Path("/var/backups/webops-install/installation-inventory"))
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect(args.target, args.state_dir)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "legacy-check":
            legacy_preflight_check(args.target, args.state_dir, args.system_root)
            print(json.dumps({"eligible": True, "requires_confirmation": True}))
            return 0
        if args.command == "adopt":
            if not args.source_dir:
                raise ValueError("Source directory required for guarded recovery")
            print(json.dumps(adopt_staged(args.target, args.state_dir,
                                          args.source_dir, args.system_root)))
            return 0
        if args.command == "stage":
            write_stage(args.target)
        else:
            advance_stage(args.target)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print("WebOps recovery state error:", e, file=__import__("sys").stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
