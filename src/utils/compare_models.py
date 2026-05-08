#!/usr/bin/env python3
"""
Model Comparison Tool - Translate same chapter with all models
Saves results to logs/temp/ for easy comparison

Usage:
    python -m src.utils.compare_models --novel sample --chapter 1
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config.skeleton_models import get_skeleton_manager
from src.config.loader import load_config
from src.pipeline.orchestrator import TranslationPipeline


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_temp_dir() -> Path:
    """Ensure temp directory exists"""
    temp_dir = Path("logs/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def translate_with_model(
    model_key: str,
    model_config: Dict[str, Any],
    novel: str,
    chapter: int,
    input_file: Path
) -> Dict[str, Any]:
    """Translate a chapter with a specific model.
    
    Args:
        model_key: Model identifier from skeleton config
        model_config: Model configuration dict
        novel: Novel name
        chapter: Chapter number
        input_file: Path to input file
        
    Returns:
        Dict with translation result and metadata
    """
    model_name = model_config['name']
    display_name = model_config.get('display_name', model_key)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Translating with: {display_name}")
    logger.info(f"Model: {model_name}")
    logger.info(f"Params: temp={model_config.get('temperature', 0.2)}, "
                f"tokens={model_config.get('max_tokens', 4096)}")
    logger.info(f"{'='*60}\n")
    
    try:
        # Load base config
        config = load_config("config/settings.yaml")
        
        # Apply model settings from skeleton
        skeleton_mgr = get_skeleton_manager()
        config_dict = skeleton_mgr.apply_model_to_config(model_key, config.model_dump())
        
        # Create new config with model settings
        from src.config import AppConfig
        config = AppConfig(**config_dict)
        
        # Create pipeline
        pipeline = TranslationPipeline(config)
        
        # Translate
        start_time = datetime.now()
        
        # Run translation using translate_file method
        result = pipeline.translate_file(
            filepath=str(input_file),
            novel_name=novel
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Extract translation from result
        translation_text = ""
        output_file = result.get('output_file', '')
        if output_file and Path(output_file).exists():
            with open(output_file, 'r', encoding='utf-8-sig') as f:
                translation_text = f.read()
        
        return {
            'success': result.get('success', False),
            'model_key': model_key,
            'model_name': model_name,
            'display_name': display_name,
            'translation': translation_text,
            'metrics': result.get('metrics', {}),
            'duration': duration,
            'output_file': output_file,
            'error': result.get('error', None)
        }
        
    except Exception as e:
        logger.error(f"Error translating with {model_name}: {e}")
        return {
            'success': False,
            'model_key': model_key,
            'model_name': model_name,
            'display_name': display_name,
            'translation': f"[ERROR: {str(e)}]",
            'metrics': {},
            'duration': 0,
            'error': str(e)
        }


def save_translation(
    result: Dict[str, Any],
    novel: str,
    chapter: int,
    temp_dir: Path,
    model_config: Dict[str, Any] = None
) -> Path:
    """Save translation result to temp file.
    
    Args:
        result: Translation result dict
        novel: Novel name
        chapter: Chapter number
        temp_dir: Temp directory path
        model_config: Optional model configuration for parameters
        
    Returns:
        Path to saved file
    """
    # Clean model name for filename
    model_name_clean = result['model_key']
    filename = f"{model_name_clean}_ch{chapter:03d}.md"
    filepath = temp_dir / filename
    
    # Get parameters from model_config if available
    if model_config:
        temp = model_config.get('temperature', 'N/A')
        max_tokens = model_config.get('max_tokens', 'N/A')
        repeat_penalty = model_config.get('repeat_penalty', 'N/A')
        chunk_size = model_config.get('chunk_size', 'N/A')
    else:
        temp = max_tokens = repeat_penalty = chunk_size = 'N/A'
    
    # Build content
    lines = [
        f"# Translation: {result['display_name']}",
        f"",
        f"**Model:** {result['model_name']}",
        f"**Novel:** {novel}",
        f"**Chapter:** {chapter}",
        f"**Duration:** {result['duration']:.1f}s",
        f"**Status:** {'✓ Success' if result['success'] else '✗ Failed'}",
        f"",
        f"## Parameters",
        f"- Temperature: {temp}",
        f"- Max Tokens: {max_tokens}",
        f"- Repeat Penalty: {repeat_penalty}",
        f"- Chunk Size: {chunk_size}",
        f"",
        f"---",
        f"",
        f"## Translation",
        f"",
        result['translation'] if result['translation'] else "[No output]",
        f"",
    ]
    
    # Add metrics if available
    if result.get('metrics'):
        lines.extend([
            f"",
            f"## Metrics",
            f"",
        ])
        for key, value in result['metrics'].items():
            lines.append(f"- {key}: {value}")
    
    # Add error if failed
    if result.get('error'):
        lines.extend([
            f"",
            f"## Error",
            f"```",
            f"{result['error']}",
            f"```",
        ])
    
    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return filepath


def compare_models(
    novel: str,
    chapter: int,
    models_filter: List[str] = None,
    categories: List[str] = None
) -> List[Path]:
    """Translate chapter with all models and save results.
    
    Args:
        novel: Novel name
        chapter: Chapter number
        models_filter: Optional list of specific model keys to use
        categories: Optional list of categories to include (myanmar, pivot, utility)
        
    Returns:
        List of saved file paths
    """
    # Find input file
    input_file = Path(f"data/input/{novel}/{novel}_chapter_{chapter:03d}.md")
    if not input_file.exists():
        # Try alternative naming
        input_file = Path(f"data/input/{novel}/chapter_{chapter:03d}.md")
        if not input_file.exists():
            input_file = Path(f"data/input/{novel}/{chapter:03d}.md")
    
    if not input_file.exists():
        logger.error(f"Input file not found for {novel} chapter {chapter}")
        logger.error(f"Tried: data/input/{novel}/{novel}_chapter_{chapter:03d}.md")
        return []
    
    logger.info(f"Input file: {input_file}")
    
    # Get all models
    skeleton_mgr = get_skeleton_manager()
    all_models = skeleton_mgr.get_all_models()
    
    # Filter models if specified
    if models_filter:
        models_to_test = {k: v for k, v in all_models.items() if k in models_filter}
    elif categories:
        models_to_test = {
            k: v for k, v in all_models.items() 
            if v.get('category') in categories
        }
    else:
        # Default: only Myanmar translation models (not pivot/utility)
        models_to_test = {
            k: v for k, v in all_models.items() 
            if v.get('category') == 'myanmar'
        }
    
    if not models_to_test:
        logger.error("No models to test!")
        return []
    
    logger.info(f"Will translate with {len(models_to_test)} models:")
    for key, config in models_to_test.items():
        logger.info(f"  - {key}: {config.get('display_name', key)}")
    
    # Ensure temp directory
    temp_dir = ensure_temp_dir()
    logger.info(f"\nResults will be saved to: {temp_dir}")
    
    # Translate with each model
    saved_files = []
    results = []
    
    for model_key, model_config in models_to_test.items():
        # Translate
        result = translate_with_model(
            model_key=model_key,
            model_config=model_config,
            novel=novel,
            chapter=chapter,
            input_file=input_file
        )
        results.append(result)
        
        # Save result
        filepath = save_translation(result, novel, chapter, temp_dir, model_config)
        saved_files.append(filepath)
        
        status = "✓" if result['success'] else "✗"
        logger.info(f"{status} Saved: {filepath.name}")
    
    # Create comparison summary
    create_comparison_summary(results, novel, chapter, temp_dir)
    
    return saved_files


def create_comparison_summary(
    results: List[Dict[str, Any]],
    novel: str,
    chapter: int,
    temp_dir: Path
):
    """Create a summary file comparing all translations.
    
    Args:
        results: List of translation results
        novel: Novel name
        chapter: Chapter number
        temp_dir: Temp directory path
    """
    summary_file = temp_dir / f"_comparison_summary_ch{chapter:03d}.md"
    
    lines = [
        f"# Model Comparison Summary",
        f"",
        f"**Novel:** {novel}",
        f"**Chapter:** {chapter}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Results Overview",
        f"",
        f"| Model | Status | Duration | Output Size |",
        f"|-------|--------|----------|-------------|",
    ]
    
    for r in results:
        status = "✓" if r['success'] else "✗"
        size = len(r['translation']) if r['translation'] else 0
        lines.append(
            f"| {r['display_name']} | {status} | {r['duration']:.1f}s | {size} chars |"
        )
    
    lines.extend([
        f"",
        f"## Files Generated",
        f"",
    ])
    
    for r in results:
        model_name_clean = r['model_name'].replace(':', '_').replace('/', '_')
        filename = f"{model_name_clean}_ch{chapter:03d}.md"
        lines.append(f"- [{filename}]({filename})")
    
    lines.extend([
        f"",
        f"## Quick Comparison",
        f"",
        f"First 500 characters of each translation:",
        f"",
    ])
    
    for r in results:
        preview = r['translation'][:500] if r['translation'] else "[No output]"
        lines.extend([
            f"### {r['display_name']}",
            f"```",
            f"{preview}",
            f"```",
            f"",
        ])
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    logger.info(f"\n✓ Comparison summary saved: {summary_file}")


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Translate a chapter with multiple models for comparison"
    )
    parser.add_argument(
        "--novel", 
        required=True,
        help="Novel name (e.g., sample, wayfarer)"
    )
    parser.add_argument(
        "--chapter", 
        type=int,
        required=True,
        help="Chapter number"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Specific model keys to test (default: all myanmar models)"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["myanmar", "pivot", "utility"],
        help="Model categories to include"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test ALL models including pivot and utility"
    )
    
    args = parser.parse_args()
    
    # Determine which models to test
    categories = None
    if args.all:
        categories = ["myanmar", "pivot", "utility"]
    elif args.categories:
        categories = args.categories
    
    # Run comparison
    saved_files = compare_models(
        novel=args.novel,
        chapter=args.chapter,
        models_filter=args.models,
        categories=categories
    )
    
    if saved_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Comparison complete! Generated {len(saved_files)} files.")
        logger.info(f"Location: logs/temp/")
        logger.info(f"{'='*60}")
    else:
        logger.error("No files generated. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
