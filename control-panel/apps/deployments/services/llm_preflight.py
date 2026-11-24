"""Fail-closed compatibility checks for the shared CPU inference preview."""
import os
import re
import shutil
from pathlib import Path
import requests
from django.conf import settings
from apps.services.runtime import portable_runtime

# Reviewed standard architectures and immutable public revisions. Expand after testing.
SUPPORTED = {
    "HuggingFaceTB/SmolLM2-135M-Instruct": "12fd25f77366fa6b3b4b768ec3050bf629380bac",
    "Qwen/Qwen2.5-0.5B-Instruct": "7ae557604adf67be50417f59c2c2f167def9a775",
}
GB = 10**9

def hardware():
    import psutil
    mem = psutil.virtual_memory()
    total, available = mem.total, mem.available
    for limit, used in (("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
                        ("/sys/fs/cgroup/memory/memory.limit_in_bytes", "/sys/fs/cgroup/memory/memory.usage_in_bytes")):
        try:
            value = int(Path(limit).read_text().strip())
            if 0 < value < total:
                total = value
                available = min(available, max(0, value - int(Path(used).read_text())))
        except (OSError, ValueError):
            pass
    root = Path(settings.WEBOPS_INSTALL_PATH)
    while not root.exists():
        root = root.parent
    return {"ram_gb": round(total/GB, 2), "available_ram_gb": round(available/GB, 2),
            "disk_gb": round(shutil.disk_usage(root).free/GB, 2),
            "cpu_count": len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else os.cpu_count(),
            "device": "CPU", "runtime": "supervisor"}

def check_model(model, backend="transformers", dtype="auto", quantization="", exclude_id=None):
    from apps.deployments.models import LLMDeployment
    h = hardware()
    result = {"success": False, "hardware": h, "model": model, "errors": [], "warnings": [],
              "suggestions": list(SUPPORTED), "parameters": None, "weights_gb": None, "estimated_ram_gb": None}
    errors = result["errors"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}(?:/[A-Za-z0-9][A-Za-z0-9_.-]{0,95})?", model or "") or ".." in model:
        errors.append("Enter a valid Hugging Face model ID."); return result
    if backend != "transformers":
        errors.append("This CPU preview supports the Transformers backend only.")
    if dtype not in ("auto","float32") or quantization:
        errors.append("Use Auto or float32 and no quantization for this CPU preview.")
    try:
        revision = SUPPORTED.get(model)
        url = "https://huggingface.co/api/models/" + model
        if revision: url += "/revision/" + revision
        response = requests.get(url, timeout=(4,8), allow_redirects=False)
        if response.status_code != 200:
            errors.append("Hugging Face metadata is unavailable or the model is private, gated or missing.")
            return result
        data = response.json()
        tensors = data.get("safetensors") or {}
        params = tensors.get("total")
        if not isinstance(params,int) or params <= 0:
            errors.append("Verified safetensors parameter count is unavailable; deployment cannot be sized safely.")
        else:
            widths = {"BF16":2,"F16":2,"F32":4,"F64":8,"I64":8,"I32":4,"I16":2,"I8":1,"U8":1,"BOOL":1}
            sizes = tensors.get("parameters") or {}
            weights = sum(n*widths.get(k,4) for k,n in sizes.items()) if sizes else params*4
            ram = (params*4*1.5 + 1.2*GB)/GB
            result.update(parameters=params, weights_gb=round(weights/GB,2), estimated_ram_gb=round(ram,2))
            if ram + 1 > h["available_ram_gb"]:
                errors.append(f"Insufficient RAM: estimated {ram:.1f} GB for inference plus 1 GB reserve; {h['available_ram_gb']:.2f} GB available.")
            if weights/GB + 3 > h["disk_gb"]:
                errors.append(f"Insufficient storage: weights need {weights/GB:.1f} GB plus 3 GB reserve; {h['disk_gb']:.2f} GB available.")
        if data.get("private") or data.get("gated"):
            errors.append("Private or gated models require an isolated authenticated worker.")
        if data.get("pipeline_tag") != "text-generation":
            errors.append("This server supports text-generation only; multimodal models require a different backend.")
        if not revision or data.get("sha") != revision:
            errors.append("This model/revision is not in the reviewed CPU model catalog. Choose a supported model or request a suitable worker.")
        result["revision"] = revision
    except (requests.RequestException, ValueError, TypeError):
        errors.append("Unable to verify model metadata. Check Hugging Face connectivity and try again.")
    runtime = portable_runtime()
    if runtime is None or not runtime.ready():
        errors.append("The Supervisor runtime is unavailable. Contact an operator.")
    envpath = Path(getattr(settings,"WEBOPS_CPU_LLM_ENV",Path(settings.WEBOPS_INSTALL_PATH)/"llm-cpu-env"))
    if not (envpath / ".ready").is_file():
        errors.append("CPU inference dependencies are not installed. Contact an operator.")
    busy = LLMDeployment.objects.filter(is_deleted=False,status__in=["building","running","stopped"]).exclude(pk=exclude_id)
    if busy.exists():
        errors.append("The shared CPU preview already has a reserved model slot. Stop and delete your unused model, or request another worker.")
    result["success"] = not errors
    result["warnings"].append("Estimates are conservative, not a guarantee. Only one model slot; CPU inference, maximum 128 output tokens, local authenticated testing.")
    return result
