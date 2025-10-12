# LLM Deployment Guide

**WebOps Large Language Model Deployment Platform**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Quick Start](#quick-start)
4. [Technical Implementation](#technical-implementation)
5. [Model Configuration](#model-configuration)
6. [API Usage](#api-usage)
7. [Popular Models](#popular-models)
8. [Troubleshooting](#troubleshooting)
9. [Performance Optimization](#performance-optimization)
10. [Security & Production](#security--production)

---

## 🎯 Overview

WebOps provides a complete platform for deploying and serving Large Language Models (LLMs) using vLLM for efficient inference. This guide covers both the technical implementation details and user-friendly deployment instructions.

### Key Features

- **Platform Integrations**: GitHub OAuth and Hugging Face API connections
- **vLLM Engine**: High-performance LLM inference with OpenAI-compatible API
- **Multi-GPU Support**: Tensor parallelism for large models
- **Model Quantization**: AWQ, GPTQ, and SqueezeLLM support
- **Automatic Service Management**: SystemD and Nginx configuration
- **Background Processing**: Celery-based deployment tasks
- **Secure Token Storage**: Encrypted API token management

---

## 🖥️ System Requirements

### Hardware Requirements
- **GPU**: NVIDIA GPU with CUDA support (required)
- **VRAM Requirements**:
  - 7B models: ~14GB VRAM
  - 13B models: ~26GB VRAM
  - 70B models: ~140GB VRAM (multi-GPU)
- **Disk Space**: 50-200GB for model cache
- **RAM**: 32GB+ recommended

### Software Requirements
- WebOps control panel installed and running
- Python 3.10+
- CUDA 11.8 or later
- SystemD (for service management)
- Nginx (for API access)

---

## 🚀 Quick Start

### Step 1: Connect Hugging Face Account

#### Getting a Hugging Face Token
1. Go to https://huggingface.co/settings/tokens
2. Click **"New token"**
3. Give it a name (e.g., "WebOps")
4. Select permissions:
   - **Read**: For public and private models
   - **Write**: For uploading models (optional)
5. Copy the token (starts with `hf_`)

#### Connect via Django Shell
```bash
cd control-panel
./venv/bin/python manage.py shell
```

```python
from django.contrib.auth.models import User
from apps.core.integration_services import HuggingFaceIntegrationService

# Get your user
user = User.objects.get(username='your_username')

# Connect Hugging Face
hf_service = HuggingFaceIntegrationService()
connection = hf_service.save_connection(
    user=user,
    token='hf_your_token_here',  # Your HF token
    token_type='read'
)

if connection:
    print(f"✓ Connected as @{connection.username}")
else:
    print("✗ Connection failed - check your token")
```

### Step 2: Deploy Your First Model

#### Simple Deployment (GPT-2 for Testing)
```python
from apps.deployments.models import Deployment
from apps.deployments.tasks import deploy_llm_model

# Create deployment
deployment = Deployment.objects.create(
    name='gpt2-test',
    project_type=Deployment.ProjectType.LLM,
    model_name='gpt2',  # Small model for testing
    deployed_by=user
)

# Queue deployment
result = deploy_llm_model.delay(deployment.id)
print(f"✓ Deployment queued: {result.id}")
```

#### Production Deployment (Llama 2 7B)
```python
deployment = Deployment.objects.create(
    name='llama-2-7b-chat',
    project_type=Deployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-7b-chat-hf',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    dtype='float16',
    deployed_by=user
)

result = deploy_llm_model.delay(deployment.id)
print(f"✓ Deployment queued: {result.id}")
```

### Step 3: Monitor Deployment

```python
# Check status
deployment.refresh_from_db()
print(f"Status: {deployment.status}")
print(f"Port: {deployment.port}")

# View logs
for log in deployment.logs.all().order_by('created_at'):
    print(f"[{log.level}] {log.message}")
```

### Step 4: Test Your Model

```bash
# Health check
curl http://localhost:9001/health

# Generate text
curl http://localhost:9001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt2",
    "prompt": "Once upon a time",
    "max_tokens": 50
  }'
```

---

## 🔧 Technical Implementation

### Database Models

#### HuggingFace Connection Model
**Location**: `apps/core/models.py:79-109`

```python
class HuggingFaceConnection(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=500)  # Encrypted
    token_type = models.CharField(max_length=20, default='read')
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    last_validation_error = models.TextField(default='')
```

#### LLM Deployment Fields
**Location**: `apps/deployments/models.py:55-81`

```python
class Deployment(models.Model):
    # ... existing fields ...
    
    # LLM-specific fields
    model_name = models.CharField(max_length=255, null=True, blank=True)
    tensor_parallel_size = models.IntegerField(default=1)
    gpu_memory_utilization = models.FloatField(default=0.9)
    max_model_len = models.IntegerField(null=True, blank=True)
    quantization = models.CharField(max_length=20, null=True, blank=True)
    dtype = models.CharField(max_length=20, default='auto')
```

### Integration Services

#### GitHub OAuth Service
**Location**: `apps/core/integration_services.py:19-169`

**Key Methods**:
- `get_authorization_url()`: Generate OAuth URL
- `exchange_code_for_token()`: Handle OAuth callback
- `get_user_info()`: Fetch GitHub profile
- `save_connection()`: Store encrypted connection
- `test_connection()`: Validate connection

#### Hugging Face Service
**Location**: `apps/core/integration_services.py:172-392`

**Key Methods**:
- `validate_token()`: Validate HF API token
- `save_connection()`: Store encrypted connection
- `list_user_models()`: List accessible models
- `test_connection()`: Validate connection

### LLM Deployment Service

#### Core Service Class
**Location**: `apps/deployments/llm_service.py`

**Key Methods**:
- `validate_model_name()`: Validate HF model format
- `create_vllm_environment()`: Set up Python venv
- `download_model()`: Download with authentication
- `render_vllm_systemd_service()`: Generate service config
- `render_nginx_config()`: Generate proxy config
- `deploy_llm()`: Complete deployment orchestration

#### Deployment Workflow
1. **Validation**: Check model name and GPU requirements
2. **Environment Setup**: Create isolated Python environment
3. **Model Download**: Download from Hugging Face with authentication
4. **Service Generation**: Create SystemD service configuration
5. **Proxy Setup**: Configure Nginx reverse proxy
6. **Service Start**: Launch vLLM server
7. **Health Check**: Verify deployment success

### System Templates

#### SystemD Service Template
**Location**: `system-templates/systemd/vllm.service.j2`

```ini
[Unit]
Description=vLLM Server for {{ deployment.name }}
After=network.target

[Service]
Type=simple
User=webops
Group=webops
WorkingDirectory={{ deployment_path }}
Environment=CUDA_VISIBLE_DEVICES={{ gpu_devices }}
Environment=HF_HOME={{ hf_cache_path }}
ExecStart={{ venv_path }}/bin/python -m vllm.entrypoints.openai.api_server \
    --model {{ deployment.model_name }} \
    --port {{ deployment.port }} \
    --tensor-parallel-size {{ deployment.tensor_parallel_size }} \
    --gpu-memory-utilization {{ deployment.gpu_memory_utilization }} \
    {% if deployment.dtype %}--dtype {{ deployment.dtype }}{% endif %} \
    {% if deployment.quantization %}--quantization {{ deployment.quantization }}{% endif %} \
    {% if deployment.max_model_len %}--max-model-len {{ deployment.max_model_len }}{% endif %}

Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Nginx Configuration Template
**Location**: `system-templates/nginx/llm.conf.j2`

```nginx
upstream {{ deployment.name }}_backend {
    server 127.0.0.1:{{ deployment.port }};
}

server {
    listen 80;
    server_name {{ deployment.domain }};
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone={{ deployment.name }}_limit:10m rate=10r/s;
    limit_req zone={{ deployment.name }}_limit burst=20 nodelay;
    
    location / {
        proxy_pass http://{{ deployment.name }}_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Extended timeouts for LLM inference
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Disable buffering for streaming responses
        proxy_buffering off;
        proxy_request_buffering off;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /health {
        proxy_pass http://{{ deployment.name }}_backend/health;
        access_log off;
    }
}
```

### Celery Background Tasks

#### LLM Deployment Task
**Location**: `apps/deployments/tasks.py:394-468`

```python
@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def deploy_llm_model(self, deployment_id):
    """Deploy an LLM model using vLLM."""
    try:
        deployment = Deployment.objects.get(id=deployment_id)
        deployment.status = Deployment.Status.BUILDING
        deployment.save()
        
        # Initialize LLM service
        llm_service = LLMDeploymentService()
        
        # Deploy the model
        success = llm_service.deploy_llm(deployment)
        
        if success:
            deployment.status = Deployment.Status.RUNNING
            deployment.save()
            return f"LLM deployment {deployment.name} completed successfully"
        else:
            deployment.status = Deployment.Status.FAILED
            deployment.save()
            raise Exception("LLM deployment failed")
            
    except Exception as exc:
        deployment.status = Deployment.Status.FAILED
        deployment.save()
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        else:
            raise exc
```

---

## ⚙️ Model Configuration

### Basic Configuration Options

```python
# Minimal setup (good for testing)
deployment = Deployment.objects.create(
    name='model-name',
    project_type=Deployment.ProjectType.LLM,
    model_name='gpt2',
    deployed_by=user
)

# Standard configuration
deployment = Deployment.objects.create(
    name='llama-2-7b',
    project_type=Deployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-7b-chat-hf',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    dtype='float16',
    deployed_by=user
)
```

### Advanced Configuration

```python
# Multi-GPU deployment
deployment = Deployment.objects.create(
    name='llama-2-70b',
    project_type=Deployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-70b-chat-hf',
    tensor_parallel_size=4,  # Use 4 GPUs
    gpu_memory_utilization=0.9,
    max_model_len=4096,  # Context length
    dtype='float16',
    deployed_by=user
)

# Quantized model
deployment = Deployment.objects.create(
    name='llama-2-13b-awq',
    project_type=Deployment.ProjectType.LLM,
    model_name='TheBloke/Llama-2-13B-chat-AWQ',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.95,
    quantization='awq',  # 4-bit quantization
    dtype='float16',
    deployed_by=user
)
```

### Configuration Parameters

| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `model_name` | Hugging Face model ID | Required | Any HF model |
| `tensor_parallel_size` | Number of GPUs | 1 | 1, 2, 4, 8 |
| `gpu_memory_utilization` | GPU memory usage | 0.9 | 0.1 - 1.0 |
| `max_model_len` | Maximum context length | Auto | 512 - 32768 |
| `quantization` | Quantization method | None | awq, gptq, squeezellm |
| `dtype` | Model data type | auto | auto, float16, bfloat16, float32 |

---

## 🔌 API Usage

### OpenAI-Compatible API

Once deployed, models are accessible via OpenAI-compatible endpoints:

#### Text Completion
```bash
curl http://localhost:9001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "prompt": "Explain quantum computing:",
    "max_tokens": 200,
    "temperature": 0.7,
    "top_p": 0.9
  }'
```

#### Chat Completion
```bash
curl http://localhost:9001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is machine learning?"}
    ],
    "max_tokens": 150,
    "temperature": 0.7
  }'
```

### Python Client Examples

#### Using Requests
```python
import requests

response = requests.post(
    "http://localhost:9001/v1/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "meta-llama/Llama-2-7b-chat-hf",
        "prompt": "Write a Python function to calculate fibonacci:",
        "max_tokens": 200,
        "temperature": 0.3,
    }
)

result = response.json()
print(result['choices'][0]['text'])
```

#### Using OpenAI Library
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:9001/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="meta-llama/Llama-2-7b-chat-hf",
    messages=[
        {"role": "user", "content": "Explain the theory of relativity"}
    ],
    max_tokens=300
)

print(response.choices[0].message.content)
```

### Streaming Responses

```python
import requests
import json

response = requests.post(
    "http://localhost:9001/v1/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "meta-llama/Llama-2-7b-chat-hf",
        "prompt": "Write a story about space exploration:",
        "max_tokens": 500,
        "stream": True
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line.decode('utf-8').replace('data: ', ''))
        if 'choices' in data:
            print(data['choices'][0]['text'], end='', flush=True)
```

---

## 🤖 Popular Models

### Small Models (Testing & Development)

```python
# GPT-2 (124M parameters, ~500MB)
model_name = 'gpt2'

# DistilGPT-2 (82M parameters)
model_name = 'distilgpt2'

# Phi-2 (2.7B parameters, ~6GB VRAM)
model_name = 'microsoft/phi-2'
```

### Medium Models (Production Ready)

```python
# Llama 2 7B Chat (7B parameters, ~14GB VRAM)
model_name = 'meta-llama/Llama-2-7b-chat-hf'

# Mistral 7B Instruct (7B parameters, ~14GB VRAM)
model_name = 'mistralai/Mistral-7B-Instruct-v0.2'

# Zephyr 7B Beta (7B parameters, ~14GB VRAM)
model_name = 'HuggingFaceH4/zephyr-7b-beta'

# Code Llama 7B (7B parameters, ~14GB VRAM)
model_name = 'codellama/CodeLlama-7b-Instruct-hf'
```

### Large Models (Multi-GPU Required)

```python
# Llama 2 13B Chat (13B parameters, ~26GB VRAM)
model_name = 'meta-llama/Llama-2-13b-chat-hf'
tensor_parallel_size = 2

# Llama 2 70B Chat (70B parameters, ~140GB VRAM)
model_name = 'meta-llama/Llama-2-70b-chat-hf'
tensor_parallel_size = 4

# Code Llama 34B (34B parameters, ~68GB VRAM)
model_name = 'codellama/CodeLlama-34b-Instruct-hf'
tensor_parallel_size = 4
```

### Quantized Models (Reduced VRAM)

```python
# AWQ Quantized (4-bit, ~50% VRAM reduction)
model_name = 'TheBloke/Llama-2-7B-Chat-AWQ'
quantization = 'awq'

model_name = 'TheBloke/Mistral-7B-Instruct-v0.2-AWQ'
quantization = 'awq'

# GPTQ Quantized (4-bit)
model_name = 'TheBloke/Llama-2-13B-Chat-GPTQ'
quantization = 'gptq'

model_name = 'TheBloke/CodeLlama-7B-Instruct-GPTQ'
quantization = 'gptq'
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Deployment Stuck in "BUILDING"

**Check Celery Worker:**
```bash
cd control-panel
./venv/bin/celery -A config inspect active
```

**Check Deployment Logs:**
```python
from apps.deployments.models import Deployment
d = Deployment.objects.get(name='your-model')
for log in d.logs.all():
    print(f"[{log.level}] {log.message}")
```

#### 2. Out of Memory (OOM) Error

**Reduce GPU Memory Utilization:**
```python
deployment.gpu_memory_utilization = 0.8  # Try 80%
deployment.save()
```

**Use Quantization:**
```python
deployment.quantization = 'awq'
deployment.save()
```

**Redeploy:**
```python
from apps.deployments.tasks import deploy_llm_model
deploy_llm_model.delay(deployment.id)
```

#### 3. Model Download Failed

**Check HF Connection:**
```python
from apps.core.integration_services import HuggingFaceIntegrationService
from django.contrib.auth.models import User

user = User.objects.get(username='your_username')
hf_service = HuggingFaceIntegrationService()
is_valid, message = hf_service.test_connection(user)
print(message)
```

**Check Token Permissions:**
- Ensure token has 'read' access
- For private models, ensure you have access
- Check token hasn't expired

#### 4. Service Won't Start

**Check SystemD Status:**
```bash
sudo systemctl status your-model-name.service
```

**Check Port Conflicts:**
```bash
sudo netstat -tulpn | grep 9001
```

**View Service Logs:**
```bash
sudo journalctl -u your-model-name.service --no-pager
```

#### 5. API Connection Refused

**Check Service Status:**
```bash
curl http://localhost:9001/health
```

**Check Nginx Configuration:**
```bash
sudo nginx -t
sudo systemctl status nginx
```

**Check Firewall:**
```bash
sudo ufw status
```

### Debugging Commands

#### Monitor GPU Usage
```bash
nvidia-smi -l 1
```

#### Check CUDA Availability
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA devices: {torch.cuda.device_count()}")
```

#### Monitor System Resources
```bash
htop
iotop
```

#### Check Disk Space
```bash
df -h
du -sh /opt/webops/llm-deployments/*
```

---

## ⚡ Performance Optimization

### GPU Optimization

#### 1. Memory Management
```python
# Start conservative, increase gradually
gpu_memory_utilization = 0.8  # Start with 80%

# Monitor GPU memory usage
# nvidia-smi
# If stable, increase to 0.9 or 0.95
```

#### 2. Tensor Parallelism
```python
# For large models, distribute across GPUs
# Rule of thumb: 1 GPU per 7-13B parameters

# 7B model: 1 GPU
tensor_parallel_size = 1

# 13B model: 1-2 GPUs
tensor_parallel_size = 2

# 70B model: 4-8 GPUs
tensor_parallel_size = 4
```

#### 3. Data Types
```python
# FP16 is fastest for most models
dtype = 'float16'

# BF16 for newer architectures
dtype = 'bfloat16'

# FP32 only if required (slower)
dtype = 'float32'
```

### Model Optimization

#### 1. Quantization
```python
# AWQ: Best quality/speed balance
quantization = 'awq'

# GPTQ: Good compression
quantization = 'gptq'

# SqueezeLLM: Experimental
quantization = 'squeezellm'
```

#### 2. Context Length
```python
# Reduce if you don't need long contexts
max_model_len = 2048  # Instead of default 4096

# Memory usage scales quadratically with context length
# 2048 tokens = 4x less memory than 4096 tokens
```

### System Optimization

#### 1. CPU Configuration
```bash
# Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

#### 2. Memory Settings
```bash
# Increase shared memory for large models
echo 'kernel.shmmax = 68719476736' | sudo tee -a /etc/sysctl.conf
echo 'kernel.shmall = 4294967296' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

#### 3. Storage Optimization
```bash
# Use SSD for model cache
# Mount with noatime for better performance
# /dev/ssd /opt/webops/llm-cache ext4 defaults,noatime 0 2
```

### Monitoring Performance

#### 1. Inference Metrics
```python
import time
import requests

start_time = time.time()
response = requests.post(
    "http://localhost:9001/v1/completions",
    json={
        "model": "meta-llama/Llama-2-7b-chat-hf",
        "prompt": "Hello world",
        "max_tokens": 100
    }
)
end_time = time.time()

print(f"Response time: {end_time - start_time:.2f}s")
print(f"Tokens generated: {len(response.json()['choices'][0]['text'].split())}")
```

#### 2. Throughput Testing
```bash
# Use Apache Bench for load testing
ab -n 100 -c 10 -p prompt.json -T application/json http://localhost:9001/v1/completions
```

---

## 🔒 Security & Production

### Security Configuration

#### 1. API Authentication
```python
# Add authentication to vLLM server
# In systemd service template:
ExecStart={{ venv_path }}/bin/python -m vllm.entrypoints.openai.api_server \
    --api-key your-secret-api-key \
    # ... other options
```

#### 2. Network Security
```nginx
# In Nginx configuration
# Restrict access by IP
allow 10.0.0.0/8;
allow 172.16.0.0/12;
allow 192.168.0.0/16;
deny all;

# Add rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req zone=api_limit burst=20 nodelay;
```

#### 3. SSL/TLS Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    # ... rest of configuration
}
```

### Production Deployment

#### 1. Environment Variables
```bash
# Production .env settings
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,api.your-domain.com
DJANGO_SECRET_KEY=your-production-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost/webops_prod

# Redis for Celery
CELERY_BROKER_URL=redis://localhost:6379/0

# Security
ENCRYPTION_KEY=your-production-encryption-key
```

#### 2. Process Management
```bash
# Use systemd for production
sudo systemctl enable webops-web
sudo systemctl enable webops-celery
sudo systemctl enable nginx

# Monitor with journald
sudo journalctl -u webops-web -f
```

#### 3. Backup Strategy
```bash
# Database backups
pg_dump webops_prod > backup_$(date +%Y%m%d).sql

# Model cache backups (optional, models can be re-downloaded)
tar -czf models_backup_$(date +%Y%m%d).tar.gz /opt/webops/llm-cache/
```

#### 4. Monitoring & Alerting
```python
# Add health check endpoints
# Monitor GPU usage, memory, disk space
# Set up alerts for service failures

# Example monitoring script
#!/bin/bash
GPU_USAGE=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)
if [ "$GPU_USAGE" -gt 95 ]; then
    echo "High GPU usage: $GPU_USAGE%" | mail -s "GPU Alert" admin@example.com
fi
```

### Scaling Considerations

#### 1. Load Balancing
```nginx
upstream llm_backend {
    server 127.0.0.1:9001;
    server 127.0.0.1:9002;
    server 127.0.0.1:9003;
}
```

#### 2. Multi-Node Deployment
- Deploy models across multiple servers
- Use shared storage for model cache
- Implement service discovery
- Consider Kubernetes for orchestration

#### 3. Auto-Scaling
- Monitor request queue length
- Scale based on GPU utilization
- Implement graceful shutdown
- Use health checks for load balancer

---

## 📚 Resources

### Documentation
- [vLLM Documentation](https://docs.vllm.ai/)
- [Hugging Face Models](https://huggingface.co/models)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Model Quantization Guide](https://huggingface.co/docs/transformers/main/en/quantization)

### Model Repositories
- [Hugging Face Hub](https://huggingface.co/models)
- [TheBloke's Quantized Models](https://huggingface.co/TheBloke)
- [Microsoft Models](https://huggingface.co/microsoft)
- [Meta Llama Models](https://huggingface.co/meta-llama)

### Performance Benchmarks
- [vLLM Performance Benchmarks](https://blog.vllm.ai/2023/06/20/vllm.html)
- [LLM Inference Optimization](https://huggingface.co/blog/optimize-llm)
- [GPU Memory Calculator](https://huggingface.co/spaces/hf-accelerate/model-memory-usage)

---

**Need Help?** Check the [WebOps documentation](../README.md) or open an issue on GitHub.

---

**Last Updated**: 2025-01-XX  
**Version**: 1.0  
**Status**: Production Ready