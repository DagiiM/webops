"""Reviewed public safetensors CPU inference server; no repository code."""
import os
import threading
from contextlib import asynccontextmanager
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM

model_id = os.environ["WEBOPS_MODEL_ID"]
directory = os.environ["WEBOPS_MODEL_DIR"]
lock = threading.Lock()
model = tokenizer = None
torch.set_num_threads(min(2, max(1, os.cpu_count() or 1)))

@asynccontextmanager
async def lifespan(app):
    global model, tokenizer
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(directory, local_files_only=True,
        trust_remote_code=False, use_safetensors=True, torch_dtype=torch.float32,
        low_cpu_mem_usage=True).eval()
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

@app.get("/")
@app.get("/health")
def health():
    if model is None: raise HTTPException(503, "Model loading")
    return {"status":"ready","model":model_id,"backend":"transformers"}

class Completion(BaseModel):
    prompt: str = Field(min_length=1,max_length=4096)
    max_tokens: int = Field(default=32,ge=1,le=128)
    temperature: float = Field(default=0.7,ge=0,le=2)

@app.post("/v1/completions")
def complete(request: Completion):
    if not lock.acquire(blocking=False): raise HTTPException(429, "Model busy; try again shortly")
    try:
        inputs = tokenizer(request.prompt, return_tensors="pt", truncation=True,max_length=512)
        opts = {"max_new_tokens":request.max_tokens,"do_sample":request.temperature>0,
                "pad_token_id":tokenizer.eos_token_id}
        if request.temperature>0: opts["temperature"]=request.temperature
        with torch.inference_mode():
            output = model.generate(**inputs, **opts)
        text = tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:],skip_special_tokens=True)
        return {"model":model_id,"choices":[{"text":text,"finish_reason":"stop","index":0}]}
    finally:
        lock.release()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["PORT"]))
