#!/bin/bash
# AMD GPU Setup Script for Ollama (RX 580)
# Run this before starting Ollama to enable GPU acceleration

echo "Setting up AMD GPU environment for Ollama..."

# Required for RX 580 Polaris (gfx803) architecture
export HSA_OVERRIDE_GFX_VERSION=10.1.0
export HCC_AMDGPU_TARGET=gfx803

# Ollama GPU settings
export OLLAMA_GPU_OVERHEAD=1
export OLLAMA_MAX_LOADED_MODELS=1

# Optional: Force GPU usage
export OLLAMA_NUM_GPU=99

echo "Environment variables set:"
echo "  HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE_GFX_VERSION"
echo "  HCC_AMDGPU_TARGET=$HCC_AMDGPU_TARGET"
echo "  OLLAMA_GPU_OVERHEAD=$OLLAMA_GPU_OVERHEAD"
echo ""
echo "You can now start Ollama with:"
echo "  ollama serve"
