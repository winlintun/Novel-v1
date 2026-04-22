#!/usr/bin/env python3
"""
Main Entry Point - Novel Translator Router

Automatically routes to the appropriate translator:
- local_main.py  - For Ollama (local, no rate limits)
- cloud_main.py  - For cloud APIs (Gemini, OpenRouter with rate limits)

Usage:
    python main.py file.md                    # Auto-detect best option
    python main.py file.md --model ollama     # Force local
    python main.py file.md --model gemini     # Force cloud

For more control, use the specific scripts directly:
    python local_main.py file.md
    python cloud_main.py file.md --model gemini
"""

import os
import sys
import argparse
from pathlib import Path


def check_ollama_available():
    """Check if Ollama is available."""
    try:
        from scripts.translator import get_translator
        translator = get_translator("ollama")
        return True
    except:
        return False


def check_api_key(model):
    """Check if API key is available for cloud model."""
    if model == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    elif model == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY"))
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Novel Translator - Routes to local or cloud",
        add_help=False  # We'll pass through to sub-scripts
    )
    
    parser.add_argument("file", nargs="?", help="File to translate")
    parser.add_argument("--model", choices=["ollama", "gemini", "openrouter"],
                       help="Translation model (default: auto-detect)")
    parser.add_argument("--help", "-h", action="store_true", help="Show help")
    
    # Parse only known args, pass rest to sub-script
    args, remaining_args = parser.parse_known_args()
    
    if args.help:
        print(__doc__)
        print("\nOptions:")
        print("  file              File to translate")
        print("  --model MODEL     Force specific model (ollama/gemini/openrouter)")
        print("  --help            Show this help")
        print("\nFor detailed options, run:")
        print("  python local_main.py --help")
        print("  python cloud_main.py --help")
        return
    
    # Determine which script to run
    use_local = None
    
    if args.model:
        # User specified model
        if args.model == "ollama":
            use_local = True
        else:
            use_local = False
    else:
        # Auto-detect
        ollama_available = check_ollama_available()
        gemini_key = check_api_key("gemini")
        openrouter_key = check_api_key("openrouter")
        
        if ollama_available:
            print("✓ Ollama detected - using local translation (no rate limits)")
            print("  (To use cloud API instead: python main.py --model gemini)")
            use_local = True
        elif gemini_key:
            print("✓ Gemini API key found - using cloud translation")
            print("  Note: Rate limits apply (15 requests/minute)")
            use_local = False
            remaining_args = ["--model", "gemini"] + remaining_args
        elif openrouter_key:
            print("✓ OpenRouter API key found - using cloud translation")
            print("  Note: Rate limits apply (20 requests/minute)")
            use_local = False
            remaining_args = ["--model", "openrouter"] + remaining_args
        else:
            print("❌ No translation method available!")
            print("\nTo use local Ollama:")
            print("  1. Install Ollama: https://ollama.ai")
            print("  2. Pull model: ollama pull qwen2.5:14b")
            print("  3. Start Ollama: ollama serve")
            print("\nTo use cloud API:")
            print("  1. Get API key from Google (Gemini) or OpenRouter")
            print("  2. Add to .env: GEMINI_API_KEY=your_key")
            print("  3. Run: python main.py --model gemini")
            return
    
    # Route to appropriate script
    script_dir = Path(__file__).parent
    
    if use_local:
        script = script_dir / "local_main.py"
        if not script.exists():
            print(f"❌ local_main.py not found")
            return
        
        # Build command
        cmd = [sys.executable, str(script)]
        if args.file:
            cmd.append(args.file)
        cmd.extend(remaining_args)
        
        print(f"\n→ Running local translation...")
        os.execv(sys.executable, cmd)
        
    else:
        script = script_dir / "cloud_main.py"
        if not script.exists():
            print(f"❌ cloud_main.py not found")
            return
        
        # Build command
        cmd = [sys.executable, str(script)]
        if args.file:
            cmd.append(args.file)
        cmd.extend(remaining_args)
        
        print(f"\n→ Running cloud translation...")
        os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
