"""Portable CPU model deployment and user-visible admission control."""
import fcntl
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from django.conf import settings
from apps.deployments.models import LLMDeployment, BaseDeployment, DeploymentLog
from apps.core.utils import generate_port
from apps.services.runtime import portable_runtime
from .llm_preflight import check_model, SUPPORTED

@contextmanager
def slot_lock():
    root = Path(settings.WEBOPS_INSTALL_PATH)
    root.mkdir(parents=True,exist_ok=True)
    with (root / ".llm-slot.lock").open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield

def log(d, message, level="info"):
    DeploymentLog.objects.create(deployment=d, message=message, level=level)

def fail(d, message):
    d.status = "failed"
    d.save(update_fields=["status"])
    log(d,message,"error")
    return {"success":False,"error":message}

def queue_llm(d):
    from apps.services.background import get_background_processor
    with slot_lock():
        d.refresh_from_db()
        if d.status not in ("pending","failed"):
            return False, "Model is already queued, running, or stopped."
        if portable_runtime():
            check = check_model(d.model_name,d.backend,d.dtype,d.quantization,d.pk)
            if not check["success"]:
                message = "Preflight blocked: " + " ".join(check["errors"])
                fail(d,message)
                return False,message
            if not (environment() / ".ready").is_file():
                message="CPU inference dependencies are not ready. Ask the operator to run the CPU runtime installer."
                fail(d,message)
                return False,message
        d.status="building"
        d.save(update_fields=["status"])
        log(d,"Preflight passed. Deployment queued; model files will be downloaded, loaded and health-checked before it is marked running.")
        try:
            get_background_processor().submit("apps.deployments.tasks.llm.deploy_llm_model", d.pk)
        except Exception:
            message="Could not queue the inference task. Check the configured background processor and retry."
            fail(d,message)
            return False,message
        return True,"Deployment queued. Follow the deployment logs for progress."

def environment():
    return Path(getattr(settings,"WEBOPS_CPU_LLM_ENV",Path(settings.WEBOPS_INSTALL_PATH)/"llm-cpu-env"))

def deploy_cpu(d):
    d.refresh_from_db()
    if d.is_deleted or d.status != "building":
        return {"success":False,"error":"Deployment is not queued"}
    check = check_model(d.model_name,d.backend,d.dtype,d.quantization,d.pk)
    if not check["success"]:
        return fail(d,"Preflight blocked: "+" ".join(check["errors"]))
    runtime = portable_runtime()
    envpath = environment()
    if not (envpath / ".ready").is_file():
        return fail(d,"CPU runtime dependencies are not installed.")
    base = Path(settings.WEBOPS_INSTALL_PATH)/"llm-deployments"/d.name
    root = base.parent.resolve()
    if not base.resolve().is_relative_to(root):
        return fail(d,"Invalid model storage path")
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    weights = base/"model"
    d.model_size_gb=check["weights_gb"]
    d.detected_parameter_count=check["parameters"]
    d.estimated_memory_required_gb=check["estimated_ram_gb"]
    d.enable_trust_remote_code=False
    d.port = d.port or generate_port(set(BaseDeployment.objects.exclude(pk=d.pk).exclude(port__isnull=True).values_list("port",flat=True)),min_port=9001,max_port=9999)
    d.save(update_fields=["model_size_gb","detected_parameter_count","estimated_memory_required_gb","enable_trust_remote_code","port"])
    env={"PATH":str(envpath/"bin")+":/usr/local/bin:/usr/bin:/bin","HOME":str(base),"LANG":"C.UTF-8",
         "PYTHONUNBUFFERED":"1","HF_HOME":str(base/"hf-cache"),"HF_HUB_DISABLE_XET":"1","HF_HUB_DISABLE_IMPLICIT_TOKEN":"1",
         "OMP_NUM_THREADS":"2","MKL_NUM_THREADS":"2","WEBOPS_MODEL_ID":d.model_name,"WEBOPS_MODEL_DIR":str(weights),"PORT":str(d.port)}
    log(d,"Downloading reviewed safetensors revision "+check["revision"][:12]+". No model code will be executed.")
    download="from huggingface_hub import snapshot_download; import sys; snapshot_download(repo_id=sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3], token=False, allow_patterns=['*.safetensors','*.json','*.model','*.txt'], max_workers=2)"
    try:
        proc=subprocess.run([str(envpath/"bin/python"),"-c",download,d.model_name,check["revision"],str(weights)],
                            env=env,capture_output=True,text=True,timeout=600)
        if proc.returncode:
            return fail(d,"Model download failed. Check Hugging Face connectivity and available disk space, then retry. "+proc.stderr[-500:].splitlines()[-1][:300] if proc.stderr else "Model download failed.")
        if not list(weights.glob("*.safetensors")):
            return fail(d,"No safetensors weights were downloaded.")
        d.download_completed=True
        d.save(update_fields=["download_completed"])
        log(d,"Download complete. Starting CPU inference and waiting for the model to load.")
        env["HF_HUB_OFFLINE"]="1"
        server=Path(__file__).with_name("cpu_inference_server.py").resolve()
        ok,msg=runtime.install_process(d,base,base,[str(envpath/"bin/python"),str(server)],env)
        if not ok:return fail(d,"Supervisor registration failed: "+msg)
        ok,msg=runtime.lifecycle(d,"start")
        if not ok:
            runtime.remove(d)
            return fail(d,"Model startup failed: "+msg+". See runtime stderr for details.")
        d.status="running"
        d.save(update_fields=["status"])
        log(d,"Model ready. Use the authenticated test panel to generate text.","success")
        return {"success":True,"deployment_id":d.pk,"port":d.port}
    except (OSError,subprocess.SubprocessError,ValueError) as exc:
        runtime.remove(d)
        return fail(d,"Inference setup failed ("+type(exc).__name__+"). Check storage/network and retry.")
