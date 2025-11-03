# 🤖 LLM Auto-Detection System

## Overview

WebOps now features **Railway-style auto-detection for LLM deployments**! Simply provide a HuggingFace model name, and the system automatically:

- 📊 Analyzes model characteristics from HuggingFace Hub
- 🎯 Recommends optimal backend (vLLM, Transformers, Ollama, TGI)
- ⚙️  Configures deployment settings automatically
- 💾 Estimates memory requirements
- ⚡ Selects optimal dtype and quantization

**Zero manual configuration required** - just like Railway, Vercel, and other modern platforms!

---

## 🚀 Quick Start

### Before (Manual Configuration)

```python
deployment = LLMDeployment.objects.create(
    name="my-llm",
    model_name="meta-llama/Llama-2-7b-chat-hf",
    backend='vllm',  # Manual selection
    dtype='float16',  # Manual selection
    max_model_len=4096,  # Manual specification
    # ... many more settings to configure manually
)
```

### After (Auto-Detection)

```python
deployment = LLMDeployment.objects.create(
    name="my-llm",
    model_name="meta-llama/Llama-2-7b-chat-hf",
    # That's it! Everything else is auto-detected and configured
)
```

The system automatically:
- ✅ Detects it's a Llama model with 7B parameters
- ✅ Recommends Transformers backend (CPU-friendly)
- ✅ Configures float16 dtype for efficiency
- ✅ Sets context length to 4096 tokens
- ✅ Estimates memory usage (~9GB)
- ✅ Provides deployment tips and warnings

---

## 🎯 How It Works

### 1. Model Analysis

The system fetches model information from HuggingFace Hub API:

- **Model Type**: GPT, Llama, Mistral, T5, BERT, etc.
- **Architecture**: Full architecture class name
- **Parameters**: Total parameter count (e.g., 7B, 13B, 70B)
- **Model Size**: File size in GB
- **Context Length**: Maximum sequence length
- **Metadata**: Author, license, downloads, tags

### 2. Backend Selection

Based on model characteristics and available hardware, the system recommends:

| Model Size | GPU Available | Recommended Backend | Reasoning |
|------------|---------------|---------------------|-----------|
| <500M params | No | **Transformers** | Fast setup, excellent CPU performance |
| 500M-1B | No | **Transformers** | Quick setup, good CPU inference |
| 1B-3B | No | **Transformers** | Reasonable CPU performance |
| 1B-3B | Yes (8GB+) | **vLLM** | Better throughput with GPU |
| 3B-7B | No | **Transformers** | Will be slow, GPU recommended |
| 3B-7B | Yes (12GB+) | **vLLM** | Optimal performance |
| 7B-13B | No | **Transformers** | Very slow, testing only |
| 7B-13B | Yes (16GB+) | **vLLM** | Excellent throughput |
| 13B-70B | Yes (24GB+) | **vLLM** | High-end GPU required |
| >70B | Yes (40GB+) | **vLLM** | Multi-GPU recommended |

### 3. Configuration Generation

Automatically generates optimal settings:

- **dtype**: `float16` (GPU), `float32` (CPU), or `bfloat16`
- **Quantization**: AWQ/GPTQ suggestions for large models
- **Max Model Length**: Based on model's native context window
- **Memory Estimates**: Accurate VRAM/RAM requirements
- **Environment Variables**: HuggingFace cache, logging, etc.

---

## 📊 Detection Result Fields

All auto-detected information is stored in the database:

```python
deployment.auto_detected = True
deployment.detected_model_type = 'llama'
deployment.detected_architecture = 'LlamaForCausalLM'
deployment.detected_task_type = 'text-generation'
deployment.detected_parameter_count = 7_000_000_000  # 7B
deployment.detected_context_length = 4096
deployment.detection_confidence = 0.95  # 95% confident

deployment.backend_recommendation = 'transformers'
deployment.backend_confidence = 0.90  # 90% confident
deployment.estimated_memory_required_gb = 9.2

deployment.model_author = 'meta-llama'
deployment.model_license = 'llama2'
deployment.model_downloads = 1_234_567
deployment.model_likes = 5_432
deployment.model_tags = ['llama', 'chat', '7b', 'conversational']
```

---

## 🎨 Example Detections

### Example 1: GPT-2 (Small Model)

**Input:**
```python
deployment = LLMDeployment.objects.create(
    name="gpt2-demo",
    model_name="gpt2",
    deployed_by=user
)
```

