# LLM Deployment Guide

**WebOps Large Language Model Deployment Platform - Complete Guide**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Prerequisites Setup](#prerequisites-setup)
4. [Hugging Face Authentication](#hugging-face-authentication)
5. [Quick Start Deployment](#quick-start-deployment)
6. [Production Deployments](#production-deployments)
7. [Model Configuration](#model-configuration)
8. [Monitoring and Management](#monitoring-and-management)
9. [API Usage](#api-usage)
10. [Popular Models](#popular-models)
11. [Troubleshooting](#troubleshooting)
12. [Performance Optimization](#performance-optimization)
13. [Security & Production](#security--production)
14. [Advanced Scenarios](#advanced-scenarios)

---

## 🎯 Overview

WebOps provides a complete platform for deploying and serving Large Language Models (LLMs) using vLLM for efficient inference. This comprehensive guide covers everything from initial setup to production deployment and management.

### Architecture Overview

```
Hugging Face Model → WebOps Control Panel → vLLM Service → OpenAI API
     ↓                      ↓                    ↓            ↓
Model Repository    Deployment Management    GPU Inference   Client Access
```

### Key Features

- **Platform Integrations**: GitHub OAuth and Hugging Face API connections
- **vLLM Engine**: High-performance LLM inference with OpenAI-compatible API
- **Multi-GPU Support**: Tensor parallelism for large models
- **Model Quantization**: AWQ, GPTQ, and SqueezeLLM support
- **Automatic Service Management**: SystemD and Nginx configuration
- **Background Processing**: Celery-based deployment tasks
- **Secure Token Storage**: Encrypted API token management

**Key Components:**
- **Hugging Face Integration**: Secure token management for model access
- **vLLM Engine**: High-performance GPU inference with tensor parallelism
- **SystemD Services**: Automatic service management and monitoring
- **Nginx Proxy**: Load balancing and API access control
- **Celery Tasks**: Background deployment processing

---

## 🖥️ System Requirements

### Hardware Requirements

```bash
# GPU Requirements (NVIDIA with CUDA)
- 7B models:  ~14GB VRAM (RTX 3090, RTX 4090, A100-40GB)
- 13B models: ~26GB VRAM (A100-40GB, H100)
- 70B models: ~140GB VRAM (Multi-GPU: 4x A100-40GB or 2x H100)

# System Resources
- CPU: 8+ cores recommended
- RAM: 32GB+ (64GB+ for large models)
- Storage: 100GB+ free space for model cache
- Network: Stable internet for model downloads
```

### Software Requirements

```bash
# Verify WebOps installation
cd $WEBOPS_DIR/control-panel
./manage.py check

# Check GPU availability
nvidia-smi

# Verify CUDA version (11.8+ required)
nvcc --version

# Check Python version (3.10+ required)
python3 --version
```

---

## 🔧 Prerequisites Setup

### Service Dependencies

Ensure these services are running:
```bash
# WebOps Control Panel
sudo systemctl status webops-web

# Celery Worker (for background tasks)
sudo systemctl status webops-celery

# Redis (for Celery broker)
sudo systemctl status redis

# Nginx (for API proxy)
sudo systemctl status nginx
```

### System Validation

```bash
# Pre-deployment validation
cd $WEBOPS_DIR/control-panel
./manage.py shell
```

```python
# Verify system readiness
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA devices: {torch.cuda.device_count()}")

# Check disk space
import shutil
free_space = shutil.disk_usage('/opt/webops/llm-deployments').free
print(f"Free disk space: {free_space / (1024**3):.1f} GB")
```

---

## 🔑 Hugging Face Authentication

### Step 1: Get Hugging Face API Token

1. **Visit Hugging Face Settings**:
   ```
   https://huggingface.co/settings/tokens
   ```

2. **Create New Token**:
   - Click "New token"
   - Name: `webops-deployment`
   - Type: `Read` (for model access)
   - Scope: Select repositories you need access to

3. **Copy Token**: Save the token (format: `hf_xxxxxxxxxxxx`)

### Step 2: Connect Token to WebOps

#### Method A: Web Interface
```bash
# Navigate to integrations dashboard
http://localhost:8000/integrations/

# Click "Connect Hugging Face"
# Paste your token and test connection
```

#### Method B: Django Shell
```bash
cd $WEBOPS_DIR/control-panel
./manage.py shell
```

```python
from django.contrib.auth.models import User
from apps.core.integration_services import HuggingFaceIntegrationService

# Get your user account
user = User.objects.get(username='your_username')  # Replace with your username

# Initialize Hugging Face service
hf_service = HuggingFaceIntegrationService()

# Connect your token
connection = hf_service.save_connection(
    user=user,
    token='hf_your_token_here',  # Replace with your actual token
    token_type='read'
)

# Verify connection
if connection:
    print(f"✅ Successfully connected as @{connection.username}")
    print(f"📊 Access to {len(connection.accessible_models)} models")
else:
    print("❌ Connection failed - check your token")

# Test connection
test_result = hf_service.test_connection(user)
print(f"🔍 Connection test: {'✅ PASSED' if test_result['success'] else '❌ FAILED'}")
```

---

## 🚀 Quick Start Deployment

### Step 1: Deploy Test Model (GPT-2)

Start with a small model to verify your setup:

```python
# In Django shell (./manage.py shell)
from django.contrib.auth.models import User
from apps.deployments.models import Deployment
from apps.deployments.tasks import deploy_llm_model

# Get your user
user = User.objects.get(username='your_username')

# Create deployment configuration
deployment = ApplicationDeployment.objects.create(
    name='gpt2-test',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='gpt2',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    dtype='float16',
    deployed_by=user
)

print(f"📦 Created deployment: {deployment.name} (ID: {deployment.id})")

# Queue deployment task
task = deploy_llm_model.delay(deployment.id)
print(f"🔄 Deployment queued with task ID: {task.id}")
```

### Step 2: Monitor Deployment Progress

```python
# Check deployment status
deployment.refresh_from_db()
print(f"Status: {deployment.status}")

# View deployment logs
for log in deployment.logs.all().order_by('created_at'):
    print(f"[{log.level.upper()}] {log.message}")

# Check if deployment is complete
if deployment.status == Deployment.Status.RUNNING:
    print(f"🎉 Deployment successful! API available on port {deployment.port}")
elif deployment.status == Deployment.Status.FAILED:
    print("❌ Deployment failed. Check logs above.")
```

### Step 3: Test the Deployed Model

Once deployment status is `RUNNING`:

```bash
# Test with curl (replace 9001 with your deployment's port)
curl http://localhost:9001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt2",
    "prompt": "The future of AI is",
    "max_tokens": 50,
    "temperature": 0.7
  }'
```

Expected response:
```json
{
  "id": "cmpl-xxx",
  "object": "text_completion",
  "created": 1234567890,
  "model": "gpt2",
  "choices": [
    {
      "text": " bright and full of possibilities...",
      "index": 0,
      "logprobs": null,
      "finish_reason": "length"
    }
  ]
}
```

---

## 🎯 Production Deployments

### Popular Model Configurations

#### Llama 2 7B Chat
```python
deployment = ApplicationDeployment.objects.create(
    name='llama2-7b-chat',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-7b-chat-hf',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    max_model_len=4096,
    dtype='float16',
    deployed_by=user
)
```

#### Code Llama 13B (Multi-GPU)
```python
deployment = ApplicationDeployment.objects.create(
    name='codellama-13b',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='codellama/CodeLlama-13b-Instruct-hf',
    tensor_parallel_size=2,  # Use 2 GPUs
    gpu_memory_utilization=0.85,
    max_model_len=8192,
    dtype='bfloat16',
    deployed_by=user
)
```

#### Quantized Model (AWQ)
```python
deployment = ApplicationDeployment.objects.create(
    name='llama2-7b-awq',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='TheBloke/Llama-2-7B-Chat-AWQ',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    quantization='awq',
    dtype='auto',
    deployed_by=user
)
```

---

## ⚙️ Model Configuration

### Basic Configuration Options

```python
# Minimal setup (good for testing)
deployment = ApplicationDeployment.objects.create(
    name='model-name',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='gpt2',
    deployed_by=user
)

# Standard configuration
deployment = ApplicationDeployment.objects.create(
    name='llama-2-7b',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-7b-chat-hf',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    dtype='float16',
    deployed_by=user
)
```

### Advanced Configuration

```python
# Full configuration example
deployment = ApplicationDeployment.objects.create(
    name='custom-model',
    project_type=ApplicationDeployment.ProjectType.LLM,
    
    # Model Configuration
    model_name='microsoft/DialoGPT-large',
    
    # GPU Settings
    tensor_parallel_size=1,           # Number of GPUs
    gpu_memory_utilization=0.9,       # GPU memory usage (0.0-1.0)
    
    # Model Parameters
    max_model_len=2048,               # Context length
    quantization='',                  # '', 'awq', 'gptq', 'squeezellm'
    dtype='float16',                  # 'auto', 'float16', 'bfloat16', 'float32'
    
    # Deployment Settings
    domain='',                        # Optional: custom domain
    env_vars={                        # Optional: environment variables
        'VLLM_ATTENTION_BACKEND': 'FLASHINFER',
        'CUDA_VISIBLE_DEVICES': '0'
    },
    
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

## 📊 Monitoring and Management

### Check Deployment Status

```python
# List all deployments
deployments = ApplicationDeployment.objects.filter(project_type=ApplicationDeployment.ProjectType.LLM)
for dep in deployments:
    print(f"{dep.name}: {dep.status} (Port: {dep.port})")

# Get specific deployment
deployment = ApplicationDeployment.objects.get(name='llama2-7b-chat')
print(f"Status: {deployment.status}")
print(f"Model: {deployment.model_name}")
print(f"Port: {deployment.port}")
print(f"GPUs: {deployment.tensor_parallel_size}")
```

### View Deployment Logs

```python
# Recent logs
logs = deployment.logs.all().order_by('-created_at')[:10]
for log in logs:
    timestamp = log.created_at.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{log.level.upper()}] {log.message}")

# Filter by log level
error_logs = deployment.logs.filter(level='error')
for log in error_logs:
    print(f"❌ {log.message}")
```

### Health Checks

```python
# Manual health check
from apps.deployments.tasks import run_health_check

# Run health check
task = run_health_check.delay(deployment.id)
print(f"Health check queued: {task.id}")

# View health check results
health_records = deployment.health_check_records.all().order_by('-created_at')[:5]
for record in health_records:
    status = "✅ HEALTHY" if record.overall_healthy else "❌ UNHEALTHY"
    print(f"{record.created_at}: {status}")
    if record.response_time_ms:
        print(f"  Response time: {record.response_time_ms}ms")
    if record.cpu_percent:
        print(f"  CPU usage: {record.cpu_percent}%")
```

### Service Management

```bash
# Check SystemD service status
sudo systemctl status webops-llm-llama2-7b-chat

# View service logs
sudo journalctl -u webops-llm-llama2-7b-chat -f

# Restart service
sudo systemctl restart webops-llm-llama2-7b-chat

# Check GPU usage
nvidia-smi

# Monitor API endpoint
curl -s http://localhost:9001/health | jq
```

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

### Common Issues and Solutions

#### Issue: Deployment Stuck in "BUILDING" Status

**Check Celery Worker:**
```bash
cd control-panel
./venv/bin/celery -A config inspect active
```

**Check Deployment Logs:**
```python
from apps.deployments.models import Deployment
d = ApplicationDeployment.objects.get(name='your-model')
for log in d.logs.all():
    print(f"[{log.level}] {log.message}")
```

**Common causes:**
- Insufficient GPU memory
- Model download failure
- CUDA driver issues
- Network connectivity problems

**Solutions:**
```bash
# Check GPU memory
nvidia-smi

# Check disk space
df -h /opt/webops/llm-deployments/

# Check network connectivity
curl -I https://huggingface.co

# Restart Celery worker
sudo systemctl restart webops-celery
```

#### Issue: "CUDA Out of Memory" Error

**Reduce GPU Memory Utilization:**
```python
deployment.gpu_memory_utilization = 0.7  # Reduce from 0.9
deployment.save()

# Or use quantization
deployment.quantization = 'awq'
deployment.save()

# Redeploy
from apps.deployments.tasks import deploy_llm_model
deploy_llm_model.delay(deployment.id)
```

#### Issue: Model Download Failed

**Check HF Connection:**
```python
from apps.core.integration_services import HuggingFaceIntegrationService
hf_service = HuggingFaceIntegrationService()
result = hf_service.test_connection(user)
print(result)

# Verify model exists and is accessible
# Visit: https://huggingface.co/model-name
```

#### Issue: Port Already in Use

**Check Port Allocation:**
```python
from apps.deployments.llm_service import LLMDeploymentService
service = LLMDeploymentService()
used_ports = service.get_used_ports()
print(f"Used ports: {used_ports}")

# Manually assign different port
deployment.port = 9002  # Choose unused port
deployment.save()
```

#### Issue: Service Won't Start

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

#### Issue: API Connection Refused

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

---

## 🔒 Security & Production

### Security Best Practices

```python
# Use environment variables for sensitive configuration
deployment = ApplicationDeployment.objects.create(
    name='secure-llm',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='private-org/private-model',
    env_vars={
        'API_KEY_REQUIRED': 'true',
        'RATE_LIMIT_ENABLED': 'true',
        'LOG_LEVEL': 'INFO'
    },
    deployed_by=user
)
```

### Resource Monitoring

```bash
# Set up monitoring scripts
cat > /opt/webops/scripts/monitor-llm.sh << 'EOF'
#!/bin/bash
# Monitor LLM deployments

echo "=== GPU Usage ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv

echo "=== Active Deployments ==="
systemctl list-units --type=service --state=running | grep webops-llm

echo "=== Disk Usage ==="
du -sh /opt/webops/llm-deployments/*

echo "=== API Health ==="
for port in $(ss -tlnp | grep :90 | awk '{print $4}' | cut -d: -f2); do
    curl -s http://localhost:$port/health > /dev/null && echo "Port $port: OK" || echo "Port $port: FAIL"
done
EOF

chmod +x /opt/webops/scripts/monitor-llm.sh
```

### Backup and Recovery

```bash
# Backup deployment configurations
./manage.py dumpdata deployments.Deployment --indent 2 > deployments_backup.json

# Backup model cache (optional - models can be re-downloaded)
tar -czf model_cache_backup.tar.gz /opt/webops/llm-deployments/*/model_cache/

# Restore deployments
./manage.py loaddata deployments_backup.json
```

---

## 📈 Advanced Scenarios

### Multi-Model Deployment

Deploy multiple models simultaneously:

```python
models_config = [
    {
        'name': 'gpt2-small',
        'model_name': 'gpt2',
        'tensor_parallel_size': 1,
        'gpu_memory_utilization': 0.3
    },
    {
        'name': 'llama2-7b',
        'model_name': 'meta-llama/Llama-2-7b-hf',
        'tensor_parallel_size': 1,
        'gpu_memory_utilization': 0.6
    }
]

deployments = []
for config in models_config:
    deployment = ApplicationDeployment.objects.create(
        project_type=ApplicationDeployment.ProjectType.LLM,
        deployed_by=user,
        **config
    )
    task = deploy_llm_model.delay(deployment.id)
    deployments.append((deployment, task))
    print(f"Queued: {deployment.name}")

# Monitor all deployments
for deployment, task in deployments:
    deployment.refresh_from_db()
    print(f"{deployment.name}: {deployment.status}")
```

### Load Balancing Setup

For high-traffic scenarios, deploy the same model multiple times:

```python
# Deploy same model on different ports
base_config = {
    'model_name': 'meta-llama/Llama-2-7b-chat-hf',
    'tensor_parallel_size': 1,
    'gpu_memory_utilization': 0.9,
    'dtype': 'float16',
    'deployed_by': user,
    'project_type': Deployment.ProjectType.LLM
}

# Create multiple instances
for i in range(3):
    deployment = ApplicationDeployment.objects.create(
        name=f'llama2-7b-instance-{i+1}',
        **base_config
    )
    deploy_llm_model.delay(deployment.id)
    print(f"Deployed instance {i+1}")
```

### Custom Domain Setup

Deploy with custom domain:

```python
deployment = ApplicationDeployment.objects.create(
    name='production-llm',
    project_type=ApplicationDeployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-7b-chat-hf',
    domain='api.yourcompany.com',  # Custom domain
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    deployed_by=user
)

# The system will automatically configure Nginx with SSL
```

### Performance Benchmarking

Test model performance:

```python
import time
import requests

def benchmark_model(api_url, model_name, num_requests=10):
    """Benchmark model inference performance."""
    
    prompt = "Explain the concept of artificial intelligence in detail:"
    times = []
    
    for i in range(num_requests):
        start_time = time.time()
        
        response = requests.post(
            f"{api_url}/v1/completions",
            json={
                "model": model_name,
                "prompt": prompt,
                "max_tokens": 100,
                "temperature": 0.7
            }
        )
        
        end_time = time.time()
        
        if response.status_code == 200:
            times.append(end_time - start_time)
            print(f"Request {i+1}: {end_time - start_time:.2f}s")
        else:
            print(f"Request {i+1}: FAILED")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"\nAverage response time: {avg_time:.2f}s")
        print(f"Requests per minute: {60/avg_time:.1f}")

# Run benchmark
benchmark_model("http://localhost:9001", "llama2-7b-chat")
```

---

## 🎯 Summary

You now have a complete understanding of deploying LLMs from Hugging Face using vLLM in the WebOps platform. The key steps are:

1. **Setup**: Ensure GPU, CUDA, and WebOps prerequisites
2. **Authentication**: Connect Hugging Face account for model access
3. **Deploy**: Create deployment configuration and queue background task
4. **Monitor**: Track deployment progress and health
5. **Use**: Access OpenAI-compatible API for inference
6. **Manage**: Monitor performance, troubleshoot issues, scale as needed

The WebOps platform handles all the complexity of:
- ✅ Model downloading and caching
- ✅ vLLM environment setup and configuration
- ✅ SystemD service creation and management
- ✅ Nginx proxy configuration
- ✅ GPU resource allocation
- ✅ Health monitoring and logging
- ✅ API endpoint provisioning

**Next Steps:**
- Explore the troubleshooting guide for detailed problem resolution
- Review the API reference for complete API documentation
- Check the performance optimization section for production tuning

---

**Happy Deploying! 🚀**