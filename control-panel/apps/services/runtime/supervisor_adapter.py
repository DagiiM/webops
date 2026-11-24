"""Single-host, trusted-workload Supervisor adapter. Not a tenant sandbox."""
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from http.client import HTTPConnection
from django.conf import settings

class SupervisorRuntime:
    name = "supervisor"
    def __init__(self):
        self.root = Path(settings.WEBOPS_INSTALL_PATH) / "runtime"
        self.config = Path(getattr(settings, "WEBOPS_SUPERVISOR_CONFIG", self.root / "supervisord.conf"))
        self.ctl = getattr(settings, "WEBOPS_SUPERVISORCTL", "supervisorctl")

    def _name(self, deployment):
        if not isinstance(deployment.pk, int) or deployment.pk < 1:
            raise ValueError("Deployment must have a saved positive ID")
        return f"webops-app-{deployment.pk}"

    def _run(self, *args):
        result = subprocess.run([str(self.ctl), "-c", str(self.config), *args],
                                capture_output=True, text=True, timeout=30)
        return result.returncode == 0, (result.stdout + result.stderr).strip()

    def ready(self):
        try:
            return self._run("pid")[0]
        except (OSError, subprocess.SubprocessError):
            return False

    def _spec_path(self, deployment):
        return self.root / "programs" / (self._name(deployment) + ".json")

    def _conf_path(self, deployment):
        return self.root / "programs" / (self._name(deployment) + ".ini")

    @staticmethod
    def _write(path, data):
        temp = path.with_suffix(path.suffix + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(data)
        os.replace(temp, path)

    def install_application(self, deployment, service):
        """Register a prepared repo; never report an unstarted app as running."""
        if not self.ready():
            return False, "Supervisor unavailable"
        try:
            from apps.deployments.models import ApplicationDeployment
            name = self._name(deployment)
            repo = service.get_repo_path(deployment).resolve()
            base = service.get_deployment_path(deployment).resolve()
            if not repo.is_relative_to(base) or not repo.is_dir():
                raise ValueError("Invalid repository path")
            if deployment.use_docker or deployment.project_type == "docker":
                raise ValueError("Docker deployment requires a Docker runtime")
            port = int(deployment.port)
            if not 1024 <= port <= 65535:
                raise ValueError("Invalid unprivileged port")
            venv = service.get_venv_path(deployment) / "bin"
            env = {"PATH": str(venv) + ":/usr/local/bin:/usr/bin:/bin",
                   "HOME": str(base), "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1"}
            for key, value in (deployment.env_vars or {}).items():
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                    raise ValueError("Invalid application environment variable name")
                env[key] = str(value)
            env["PORT"] = str(port)
            env["HOST"] = "127.0.0.1"
            cwd = repo
            if deployment.project_type == ApplicationDeployment.ProjectType.STATIC:
                src = next((repo / p for p in ("public", "dist", "build", ".")
                            if (repo / p / "index.html").is_file()), None)
                if src is None:
                    raise ValueError("No static index.html found")
                # Publish assets, not git history, dotfiles, or linked host files.
                public = base / "published"
                if public.exists():
                    shutil.rmtree(public)
                public.mkdir(mode=0o700)
                allowed = {".html",".htm",".css",".js",".mjs",".json",".png",".jpg",".jpeg",".gif",
                           ".svg",".ico",".webp",".woff",".woff2",".ttf",".txt",".map",".avif",".pdf"}
                for path in src.rglob("*"):
                    rel = path.relative_to(src)
                    if any(p.startswith(".") for p in rel.parts) or path.is_symlink():
                        continue
                    if path.is_file() and path.suffix.lower() in allowed and path.resolve().is_relative_to(src.resolve()):
                        dest = public / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, dest)
                if not (public / "index.html").is_file():
                    raise ValueError("Static index is not a regular publishable asset")
                cwd = public
                argv = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(public)]
            else:
                command = deployment.start_command
                if deployment.project_type == ApplicationDeployment.ProjectType.DJANGO:
                    cwd = service.get_project_root(deployment).resolve()
                    if not cwd.is_relative_to(repo):
                        raise ValueError("Invalid Django project root")
                    module = deployment.configuration.settings_module if hasattr(deployment, "configuration") and deployment.configuration.settings_module else service.detect_django_settings_module(deployment)
                    env = service.portable_application_env(deployment, module)
                    if not command:
                        command = "gunicorn " + module.rsplit(".", 1)[0] + ".wsgi:application --bind 127.0.0.1:$PORT --workers 2"
                    command = command.replace("${DJANGO_SETTINGS_MODULE%.*}", module.rsplit(".", 1)[0])
                if not command:
                    raise ValueError("No detected start command; runtime cannot start this project")
                command = command.replace("${PORT}", str(port)).replace("$PORT", str(port)).replace("0.0.0.0", "127.0.0.1")
                argv = shlex.split(command)
                if not argv or any(a in {"|","||","&","&&",";",">","<"} for a in argv):
                    raise ValueError("Shell pipelines are unsupported in Supervisor mode")
                if (venv / argv[0]).is_file():
                    argv[0] = str(venv / argv[0])
            return self.install_process(deployment,base,cwd,argv,env)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def install_process(self,deployment,base,cwd,argv,env):
        try:
            name=self._name(deployment)
            if not self.ready():return False,"Supervisor unavailable"
            self.root.joinpath("programs").mkdir(parents=True, exist_ok=True, mode=0o700)
            logs = base / "runtime-logs"
            logs.mkdir(exist_ok=True, mode=0o700)
            spec = self._spec_path(deployment)
            config = self._conf_path(deployment)
            launcher = Path(__file__).with_name("launcher.py").resolve()
            for path in (spec, config, launcher, logs, Path(sys.executable)):
                if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)):
                    raise ValueError("Unsupported runtime path")
            self._write(spec, json.dumps({"cwd": str(cwd), "argv": argv, "env": env}))
            self._write(config, f"""[program:{name}]
command={sys.executable} {launcher} {spec}
autostart=false
autorestart=true
startsecs=1
startretries=3
stopasgroup=true
killasgroup=true
stopwaitsecs=8
stdout_logfile={logs}/stdout.log
stderr_logfile={logs}/stderr.log
stdout_logfile_maxbytes=5MB
stderr_logfile_maxbytes=5MB
stdout_logfile_backups=2
stderr_logfile_backups=2
""")
            ok, msg = self._run("reread")
            if not ok:
                return False, msg
            ok, msg = self._run("update", name)
            return ok, msg or f"Registered {name}"
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def status(self, deployment):
        try:
            ok, output = self._run("status", self._name(deployment))
            fields = output.split()
            state = fields[1] if len(fields) > 1 and fields[0] == self._name(deployment) else "UNKNOWN"
            match = re.search(r"\bpid (\d+)", output) if state == "RUNNING" else None
            return {"active": state == "RUNNING", "enabled": self._conf_path(deployment).exists(),
                    "status": state.lower(), "state": state, "pid": int(match[1]) if match else None,
                    "output": output, "runtime": self.name}
        except (OSError, subprocess.SubprocessError) as exc:
            return {"active": False, "enabled": False, "status": "unknown", "state": "UNKNOWN",
                    "pid": None, "output": str(exc), "runtime": self.name}

    def lifecycle(self, deployment, action):
        try:
            if action not in ("start", "stop", "restart"):
                return False, "Unsupported operation"
            before = self.status(deployment)
            if action == "start" and before["active"]:
                return True, "Already running"
            if action == "stop" and before["state"] in ("STOPPED", "EXITED", "FATAL"):
                return True, "Already stopped"
            if action == "start":
                with socket.socket() as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        s.bind(("127.0.0.1", int(deployment.port)))
                    except OSError:
                        return False, "Application port is already occupied"
            ok, msg = self._run(action, self._name(deployment))
            if not ok:
                return False, msg
            if action == "stop":
                return (not self.status(deployment)["active"]), msg
            deadline = time.monotonic() + (120 if getattr(deployment,"project_type",None) == "llm" or hasattr(deployment,"llmdeployment") else 15)
            while time.monotonic() < deadline:
                if self.status(deployment)["active"]:
                    try:
                        connection = HTTPConnection("127.0.0.1", int(deployment.port), timeout=2)
                        try:
                            connection.request("GET", "/")
                            if 200 <= connection.getresponse().status < 400:
                                return True, msg
                        finally:
                            connection.close()
                    except (OSError, ValueError):
                        pass
                time.sleep(.3)
            self._run("stop", self._name(deployment))
            return False, "Process did not pass HTTP readiness check"
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def remove(self, deployment):
        try:
            state = self.status(deployment)
            if state["state"] not in ("UNKNOWN", "STOPPED", "EXITED", "FATAL"):
                ok, msg = self.lifecycle(deployment, "stop")
                if not ok:
                    return False, msg
            if not self.ready():
                return False, "Supervisor unavailable; cannot confirm removal"
            self._conf_path(deployment).unlink(missing_ok=True)
            ok, msg = self._run("reread")
            if not ok:
                return False, msg
            if state["state"] != "UNKNOWN":
                ok, msg = self._run("update", self._name(deployment))
                if not ok:
                    return False, msg
            self._spec_path(deployment).unlink(missing_ok=True)
            return True, "Runtime registration removed"
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)
