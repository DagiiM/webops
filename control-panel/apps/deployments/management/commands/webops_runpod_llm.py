"""Runpod Pod development launcher for WebOps-managed LLM deployment records.

Requires a preinstalled GPU-capable vLLM environment. This does NOT replace
WebOps' VPS/systemd production deployment path. It keeps the public-facing
gateway authenticated and the actual model bound to loopback.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import secrets
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.deployments.models import LLMDeployment, DeploymentLog


def alive(pid: int, needle: str) -> bool:
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
        return needle in cmd
    except (OSError, ValueError):
        return False


def model_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            return r.status == 200
    except (OSError, urllib.error.URLError):
        return False


class Command(BaseCommand):
    help = "Run a private, authenticated vLLM gateway on a Runpod development Pod"

    def add_arguments(self, parser):
        parser.add_argument("--action", choices=("start", "status", "stop"), default="status")
        parser.add_argument("--name", default="jani-small")
        parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
        parser.add_argument("--port", type=int, default=8001)
        parser.add_argument("--upstream-port", type=int, default=8002)
        parser.add_argument("--admin-user", default="webops-admin")
        parser.add_argument("--max-model-len", type=int, default=2048)

    def handle(self, *args, **options):
        if os.environ.get("WEBOPS_RUNPOD_MODE") != "1":
            raise CommandError("Set WEBOPS_RUNPOD_MODE=1 for this development-only adapter")
        name = options["name"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}", name):
            raise CommandError("Invalid deployment name")
        if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", options["model"]):
            raise CommandError("Model must be a Hugging Face organization/name")
        if options["port"] == options["upstream_port"] or min(options["port"], options["upstream_port"]) < 1024:
            raise CommandError("Ports must be distinct and >= 1024")
        base = Path(settings.WEBOPS_INSTALL_PATH) / "llm-deployments" / name
        pidfile = base / "pids.json"
        keyfile = base / "access.key"
        records = LLMDeployment.objects.filter(name=name)
        deployment = records.first()
        action = options["action"]

        if action != "start" and deployment is None:
            raise CommandError("No deployment record exists")

        if action == "start":
            if deployment and (deployment.model_name != options["model"] or deployment.port != options["port"]):
                raise CommandError("Existing deployment differs; use a new name")
            if pidfile.exists():
                pids = json.loads(pidfile.read_text())
                if alive(pids.get("model", 0), "vllm") or alive(pids.get("gateway", 0), "llm_gateway"):
                    raise CommandError("Service already started; use --action status")
            try:
                service_user = pwd.getpwnam("webops")
            except KeyError as exc:
                raise CommandError("Create dedicated unprivileged system user 'webops' first") from exc
            python = Path(os.environ.get("WEBOPS_LLM_PYTHON", "/usr/local/bin/python3"))
            if not python.exists():
                raise CommandError(f"Runtime Python not found: {python}")
            if subprocess.run(["nvidia-smi", "-L"], capture_output=True).returncode != 0:
                raise CommandError("NVIDIA GPU is not available")
            if not deployment:
                admin = get_user_model().objects.filter(username=options["admin_user"], is_superuser=True).first()
                if not admin:
                    raise CommandError("An actual WebOps administrator is required")
                deployment = LLMDeployment.objects.create(
                    name=name, model_name=options["model"], backend="vllm",
                    port=options["port"], deployed_by=admin)
            base.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chown(base, service_user.pw_uid, service_user.pw_gid)
            if not keyfile.exists():
                fd = os.open(str(keyfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(secrets.token_urlsafe(48) + "\n")
            os.chown(keyfile, service_user.pw_uid, service_user.pw_gid)
            for p in (base / "cache", base / "model.log", base / "gateway.log"):
                if p.suffix == ".log":
                    p.touch(mode=0o600, exist_ok=True)
                else:
                    p.mkdir(parents=True, exist_ok=True)
                os.chown(p, service_user.pw_uid, service_user.pw_gid)
            env = os.environ.copy()
            env.update({"HF_HOME": str(base / "cache"), "TOKENIZERS_PARALLELISM": "false"})
            env.pop("VLLM_TARGET_DEVICE", None)
            model_cmd = [
                str(python), "-m", "vllm.entrypoints.openai.api_server",
                "--model", options["model"], "--host", "127.0.0.1",
                "--port", str(options["upstream_port"]),
                "--dtype", "half", "--gpu-memory-utilization", "0.78",
                "--max-model-len", str(options["max_model_len"]),
                "--max-num-seqs", "2", "--enforce-eager",
                "--served-model-name", name,
            ]
            gateway_env = env.copy()
            gateway_env.update({
                "WEBOPS_LLM_KEY_FILE": str(keyfile),
                "WEBOPS_LLM_PROXY_PORT": str(options["port"]),
                "WEBOPS_LLM_UPSTREAM_PORT": str(options["upstream_port"]),
                "PYTHONPATH": str(settings.BASE_DIR),
            })
            uid, gid = service_user.pw_uid, service_user.pw_gid
            with (base / "model.log").open("ab") as log:
                model = subprocess.Popen(model_cmd, env=env, cwd=str(base),
                                         stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True, user=uid, group=gid)
            with (base / "gateway.log").open("ab") as log:
                gateway = subprocess.Popen(
                    [str(python), "-m", "apps.deployments.llm_gateway"],
                    env=gateway_env, cwd=str(settings.BASE_DIR),
                    stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True, user=uid, group=gid)
            pidfile.write_text(json.dumps({"model": model.pid, "gateway": gateway.pid,
                                           "upstream_port": options["upstream_port"]}))
            pidfile.chmod(0o600)
            deployment.status = LLMDeployment.Status.BUILDING
            deployment.save(update_fields=["status"])
            DeploymentLog.objects.create(deployment=deployment, level=DeploymentLog.Level.INFO,
                                         message="Runpod vLLM and authenticated gateway launched; awaiting health checks")
            self.stdout.write(f"Started {name}; health pending; port {options['port']}; key held in private file")
            return

        pids = json.loads(pidfile.read_text()) if pidfile.exists() else {}
        if action == "stop":
            for kind, marker in (("gateway", "llm_gateway"), ("model", "vllm")):
                pid = pids.get(kind, 0)
                if pid and alive(pid, marker):
                    os.kill(pid, signal.SIGTERM)
            pidfile.unlink(missing_ok=True)
            deployment.status = LLMDeployment.Status.STOPPED
            deployment.save(update_fields=["status"])
            DeploymentLog.objects.create(deployment=deployment, level=DeploymentLog.Level.INFO,
                                         message="Runpod LLM processes stopped")
            self.stdout.write("Stopped")
            return

        process_ok = alive(pids.get("model", 0), "vllm")
        gateway_ok = alive(pids.get("gateway", 0), "llm_gateway")
        ready = process_ok and gateway_ok and model_ready(pids.get("upstream_port", 8002))
        deployment.status = (LLMDeployment.Status.RUNNING if ready else
                             LLMDeployment.Status.BUILDING if process_ok and gateway_ok else
                             LLMDeployment.Status.FAILED)
        deployment.save(update_fields=["status"])
        self.stdout.write(f"status={deployment.status} model_process={process_ok} gateway_process={gateway_ok} model_health={ready}")
