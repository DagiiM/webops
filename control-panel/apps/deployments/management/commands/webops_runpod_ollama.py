"""Ollama GPU deployment managed through WebOps models (Runpod development).

No systemd, no CPU-only vLLM build. Real model is downloaded from Ollama
under an unprivileged user and then exposed by an authenticated gateway.
"""
import json
import os
import pwd
import re
import secrets
import signal
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from apps.deployments.models import LLMDeployment, DeploymentLog


def process_alive(pid, needle):
    try:
        return needle in Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except (OSError, ValueError):
        return False


def installed_model(port, name):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tags", timeout=4) as response:
            models = json.load(response).get("models", [])
        return any(m.get("name") == name or m.get("model") == name for m in models)
    except (OSError, ValueError):
        return False


class Command(BaseCommand):
    help = "Install and serve Ollama model through WebOps on an isolated Runpod Pod"

    def add_arguments(self, parser):
        parser.add_argument("--action", choices=("start", "status", "stop"), default="status")
        parser.add_argument("--name", default="jani-small")
        parser.add_argument("--model", default="qwen3:1.7b")
        parser.add_argument("--port", type=int, default=8001)
        parser.add_argument("--upstream-port", type=int, default=8002)
        parser.add_argument("--admin-user", default="webops-admin")

    def handle(self, *args, **options):
        if os.environ.get("WEBOPS_RUNPOD_MODE") != "1":
            raise CommandError("WEBOPS_RUNPOD_MODE=1 is required for development-only adapter")
        name, model_name, action = options["name"], options["model"], options["action"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}", name):
            raise CommandError("Invalid deployment name")
        if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{3,120}", model_name) or model_name.startswith(("/", ".")):
            raise CommandError("Invalid Ollama model name")
        port, upstream = options["port"], options["upstream_port"]
        if port < 1024 or upstream < 1024 or port == upstream:
            raise CommandError("Ports must be distinct and above 1023")
        base = Path(settings.WEBOPS_INSTALL_PATH) / "llm-deployments" / name
        pidfile, keyfile = base / "pids-ollama.json", base / "access.key"
        row = LLMDeployment.objects.filter(name=name).first()
        if action != "start" and not row:
            raise CommandError("Deployment does not exist")
        if action == "start":
            if row and (row.backend != "ollama" or row.model_name != model_name or row.port != port):
                raise CommandError("Conflicting deployment. Choose a different name")
            if pidfile.exists():
                pids = json.loads(pidfile.read_text())
                if process_alive(pids.get("model", 0), "ollama serve") or process_alive(pids.get("gateway", 0), "llm_gateway"):
                    raise CommandError("Processes already running; check status")
            binary = Path("/usr/local/bin/ollama")
            if not binary.is_file():
                raise CommandError("Ollama must first be installed from official Linux package")
            if subprocess.run(["nvidia-smi", "-L"], capture_output=True).returncode:
                raise CommandError("NVIDIA GPU not visible")
            try:
                os_user = pwd.getpwnam("webops")
            except KeyError as error:
                raise CommandError("Create unprivileged OS user webops") from error
            if not row:
                admin = get_user_model().objects.filter(
                    username=options["admin_user"], is_superuser=True).first()
                if not admin:
                    raise CommandError("Create a WebOps superuser before launching")
                row = LLMDeployment.objects.create(name=name, model_name=model_name,
                                                   backend="ollama", port=port, deployed_by=admin)
            uid, gid = os_user.pw_uid, os_user.pw_gid
            base.mkdir(parents=True, exist_ok=True, mode=0o700)
            base.chmod(0o700)
            os.chown(base, uid, gid)
            if not keyfile.exists():
                fd = os.open(str(keyfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w") as handle:
                    handle.write(secrets.token_urlsafe(48) + "\n")
            os.chown(keyfile, uid, gid)
            models_dir = base / "models"
            models_dir.mkdir(exist_ok=True, mode=0o700)
            os.chown(models_dir, uid, gid)
            for p in (base / "ollama.log", base / "ollama-pull.log", base / "gateway.log"):
                p.touch(exist_ok=True, mode=0o600)
                os.chown(p, uid, gid)
            env = os.environ.copy()
            env.update({
                "OLLAMA_HOST": f"127.0.0.1:{upstream}",
                "OLLAMA_MODELS": str(models_dir),
                "OLLAMA_KEEP_ALIVE": "10m",
                "HOME": os_user.pw_dir,
            })
            for k in ("HF_TOKEN", "JANI_API_KEY", "GITHUB_TOKEN"):
                env.pop(k, None)
            with (base / "ollama.log").open("ab") as output:
                server = subprocess.Popen([str(binary), "serve"], cwd=str(base),
                                          env=env, stdout=output, stderr=subprocess.STDOUT,
                                          user=uid, group=gid, start_new_session=True)
            proxy_env = env.copy()
            proxy_env.update({
                "WEBOPS_LLM_KEY_FILE": str(keyfile),
                "WEBOPS_LLM_PROXY_PORT": str(port),
                "WEBOPS_LLM_UPSTREAM_PORT": str(upstream),
                "PYTHONPATH": str(settings.BASE_DIR),
            })
            with (base / "gateway.log").open("ab") as output:
                gateway = subprocess.Popen(
                    ["/workspace/webops/.venv/bin/python", "-m", "apps.deployments.llm_gateway"],
                    cwd=str(settings.BASE_DIR), env=proxy_env,
                    stdout=output, stderr=subprocess.STDOUT,
                    user=uid, group=gid, start_new_session=True)
            # Pull asynchronously after the server's readiness endpoint works.
            script = """import os,subprocess,time,urllib.request,sys
url="http://"+os.environ["OLLAMA_HOST"]+"/api/version"
for i in range(90):
    try:
        with urllib.request.urlopen(url,timeout=2) as response:
            if response.status==200:
                break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("Ollama server unavailable; model pull cancelled")
raise SystemExit(subprocess.call(["/usr/local/bin/ollama","pull",sys.argv[1]]))
"""
            with (base / "ollama-pull.log").open("ab") as output:
                pull = subprocess.Popen(
                    ["/usr/local/bin/python3", "-u", "-c", script, model_name],
                    cwd=str(base), env=env, stdout=output, stderr=subprocess.STDOUT,
                    user=uid, group=gid, start_new_session=True)
            pidfile.write_text(json.dumps({"model": server.pid, "gateway": gateway.pid,
                                           "pull": pull.pid, "upstream_port": upstream,
                                           "model_name": model_name}))
            pidfile.chmod(0o600)
            row.status = LLMDeployment.Status.BUILDING
            row.save(update_fields=["status"])
            DeploymentLog.objects.create(deployment=row, level=DeploymentLog.Level.INFO,
                                         message="Runpod Ollama and authenticated proxy launched; real model pull pending")
            self.stdout.write(f"Ollama launched as webops. Model download started. Local gateway port {port}.")
            return

        pids = json.loads(pidfile.read_text()) if pidfile.exists() else {}
        if action == "stop":
            for name_key, needle in (("gateway", "llm_gateway"), ("pull", "ollama"), ("model", "ollama serve")):
                pid = pids.get(name_key, 0)
                if pid and process_alive(pid, needle):
                    os.kill(pid, signal.SIGTERM)
            pidfile.unlink(missing_ok=True)
            row.status = LLMDeployment.Status.STOPPED
            row.save(update_fields=["status"])
            DeploymentLog.objects.create(deployment=row, level=DeploymentLog.Level.INFO,
                                         message="Runpod Ollama processes stopped")
            self.stdout.write("Stopped")
            return
        server_alive = process_alive(pids.get("model", 0), "ollama serve")
        gateway_alive = process_alive(pids.get("gateway", 0), "llm_gateway")
        model_loaded = server_alive and installed_model(
            pids.get("upstream_port", upstream), row.model_name)
        status = (LLMDeployment.Status.RUNNING if (model_loaded and gateway_alive)
                  else LLMDeployment.Status.BUILDING if server_alive and gateway_alive
                  else LLMDeployment.Status.FAILED)
        row.status = status
        row.save(update_fields=["status"])
        self.stdout.write(f"status={status} server={server_alive} gateway={gateway_alive} model_installed={model_loaded}")