**Auto-Detected Configuration:**
```python
{
    "detected_model_type": "gpt",
    "detected_architecture": "GPT2LMHeadModel",
    "detected_parameter_count": 124_000_000,  # 124M params
    "model_size_gb": 0.5,
    "context_length": 1024,

    "recommended_backend": "transformers",
    "backend_confidence": 0.95,
    "backend_reasoning": "Model is very small (0.1B params). Transformers provides fast setup and excellent CPU performance for small models.",

    "suggested_dtype": "float32",  # CPU-optimized
    "estimated_memory_gb": 0.7,

    "info_messages": [
        "Estimated memory usage: ~0.7GB",
        "Maximum context length: 1024 tokens",
        "Transformers backend selected: Fast setup, excellent CPU support"
    ]
}
```

### Example 2: Llama-2-7B (Medium Model)

**Input:**
```python
deployment = LLMDeployment.objects.create(
    name="llama-chat",
    model_name="meta-llama/Llama-2-7b-chat-hf",
    deployed_by=user
)
```

**Auto-Detected Configuration:**
```python
{
    "detected_model_type": "llama",
    "detected_architecture": "LlamaForCausalLM",
    "detected_parameter_count": 7_000_000_000,  # 7B params
    "model_size_gb": 13.5,
    "context_length": 4096,

    "recommended_backend": "transformers",  # CPU deployment
    "backend_confidence": 0.70,
    "backend_reasoning": "Model size (7.0B params) can run on CPU but will be slow. Consider GPU for production use.",

    "suggested_dtype": "float32",
    "estimated_memory_gb": 18.9,

    "warnings": [
        "This model may be slow on CPU. GPU strongly recommended for production."
    ],

    "info_messages": [
        "Estimated memory usage: ~18.9GB",
        "Maximum context length: 4096 tokens",
        "⚠️ This model is gated. Ensure you have HuggingFace access token configured"
    ]
}
```

### Example 3: Mistral-7B-Instruct (With GPU)

**Input:**
```python
# Assuming GPU detected (future enhancement)
deployment = LLMDeployment.objects.create(
    name="mistral-instruct",
    model_name="mistralai/Mistral-7B-Instruct-v0.2",
    deployed_by=user
)
```

**Auto-Detected Configuration:**
```python
{
    "detected_model_type": "mistral",
    "detected_architecture": "MistralForCausalLM",
    "detected_parameter_count": 7_000_000_000,
    "model_size_gb": 14.5,
    "context_length": 32768,  # Extended context!

    "recommended_backend": "vllm",  # GPU available
    "backend_confidence": 0.95,
    "backend_reasoning": "Model size (7.0B params) requires GPU for practical use. vLLM provides excellent throughput.",

    "suggested_dtype": "float16",  # GPU-optimized
    "estimated_memory_gb": 20.3,

    "info_messages": [
        "Estimated memory usage: ~20.3GB",
        "Maximum context length: 32768 tokens",
        "vLLM backend selected: Optimized for high throughput and batching",
        "✅ SafeTensors format available - faster and safer model loading"
    ]
}
```

### Example 4: TinyLlama (Tiny Model)

**Input:**
```python
deployment = LLMDeployment.objects.create(
    name="tiny-llama",
    model_name="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    deployed_by=user
)
```

**Auto-Detected Configuration:**
```python
{
    "detected_model_type": "llama",
    "detected_parameter_count": 1_100_000_000,  # 1.1B params
    "model_size_gb": 2.2,
    "context_length": 2048,

    "recommended_backend": "transformers",
    "backend_confidence": 0.90,
    "backend_reasoning": "Model size (1.1B params) is ideal for Transformers backend with quick setup and good CPU inference.",

    "suggested_dtype": "float32",
    "estimated_memory_gb": 3.1,

    "info_messages": [
        "Estimated memory usage: ~3.1GB",
        "Maximum context length: 2048 tokens"
    ]
}
```

---

## 🔧 Architecture

### File Structure

```
apps/deployments/shared/llm_detection/
├── __init__.py                # Public API
├── detector.py                # Main orchestrator
├── model_analyzer.py          # HuggingFace Hub analysis
├── backend_selector.py        # Backend recommendation logic
└── config_generator.py        # Configuration generation
```

### Components

#### 1. **detector.py** - Main Orchestrator

```python
from apps.deployments.shared.llm_detection import detect_model

result = detect_model(
    model_name='meta-llama/Llama-2-7b-chat-hf',
    hf_token=hf_token,
    available_gpu=False,
    available_vram_gb=0.0
)
```

Returns `ModelDetectionResult` with complete analysis.

#### 2. **model_analyzer.py** - HuggingFace Hub Analysis

Fetches model information from HuggingFace Hub API:
- Model metadata (author, license, downloads)
- Configuration (architecture, parameters, context length)
- File information (size, safetensors availability)
- Infers model type from architecture or model ID

