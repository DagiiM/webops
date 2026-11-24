"""Bounded public Hugging Face discovery; never downloads model files."""
import hashlib
import re
import requests
from django.core.cache import cache
from .llm_preflight import SUPPORTED

URL = "https://huggingface.co/api/models"
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}(?:/[A-Za-z0-9][A-Za-z0-9_.-]{0,95})?")
LIMIT = 12

def row(data, reviewed_id=None):
    model = data.get("id") or data.get("modelId")
    if not isinstance(model,str) or not MODEL_ID.fullmatch(model) or ".." in model:
        return None
    if data.get("private") or data.get("gated"):
        return None
    reviewed = model in SUPPORTED
    if reviewed_id is not None and (model != reviewed_id or data.get("sha") != SUPPORTED[model]):
        return None
    task = data.get("pipeline_tag")
    if task != "text-generation":
        return None
    tags = data.get("tags") or []
    tensors = data.get("safetensors") or {}
    count = tensors.get("total") if isinstance(tensors,dict) else None
    params = count if type(count) is int and count > 0 else None
    return {"id":model,"reviewed":reviewed,"pipeline_tag":task,
            "downloads":data.get("downloads") if type(data.get("downloads")) is int else None,
            "parameters":params,"safetensors":"safetensors" in tags or params is not None}

def discover(query=""):
    key="hf-public-models-v1:"+hashlib.sha256(query.lower().encode()).hexdigest()
    cached=cache.get(key)
    if cached is not None:return cached
    if not query:
        # Default is the reviewed pinned catalog, not globally popular large models.
        models=[]
        for model, revision in SUPPORTED.items():
            try:
                response=requests.get(f"{URL}/{model}/revision/{revision}",timeout=(3,5),allow_redirects=False)
                response.raise_for_status()
                data=row(response.json(),reviewed_id=model)
                if data:models.append(data)
            except (requests.RequestException,ValueError,TypeError,AttributeError):
                continue
        if not models:raise RuntimeError("Hugging Face metadata unavailable.")
        result={"models":models,"source":"Hugging Face","partial":len(models)!=len(SUPPORTED)}
    else:
        response=requests.get(URL,params={"search":query,"pipeline_tag":"text-generation","sort":"downloads","direction":-1,"limit":LIMIT},timeout=(3,5),allow_redirects=False)
        response.raise_for_status()
        data=response.json()
        if not isinstance(data,list):raise ValueError("Unexpected model catalog response")
        models=[m for d in data[:LIMIT] if isinstance(d,dict) and (m:=row(d))]
        models.sort(key=lambda m:not m["reviewed"])
        result={"models":models,"source":"Hugging Face","partial":False}
    cache.set(key,result,300)
    return result
