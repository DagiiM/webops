#!/usr/bin/env python3
"""WebOps build worker agent. Standard library only.

Runs on a separate machine, never on the panel's host. It only ever connects OUT to the panel, authenticates with
a bearer token, claims one job at a time and builds it. See worker/README.md.

What isolates a job (process-level; this container type has no user/network namespaces or cgroups):
  * its own throw-away unprivileged Unix user and a 0700 job directory, deleted afterwards
  * privileges dropped before exec (uid, gid, no supplementary groups, no_new_privs), so no capabilities survive
  * rlimits: CPU time, address space, file size, process count, open files; a wall-clock limit and a disk cap
  * a minimal environment: the worker token and panel address are never visible to a job
  * after the job, every process still owned by that user is killed
It does NOT isolate the network: a job can reach the internet. That is why the panel only schedules repositories
owned by trusted owners and why this machine must hold nothing but the agent.

Jobs name a *kind* (rust, node, python). The agent turns the kind into fixed commands itself; the panel cannot
send a command line.
"""
import ctypes
import json
import os
import pwd
import resource
import selectors
import shutil
import signal
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

VERSION = "1.0"
JOBS_DIR = Path(os.environ.get("WEBOPS_WORKER_JOBS", "/var/lib/webops-worker/jobs"))
TOKEN_FILE = Path(os.environ.get("WEBOPS_WORKER_TOKEN_FILE", "/etc/webops-worker/token"))
POLL_SECONDS = 5
HEARTBEAT_SECONDS = 30
LOG_FLUSH_SECONDS = 2
LOG_FLUSH_BYTES = 8192
MAX_SOURCE_BYTES = 200 * 1024 * 1024
MAX_EXTRACTED_BYTES = 2 * 1024 ** 3
MAX_FILES = 100_000
# The agent's own ceilings: a job's requested limits are clamped to these, whatever the panel asks for.
CEILING = {"wall_seconds": 3600, "cpu_seconds": 14400, "memory_mb": 28 * 1024, "file_mb": 8192, "procs": 4096, "disk_mb": 20 * 1024}
PR_SET_NO_NEW_PRIVS = 38


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


# ───────────────────────────── what a job may run ─────────────────────────────

def plan(kind, src):
    """Fixed command lines for a catalog kind, chosen from what the source contains."""
    src = Path(src)
    if kind == "rust":
        return [["cargo", "build", "--release"] + (["--locked"] if (src / "Cargo.lock").is_file() else [])]
    if kind == "node":
        install = ["npm", "ci", "--ignore-scripts"] if (src / "package-lock.json").is_file() else ["npm", "install", "--ignore-scripts"]
        steps = [install]
        try:
            scripts = (json.loads((src / "package.json").read_text()) or {}).get("scripts") or {}
        except (OSError, ValueError):
            scripts = {}
        if isinstance(scripts, dict) and "build" in scripts:
            steps.append(["npm", "run", "build"])
        return steps
    if kind == "python":
        steps = [["python3", "-m", "venv", ".venv"]]
        if (src / "requirements.txt").is_file():
            steps.append([".venv/bin/pip", "install", "--no-input", "-r", "requirements.txt"])
        elif (src / "pyproject.toml").is_file():
            steps.append([".venv/bin/pip", "install", "--no-input", "."])
        return steps
    raise ValueError("Unsupported job kind: %r" % (kind,))


def artifacts(kind, src):
    src = Path(src)
    found = []
    if kind == "rust":
        release = src / "target" / "release"
        if release.is_dir():
            for p in sorted(release.iterdir()):
                if p.is_file() and not p.is_symlink() and os.access(p, os.X_OK) and p.suffix not in (".d", ".so", ".rlib", ".a"):
                    found.append("target/release/" + p.name)
    elif kind == "node":
        found = [d + "/" for d in ("dist", "build", "out") if (src / d).is_dir()] + (["node_modules/"] if (src / "node_modules").is_dir() else [])
    elif kind == "python":
        found = [".venv/"] if (src / ".venv").is_dir() else []
    return found[:20]