#### 3. **backend_selector.py** - Backend Recommendation

Decision matrix based on:
- Model parameter count
- Available hardware (GPU/VRAM)
- Model characteristics
- Performance requirements

Returns `BackendRecommendation` with:
- Recommended backend
- Confidence score
- Reasoning explanation
- Hardware requirements
- Warnings

#### 4. **config_generator.py** - Configuration Generation

Generates optimal settings:
- Data type (float16/float32/bfloat16)
- Quantization recommendations
- Context length limits
- Memory estimates
- Environment variables

---

## 💡 Usage in Code

### Auto-Detection During Deployment

Auto-detection runs automatically in `LLMDeploymentService.prepare_llm_deployment()`:

```python
# services/llm.py

def prepare_llm_deployment(self, deployment: LLMDeployment):
    # ... status updates ...

    # Auto-detect model (NEW!)
    self.detect_and_configure_model(deployment)

    # ... continue with deployment ...
```

### Manual Detection

You can also run detection manually:

```python
from apps.deployments.shared.llm_detection import detect_model

# Detect a model
result = detect_model('gpt2')

if result.detected:
    print(f"Model: {result.model_type}")
    print(f"Parameters: {result.parameter_count:,}")
    print(f"Backend: {result.recommended_backend}")
    print(f"Memory: {result.estimated_memory_gb}GB")
```

### Accessing Detection Results

```python
# Get deployment with auto-detection results
deployment = LLMDeployment.objects.get(name='my-llm')

if deployment.auto_detected:
    print(f"Detected: {deployment.detected_model_type}")
    print(f"Params: {deployment.detected_parameter_count:,}")
    print(f"Recommended: {deployment.backend_recommendation}")
    print(f"Confidence: {deployment.detection_confidence:.0%}")

    # Check warnings
    for tag in deployment.model_tags:
        if 'gated' in tag.lower():
            print("⚠️  This is a gated model")
```

---

## 🎓 Model Type Detection

The system recognizes common model architectures:

### Causal Language Models (Text Generation)
- **GPT Family**: GPT-2, GPT-Neo, GPT-J, GPT-NeoX
- **Llama Family**: Llama, Llama-2, Code Llama
- **Mistral Family**: Mistral, Mixtral
- **Other**: Falcon, MPT, BLOOM

### Encoder-Decoder Models (Text-to-Text)
- **T5 Family**: T5, Flan-T5, mT5
- **BART Family**: BART, mBART

### Encoder-Only Models (Understanding)
- **BERT Family**: BERT, RoBERTa, DistilBERT
- **Other**: ELECTRA, XLNet

### Detection Strategy

1. **From config.json**: Read `architectures` field
2. **From model name**: Pattern matching (e.g., "llama", "gpt", "mistral")
3. **From Hub metadata**: Pipeline tag and model card

---

## 📈 Confidence Scoring

Detection confidence is calculated based on:

- **Model Type Detected**: +30% confidence
- **Parameter Count Available**: +20% confidence
- **Model Size Available**: +20% confidence
- **Backend Recommendation**: +30% confidence (weighted by backend confidence)

**Confidence Levels:**
- **90-100%**: Excellent - All information available
- **70-89%**: Good - Most information available
- **50-69%**: Fair - Some information missing
- **<50%**: Poor - Limited information, proceed with caution

---

## 🔍 Detection Process Flow

```
User Creates LLM Deployment
         ↓
    Validate Model Name
         ↓
┌────────────────────────┐
│  1. Model Analysis     │
│  - Fetch from HF Hub   │
│  - Parse config.json   │
│  - Get file sizes      │
│  - Extract metadata    │
└────────────────────────┘
         ↓
┌────────────────────────┐
│  2. Backend Selection  │
│  - Check model size    │
│  - Check hardware      │
│  - Apply decision tree │
│  - Generate reasoning  │
└────────────────────────┘
         ↓
┌────────────────────────┐
│  3. Config Generation  │
│  - Select dtype        │
│  - Suggest quantize    │
│  - Set context length  │
│  - Estimate memory     │
└────────────────────────┘
         ↓
┌────────────────────────┐
│  4. Apply to Deployment│
│  - Update DB fields    │
│  - Log results         │
│  - Show warnings       │
└────────────────────────┘
         ↓
    Continue Deployment
```

---

## ⚙️  Backend Decision Matrix

### Transformers Backend

**Recommended for:**
- Small models (<3B parameters)
- CPU-only deployments
- Quick testing and development
- Single-request inference
- Low-latency requirements

**Pros:**
- ✅ Fast setup (no GPU dependencies)
- ✅ Excellent CPU performance for small models
- ✅ Lower memory overhead
- ✅ Simple configuration

