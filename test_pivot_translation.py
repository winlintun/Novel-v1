#!/usr/bin/env python3
"""
Test script for Chinese → English → Myanmar pivot translation workflow.
Tests the two-stage pipeline with alternative 7B models.

Usage:
    python test_pivot_translation.py
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from src.utils.ollama_client import OllamaClient


def load_config(config_path: str = "config/settings.pivot.yaml") -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to load config from {config_path}: {e}")
        return {}


def validate_config(config: dict) -> bool:
    """Validate that config has required keys."""
    required = ['models', 'translation_pipeline', 'processing']
    for key in required:
        if key not in config:
            print(f"❌ Config missing required key: {key}")
            return False
    return True


def check_model_available(model: str) -> bool:
    """Check if a model is available in Ollama."""
    client = None
    try:
        client = OllamaClient(model=model)
        return client.check_model_available()
    except Exception as e:
        print(f"❌ Error checking model {model}: {e}")
        return False
    finally:
        if client:
            client.cleanup()


def test_stage1_chinese_to_english(text: str, config: dict) -> str:
    """
    Stage 1: Chinese → English translation.
    
    Args:
        text: Chinese text to translate
        config: Configuration dictionary
        
    Returns:
        English translation
    """
    models = config.get('models', {})
    pipeline = config.get('translation_pipeline', {})
    processing = config.get('processing', {})
    
    model = pipeline.get('stage1_model', models.get('translator', 'qwen2.5:14b'))
    temperature = processing.get('temperature', 0.3)
    repeat_penalty = processing.get('repeat_penalty', 1.15)
    top_p = processing.get('top_p', 0.92)
    top_k = processing.get('top_k', 50)
    
    print(f"\n{'='*60}")
    print("STAGE 1: Chinese → English")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"\nInput (Chinese):\n{text[:100]}...")
    
    # Rate limiting
    time.sleep(0.5)
    
    client = OllamaClient(
        model=model,
        temperature=temperature,
        repeat_penalty=repeat_penalty,
        top_p=top_p,
        top_k=top_k
    )
    
    # Use prompt from config
    prompt_template = pipeline.get('stage1_prompt', '')
    prompt = prompt_template.format(text=text, glossary="")
    
    system_prompt = pipeline.get("stage1_system_prompt", "You are an expert Chinese-to-English literary translator. Output ONLY English translation.")
    
    try:
        result = client.chat(prompt=prompt, system_prompt=system_prompt)
        print(f"\nOutput (English):\n{result[:200]}...")
        return result.strip()
    except Exception as e:
        print(f"\n❌ Stage 1 FAILED: {e}")
        return ""
    finally:
        client.cleanup()


def test_stage2_english_to_myanmar(text: str, config: dict) -> str:
    """
    Stage 2: English → Myanmar translation.
    
    Args:
        text: English text to translate
        config: Configuration dictionary
        
    Returns:
        Myanmar translation
    """
    models = config.get('models', {})
    pipeline = config.get('translation_pipeline', {})
    processing = config.get('processing', {})
    
    model = pipeline.get('stage2_model', models.get('editor', 'qwen:7b'))
    temperature = processing.get('temperature', 0.3)
    repeat_penalty = processing.get('repeat_penalty', 1.15)
    top_p = processing.get('top_p', 0.92)
    top_k = processing.get('top_k', 50)
    
    print(f"\n{'='*60}")
    print("STAGE 2: English → Myanmar")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"\nInput (English):\n{text[:100]}...")
    
    # Rate limiting
    time.sleep(0.5)
    
    client = OllamaClient(
        model=model,
        temperature=temperature,
        repeat_penalty=repeat_penalty,
        top_p=top_p,
        top_k=top_k
    )
    
    # Use prompt from config
    prompt_template = pipeline.get('stage2_prompt', '')
    prompt = prompt_template.format(text=text, glossary="")
    
    system_prompt = pipeline.get("stage2_system_prompt", "CRITICAL: Output ONLY Myanmar (Burmese) language using Myanmar Unicode script. NO English words or Chinese characters.")
    
    try:
        result = client.chat(prompt=prompt, system_prompt=system_prompt)
        print(f"\nOutput (Myanmar):\n{result[:200]}...")
        return result.strip()
    except Exception as e:
        print(f"\n❌ Stage 2 FAILED: {e}")
        return ""
    finally:
        client.cleanup()


def main():
    """Main test function."""
    # Test sentence from user
    test_chinese = """罗青，十二岁，小戎镇罗家村村民，相貌平凡，家境贫寒。

小戎山，草木葱茂，枝叶滴翠。"""
    
    print("="*60)
    print("PIVOT TRANSLATION TEST (CN → EN → MM)")
    print("="*60)
    print("\nTest Sentence:")
    print(test_chinese)
    
    # Load configuration
    print(f"\n{'='*60}")
    print("LOADING CONFIGURATION")
    print(f"{'='*60}")
    
    config = load_config("config/settings.pivot.yaml")
    if not config:
        print("❌ Cannot proceed without valid config")
        return 1
    
    if not validate_config(config):
        print("❌ Config validation failed")
        return 1
    
    print("✓ Config loaded successfully")
    
    pipeline = config.get('translation_pipeline', {})
    stage1_model = pipeline.get('stage1_model', 'qwen2.5:7b')
    stage2_model = pipeline.get('stage2_model', 'qwen:7b')
    
    # Check models
    print(f"\n{'='*60}")
    print("CHECKING MODELS")
    print(f"{'='*60}")
    
    for model in [stage1_model, stage2_model]:
        if check_model_available(model):
            print(f"✓ {model} - Available")
        else:
            print(f"✗ {model} - NOT AVAILABLE")
            print(f"  Run: ollama pull {model}")
            return 1
    
    # Stage 1: Chinese → English
    english_result = test_stage1_chinese_to_english(test_chinese, config)
    if not english_result:
        return 1
    
    # Stage 2: English → Myanmar
    myanmar_result = test_stage2_english_to_myanmar(english_result, config)
    if not myanmar_result:
        return 1
    
    # Final result
    print(f"\n{'='*60}")
    print("FINAL RESULT")
    print(f"{'='*60}")
    print(f"\n🇨🇳 Chinese (Original):\n{test_chinese}")
    print(f"\n🇬🇧 English (Stage 1):\n{english_result}")
    print(f"\n🇲🇲 Myanmar (Stage 2):\n{myanmar_result}")
    
    # Validate Myanmar output
    from src.utils.postprocessor import validate_output, detect_language_leakage
    
    print(f"\n{'='*60}")
    print("VALIDATION")
    print(f"{'='*60}")
    
    validation = validate_output(myanmar_result, chapter_num=0)
    leakage = detect_language_leakage(myanmar_result)
    
    print(f"Status: {validation['status']}")
    print(f"Myanmar ratio: {validation.get('myanmar_ratio', 0):.2%}")
    print(f"Chinese chars: {leakage.get('chinese_chars', 0)}")
    print(f"English words: {leakage.get('latin_words', 0)}")
    
    if validation['status'] == "APPROVED":
        print("\n✅ TEST PASSED - Pipeline is working!")
        return 0
    else:
        print(f"\n⚠️  TEST COMPLETED with warnings: {validation}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