def clamp_limits(requested):
    out = {}
    for key, ceiling in CEILING.items():
        value = requested.get(key) if isinstance(requested, dict) else None
        out[key] = min(int(value), ceiling) if isinstance(value, int) and not isinstance(value, bool) and value > 0 else ceiling // 2
    return out


def build_env(home, token_free=True):
    """The only environment a job sees. Nothing from the agent's own environment is passed on."""
    home = str(home)
    return {
        "PATH": "/opt/rust/cargo/bin:/usr/local/bin:/usr/bin:/bin", "HOME": home, "TMPDIR": home + "/tmp", "LANG": "C.UTF-8", "CI": "1",
        "CARGO_HOME": home + "/.cargo", "RUSTUP_HOME": "/opt/rust/rustup", "npm_config_cache": home + "/.npm",
        "PIP_CACHE_DIR": home + "/.pip", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "NO_COLOR": "1",
    }


# ───────────────────────────── source ─────────────────────────────

def safe_extract_zip(zip_path, dest, max_files=MAX_FILES, max_bytes=MAX_EXTRACTED_BYTES):
    """Extract a GitHub archive: no absolute or parent paths, no links, bounded size. Returns the project folder."""
    dest = Path(dest)
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > max_files or sum(m.file_size for m in members) > max_bytes:
            raise ValueError("The source is too large.")
        roots = set()
        for item in members:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in item.filename or "\x00" in item.filename:
                raise ValueError("The source contains an unsafe path.")
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError("The source has an unexpected layout.")
        dest.mkdir(parents=True, exist_ok=True)
        for item in members:
            if stat.S_ISLNK(item.external_attr >> 16):
                continue                                                     # links are never created
            target = dest / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, open(target, "xb") as out:
                shutil.copyfileobj(source, out, 65536)
            mode = (item.external_attr >> 16) & 0o777
            os.chmod(target, 0o755 if mode & 0o100 else 0o644)
    return dest / roots.pop()


# ───────────────────────────── the sandbox ─────────────────────────────

def _no_new_privs():
    ctypes.CDLL(None, use_errno=True).prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)


def _limiter(limits):
    def apply():
        os.setsid()
        os.umask(0o077)
        _no_new_privs()
        mb = 1024 * 1024
        for res, value in ((resource.RLIMIT_CPU, limits["cpu_seconds"]), (resource.RLIMIT_AS, limits["memory_mb"] * mb),
                           (resource.RLIMIT_FSIZE, limits["file_mb"] * mb), (resource.RLIMIT_NPROC, limits["procs"]),
                           (resource.RLIMIT_NOFILE, 4096), (resource.RLIMIT_CORE, 0)):
            resource.setrlimit(res, (value, value))
    return apply


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _live_pids(uid):
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if os.stat(f"/proc/{entry}").st_uid != uid:
                continue
            with open(f"/proc/{entry}/stat") as handle:
                state = handle.read().rsplit(")", 1)[1].split()[0]
            if state != "Z":                           # a zombie is already dead; only its parent can reap it
                pids.append(int(entry))
        except (OSError, IndexError):
            pass
    return pids


def kill_user_processes(uid):
    """SIGKILL everything still owned by this uid (daemonised or escaped children included)."""
    for _ in range(5):
        pids = _live_pids(uid)
        if not pids:
            return
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.2)


