# LLM Deployment Steps Guide: From Hugging Face to vLLM

**WebOps LLM Deployment - Complete Step-by-Step Process**

---

## 📋 Overview

This guide provides detailed steps for deploying Large Language Models (LLMs) from Hugging Face using vLLM in the WebOps platform. The system automates the entire process from model selection to running inference server with OpenAI-compatible API.

### Architecture Overview

```
Hugging Face Model → WebOps Control Panel → vLLM Service → OpenAI API
     ↓                      ↓                    ↓            ↓
Model Repository    Deployment Management    GPU Inference   Client Access
```

**Key Components:**
- **Hugging Face Integration**: Secure token management for model access
- **vLLM Engine**: High-performance GPU inference with tensor parallelism
- **SystemD Services**: Automatic service management and monitoring
- **Nginx Proxy**: Load balancing and API access control
- **Celery Tasks**: Background deployment processing

---

## 🔧 Prerequisites

### System Requirements

#### Hardware Requirements
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

#### Software Requirements
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

---

## 🔑 Step 1: Hugging Face Authentication Setup

### 1.1 Get Hugging Face API Token

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

### 1.2 Connect Token to WebOps

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

## 🚀 Step 2: Deploy Your First Model

### 2.1 Quick Test Deployment (GPT-2)

Start with a small model to verify your setup:

