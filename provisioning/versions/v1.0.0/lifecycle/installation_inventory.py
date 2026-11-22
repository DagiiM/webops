#!/usr/bin/env python3
"""Record and safely reverse WebOps-owned installation changes.

Use a root-owned state directory outside the installation tree. Unrecognized
or subsequently modified resources are preserved and reported, not overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

VERSION = 1
MARKER = ".webops-install-origin"
CONFIG_PATHS = (
    "/etc/ssh/sshd_config",
    "/etc/hostname",
    "/etc/hosts",
    "/etc/timezone",
    "/etc/fstab",
    "/etc/fstab.webops-backup",
    "/etc/security/limits.conf",
    "/etc/security/limits.d/99-webops.conf",
    "/etc/sysctl.d/99-webops-base.conf",
    "/etc/sudoers.d/webops",
    "/etc/systemd/journald.conf.d/99-webops.conf",
    "/etc/logrotate.d/webops",
    "/etc/logrotate.d/webops-autorecovery",
    "/etc/apt/apt.conf.d/50unattended-upgrades",
    "/etc/apt/apt.conf.d/20auto-upgrades",
    "/etc/chrony/chrony.conf",
    "/etc/chrony.conf",
    "/etc/redis/redis.conf",
    "/etc/redis/redis.conf.webops-backup",
    "/etc/redis.conf",
    "/etc/nginx/sites-available/webops",
    "/etc/nginx/sites-enabled/webops",
    "/etc/nginx/conf.d/webops",
    "/etc/systemd/system/webops-web.service",
    "/etc/systemd/system/webops-worker.service",
    "/etc/systemd/system/webops-beat.service",
    "/etc/systemd/system/webops-channels.service",
    "/etc/systemd/system/etcd.service",
    "/etc/apt/sources.list.d/kubernetes.list",
    "/etc/apt/keyrings/kubernetes-apt-keyring.gpg",
    "/etc/yum.repos.d/kubernetes.repo",
    "/etc/modules-load.d/k8s.conf",
    "/etc/sysctl.d/k8s.conf",
    "/etc/containerd/config.toml",
    "/usr/local/bin/webops-etcd-backup",
    "/usr/local/bin/webops-k8s-status",
    "/usr/local/bin/webops-k8s-join",
    "/usr/local/bin/webops-k8s-reset",
)
CONFIG_DIRS = ("/etc/ufw", "/etc/firewalld")
SHARED_SERVICES = ("nginx", "postgresql", "redis-server", "ssh", "sshd",
                   "systemd-journald", "chrony", "rsyslog", "ufw", "firewalld")
WEBOPS_SERVICES = ("webops-web", "webops-worker", "webops-beat", "webops-channels")
PRESERVE_DIRS = frozenset(("deployments", "data", "backups", "logs", "postgresql",
                            "redis", "storage", "media", "uploads", ".secrets",
                            "sites", "projects", "user-data", "databases"))


def command(*argv: str) -> str:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=12)
        if argv[:2] in (("systemctl", "is-active"), ("systemctl", "is-enabled")):
            return p.stdout.strip()  # Inactive/disabled commonly use nonzero exit codes.
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def signature(path: Path) -> str:
    """Do not follow symbolic links, including into other users' directories."""
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_file():
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        return "file:" + h.hexdigest() + ":" + oct(stat.S_IMODE(path.stat().st_mode))
    if path.is_dir():
        entries = []
        for child in sorted(path.iterdir(), key=lambda p: p.name):
            entries.append((child.name, signature(child)))
        raw = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        return "dir:" + hashlib.sha256(raw).hexdigest()
    return "absent"


