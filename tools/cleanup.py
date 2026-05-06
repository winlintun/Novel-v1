"""
Cleanup Tool for Novel Translation Project
Manages Ollama memory and system resources.

Usage:
    python -m tools.cleanup --status          # Check Ollama status
    python -m tools.cleanup --stop-all        # Stop all running models
    python -m tools.cleanup --stop-service    # Stop Ollama service
    python -m tools.cleanup --full            # Full cleanup + status
    python -m tools.cleanup --all             # Comprehensive cleanup (stop models + clean cache)
    python -m tools.cleanup --tips            # Show memory tips
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_command(cmd, check=True, timeout=30):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if check and result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"  ✗ Error running command: {e}")
        return None


def check_ollama_status():
    """Check if Ollama is running and what models are loaded."""
    print("=" * 60)
    print("🔍 OLLAMA STATUS CHECK")
    print("=" * 60)
    
    # Check if Ollama process is running
    ps_output = run_command("ps aux | grep 'ollama serve' | grep -v grep", check=False)
    if ps_output:
        print("✓ Ollama server is RUNNING")
        # Parse PID and memory
        parts = ps_output.split()
        if len(parts) >= 6:
            pid = parts[1]
            cpu = parts[2]
            mem = parts[3]
            print(f"  PID: {pid}")
            print(f"  CPU: {cpu}%")
            print(f"  Memory: {mem}%")
    else:
        print("✗ Ollama server is NOT running")
    
    # Check loaded models
    print("\n📦 Loaded Models in Memory:")
    print("-" * 40)
    models_output = run_command("ollama ps 2>/dev/null", check=False)
    if models_output and "NAME" in models_output:
        print(models_output)
        # Count models
        lines = models_output.strip().split('\n')
        if len(lines) > 1:
            model_count = len(lines) - 1  # Exclude header
            print(f"\n  → {model_count} model(s) currently loaded")
        else:
            print("  → No models loaded")
    else:
        print("  No models currently loaded in memory")
    
    # Check available models
    print("\n📋 Available Models:")
    print("-" * 40)
    list_output = run_command("ollama list 2>/dev/null", check=False)
    if list_output:
        # Count available models
        lines = list_output.strip().split('\n')
        if len(lines) > 1:
            print(f"  {lines[0]}")  # Header
            for line in lines[1:]:
                print(f"  {line}")
            print(f"\n  → {len(lines)-1} model(s) installed")
        else:
            print("  No models installed")
    else:
        print("  Could not retrieve model list")
    
    # Check system memory
    print("\n💾 System Memory:")
    print("-" * 40)
    mem_output = run_command("free -h", check=False)
    if mem_output:
        print(mem_output)
    
    print("=" * 60)


def get_running_models():
    """Get list of currently running model names."""
    models_output = run_command("ollama ps 2>/dev/null", check=False)
    if not models_output or "NAME" not in models_output:
        return []
    
    running_models = []
    lines = models_output.strip().split('\n')[1:]  # Skip header
    for line in lines:
        if line.strip():
            parts = line.split()
            if parts:
                model_name = parts[0]
                running_models.append(model_name)
    
    return running_models


def stop_all_models(verbose=True):
    """Stop all running models by unloading them."""
    if verbose:
        print("\n🛑 Stopping all running models...")
        print("-" * 40)
    
    # Get list of running models
    running_models = get_running_models()
    
    if not running_models:
        if verbose:
            print("  ✓ No models are currently running")
        return True
    
    if verbose:
        print(f"  Found {len(running_models)} running model(s):")
        for model in running_models:
            print(f"    - {model}")
        print()
    
    # Stop each model using multiple methods
    success_count = 0
    for model_name in running_models:
        if verbose:
            print(f"  Stopping {model_name}...")
        
        # Method 1: Use ollama stop command (if available in newer versions)
        result = run_command(f'ollama stop {model_name} 2>/dev/null', check=False, timeout=10)
        time.sleep(0.5)
        
        # Method 2: Generate empty with keepalive 0
        run_command(f'ollama run {model_name} "" --keepalive 0 2>/dev/null', check=False, timeout=5)
        time.sleep(0.5)
        
        success_count += 1
        if verbose:
            print(f"    ✓ Stopped")
    
    # Wait a moment and verify
    time.sleep(1)
    remaining = get_running_models()
    
    if verbose:
        if not remaining:
            print(f"\n  ✓ All {success_count} model(s) stopped successfully")
        else:
            print(f"\n  ⚠ {len(remaining)} model(s) still running:")
            for model in remaining:
                print(f"    - {model}")
    
    return len(remaining) == 0


def stop_ollama_service():
    """Stop the Ollama service completely."""
    print("\n🔴 Stopping Ollama service...")
    print("-" * 40)
    
    # First stop all running models gracefully
    print("  Step 1: Stopping running models...")
    stop_all_models(verbose=False)
    time.sleep(2)
    
    # Try different methods to stop Ollama
    methods = [
        ("systemctl stop ollama 2>/dev/null", "Systemd service"),
        ("sudo systemctl stop ollama 2>/dev/null", "Systemd service (sudo)"),
        ("pkill -TERM -f 'ollama serve' 2>/dev/null", "Graceful process kill"),
        ("pkill -f 'ollama serve' 2>/dev/null", "Process kill"),
        ("killall -TERM ollama 2>/dev/null", "Killall (graceful)"),
        ("killall ollama 2>/dev/null", "Killall"),
    ]
    
    stopped = False
    for cmd, method_name in methods:
        print(f"  Trying {method_name}...")
        result = run_command(cmd, check=False, timeout=10)
        time.sleep(2)
        
        # Check if stopped
        check = run_command("ps aux | grep 'ollama serve' | grep -v grep", check=False)
        if not check:
            print(f"  ✓ Ollama service stopped using {method_name}")
            stopped = True
            break
    
    if not stopped:
        print("  ✗ Could not stop Ollama service automatically")
        print("\n  Manual steps to stop Ollama:")
        print("    1. Find PID: ps aux | grep ollama")
        print("    2. Kill: sudo kill -9 <PID>")
    
    return stopped


def clean_python_cache(verbose=True):
    """Clean Python __pycache__ directories and .pyc files."""
    if verbose:
        print("\n🧹 Cleaning Python cache files...")
        print("-" * 40)
    
    project_root = Path(__file__).parent.parent
    cache_dirs_removed = 0
    pyc_files_removed = 0
    
    # Find and remove __pycache__ directories
    for pycache_dir in project_root.rglob('__pycache__'):
        if pycache_dir.is_dir():
            try:
                shutil.rmtree(pycache_dir)
                cache_dirs_removed += 1
                if verbose:
                    print(f"  ✓ Removed {pycache_dir.relative_to(project_root)}")
            except Exception as e:
                if verbose:
                    print(f"  ✗ Failed to remove {pycache_dir}: {e}")
    
    # Find and remove .pyc files
    for pyc_file in project_root.rglob('*.pyc'):
        try:
            pyc_file.unlink()
            pyc_files_removed += 1
        except Exception:
            pass
    
    # Remove .pyo files
    for pyo_file in project_root.rglob('*.pyo'):
        try:
            pyo_file.unlink()
            pyo_files_removed += 1
        except Exception:
            pass
    
    if verbose:
        total = cache_dirs_removed + pyc_files_removed
        print(f"\n  ✓ Cleaned {total} cache item(s)")
        print(f"    - {cache_dirs_removed} __pycache__ directorie(s)")
        print(f"    - {pyc_files_removed} .pyc file(s)")
    
    return cache_dirs_removed + pyc_files_removed


def clear_swap():
    """Clear system swap (requires sudo)."""
    print("\n💫 Clearing swap memory...")
    print("-" * 40)
    
    result = run_command("sudo swapoff -a && sudo swapon -a 2>&1", check=False, timeout=30)
    if result is not None:
        print("  ✓ Swap cleared successfully")
        return True
    else:
        print("  ✗ Failed to clear swap (may require sudo)")
        print("  Run manually: sudo swapoff -a && sudo swapon -a")
        return False


def comprehensive_cleanup(clean_cache=True, clear_swap_memory=False):
    """Perform comprehensive cleanup - stop models, clean cache, show status."""
    print("\n" + "=" * 60)
    print("🧹 COMPREHENSIVE CLEANUP")
    print("=" * 60)
    
    # Step 1: Check initial status
    print("\n📊 STEP 1: Checking initial status...")
    print("-" * 40)
    initial_models = get_running_models()
    if initial_models:
        print(f"  Found {len(initial_models)} running model(s):")
        for model in initial_models:
            print(f"    - {model}")
    else:
        print("  No models currently running")
    
    # Step 2: Stop all running models
    print("\n🛑 STEP 2: Stopping running models...")
    print("-" * 40)
    if initial_models:
        stop_all_models(verbose=False)
        time.sleep(2)
        remaining = get_running_models()
        if not remaining:
            print("  ✓ All models stopped successfully")
        else:
            print(f"  ⚠ {len(remaining)} model(s) still running")
    else:
        print("  ✓ No models to stop")
    
    # Step 3: Clean Python cache
    if clean_cache:
        print("\n🧹 STEP 3: Cleaning Python cache...")
        print("-" * 40)
        cache_items = clean_python_cache(verbose=False)
        print(f"  ✓ Cleaned {cache_items} cache item(s)")
    
    # Step 4: Clear swap (optional)
    if clear_swap_memory:
        print("\n💫 STEP 4: Clearing swap memory...")
        print("-" * 40)
        clear_swap()
    
    # Step 5: Final status
    print("\n📊 STEP 5: Final status...")
    print("-" * 40)
    final_models = get_running_models()
    if not final_models:
        print("  ✓ No models running")
    else:
        print(f"  ⚠ {len(final_models)} model(s) still running:")
        for model in final_models:
            print(f"    - {model}")
    
    # Memory status
    mem_output = run_command("free -h | grep -E 'Mem|Swap'", check=False)
    if mem_output:
        print("\n  Memory Status:")
        for line in mem_output.split('\n'):
            print(f"    {line}")
    
    print("\n" + "=" * 60)
    print("✅ CLEANUP COMPLETE")
    print("=" * 60)


def full_cleanup():
    """Perform full cleanup - stop models and show status before/after."""
    print("\n" + "=" * 60)
    print("FULL CLEANUP")
    print("=" * 60 + "\n")
    
    # Check status before
    print("BEFORE CLEANUP:")
    check_ollama_status()
    
    # Stop models
    print("\n" + "-" * 60)
    stop_all_models()
    
    # Check status after
    print("\n" + "-" * 60)
    print("AFTER CLEANUP:")
    check_ollama_status()


def show_memory_tips():
    """Show memory management tips."""
    print("=" * 60)
    print("MEMORY MANAGEMENT TIPS")
    print("=" * 60)
    
    print("\n1. 🚀 QUICK CLEANUP (Recommended after translation):")
    print("   python -m tools.cleanup --stop-all")
    print("   → Stops all running models, frees GPU VRAM")
    
    print("\n2. 🧹 COMPREHENSIVE CLEANUP:")
    print("   python -m tools.cleanup --all")
    print("   → Stops models + cleans Python cache + shows memory")
    
    print("\n3. 🔴 COMPLETELY STOP OLLAMA:")
    print("   python -m tools.cleanup --stop-service")
    print("   → Stops Ollama service completely (frees all memory)")
    
    print("\n4. 📊 CHECK MEMORY USAGE:")
    print("   python -m tools.cleanup --status")
    print("   → Shows running models and system memory")
    
    print("\n5. 🧽 CLEAN PYTHON CACHE ONLY:")
    print("   python -m tools.cleanup --clean-cache")
    print("   → Removes __pycache__ and .pyc files")
    
    print("\n6. 💫 CLEAR SWAP MEMORY:")
    print("   python -m tools.cleanup --clear-swap")
    print("   → Runs: sudo swapoff -a && sudo swapon -a")
    
    print("\n7. 📚 DURING BATCH TRANSLATION:")
    print("   Use --unload-after-chapter flag to free memory between chapters")
    print("   python -m src.main --novel NAME --all --unload-after-chapter")
    
    print("\n8. 💾 MODEL SIZE COMPARISON:")
    print("   qwen2.5:14b  ~ 9GB VRAM  (Best quality)")
    print("   qwen2.5:7b   ~ 4GB VRAM  (Good quality, 2x faster)")
    print("   qwen:7b      ~ 4GB VRAM  (Fastest)")
    print("   padauk-gemma:q8_0 ~ 6GB VRAM (Myanmar specialized)")
    
    print("\n9. 🔧 IF SYSTEM IS SLOW:")
    print("   python -m tools.cleanup --all")
    print("   → Comprehensive cleanup")
    print("   OR manually:")
    print("   - Stop Ollama service")
    print("   - Clear swap: sudo swapoff -a && sudo swapon -a")
    print("   - Check free memory: free -h")
    
    print("\n10. ⚡ EMERGENCY MEMORY FREE:")
    print("   python -m tools.cleanup --stop-service")
    print("   → Stops Ollama completely (immediate memory release)")
    
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup tool for Ollama memory management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.cleanup --status           # Check current status
  python -m tools.cleanup --stop-all         # Stop running models
  python -m tools.cleanup --all              # Comprehensive cleanup
  python -m tools.cleanup --full             # Full cleanup with before/after
  python -m tools.cleanup --stop-service     # Stop Ollama service
  python -m tools.cleanup --clean-cache      # Clean Python cache only
  python -m tools.cleanup --clear-swap       # Clear swap memory
  python -m tools.cleanup --tips             # Show memory tips
        """
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check Ollama status and memory usage'
    )
    parser.add_argument(
        '--stop-all',
        action='store_true',
        help='Stop all running models (frees GPU VRAM)'
    )
    parser.add_argument(
        '--stop-service',
        action='store_true',
        help='Stop Ollama service completely (frees all memory)'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Perform full cleanup and show before/after status'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Comprehensive cleanup: stop models + clean cache + show status'
    )
    parser.add_argument(
        '--clean-cache',
        action='store_true',
        help='Clean Python __pycache__ and .pyc files'
    )
    parser.add_argument(
        '--clear-swap',
        action='store_true',
        help='Clear system swap memory (requires sudo)'
    )
    parser.add_argument(
        '--with-swap',
        action='store_true',
        help='Include swap clearing in --all (use with caution)'
    )
    parser.add_argument(
        '--tips',
        action='store_true',
        help='Show memory management tips'
    )
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if not any([args.status, args.stop_all, args.stop_service, args.full, 
                args.all, args.clean_cache, args.clear_swap, args.tips]):
        parser.print_help()
        print("\n" + "=" * 60)
        print("🚀 QUICK START")
        print("=" * 60)
        print("\nMost common commands:")
        print("  python -m tools.cleanup --all              # Comprehensive cleanup")
        print("  python -m tools.cleanup --stop-all         # Stop running models")
        print("  python -m tools.cleanup --status           # Check status")
        print("\nFor more help:")
        print("  python -m tools.cleanup --tips             # Show memory tips")
        return
    
    # Execute requested actions
    if args.tips:
        show_memory_tips()
    
    if args.all:
        comprehensive_cleanup(clean_cache=True, clear_swap_memory=args.with_swap)
    elif args.full:
        full_cleanup()
    elif args.status:
        check_ollama_status()
    elif args.stop_all:
        stop_all_models()
    elif args.stop_service:
        stop_ollama_service()
    elif args.clean_cache:
        clean_python_cache()
    elif args.clear_swap:
        clear_swap()


if __name__ == '__main__':
    main()