```python
# In Django shell (./manage.py shell)
from django.contrib.auth.models import User
from apps.deployments.models import Deployment
from apps.deployments.tasks import deploy_llm_model

# Get your user
user = User.objects.get(username='your_username')

# Create deployment configuration
deployment = Deployment.objects.create(
    name='gpt2-test',
    project_type=Deployment.ProjectType.LLM,
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

### 2.2 Monitor Deployment Progress

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

### 2.3 Test the Deployed Model

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

## 🎯 Step 3: Deploy Production Models

### 3.1 Popular Model Configurations

#### Llama 2 7B Chat
```python
deployment = Deployment.objects.create(
    name='llama2-7b-chat',
    project_type=Deployment.ProjectType.LLM,
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
deployment = Deployment.objects.create(
    name='codellama-13b',
    project_type=Deployment.ProjectType.LLM,
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
deployment = Deployment.objects.create(
    name='llama2-7b-awq',
    project_type=Deployment.ProjectType.LLM,
    model_name='TheBloke/Llama-2-7B-Chat-AWQ',
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    quantization='awq',
    dtype='auto',
    deployed_by=user
)
```

### 3.2 Advanced Configuration Options

```python
# Full configuration example
deployment = Deployment.objects.create(
    name='custom-model',
    project_type=Deployment.ProjectType.LLM,
    
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

---

## 📊 Step 4: Monitoring and Management

### 4.1 Check Deployment Status

```python
# List all deployments
deployments = Deployment.objects.filter(project_type=Deployment.ProjectType.LLM)
for dep in deployments:
    print(f"{dep.name}: {dep.status} (Port: {dep.port})")

# Get specific deployment
deployment = Deployment.objects.get(name='llama2-7b-chat')
print(f"Status: {deployment.status}")
print(f"Model: {deployment.model_name}")
print(f"Port: {deployment.port}")
print(f"GPUs: {deployment.tensor_parallel_size}")
```

### 4.2 View Deployment Logs

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

### 4.3 Health Checks

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

### 4.4 Service Management

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

## 🔧 Step 5: Troubleshooting

### 5.1 Common Issues and Solutions

#### Issue: Deployment Stuck in "BUILDING" Status
```python
# Check deployment logs
deployment = Deployment.objects.get(name='your-deployment')
for log in deployment.logs.filter(level='error'):
    print(log.message)

# Common causes:
# 1. Insufficient GPU memory
# 2. Model download failure
# 3. CUDA driver issues
# 4. Network connectivity problems
```

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
```python
# Reduce GPU memory utilization
deployment.gpu_memory_utilization = 0.7  # Reduce from 0.9
deployment.save()

# Or use quantization
deployment.quantization = 'awq'
deployment.save()

# Redeploy
task = deploy_llm_model.delay(deployment.id)
```

#### Issue: Model Download Fails
```python
# Check Hugging Face connection
from apps.core.integration_services import HuggingFaceIntegrationService
hf_service = HuggingFaceIntegrationService()
result = hf_service.test_connection(user)
print(result)

# Verify model exists and is accessible
# Visit: https://huggingface.co/model-name
```

#### Issue: Port Already in Use
```python
# Check port allocation
from apps.deployments.llm_service import LLMDeploymentService
service = LLMDeploymentService()
used_ports = service.get_used_ports()
print(f"Used ports: {used_ports}")

# Manually assign different port
deployment.port = 9002  # Choose unused port
deployment.save()
```

### 5.2 Performance Optimization

#### GPU Memory Optimization
```python
# For large models, use tensor parallelism
deployment.tensor_parallel_size = 2  # Use 2 GPUs

# Reduce memory usage
deployment.gpu_memory_utilization = 0.8
deployment.dtype = 'float16'  # Use half precision

# Enable quantization for memory savings
deployment.quantization = 'awq'  # or 'gptq'
```

#### Context Length Optimization
```python
# Reduce context length for better performance
deployment.max_model_len = 2048  # Reduce from default 4096

# For chat applications, shorter contexts are often sufficient
deployment.max_model_len = 1024
```

---

## 🌐 Step 6: API Usage Examples

### 6.1 OpenAI-Compatible API

Once deployed, your model provides an OpenAI-compatible API:

#### Text Completion
```bash
curl http://localhost:9001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2-7b-chat",
    "prompt": "Explain quantum computing in simple terms:",
    "max_tokens": 150,
    "temperature": 0.7,
    "top_p": 0.9
  }'
```

#### Chat Completion (for chat models)
```bash
curl http://localhost:9001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2-7b-chat",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is machine learning?"}
    ],
    "max_tokens": 150,
    "temperature": 0.7
  }'
```

### 6.2 Python Client Example

```python
import requests
import json

# Configuration
API_BASE = "http://localhost:9001/v1"
MODEL_NAME = "llama2-7b-chat"

def generate_text(prompt, max_tokens=100):
    """Generate text using the deployed model."""
    response = requests.post(
        f"{API_BASE}/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["text"]
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Example usage
prompt = "The benefits of renewable energy include:"
generated_text = generate_text(prompt)
print(f"Generated: {generated_text}")
```

---

## 📚 Step 7: Advanced Deployment Scenarios

### 7.1 Multi-Model Deployment

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
    deployment = Deployment.objects.create(
        project_type=Deployment.ProjectType.LLM,
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

### 7.2 Load Balancing Setup

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
    deployment = Deployment.objects.create(
        name=f'llama2-7b-instance-{i+1}',
        **base_config
    )
    deploy_llm_model.delay(deployment.id)
    print(f"Deployed instance {i+1}")
```

### 7.3 Custom Domain Setup

Deploy with custom domain:

```python
deployment = Deployment.objects.create(
    name='production-llm',
    project_type=Deployment.ProjectType.LLM,
    model_name='meta-llama/Llama-2-7b-chat-hf',
    domain='api.yourcompany.com',  # Custom domain
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    deployed_by=user
)

# The system will automatically configure Nginx with SSL
```

---

## 🔒 Step 8: Security and Production Considerations

### 8.1 Security Best Practices

```python
# Use environment variables for sensitive configuration
deployment = Deployment.objects.create(
    name='secure-llm',
    project_type=Deployment.ProjectType.LLM,
    model_name='private-org/private-model',
    env_vars={
        'API_KEY_REQUIRED': 'true',
        'RATE_LIMIT_ENABLED': 'true',
        'LOG_LEVEL': 'INFO'
    },
    deployed_by=user
)
```

### 8.2 Resource Monitoring

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

### 8.3 Backup and Recovery

```bash
# Backup deployment configurations
./manage.py dumpdata deployments.Deployment --indent 2 > deployments_backup.json

# Backup model cache (optional - models can be re-downloaded)
tar -czf model_cache_backup.tar.gz /opt/webops/llm-deployments/*/model_cache/

# Restore deployments
./manage.py loaddata deployments_backup.json
```

---

## 📈 Performance Benchmarking

### Test Model Performance

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
- Explore the <mcfile name="llm-deployment-guide.md" path="$WEBOPS_DIR/docs/llm-deployment-guide.md"></mcfile> for advanced configurations
- Check the <mcfile name="troubleshooting.md" path="$WEBOPS_DIR/docs/troubleshooting.md"></mcfile> guide for detailed problem resolution
- Review the <mcfile name="api-reference.md" path="$WEBOPS_DIR/docs/api-reference.md"></mcfile> for complete API documentation

---

**Happy Deploying! 🚀**