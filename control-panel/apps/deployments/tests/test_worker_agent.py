"""The worker agent: catalog, safe extraction, the sandbox primitive and a real end-to-end job.

The sandbox and end-to-end tests change privileges, so they need root and `useradd`; elsewhere they are skipped.
"""
import importlib.util
import io
import os
import pwd
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path
from unittest import mock, skipIf

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import LiveServerTestCase, SimpleTestCase, override_settings

from apps.deployments.models import ApplicationDeployment, BuildJob
from apps.deployments.services import worker_queue as wq

AGENT_PATH = Path(settings.BASE_DIR).parent / "worker" / "webops_worker.py"
spec = importlib.util.spec_from_file_location("webops_worker", AGENT_PATH)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

CAN_SANDBOX = os.geteuid() == 0 and shutil.which("useradd") is not None
LIMITS = {"cpu_seconds": 60, "memory_mb": 4096, "file_mb": 50, "procs": 200, "disk_mb": 200, "wall_seconds": 60}


def make_zip(entries, root="proj-abc", links=()):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in entries.items():
            info = zipfile.ZipInfo(f"{root}/{name}" if root else name)
            info.external_attr = (0o755 if name.endswith(".sh") else 0o644) << 16
            z.writestr(info, data)
        for name, target in links:
            info = zipfile.ZipInfo(f"{root}/{name}")
            info.external_attr = 0o120777 << 16
            z.writestr(info, target)
    return out.getvalue()


class CatalogTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def touch(self, *names, text=""):
        for n in names:
            (self.tmp / n).write_text(text)

    def test_rust_uses_locked_only_with_a_lockfile(self):
        self.assertEqual(agent.plan("rust", self.tmp), [["cargo", "build", "--release"]])
        self.touch("Cargo.lock")
        self.assertEqual(agent.plan("rust", self.tmp), [["cargo", "build", "--release", "--locked"]])

    def test_node_never_runs_install_scripts(self):
        self.touch("package.json", text='{"scripts": {"build": "x", "postinstall": "evil"}}')
        steps = agent.plan("node", self.tmp)
        self.assertEqual(steps, [["npm", "install", "--ignore-scripts"], ["npm", "run", "build"]])
        self.touch("package-lock.json")
        self.assertEqual(agent.plan("node", self.tmp)[0], ["npm", "ci", "--ignore-scripts"])
        self.touch("package.json", text='{"scripts": {"start": "x"}}')
        self.assertEqual(len(agent.plan("node", self.tmp)), 1)
        self.touch("package.json", text="{not json")
        self.assertEqual(len(agent.plan("node", self.tmp)), 1)

    def test_python(self):
        self.touch("requirements.txt")
        self.assertEqual(agent.plan("python", self.tmp)[1][-2:], ["-r", "requirements.txt"])

    def test_unknown_kinds_are_refused_and_commands_are_plain_argv_lists(self):
        for bad in ("bash", "", None, "rust; rm -rf /"):
            with self.assertRaises(ValueError):
                agent.plan(bad, self.tmp)
        for kind in ("rust", "node", "python"):
            self.touch("Cargo.toml", "package.json", "requirements.txt", text="{}")
            for argv in agent.plan(kind, self.tmp):
                self.assertTrue(all(isinstance(a, str) for a in argv) and isinstance(argv, list))

    def test_artifacts_are_listed_conservatively(self):
        rel = self.tmp / "target" / "release"
        rel.mkdir(parents=True)
        (rel / "care").write_text("bin"); (rel / "care").chmod(0o755)
        (rel / "care.d").write_text("x"); (rel / "care.d").chmod(0o755)
        (rel / "notes.txt").write_text("x")
        self.assertEqual(agent.artifacts("rust", self.tmp), ["target/release/care"])

    def test_limits_are_clamped_to_the_agents_own_ceilings(self):
        out = agent.clamp_limits({"wall_seconds": 10 ** 9, "memory_mb": -5, "procs": "many", "file_mb": True, "cpu_seconds": 100})
        self.assertEqual(out["wall_seconds"], agent.CEILING["wall_seconds"])
        self.assertEqual(out["cpu_seconds"], 100)
        self.assertEqual(out["memory_mb"], agent.CEILING["memory_mb"] // 2)
        self.assertEqual(out["procs"], agent.CEILING["procs"] // 2)
        self.assertEqual(out["file_mb"], agent.CEILING["file_mb"] // 2)
        self.assertEqual(agent.clamp_limits(None)["disk_mb"], agent.CEILING["disk_mb"] // 2)

    def test_environment_is_minimal_and_secret_free(self):
        with mock.patch.dict(os.environ, {"WEBOPS_WORKER_TOKEN": "wops_wrk_secret", "WEBOPS_PANEL_URL": "https://panel", "AWS_SECRET_ACCESS_KEY": "x"}):
            env = agent.build_env("/var/lib/webops-worker/jobs/7")
        blob = " ".join(f"{k}={v}" for k, v in env.items())
        for forbidden in ("wops_wrk", "panel", "AWS_", "TOKEN"):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(env["HOME"], "/var/lib/webops-worker/jobs/7")

    def test_the_panel_address_must_be_https(self):
        with self.assertRaises(SystemExit):
            agent.Panel("http://panel.example", "t")
        agent.Panel("https://panel.example/", "t")


class ExtractionTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def extract(self, raw, **kw):
        z = self.tmp / "s.zip"
        z.write_bytes(raw)
        return agent.safe_extract_zip(z, self.tmp / "out", **kw)

    def test_extracts_and_preserves_the_executable_bit(self):
        project = self.extract(make_zip({"a/b.txt": "hi", "run.sh": "#!/bin/sh"}))
        self.assertEqual((project / "a" / "b.txt").read_text(), "hi")
        self.assertTrue(os.access(project / "run.sh", os.X_OK))
        self.assertFalse(os.access(project / "a" / "b.txt", os.X_OK))

    def test_unsafe_archives_are_refused_before_anything_is_written(self):
        for name in ("../../etc/passwd", "/abs/x", "a\\b", "a/../../b"):
            with self.assertRaises(ValueError, msg=name):
                self.extract(make_zip({name: "x"}, root=""))
        self.assertFalse((self.tmp / "out").exists())

    def test_layout_and_size_limits(self):
        # two roots
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("one/a", "x"); z.writestr("two/b", "x")
        with self.assertRaises(ValueError):
            self.extract(out.getvalue())
        with self.assertRaises(ValueError):
            self.extract(make_zip({f"f{i}": "x" for i in range(10)}), max_files=5)
        with self.assertRaises(ValueError):
            self.extract(make_zip({"big": "x" * 1000}), max_bytes=100)

    def test_symlinks_are_never_created(self):
        project = self.extract(make_zip({"a": "1"}, links=[("evil", "/etc/shadow")]))
        self.assertFalse((project / "evil").exists() or (project / "evil").is_symlink())


@skipIf(not CAN_SANDBOX, "needs root and useradd")
class SandboxTests(SimpleTestCase):
    """The privilege-dropping primitive, with deliberately hostile commands."""
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="wo-job-"))
        os.chmod(self.home, 0o755)
        self.name = f"wjt{os.getpid() % 100000}"
        import subprocess
        subprocess.run(["userdel", "-f", self.name], capture_output=True)
        subprocess.run(["useradd", "--no-create-home", "--home-dir", str(self.home), "--shell", "/usr/sbin/nologin", "--user-group", self.name], check=True)
        e = pwd.getpwnam(self.name)
        self.uid, self.gid = e.pw_uid, e.pw_gid
        subprocess.run(["chown", "-R", f"{self.uid}:{self.gid}", str(self.home)], check=True)
        self.addCleanup(self.cleanup)
        self.out = []
        self.secret = Path(tempfile.mkdtemp()) / "token"
        self.secret.write_text("wops_wrk_topsecret")
        self.secret.chmod(0o600)

    def cleanup(self):
        import subprocess
        agent.kill_user_processes(self.uid)
        subprocess.run(["userdel", "-f", self.name], capture_output=True)
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.secret.parent, ignore_errors=True)

    def run_cmd(self, script, limits=None, wall=20):
        lim = {**LIMITS, **(limits or {})}
        self.out.clear()
        code, reason = agent.run_sandboxed(["bash", "-c", script], cwd=self.home, uid=self.uid, gid=self.gid, env=agent.build_env(self.home),
                                           limits=lim, emit=self.out.append, wall_deadline=time.time() + wall, disk_root=self.home)
        return code, reason, "".join(self.out)

    def test_runs_as_the_job_user_without_privileges(self):
        code, _, out = self.run_cmd("id -u; id -G; grep -E 'CapEff|NoNewPrivs' /proc/self/status")
        lines = out.split()
        self.assertEqual(lines[0], str(self.uid))
        self.assertNotEqual(self.uid, 0)
        self.assertEqual(lines[1], str(self.gid))                                   # no supplementary groups
        self.assertIn("CapEff:\t0000000000000000", out)
        self.assertIn("NoNewPrivs:\t1", out)

    def test_cannot_read_the_workers_secrets_or_write_outside_its_directory(self):
        _, _, out = self.run_cmd(f"cat {self.secret} 2>&1; touch /etc/pwned 2>&1; touch /usr/local/pwned 2>&1; touch ./ok && echo wrote-home")
        self.assertNotIn("topsecret", out)
        self.assertEqual(out.count("Permission denied"), 3)
        self.assertIn("wrote-home", out)
        self.assertFalse(Path("/etc/pwned").exists())

    def test_environment_leaks_nothing(self):
        with mock.patch.dict(os.environ, {"WEBOPS_WORKER_TOKEN": "wops_wrk_topsecret", "SOME_API_KEY": "k"}):
            _, _, out = self.run_cmd("env")
        self.assertNotIn("topsecret", out)
        self.assertNotIn("SOME_API_KEY", out)

    def test_resource_limits_are_applied(self):
        _, _, out = self.run_cmd("ulimit -t; ulimit -v; ulimit -f; ulimit -u; ulimit -c")
        cpu, vm, fsize, nproc, core = out.split()
        self.assertEqual((cpu, vm, nproc, core), ("60", str(4096 * 1024), "200", "0"))
        self.assertTrue(int(fsize) in (50 * 1024, 50 * 1024 * 2))                  # 1 KiB or 512-byte blocks, depending on the shell

    def test_wall_clock_limit_kills_the_job(self):
        started = time.time()
        code, reason, _ = self.run_cmd("sleep 60", wall=2)
        self.assertEqual(reason, "wall-clock limit reached")
        self.assertLess(time.time() - started, 15)

    def test_disk_cap_stops_runaway_writes(self):
        # run for real: write more than the cap while the agent watches
        _, reason, _ = self.run_cmd("dd if=/dev/zero of=./fill bs=1M count=40 2>/dev/null; sleep 40", limits={"disk_mb": 5}, wall=60)
        self.assertEqual(reason, "disk limit reached")

    def test_a_process_bomb_is_capped_and_leftovers_are_swept(self):
        _, _, out = self.run_cmd("for i in $(seq 1 400); do sleep 30 & done 2>&1; wait", limits={"procs": 50}, wall=8)
        deadline = time.time() + 5
        while time.time() < deadline and agent._live_pids(self.uid):
            time.sleep(0.2)
        self.assertEqual(agent._live_pids(self.uid), [])

    def test_a_daemonised_child_does_not_survive_the_job(self):
        self.run_cmd("nohup sleep 300 >/dev/null 2>&1 &", wall=10)
        time.sleep(0.5)
        self.assertEqual(agent._live_pids(self.uid), [])


@skipIf(not CAN_SANDBOX, "needs root and useradd")
@override_settings(DEBUG=True, ALLOWED_HOSTS=["*"])
class EndToEndTests(LiveServerTestCase):
    """A real job: panel API over HTTP, the agent downloads, builds as an unprivileged user, reports, cleans up."""
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.op = U.objects.create_user("op", "op@example.com", "pw-123456-x", is_staff=True)
        self.owner = U.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.d = ApplicationDeployment.objects.create(name="demo", repo_url="https://github.com/ifinsta/demo", branch="main",
                                                      deployed_by=self.owner, status="building")
        node, token = wq.create_worker("e2e", self.op)
        self.node = node
        self.jobs = Path(tempfile.mkdtemp(prefix="wo-jobs-"))
        os.chmod(self.jobs, 0o711)
        self.addCleanup(shutil.rmtree, self.jobs, True)
        env = mock.patch.dict(os.environ, {"WEBOPS_WORKER_ALLOW_HTTP": "1"})
        env.start()
        self.addCleanup(env.stop)
        jobs = mock.patch.object(agent, "JOBS_DIR", self.jobs)
        jobs.start()
        self.addCleanup(jobs.stop)
        self.panel = agent.Panel(self.live_server_url, token)

    def enqueue(self, kind, entries):
        job = wq.enqueue(self.d, kind, "b" * 40)
        self.archive = make_zip(entries)
        p = mock.patch.object(wq, "open_source", side_effect=lambda j: iter([self.archive]))
        p.start()
        self.addCleanup(p.stop)
        return job

    def test_python_job_succeeds_and_leaves_nothing_behind(self):
        job = self.enqueue("python", {"requirements.txt": "# nothing to install\n", "app.py": "print('hi')"})
        self.assertTrue(agent.run_once(self.panel))
        job.refresh_from_db(); self.d.refresh_from_db()
        self.assertEqual((job.status, self.d.status), ("succeeded", "stopped"), job.log)
        self.assertIn("python3 -m venv .venv", job.log)
        self.assertIn("pip install", job.log)
        self.assertEqual(job.result["artifacts"], [".venv/"])
        self.assertFalse(list(self.jobs.iterdir()))                                    # job directory removed
        with self.assertRaises(KeyError):
            pwd.getpwnam(f"wj{job.pk}")                                                # job user removed
        self.assertFalse(agent.run_once(self.panel))                                   # nothing else to do

    def test_a_failing_build_is_reported_and_cleaned_up(self):
        job = self.enqueue("rust", {"Cargo.toml": "[package]\nname='x'\n"})            # no cargo on this machine
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            agent.run_once(self.panel)
        job.refresh_from_db(); self.d.refresh_from_db()
        self.assertEqual((job.status, self.d.status), ("failed", "failed"))
        self.assertTrue(job.result["summary"])
        self.assertFalse(list(self.jobs.iterdir()))
        with self.assertRaises(KeyError):
            pwd.getpwnam(f"wj{job.pk}")

    def test_a_hostile_archive_is_refused_not_extracted(self):
        job = self.enqueue("python", {"../../escape.txt": "x"})
        self.archive = make_zip({"../../escape.txt": "x"}, root="")
        agent.run_once(self.panel)
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIn("unsafe path", job.log)
        self.assertFalse(Path("/escape.txt").exists())

    def test_a_revoked_token_stops_the_agent_cleanly(self):
        wq.revoke(self.node)
        status, _ = self.panel.call("POST", "/api/worker/v1/claim", {})
        self.assertEqual(status, 401)
