#!/usr/bin/env python
"""
Comprehensive test suite for LLM auto-detection system.

Tests various model families, sizes, and architectures to validate detection accuracy.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.deployments.shared.llm_detection import detect_model


def print_separator():
    """Print a visual separator."""
    print("\n" + "="*80 + "\n")


def test_model(model_name: str, description: str):
    """Test a single model and print results."""
    print(f"🔍 Testing: {model_name}")
    print(f"📝 Description: {description}")
    print("-" * 80)

    try:
        result = detect_model(model_name)

        if result.detected:
            print(f"✅ Detection: SUCCESS")
            print(f"📊 Model Type: {result.model_type}")
            print(f"🏗️  Architecture: {result.architecture}")
            print(f"📋 Task Type: {result.task_type}")

            if result.parameter_count:
                params_b = result.parameter_count / 1e9
                print(f"🔢 Parameters: {result.parameter_count:,} ({params_b:.2f}B)")
            else:
                print(f"🔢 Parameters: Unknown")

            if result.model_size_gb:
                print(f"💾 Model Size: {result.model_size_gb:.2f}GB")
            else:
                print(f"💾 Model Size: Unknown")

            if result.context_length:
                print(f"📏 Context Length: {result.context_length:,} tokens")
            else:
                print(f"📏 Context Length: Unknown")

            print(f"🎯 Recommended Backend: {result.recommended_backend}")
            print(f"📈 Backend Confidence: {result.backend_confidence:.0%}")
            print(f"💡 Reasoning: {result.backend_reasoning}")
            print(f"⚙️  Suggested dtype: {result.suggested_dtype}")

            if result.suggested_quantization:
                print(f"🗜️  Quantization: {result.suggested_quantization}")

            print(f"🧮 Estimated Memory: {result.estimated_memory_gb:.2f}GB")
            print(f"🎓 Overall Confidence: {result.confidence:.0%}")

            if result.requires_gpu:
                print(f"🖥️  GPU Required: Yes (min {result.min_vram_gb:.0f}GB VRAM)")
            else:
                print(f"🖥️  GPU Required: No")

            if result.warnings:
                print(f"\n⚠️  Warnings:")
                for warning in result.warnings:
                    print(f"   - {warning}")

            if result.info_messages:
                print(f"\n💬 Info:")
                for info in result.info_messages:
                    print(f"   - {info}")

            print(f"\n📚 Metadata:")
            print(f"   Author: {result.author}")
            print(f"   License: {result.license}")
            print(f"   Downloads: {result.downloads:,}")
            print(f"   Likes: {result.likes:,}")

            return True
        else:
            print(f"❌ Detection: FAILED")
            print(f"Error: {result.error_message}")
            if result.warnings:
                for warning in result.warnings:
                    print(f"⚠️  {warning}")
            return False

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run comprehensive test suite."""
    print("="*80)
    print("🧪 LLM AUTO-DETECTION COMPREHENSIVE TEST SUITE")
    print("="*80)

    test_cases = [
        # Small models (< 500M params)
        ("gpt2", "GPT-2 - Small OpenAI model (124M params)"),
        ("distilbert-base-uncased", "DistilBERT - Small BERT variant (66M params)"),
        ("google/flan-t5-small", "Flan-T5 Small - Google's instruction-tuned T5 (80M params)"),

        # Medium models (500M - 3B params)
        ("TinyLlama/TinyLlama-1.1B-Chat-v1.0", "TinyLlama - Small Llama variant (1.1B params)"),
        ("bert-base-uncased", "BERT Base - Classic encoder model (110M params)"),
        ("facebook/opt-1.3b", "OPT-1.3B - Meta's open model"),

        # Large models (3B - 13B params)
        ("mistralai/Mistral-7B-v0.1", "Mistral 7B - High-performance 7B model"),
        ("google/flan-t5-base", "Flan-T5 Base - Instruction-tuned (250M params)"),
        ("microsoft/phi-2", "Phi-2 - Microsoft's efficient 2.7B model"),

        # Very large models (13B+)
        ("meta-llama/Llama-2-7b-chat-hf", "Llama 2 7B Chat - Meta's conversational model"),
        ("meta-llama/Llama-2-13b-hf", "Llama 2 13B - Larger Llama variant"),

        # Specialized architectures
        ("sentence-transformers/all-MiniLM-L6-v2", "Sentence Transformer - Embedding model"),
        ("facebook/bart-large-cnn", "BART Large - Seq2seq for summarization"),
        ("bigscience/bloom-560m", "BLOOM 560M - Multilingual model"),

        # Code models
        ("Salesforce/codegen-350M-mono", "CodeGen - Code generation model"),
    ]

    results = {
        'total': len(test_cases),
        'passed': 0,
        'failed': 0
    }

    for i, (model_name, description) in enumerate(test_cases, 1):
        print_separator()
        print(f"[{i}/{len(test_cases)}]")
        success = test_model(model_name, description)

        if success:
            results['passed'] += 1
        else:
            results['failed'] += 1

    # Print summary
    print_separator()
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {results['passed']/results['total']*100:.1f}%")
    print("="*80)

    # Print recommendations
    print("\n💡 DETECTION SYSTEM INSIGHTS:")
    print("-" * 80)
    print("1. Model Type Coverage: GPT, Llama, BERT, T5, Mistral, BART, BLOOM, OPT")
    print("2. Size Range: 66M to 13B+ parameters")
    print("3. Architecture Types: Causal LM, Encoder-only, Encoder-Decoder, Embeddings")
    print("4. Backend Recommendations: Transformers, vLLM, Ollama, TGI")
    print("5. Hardware Configurations: CPU, GPU (various VRAM requirements)")
    print("-" * 80)


if __name__ == '__main__':
    main()
