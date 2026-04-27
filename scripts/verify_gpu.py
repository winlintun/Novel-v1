#!/usr/bin/env python3
"""
GPU Verification Script for Novel Translation Pipeline

This script checks if GPU is available and properly configured for Ollama inference.
Supports both NVIDIA (CUDA) and AMD (ROCm) GPUs.
Run this before starting translation to verify GPU acceleration is working.

Usage:
    python scripts/verify_gpu.py
"""

import subprocess
import sys
import os


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
            return "nvidia"
        else:
            print("❌ nvidia-smi returned an error")
            return None
    except FileNotFoundError:
        print("❌ nvidia-smi not found. No NVIDIA GPU detected.")
        return None
    except subprocess.TimeoutExpired:
        print("❌ nvidia-smi timed out")
        return None
    except Exception as e:
        print(f"❌ Error checking NVIDIA GPU: {e}")
        return None


def check_amd_gpu():
    """Check if AMD GPU is available."""
    print("=" * 60)
    print("🔍 Checking AMD GPU Availability")
    print("=" * 60)

    gpu_info = []
    
    # Method 1: Check ROCm (modern AMD GPUs)
    try:
        result = subprocess.run(
            ["rocminfo"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ ROCm (AMD GPU) detected!")
            # Extract GPU name from rocminfo
            for line in result.stdout.split('\n'):
                if 'Name:' in line and 'gfx' in line:
                    gpu_name = line.split('Name:')[-1].strip()
                    gpu_info.append(f"  GPU: {gpu_name}")
            return "amd"
    except FileNotFoundError:
        print("❌ rocminfo not found. ROCm may not be installed.")
    except Exception as e:
        print(f"❌ Error checking ROCm: {e}")

    # Method 2: Check via lspci
    try:
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            if 'VGA' in result.stdout or 'Display' in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'VGA' in line or 'Display' in line:
                        if 'AMD' in line or 'ATI' in line:
                            print(f"✅ AMD GPU found via lspci: {line}")
                            gpu_info.append(line.strip())
                            return "amd"
                        elif 'NVIDIA' in line:
                            # Already handled by nvidia-smi
                            pass
    except FileNotFoundError:
        print("❌ lspci not found.")
    except Exception as e:
        print(f"❌ Error checking lspci: {e}")

    # Method 3: Check /sys/class/drm for AMD cards
    try:
        if os.path.exists('/sys/class/drm'):
            for entry in os.listdir('/sys/class/drm'):
                if entry.startswith('card') and 'render' not in entry:
                    vendor_path = f'/sys/class/drm/{entry}/device/vendor'
                    if os.path.exists(vendor_path):
                        with open(vendor_path, 'r') as f:
                            vendor = f.read().strip()
                            if vendor == '0x1002':  # AMD vendor ID
                                device_path = f'/sys/class/drm/{entry}/device/device'
                                if os.path.exists(device_path):
                                    with open(device_path, 'r') as f:
                                        device = f.read().strip()
                                    print(f"✅ AMD GPU detected via /sys/class/drm: {device}")
                                    return "amd"
    except Exception as e:
        print(f"❌ Error checking /sys/class/drm: {e}")

    print("❌ No AMD GPU detected.")
    return None


def get_amd_gpu_details():
    """Get AMD GPU details specifically for RX 580."""
    print("=" * 60)
    print("🎮 AMD Radeon RX 580 2048SP Specific Info")
    print("=" * 60)
    
    info = []
    
    # Try to get more info about the GPU
    try:
        # Check if rocminfo shows the GPU
        result = subprocess.run(
            ["rocminfo", "|", "grep", "-A", "5", "Name:"],
            capture_output=True,
            text=True,
            shell=True,
            timeout=10
        )
        if result.returncode == 0:
            info.append("ROCm Info available")
            print("📊 ROCm GPU Information:")
            print(result.stdout[:500])
    except:
        pass

    # Check VRAM info
    try:
        if os.path.exists('/sys/class/drm'):
            for entry in os.listdir('/sys/class/drm'):
                mem_path = f'/sys/class/drm/{entry}/device/mem_info_vram_total'
                if os.path.exists(mem_path):
                    with open(mem_path, 'r') as f:
                        vram_bytes = int(f.read().strip())
                        vram_gb = vram_bytes / (1024**3)
                        info.append(f"VRAM: {vram_gb:.1f} GB")
                        print(f"📊 VRAM: {vram_gb:.1f} GB")
    except Exception as e:
        print(f"❌ Could not read VRAM info: {e}")

    return info


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
            models = client.list()
            print(f"✅ Ollama server is running")
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


def print_amd_setup_guide():
    """Print AMD GPU setup guide for RX 580."""
    print("=" * 60)
    print("📋 AMD RX 580 Setup Guide for Ollama")
    print("=" * 60)
    print("""
Your AMD Radeon RX 580 2048SP (8GB) can be used with Ollama via ROCm!

🔧 Installation Steps:

1. Install ROCm (Linux only):
   sudo apt install rocm-opencl-runtime rocm-hip-runtime
   
   Or download from: https://rocm.docs.amd.com/

2. Set environment variables before running Ollama:
   export HSA_OVERRIDE_GFX_VERSION=10.1.0
   export OLLAMA_GPU_OVERHEAD=1
   export OLLAMA_MAX_LOADED_MODELS=1
   
   # For RX 580 Polaris (gfx803)
   export HCC_AMDGPU_TARGET=gfx803

3. Check Ollama GPU support:
   ollama ps
   
   This should show GPU % usage if working correctly.

4. Verify GPU is being used:
   watch -n 1 rocm-smi
   
   Or check Ollama logs:
   sudo journalctl -u ollama -f | grep -i gpu

⚠️  Important Notes for RX 580:
- RX 580 uses Polaris architecture (gfx803)
- Official ROCm support for gfx803 is limited, but community builds work
- You may need to use a custom Ollama build or older ROCm version
- Consider using smaller models (7B) for better performance
- With 8GB VRAM, you can load qwen2.5:7b (~4GB) comfortably

🐛 Troubleshooting:
- If GPU not detected, try: export ROCM_VISIBLE_DEVICES=0
- For "hipErrorNoBinaryForGpu" error, you need gfx803 enabled ROCm
- Check: https://github.com/ollama/ollama/issues for AMD-specific issues
""")


def print_nvidia_setup_guide():
    """Print NVIDIA GPU setup guide."""
    print("=" * 60)
    print("📋 NVIDIA GPU Setup Guide")
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
    print("║" + " " * 13 + "(NVIDIA & AMD Support)" + " " * 24 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # Check for both NVIDIA and AMD GPUs
    nvidia_gpu = check_nvidia_gpu()
    print()
    amd_gpu = check_amd_gpu()
    print()
    
    # Determine which GPU type we found
    gpu_type = nvidia_gpu or amd_gpu
    
    if gpu_type == "amd":
        get_amd_gpu_details()
        print()
    
    ollama_ok = check_ollama_gpu()
    print()

    if gpu_type and ollama_ok:
        test_gpu_inference()
        print()

    # Print appropriate setup guide
    if gpu_type == "amd":
        print_amd_setup_guide()
    elif gpu_type == "nvidia":
        print_nvidia_setup_guide()
    else:
        print("=" * 60)
        print("📋 No GPU Detected")
        print("=" * 60)
        print("""
No NVIDIA or AMD GPU was detected. Translation will use CPU only.

For CPU-only mode:
- Set use_gpu: false in config/settings.yaml
- Expect slower translation speeds
- Consider using smaller models (qwen2.5:7b instead of 14b)
""")

    # Summary
    print("=" * 60)
    print("📋 Summary")
    print("=" * 60)

    if nvidia_gpu:
        print("✅ NVIDIA GPU: Available")
    else:
        print("❌ NVIDIA GPU: Not available")

    if amd_gpu:
        print("✅ AMD GPU: Available (ROCm)")
    else:
        print("❌ AMD GPU: Not available")

    if ollama_ok:
        print("✅ Ollama Server: Running")
    else:
        print("❌ Ollama Server: Not running")

    print()

    if gpu_type and ollama_ok:
        print("🎉 GPU configuration looks good! You're ready to translate.")
        print()
        print("To start translation with GPU acceleration:")
        print("  python -m src.main --novel <novel_name> --chapter 1")
        return 0
    elif ollama_ok:
        print("⚠️  No GPU detected, but Ollama is running.")
        print("   Translation will work but will use CPU only (slower).")
        return 0
    else:
        print("❌ Ollama server is not running. Please start it first:")
        print("   ollama serve")
        return 1


if __name__ == "__main__":
    sys.exit(main())