def run_sandboxed(argv, *, cwd, uid, gid, env, limits, emit, wall_deadline, disk_root):
    """Run one command as the job user. Returns (exit_code, reason) where reason is '' or why it was stopped."""
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            user=uid, group=gid, extra_groups=[], preexec_fn=_limiter(limits), close_fds=True)
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    buffer, last_flush, last_disk, reason = b"", time.monotonic(), 0.0, ""
    try:
        while True:
            for key, _ in selector.select(timeout=1.0):
                chunk = os.read(key.fd, 4096)
                if chunk:
                    buffer += chunk
            now = time.monotonic()
            if buffer and (len(buffer) >= LOG_FLUSH_BYTES or now - last_flush >= LOG_FLUSH_SECONDS):
                emit(buffer.decode("utf-8", "replace"))
                buffer, last_flush = b"", now
            if proc.poll() is not None:
                break
            if time.time() > wall_deadline:
                reason = "wall-clock limit reached"
            elif now - last_disk > 10:
                last_disk = now
                if dir_size(disk_root) > limits["disk_mb"] * 1024 * 1024:
                    reason = "disk limit reached"
            if reason:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                proc.wait()
                break
        rest = proc.stdout.read()
        buffer += rest or b""
        if buffer:
            emit(buffer.decode("utf-8", "replace"))
    finally:
        selector.close()
        kill_user_processes(uid)
    return proc.returncode, reason


# ───────────────────────────── panel client ─────────────────────────────

class Panel:
    def __init__(self, base, token):
        allow_http = os.environ.get("WEBOPS_WORKER_ALLOW_HTTP") == "1"            # tests only
        if not (base.startswith("https://") or (allow_http and base.startswith("http://"))):
            raise SystemExit("WEBOPS_PANEL_URL must be an https:// address")
        self.base, self.token = base.rstrip("/"), token
        self.context = ssl.create_default_context()

    def _open(self, method, path, body=None, timeout=30):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.token, "Content-Type": "application/json", "User-Agent": "webops-worker/" + VERSION})
        return urllib.request.urlopen(req, timeout=timeout, context=self.context)

    def call(self, method, path, body=None):
        try:
            with self._open(method, path, body) as response:
                raw = response.read(1_000_000)
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            return exc.code, None

    def download(self, path, destination, limit=MAX_SOURCE_BYTES):
        with self._open("GET", path, timeout=60) as response, open(destination, "wb") as out:
            total = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    return total
                total += len(chunk)
                if total > limit:
                    raise ValueError("The source download exceeded the size limit.")
                out.write(chunk)


def host_info():
    info = {"agent": "webops-worker/" + VERSION, "os": " ".join(os.uname()[:1] + os.uname()[2:3]), "cpus": os.cpu_count() or 0,
            "isolation": "process: unprivileged user, rlimits, no_new_privs; no network isolation"}
    try:
        info["free_disk_gb"] = shutil.disk_usage(JOBS_DIR.parent if JOBS_DIR.parent.exists() else "/").free / 1024 ** 3
        limit = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if limit.isdigit():
            info["memory_gb"] = int(limit) / 1024 ** 3
    except OSError:
        pass
    return info


# ───────────────────────────── a job ─────────────────────────────