**Cons:**
- ❌ Slower for large models
- ❌ No batching optimization
- ❌ Limited throughput

### vLLM Backend

**Recommended for:**
- Large models (>3B parameters)
- GPU-accelerated deployments
- High-throughput production workloads
- Batched inference
- Multi-user serving

**Pros:**
- ✅ Optimized for GPU
- ✅ Excellent batching and throughput
- ✅ Continuous batching support
- ✅ PagedAttention for memory efficiency

**Cons:**
- ❌ Requires GPU for best performance
- ❌ Complex CPU-only build
- ❌ Longer setup time

---

## 🚨 Warnings and Recommendations

The system provides intelligent warnings:

### Gated Models
```
⚠️ This model is gated. Ensure you have HuggingFace access token
   configured and have accepted the model's license agreement.
```

### GPU Recommendations
```
⚠️ This model may be slow on CPU. GPU strongly recommended for production.
```

### Large Models on CPU
```
⚠️ This 13B parameter model requires significant GPU resources.
   CPU deployment will be extremely slow (10+ minutes per request).
   Minimum 24GB VRAM GPU strongly recommended.
   Consider using quantization (AWQ/GPTQ) or smaller model variant.
```

### Multi-GPU Requirements
```
⚠️ This model may require tensor parallelism across multiple GPUs.
   Consider using quantized versions (AWQ/GPTQ) to reduce memory requirements.
```

---

## 📚 Integration Points

### 1. Model Creation (Django Admin / API)

Auto-detection runs automatically when creating deployments.

### 2. Deployment Service

`LLMDeploymentService.detect_and_configure_model()` is called during `prepare_llm_deployment()`.

### 3. Task Queue

Background task `deploy_llm_model` uses auto-detected settings.

### 4. Logging

All detection results and warnings are logged to `DeploymentLog`.

---

## 🎯 Future Enhancements

### Planned Features

1. **GPU Detection**
   - Auto-detect available GPUs and VRAM
   - Recommend tensor parallelism settings
   - Suggest optimal quantization

2. **Performance Prediction**
   - Estimate inference latency
   - Predict throughput (tokens/sec)
   - Memory usage profiling

3. **Cost Estimation**
   - Estimate deployment costs
   - Compare backend costs
   - Optimize for budget

4. **Model Comparison**
   - Compare similar models
   - Suggest alternatives
   - Performance/cost trade-offs

5. **UI Integration**
   - Web interface for detection preview
   - Interactive model explorer
   - Visual configuration wizard

---

## 🧪 Testing

### Manual Testing

```python
# In Django shell
from apps.deployments.shared.llm_detection import detect_model

# Test small model
result = detect_model('gpt2')
print(f"Backend: {result.recommended_backend}")
print(f"Memory: {result.estimated_memory_gb}GB")

# Test large model
result = detect_model('meta-llama/Llama-2-13b-chat-hf', hf_token='your-token')
print(f"Backend: {result.recommended_backend}")
print(f"Warnings: {result.warnings}")
```

### Example Models to Test

| Model | Size | Expected Backend |
|-------|------|------------------|
| `gpt2` | 124M | Transformers |
| `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | 1.1B | Transformers |
| `mistralai/Mistral-7B-Instruct-v0.2` | 7B | Transformers (CPU) / vLLM (GPU) |
| `meta-llama/Llama-2-13b-chat-hf` | 13B | vLLM (GPU) |

---

## 📊 Statistics

### Detection Capabilities

- **Model Types**: 10+ model families recognized
- **Backends**: 4 backends supported (vLLM, Transformers, Ollama, TGI)
- **Auto-Configured**: 15+ deployment fields
- **Confidence Scoring**: 0.0 to 1.0 scale
- **HuggingFace Integration**: Direct Hub API access

### Detection Fields

- **15 auto-detection fields** in `LLMDeployment` model
- **8 configuration parameters** auto-configured
- **4 metadata fields** from HuggingFace
- **Complete detection result** with warnings and recommendations

---

## 🎉 Conclusion

WebOps LLM auto-detection provides a **Railway-like experience** for deploying language models:

✅ **Zero manual configuration** - just provide model name
✅ **Intelligent backend selection** - optimal for your hardware
✅ **Automatic optimization** - dtype, quantization, context length
✅ **Production-ready** - memory estimates, warnings, recommendations
✅ **HuggingFace integrated** - direct Hub API access

**Deploy LLMs as easily as deploying web applications!**

---

**Built with ❤️  for the WebOps community**

*WebOps - Enterprise-Grade Auto-Deployment Platform*
