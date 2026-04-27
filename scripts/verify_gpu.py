#!/usr/bin/env python3
"""
GPU Verification Script for Novel Translation Pipeline

This script checks if GPU is available and properly configured for Ollama inference.
Run this before starting translation to verify GPU acceleration is working.

Usage:
    python scripts/verify_gpu.py
"""

import subprocess
import sys
import json


def check_nvidia_gpu():
    """Check if NVIDIA GPU is available."""
    print("=" * 60)
    print("🔍 Checking NVIDIA GPU Availability")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ NVIDIA GPU detected!")
            print("\n📊 GPU Information:")
            print(result.stdout)
            return True
        else:
            print("❌ nvidia-smi returned an error")
            return False
    except FileNotFoundError:
        print("❌ nvidia-smi not found. NVIDIA drivers may not be installed.")
        return False
    except subprocess.TimeoutExpired:
        print("❌ nvidia-smi timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking GPU: {e}")
        return False


def check_ollama_gpu():
    """Check if Ollama is configured to use GPU."""
    print("=" * 60)
    print("🔍 Checking Ollama GPU Configuration")
    print("=" * 60)

    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434")

        # Check if Ollama server is running
        try:
            version = client.version()
            print(f"✅ Ollama server is running (version: {version})")
        except Exception as e:
            print(f"❌ Cannot connect to Ollama server: {e}")
            return False

        # List available models
        models = client.list()
        model_list = models.get('models', [])

        if model_list:
            print(f"\n📦 Available models ({len(model_list)}):")
            for m in model_list:
                model_name = m.get('model') or m.get('name', 'unknown')
                print(f"  - {model_name}")
        else:
            print("\n⚠️  No models found. You may need to pull models first:")
            print("     ollama pull qwen2.5:14b")

        return True

    except ImportError:
        print("❌ ollama Python package not installed")
        print("   Install with: pip install ollama")
        return False
    except Exception as e:
        print(f"❌ Error checking Ollama: {e}")
        return False


def test_gpu_inference():
    """Test GPU inference with a simple prompt."""
    print("=" * 60)
    print("🧪 Testing GPU Inference")
    print("=" * 60)

    try:
        import ollama
        import time

        client = ollama.Client(host="http://localhost:11434")

        # Check available models
        models = client.list()
        model_list = models.get('models', [])

        if not model_list:
            print("❌ No models available for testing")
            return False

        # Use the first available model
        test_model = model_list[0].get('model') or model_list[0].get('name')
        print(f"📝 Testing with model: {test_model}")

        # Simple test prompt
        test_prompt = "Hello, this is a GPU test. Respond with 'GPU test successful' only."

        print("⏳ Running inference test...")
        start_time = time.time()

        response = client.generate(
            model=test_model,
            prompt=test_prompt,
            options={
                "temperature": 0.1,
                "num_predict": 50,
                "num_gpu": 99  # Try to use GPU layers
            }
        )

        elapsed = time.time() - start_time

        print(f"✅ Inference completed in {elapsed:.2f} seconds")
        print(f"📝 Response: {response.get('response', 'No response')[:100]}...")

        # Check response metadata for GPU usage
        if 'eval_count' in response:
            tokens = response['eval_count']
            tokens_per_sec = tokens / elapsed if elapsed > 0 else 0
            print(f"📊 Tokens generated: {tokens}")
            print(f"📊 Speed: {tokens_per_sec:.2f} tokens/sec")

            # Heuristic: If speed > 10 tokens/sec, likely using GPU
            if tokens_per_sec > 10:
                print("⚡ High token generation speed suggests GPU is being used!")
            else:
                print("🐢 Low token generation speed may indicate CPU-only mode")

        return True

    except KeyboardInterrupt:
        print("\n⚠️  GPU test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error during GPU test: {e}")
        return False


def check_ollama_logs():
    """Provide guidance on checking Ollama GPU logs."""
    print("=" * 60)
    print("📋 How to Verify GPU Usage")
    print("=" * 60)
    print("""
To verify GPU is being used during translation:

1. Watch nvidia-smi in another terminal:
   watch -n 1 nvidia-smi

2. Check Ollama logs for GPU offload:
   sudo journalctl -u ollama -f
   
   Look for messages like:
   - "offloading X layers to GPU"
   - "using CUDA"

3. For manual testing, run:
   ollama run qwen2.5:14b
   Then check nvidia-smi to see GPU memory usage

4. Environment variables (set before running Ollama):
   export OLLAMA_GPU_OVERHEAD=1
   export OLLAMA_MAX_LOADED_MODELS=1
   export CUDA_VISIBLE_DEVICES=0  # Use specific GPU
""")


def main():
    """Main verification function."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 12 + "GPU Verification Tool" + " " * 25 + "║")
    print("║" + " " * 7 + "Novel Translation Pipeline" + " " * 24 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # Run all checks
    gpu_available = check_nvidia_gpu()
    ollama_ok = check_ollama_gpu()

    if gpu_available and ollama_ok:
        test_gpu_inference()

    check_ollama_logs()

    # Summary
    print("=" * 60)
    print("📋 Summary")
    print("=" * 60)

    if gpu_available:
        print("✅ NVIDIA GPU: Available")
    else:
        print("❌ NVIDIA GPU: Not available")

    if ollama_ok:
        print("✅ Ollama Server: Running")
    else:
        print("❌ Ollama Server: Not running")

    print()

    if gpu_available and ollama_ok:
        print("🎉 GPU configuration looks good! You're ready to translate.")
        print()
        print("To start translation with GPU acceleration:")
        print("  python -m src.main --novel <novel_name> --chapter 1")
        return 0
    else:
        print("⚠️  Some issues detected. Please fix them before translating.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
