"""
Cleanup Tool for Novel Translation Project
Manages Ollama memory and system resources.

Usage:
    python -m tools.cleanup --status          # Check Ollama status
    python -m tools.cleanup --stop-all        # Stop all running models
    python -m tools.cleanup --stop-service    # Stop Ollama service
    python -m tools.cleanup --full            # Full cleanup + status
    python -m tools.cleanup --tips            # Show memory tips
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_command(cmd, check=True):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if check and result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"Error running command: {e}")
        return None


def check_ollama_status():
    """Check if Ollama is running and what models are loaded."""
    print("=" * 60)
    print("OLLAMA STATUS CHECK")
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
    print("\n--- Loaded Models ---")
    models_output = run_command("ollama ps 2>/dev/null", check=False)
    if models_output and "NAME" in models_output:
        print(models_output)
    else:
        print("No models currently loaded in memory")
    
    # Check available models
    print("\n--- Available Models ---")
    list_output = run_command("ollama list 2>/dev/null", check=False)
    if list_output:
        print(list_output)
    else:
        print("Could not retrieve model list")
    
    # Check system memory
    print("\n--- System Memory ---")
    mem_output = run_command("free -h", check=False)
    if mem_output:
        print(mem_output)
    
    print("=" * 60)


def stop_all_models():
    """Stop all running models by unloading them."""
    print("Stopping all running models...")
    
    # Get list of running models
    models_output = run_command("ollama ps 2>/dev/null", check=False)
    if not models_output or "NAME" not in models_output:
        print("No models are currently running")
        return
    
    # Parse running models (skip header)
    lines = models_output.strip().split('\n')[1:]
    for line in lines:
        if line.strip():
            model_name = line.split()[0]
            print(f"  Unloading {model_name}...")
            # Generate with keep_alive=0 to unload
            run_command(f'ollama run {model_name} "" --keepalive 0 2>/dev/null', check=False)
            time.sleep(1)
    
    print("✓ All models stopped")


def stop_ollama_service():
    """Stop the Ollama service completely."""
    print("Stopping Ollama service...")
    
    # Try different methods to stop Ollama
    methods = [
        ("systemctl stop ollama", "Systemd service"),
        ("pkill -f 'ollama serve'", "Process kill"),
        ("killall ollama", "Killall"),
    ]
    
    for cmd, method_name in methods:
        print(f"  Trying {method_name}...")
        result = run_command(cmd, check=False)
        time.sleep(2)
        
        # Check if stopped
        check = run_command("ps aux | grep 'ollama serve' | grep -v grep", check=False)
        if not check:
            print(f"✓ Ollama service stopped using {method_name}")
            return True
    
    print("✗ Could not stop Ollama service automatically")
    print("\nManual steps to stop Ollama:")
    print("  1. Find PID: ps aux | grep ollama")
    print("  2. Kill: sudo kill -9 <PID>")
    return False


def show_memory_tips():
    """Show memory management tips."""
    print("=" * 60)
    print("MEMORY MANAGEMENT TIPS")
    print("=" * 60)
    
    print("\n1. AFTER TRANSLATION - Free GPU Memory:")
    print("   python -m tools.cleanup --stop-all")
    
    print("\n2. COMPLETELY STOP OLLAMA:")
    print("   python -m tools.cleanup --stop-service")
    
    print("\n3. CHECK MEMORY USAGE:")
    print("   python -m tools.cleanup --status")
    
    print("\n4. DURING BATCH TRANSLATION:")
    print("   Use --unload-after-chapter flag to free memory between chapters")
    print("   python -m src.main --novel NAME --all --unload-after-chapter")
    
    print("\n5. MODEL SIZE COMPARISON:")
    print("   qwen2.5:14b  ~ 9GB VRAM  (Best quality)")
    print("   qwen2.5:7b   ~ 4GB VRAM  (Good quality, 2x faster)")
    print("   qwen:7b      ~ 4GB VRAM  (Fastest)")
    
    print("\n6. IF SYSTEM IS SLOW:")
    print("   - Stop Ollama service")
    print("   - Clear swap: sudo swapoff -a && sudo swapon -a")
    print("   - Check free memory: free -h")
    
    print("=" * 60)


def full_cleanup():
    """Perform full cleanup."""
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup tool for Ollama memory management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.cleanup --status           # Check current status
  python -m tools.cleanup --stop-all         # Stop running models
  python -m tools.cleanup --stop-service     # Stop Ollama service
  python -m tools.cleanup --full             # Full cleanup
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
        help='Perform full cleanup and show status'
    )
    parser.add_argument(
        '--tips',
        action='store_true',
        help='Show memory management tips'
    )
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if not any([args.status, args.stop_all, args.stop_service, args.full, args.tips]):
        parser.print_help()
        print("\n" + "=" * 60)
        print("QUICK START")
        print("=" * 60)
        print("\nTo free memory after translation:")
        print("  python -m tools.cleanup --stop-all")
        print("\nTo check current status:")
        print("  python -m tools.cleanup --status")
        return
    
    # Execute requested actions
    if args.tips:
        show_memory_tips()
    
    if args.full:
        full_cleanup()
    elif args.status:
        check_ollama_status()
    elif args.stop_all:
        stop_all_models()
    elif args.stop_service:
        stop_ollama_service()


if __name__ == '__main__':
    main()
