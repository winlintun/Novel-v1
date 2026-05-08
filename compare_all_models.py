#!/usr/bin/env python3
"""
Quick Model Comparison Script
Translate a chapter with all models and save to logs/temp/

Usage:
    python compare_all_models.py --novel sample --chapter 1
"""

import sys
import argparse
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.compare_models import compare_models


def main():
    parser = argparse.ArgumentParser(
        description="Compare all models by translating same chapter"
    )
    parser.add_argument(
        "--novel",
        default="sample",
        help="Novel name (default: sample)"
    )
    parser.add_argument(
        "--chapter",
        type=int,
        default=1,
        help="Chapter number (default: 1)"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["myanmar", "pivot", "utility"],
        default=["myanmar"],
        help="Model categories to test (default: myanmar)"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("  MODEL COMPARISON TOOL")
    print("="*60)
    print(f"Novel: {args.novel}")
    print(f"Chapter: {args.chapter}")
    print(f"Categories: {args.categories}")
    print("="*60)
    print()
    
    saved_files = compare_models(
        novel=args.novel,
        chapter=args.chapter,
        categories=args.categories
    )
    
    if saved_files:
        print("\n" + "="*60)
        print(f"✓ Generated {len(saved_files)} files:")
        for f in saved_files:
            print(f"  - {f}")
        print("="*60)
        return 0
    else:
        print("\n✗ No files generated")
        return 1


if __name__ == "__main__":
    sys.exit(main())