def create_job_user(job_id):
    name = f"wj{job_id}"
    subprocess.run(["userdel", "-f", name], capture_output=True)
    done = subprocess.run(["useradd", "--no-create-home", "--home-dir", str(JOBS_DIR / str(job_id)), "--shell", "/usr/sbin/nologin",
                           "--user-group", name], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("Could not create the job user: " + done.stderr.strip()[:200])
    entry = pwd.getpwnam(name)
    return name, entry.pw_uid, entry.pw_gid


def handle(panel, job):
    job_id, kind = int(job["id"]), job["kind"]
    limits = clamp_limits(job.get("limits"))
    home = JOBS_DIR / str(job_id)
    name = uid = gid = None
    pending = []

    def emit(text):
        pending.append(text)
        status, _ = panel.call("POST", f"/api/worker/v1/jobs/{job_id}/log", {"text": "".join(pending)})
        if status == 200:
            pending.clear()

    ok, exit_code, summary, found = False, None, "", []
    try:
        if os.geteuid() != 0:
            raise RuntimeError("The agent must run as root to drop privileges per job.")
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(JOBS_DIR, 0o711)                      # job users must be able to reach their own 0700 directory, not list others
        shutil.rmtree(home, ignore_errors=True)
        home.mkdir(parents=True, mode=0o700)
        name, uid, gid = create_job_user(job_id)
        archive = home / "source.zip"
        panel.download(f"/api/worker/v1/jobs/{job_id}/source", archive)
        project = safe_extract_zip(archive, home / "src")
        archive.unlink()
        for sub in ("tmp", ".cargo", ".npm", ".pip"):
            (home / sub).mkdir(exist_ok=True)
        subprocess.run(["chown", "-R", f"{uid}:{gid}", str(home)], check=True)
        os.chmod(home, 0o700)
        env = build_env(home)
        deadline = time.time() + limits["wall_seconds"]
        emit(f"== job {job_id}: {kind} build of commit {job.get('commit', '')[:10]} (attempt {job.get('attempt', 1)})\n")
        steps = plan(kind, project)
        for number, argv in enumerate(steps, 1):
            emit(f"\n$ [{number}/{len(steps)}] {' '.join(argv)}\n")
            code, reason = run_sandboxed(argv, cwd=project, uid=uid, gid=gid, env=env, limits=limits, emit=emit,
                                         wall_deadline=deadline, disk_root=home)
            exit_code = code
            if reason:
                summary = f"Stopped: {reason}."
                break
            if code != 0:
                summary = f"Step {number} ({argv[0]}) exited with {code}."
                break
        else:
            ok, summary, found = True, f"{len(steps)} step(s) succeeded.", artifacts(kind, project)
    except Exception as exc:                                    # reported to the panel, never raised past the loop
        summary = f"Worker error: {str(exc)[:200]}"
        emit(f"\n{summary}\n")
    finally:
        if uid is not None:
            kill_user_processes(uid)
        if name:
            subprocess.run(["userdel", "-f", name], capture_output=True)
        shutil.rmtree(home, ignore_errors=True)
    if pending:
        panel.call("POST", f"/api/worker/v1/jobs/{job_id}/log", {"text": "".join(pending)})
    panel.call("POST", f"/api/worker/v1/jobs/{job_id}/complete", {"ok": ok, "exit_code": exit_code, "summary": summary, "artifacts": found})
    log(f"job {job_id} {'succeeded' if ok else 'failed'}: {summary}")
    return ok


def run_once(panel):
    """Claim and run at most one job. Returns True if a job was run."""
    status, job = panel.call("POST", "/api/worker/v1/claim", {})
    if status == 200 and job:
        handle(panel, job)
        return True
    return False


def main():
    base = os.environ.get("WEBOPS_PANEL_URL", "")
    token = os.environ.get("WEBOPS_WORKER_TOKEN") or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.is_file() else "")
    if not base or not token:
        raise SystemExit("Set WEBOPS_PANEL_URL and provide the token in %s" % TOKEN_FILE)
    os.environ.pop("WEBOPS_WORKER_TOKEN", None)                 # never inherited by anything we start
    panel = Panel(base, token)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(JOBS_DIR, 0o711)
    log(f"webops-worker {VERSION} polling {panel.base}")
    last_beat, failures = 0.0, 0
    while True:
        try:
            if time.monotonic() - last_beat > HEARTBEAT_SECONDS:
                status, _ = panel.call("POST", "/api/worker/v1/heartbeat", host_info())
                if status == 401:
                    raise SystemExit("The panel rejected this worker's token (revoked?).")
                last_beat = time.monotonic()
            if not run_once(panel):
                time.sleep(POLL_SECONDS)
            failures = 0
        except SystemExit:
            raise
        except Exception as exc:
            failures += 1
            log(f"error: {exc}")
            time.sleep(min(60, POLL_SECONDS * failures))


if __name__ == "__main__":
    main()
