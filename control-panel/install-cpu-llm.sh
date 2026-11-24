#!/usr/bin/env bash
# Operator-managed CPU-only environment. Run as the WebOps service account.
set -euo pipefail
env_dir="${1:?Usage: bash install-cpu-llm.sh /absolute/path/to/llm-cpu-env}"
case "$env_dir" in /*) ;; *) echo "Use an absolute environment path" >&2; exit 2;; esac
python3 -m venv "$env_dir"
rm -f "$env_dir/.ready"
"$env_dir/bin/pip" install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0+cpu
"$env_dir/bin/pip" install --no-cache-dir transformers==4.51.3 huggingface-hub==0.30.2 safetensors==0.5.3 accelerate==1.6.0 fastapi==0.115.12 uvicorn==0.34.2
"$env_dir/bin/python" -c 'import torch,transformers,fastapi,uvicorn; assert torch.version.cuda is None'
touch "$env_dir/.ready"