def valid_install_root(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or str(path) in ("/", "/opt", "/var", "/home", "/usr"):
        raise ValueError("Unsafe installation root: " + raw)
    if path.is_symlink() or path.resolve() != path:
        raise ValueError("Installation root must not be a symlink or contain traversal")
    return path


def state_path(state_dir: Path) -> Path:
    return state_dir / "inventory.json"


def atomic_save(state_dir: Path, data: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    file = state_path(state_dir)
    temp = state_dir / "inventory.json.tmp"
    with temp.open("w", encoding="utf-8") as out:
        json.dump(data, out, indent=2, sort_keys=True)
    os.chmod(temp, 0o600)
    temp.replace(file)


def load(state_dir: Path) -> dict:
    with state_path(state_dir).open(encoding="utf-8") as inp:
        data = json.load(inp)
    if data.get("version") != VERSION or data.get("status") not in ("captured", "sealed", "removed"):
        raise ValueError("Invalid installation inventory")
    valid_install_root(data["install_root"])
    if set(data["config"]) != set(CONFIG_PATHS + CONFIG_DIRS):
        raise ValueError("Inventory paths differ from the audited allowlist")
    return data


def system_path(path: str, system_root: Path) -> Path:
    """Optional filesystem root is for isolated tests, never user-supplied production paths."""
    return system_root / path.lstrip("/")


def capture(state_dir: Path, install_root: Path, system_root: Path) -> dict:
    if state_path(state_dir).exists():
        raise ValueError("An installation inventory already exists; refusing to overwrite it")
    originals = state_dir / "originals"
    originals.mkdir(parents=True, exist_ok=False)
    os.chmod(state_dir, 0o700)
    os.chmod(originals, 0o700)
    config = {}
    for index, name in enumerate(CONFIG_PATHS + CONFIG_DIRS):
        target = system_path(name, system_root)
        before = signature(target)
        if before != "absent":
            dest = originals / str(index)
            if target.is_symlink():
                dest.symlink_to(os.readlink(target))
            elif target.is_dir():
                shutil.copytree(target, dest, symlinks=True)
            else:
                shutil.copy2(target, dest, follow_symlinks=False)
        config[name] = {"before": before, "after": None, "backup": str(index)}
    services = {s: {"active_before": command("systemctl", "is-active", s),
                    "enabled_before": command("systemctl", "is-enabled", s)}
                for s in SHARED_SERVICES + WEBOPS_SERVICES}
    packages = command("dpkg-query", "-W", "-f=" + chr(36) + "{binary:Package}\\n")
    data = {
        "version": VERSION, "status": "captured", "install_root": str(install_root),
        "owned_root": (install_root / MARKER).is_file(),
        "config": config, "services": services,
        "packages_before": sorted(packages.splitlines()) if packages else [],
        "hostname_before": command("hostnamectl", "--static"),
        "ufw_before": command("ufw", "status"),
        "tracked_files": {},
    }
    atomic_save(state_dir, data)
    return data


def is_protected(relative: Path) -> bool:
    return any(part in PRESERVE_DIRS for part in relative.parts)


def tree_inventory(root: Path) -> dict:
    """Only inventory a fresh, WebOps-marked tree; leave data locations alone."""
    found = {}
    if not root.is_dir():
        return found
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        rel = current.relative_to(root)
        dirs[:] = sorted(d for d in dirs if not is_protected(rel / d)
                         and not (current / d).is_symlink())
        for name in sorted(files):
            relative = rel / name
            if is_protected(relative):
                continue
            path = current / name
            if path.is_symlink() or path.is_file():
                found[str(relative)] = signature(path)
    return found


def seal(state_dir: Path, system_root: Path) -> dict:
    data = load(state_dir)
    if data["status"] != "captured":
        raise ValueError("Inventory is not awaiting completion")
    for name in data["config"]:
        data["config"][name]["after"] = signature(system_path(name, system_root))
    for service, states in data["services"].items():
        states["active_after"] = command("systemctl", "is-active", service)
        states["enabled_after"] = command("systemctl", "is-enabled", service)
    packages_after = command("dpkg-query", "-W", "-f=" + chr(36) + "{binary:Package}\\n")
    data["packages_after"] = sorted(packages_after.splitlines()) if packages_after else []
    data["ufw_after"] = command("ufw", "status")
    data["hostname_after"] = command("hostnamectl", "--static")
    root = valid_install_root(data["install_root"])
    if data["owned_root"]:
        if not (root / MARKER).is_file():
            raise ValueError("Installation ownership marker disappeared")
        data["tracked_files"] = tree_inventory(root)
    data["status"] = "sealed"
    atomic_save(state_dir, data)
    return data


def run_system(argv: list[str], reports: dict) -> None:
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        if completed.returncode:
            reports["warnings"].append("Command failed: " + " ".join(argv))
    except (OSError, subprocess.TimeoutExpired):
        reports["warnings"].append("Command unavailable: " + " ".join(argv))


def plan_or_uninstall(state_dir: Path, system_root: Path, apply: bool,
                      purge_data: bool = False) -> dict:
    data = load(state_dir)
    if data["status"] == "removed":
        raise ValueError("This installation has already been uninstalled")
    if data["status"] != "sealed":
        raise ValueError("Installation inventory is incomplete; refusing removal")
    root = valid_install_root(data["install_root"])
    if purge_data and not data["owned_root"]:
        raise ValueError("Cannot purge data: install root ownership has not been established")
    report = {"restored": [], "removed": [], "preserved": [], "warnings": []}
    if not data["owned_root"]:
        report["warnings"].append("Root not proven WebOps-owned: preserve installation directory")
    elif not (root / MARKER).is_file():
        raise ValueError("WebOps ownership marker missing; refusing installation tree cleanup")

    # Preflight every required backup BEFORE changing anything; an incomplete
    # or corrupted backup must never cause a half-restored system.
    for name, record in data["config"].items():
        if record["before"] == record["after"]:
            continue
        if signature(system_path(name, system_root)) == record["after"] and record["before"] != "absent":
            saved = state_dir / "originals" / record["backup"]
            if signature(saved) != record["before"]:
                raise ValueError("Original backup is missing or corrupted: " + name)

    # Before overwriting a production SSH configuration, verify the original
    # saved configuration with sshd. A corrupt backup must never lock out SSH.
    ssh_name = "/etc/ssh/sshd_config"
    ssh_state = data["config"][ssh_name]
    if (system_root == Path("/") and
            ssh_state["before"] not in ("absent", ssh_state["after"]) and
            signature(system_path(ssh_name, system_root)) == ssh_state["after"]):
        ssh_backup = state_dir / "originals" / ssh_state["backup"]
        try:
            check = subprocess.run(["sshd", "-t", "-f", str(ssh_backup)],
                                   capture_output=True, text=True, timeout=12)
            if check.returncode:
                raise ValueError("Saved SSH configuration failed validation; refusing uninstall")
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Could not validate saved SSH configuration") from error

    # Preflight untrusted JSON relative paths before any changes.
    for relative in data["tracked_files"]:
        part = Path(relative)
        if part.is_absolute() or ".." in part.parts or is_protected(part):
            raise ValueError("Unsafe inventory entry: " + relative)

    # Compare with the installed state; never overwrite subsequent user changes.
    for name, record in data["config"].items():
        path = system_path(name, system_root)
        current = signature(path)
        if current != record["after"]:
            report["preserved"].append(name + " (changed since installation)")
            continue
        if record["before"] == record["after"]:
            continue
        report["restored"].append(name)
        if not apply:
            continue
        source = state_dir / "originals" / record["backup"]
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
        if record["before"] != "absent":
            path.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                path.symlink_to(os.readlink(source))
            elif source.is_dir():
                shutil.copytree(source, path, symlinks=True)
            else:
                shutil.copy2(source, path, follow_symlinks=False)

    if data["owned_root"]:
        for relative, expected in data["tracked_files"].items():
            candidate = root / relative
            if (Path(relative).is_absolute() or ".." in Path(relative).parts
                    or not candidate.is_relative_to(root) or is_protected(Path(relative))):
                raise ValueError("Unsafe inventory entry: " + relative)
            # Do not traverse symlinked parent directories.
            if any(parent.is_symlink() for parent in candidate.parents if parent == root or root in parent.parents):
                report["preserved"].append(str(candidate) + " (symlinked parent)")
                continue
            if signature(candidate) != expected:
                report["preserved"].append(str(candidate) + " (changed since installation)")
                continue
            report["removed"].append(str(candidate))
            if apply:
                candidate.unlink()
        if purge_data:
            for name in sorted(PRESERVE_DIRS):
                target = root / name
                if target.is_symlink():
                    report["preserved"].append(str(target) + " (symlink)")
                elif target.is_dir():
                    report["removed"].append(str(target) + " (data purge)")
                    if apply:
                        shutil.rmtree(target)
        if apply and root.exists():
            for parent, dirs, files in os.walk(root, topdown=False, followlinks=False):
                path = Path(parent)
                if not path.is_symlink():
                    try:
                        path.rmdir()
                    except OSError:
                        pass

    if apply and system_root == Path("/"):
        for service in WEBOPS_SERVICES:
            baseline = data["services"].get(service, {})
            post = baseline.get("active_after", "")
            enabled_post = baseline.get("enabled_after", "")
            if post and command("systemctl", "is-active", service) == post:
                run_system(["systemctl", "start" if baseline.get("active_before") == "active"
                            else "stop", service], report)
            if enabled_post and command("systemctl", "is-enabled", service) == enabled_post:
                run_system(["systemctl", "enable" if baseline.get("enabled_before") == "enabled"
                            else "disable", service], report)
        run_system(["systemctl", "daemon-reload"], report)
        for service in SHARED_SERVICES:
            states = data["services"][service]
            if states.get("active_after") and command("systemctl", "is-active", service) == states["active_after"]:
                before = states.get("active_before")
                if before in ("active", "inactive", "failed", "not-found"):
                    run_system(["systemctl", "start" if before == "active" else "stop", service], report)
            if states.get("enabled_after") and command("systemctl", "is-enabled", service) == states["enabled_after"]:
                before = states.get("enabled_before")
                if before in ("enabled", "disabled", "not-found"):
                    run_system(["systemctl", "enable" if before == "enabled" else "disable", service], report)
        if "/etc/ssh/sshd_config" in report["restored"]:
            run_system(["sshd", "-t"], report)
            run_system(["systemctl", "reload", "ssh"], report)
        if "/etc/sysctl.d/99-webops-base.conf" in report["restored"]:
            run_system(["sysctl", "--system"], report)
        if "/etc/ufw" in report["restored"]:
            ufw_before = data.get("ufw_before", "")
            ufw_after = data.get("ufw_after", "")
            ufw_now = command("ufw", "status")
            if ufw_before and ufw_after and ufw_now == ufw_after:
                if "Status: inactive" in ufw_before:
                    run_system(["ufw", "--force", "disable"], report)
                elif "Status: active" in ufw_before:
                    run_system(["ufw", "--force", "reload"], report)
            else:
                report["warnings"].append("UFW runtime state changed; check restored firewall rules")
        if "/etc/firewalld" in report["restored"]:
            run_system(["firewall-cmd", "--reload"], report)
        before = data.get("hostname_before")
        after = data.get("hostname_after")
        if before and after and before != after and command("hostnamectl", "--static") == after:
            run_system(["hostnamectl", "set-hostname", before], report)
    added = sorted(set(data.get("packages_after", [])) - set(data.get("packages_before", [])))
    if added:
        report["warnings"].append(
            "Installed OS packages retained for safety (review before manual removal): " +
            ", ".join(added))
    report["warnings"].append(
        "Untracked system changes and external resources require manual review; "
        "exact machine rollback is not guaranteed.")
    if apply:
        data["status"] = "removed"
        data["uninstall_report"] = report
        atomic_save(state_dir, data)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "seal", "plan", "uninstall"))
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--install-root")
    parser.add_argument("--system-root", type=Path, default=Path("/"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--purge-data", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "capture":
            if not args.install_root:
                raise ValueError("--install-root required for capture")
            output = capture(args.state_dir, valid_install_root(args.install_root), args.system_root)
        elif args.action == "seal":
            output = seal(args.state_dir, args.system_root)
        else:
            output = plan_or_uninstall(args.state_dir, args.system_root,
                                       apply=args.action == "uninstall",
                                       purge_data=args.purge_data)
        print(json.dumps(output if args.action in ("plan", "uninstall")
                         else {"status": output["status"], "owned_root": output["owned_root"]},
                         indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print("WebOps installation inventory error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
