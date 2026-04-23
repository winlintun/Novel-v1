#!/usr/bin/env python3
"""
Myanmar Readability Checker for translated text chunks.

This script validates that translated Burmese text meets quality standards:
- At least 70% Myanmar Unicode characters (U+1000–U+109F)
- At least one sentence-ending marker (။) per chunk
- Zero Chinese characters (U+4E00–U+9FFF) - no leakage
- No replacement characters (U+FFFD) - encoding integrity
- Output length at least 30% of input length

Usage:
    python scripts/myanmar_checker.py <translated_file> [source_file]
    python scripts/myanmar_checker.py working_data/translated_chunks/my_novel/chunk_1.txt
    python scripts/myanmar_checker.py --report working_data/readability_reports/my_novel_readability.json
"""

import os
import sys
import json
import re
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Setup logging
LOG_DIR = Path("working_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add handlers if they don't exist (prevents duplicate logs when module reloads)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / "myanmar_checker.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def load_config():
    """Load configuration from config.json."""
    try:
        config_path = Path("config/config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('myanmar_readability', {})
    except FileNotFoundError:
        logger.error("Config file not found: config/config.json")
        return {
            'enabled': True,
            'min_myanmar_ratio': 0.7,
            'flag_on_fail': True,
            'block_on_fail': False
        }
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            'enabled': True,
            'min_myanmar_ratio': 0.7,
            'flag_on_fail': True,
            'block_on_fail': False
        }


# Unicode ranges
MYANMAR_UNICODE_RANGE = (0x1000, 0x109F)  # Myanmar script
CHINESE_UNICODE_RANGE = (0x4E00, 0x9FFF)   # CJK Unified Ideographs
REPLACEMENT_CHAR = '\uFFFD'                # Unicode replacement character
MYANMAR_SENTENCE_ENDER = '။'                # Myanmar sentence-ending marker


def count_myanmar_chars(text):
    """Count Myanmar Unicode characters in text."""
    try:
        count = 0
        for char in text:
            code_point = ord(char)
            if MYANMAR_UNICODE_RANGE[0] <= code_point <= MYANMAR_UNICODE_RANGE[1]:
                count += 1
        return count
    except Exception as e:
        logger.error(f"Error counting Myanmar characters: {e}")
        return 0


def count_chinese_chars(text):
    """Count Chinese Unicode characters in text."""
    try:
        count = 0
        for char in text:
            code_point = ord(char)
            if CHINESE_UNICODE_RANGE[0] <= code_point <= CHINESE_UNICODE_RANGE[1]:
                count += 1
        return count
    except Exception as e:
        logger.error(f"Error counting Chinese characters: {e}")
        return 0


def has_replacement_chars(text):
    """Check for Unicode replacement characters (encoding errors)."""
    try:
        return REPLACEMENT_CHAR in text
    except Exception as e:
        logger.error(f"Error checking for replacement characters: {e}")
        return False


def count_sentence_enders(text):
    """Count Myanmar sentence-ending markers."""
    try:
        return text.count(MYANMAR_SENTENCE_ENDER)
    except Exception as e:
        logger.error(f"Error counting sentence enders: {e}")
        return 0


def calculate_myanmar_ratio(text):
    """Calculate the ratio of Myanmar characters to total characters."""
    try:
        if not text:
            return 0.0
        
        total_chars = len(text)
        myanmar_chars = count_myanmar_chars(text)
        
        return myanmar_chars / total_chars if total_chars > 0 else 0.0
    except Exception as e:
        logger.error(f"Error calculating Myanmar ratio: {e}")
        return 0.0


def check_readability(translated_text, source_text=None, config=None):
    """
    Check the readability of translated Burmese text.
    
    Args:
        translated_text: The translated Burmese text
        source_text: Original Chinese text (optional, for length comparison)
        config: Readability configuration dictionary
        
    Returns:
        Dictionary with check results
    """
    if config is None:
        config = load_config()
    
    try:
        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'passed': True,
            'flagged': False
        }
        
        # Check 1: Myanmar script ratio >= 70%
        myanmar_ratio = calculate_myanmar_ratio(translated_text)
        min_ratio = config.get('min_myanmar_ratio', 0.7)
        myanmar_check_pass = myanmar_ratio >= min_ratio
        
        results['checks']['myanmar_ratio'] = {
            'value': round(myanmar_ratio, 4),
            'minimum': min_ratio,
            'passed': myanmar_check_pass,
            'myanmar_chars': count_myanmar_chars(translated_text),
            'total_chars': len(translated_text)
        }
        
        # Check 2: No Chinese characters
        chinese_count = count_chinese_chars(translated_text)
        no_chinese_pass = chinese_count == 0
        
        results['checks']['no_chinese'] = {
            'value': chinese_count,
            'maximum': 0,
            'passed': no_chinese_pass
        }
        
        # Check 3: At least one sentence ender
        sentence_enders = count_sentence_enders(translated_text)
        sentence_check_pass = sentence_enders >= 1
        
        results['checks']['sentence_boundaries'] = {
            'value': sentence_enders,
            'minimum': 1,
            'passed': sentence_check_pass
        }
        
        # Check 4: No replacement characters
        has_replacements = has_replacement_chars(translated_text)
        encoding_check_pass = not has_replacements
        
        results['checks']['encoding_integrity'] = {
            'has_replacement_chars': has_replacements,
            'passed': encoding_check_pass
        }
        
        # Check 5: Minimum length ratio
        if source_text and len(source_text) > 0:
            length_ratio = len(translated_text) / len(source_text)
            min_length_ratio = 0.3
            length_check_pass = length_ratio >= min_length_ratio
            
            results['checks']['length_ratio'] = {
                'value': round(length_ratio, 4),
                'minimum': min_length_ratio,
                'input_chars': len(source_text),
                'output_chars': len(translated_text),
                'passed': length_check_pass
            }
        else:
            results['checks']['length_ratio'] = {
                'passed': True,  # Skip if no source text
                'skipped': True
            }
        
        # Determine overall pass/fail status
        all_checks = [
            myanmar_check_pass,
            no_chinese_pass,
            sentence_check_pass,
            encoding_check_pass
        ]
        
        if 'length_ratio' in results['checks'] and not results['checks']['length_ratio'].get('skipped'):
            all_checks.append(results['checks']['length_ratio']['passed'])
        
        results['passed'] = all(all_checks)
        results['flagged'] = not results['passed']
        
        # Log results
        status = "PASS" if results['passed'] else "FLAGGED"
        logger.info(f"Readability check: {status}")
        logger.info(f"  - Myanmar ratio: {myanmar_ratio:.1%} (min: {min_ratio:.0%})")
        logger.info(f"  - Chinese chars: {chinese_count} (max: 0)")
        logger.info(f"  - Sentence enders: {sentence_enders} (min: 1)")
        logger.info(f"  - Encoding errors: {has_replacements}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error during readability check: {e}")
        return {
            'passed': False,
            'flagged': True,
            'error': str(e)
        }


def save_readability_report(novel_name, chunk_results):
    """Save a consolidated readability report for a novel."""
    try:
        report_dir = Path("working_data/readability_reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = report_dir / f"{novel_name}_readability.json"
        
        # Load existing report if present
        existing_report = {}
        if report_path.exists():
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    existing_report = json.load(f)
            except Exception as e:
                logger.error(f"Error loading existing report: {e}")
        
        # Update with new results
        if 'chunks' not in existing_report:
            existing_report['chunks'] = {}
        
        for chunk_id, result in chunk_results.items():
            existing_report['chunks'][chunk_id] = result
        
        # Calculate summary statistics
        total_chunks = len(existing_report['chunks'])
        passed_chunks = sum(1 for r in existing_report['chunks'].values() if r.get('passed', False))
        flagged_chunks = total_chunks - passed_chunks
        
        existing_report['summary'] = {
            'total_chunks': total_chunks,
            'passed': passed_chunks,
            'flagged': flagged_chunks,
            'pass_rate': round(passed_chunks / total_chunks, 4) if total_chunks > 0 else 0,
            'updated_at': datetime.now().isoformat()
        }
        
        # Save report
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(existing_report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved readability report: {report_path}")
        return str(report_path)
        
    except Exception as e:
        logger.error(f"Error saving readability report: {e}")
        return None


def print_report_summary(report_path):
    """Print a human-readable summary of a readability report."""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        summary = report.get('summary', {})
        novel_name = Path(report_path).stem.replace('_readability', '')
        
        print(f"\n{'='*60}")
        print(f"Readability Report — {novel_name}")
        print(f"{'='*60}")
        print(f"Total chunks :  {summary.get('total_chunks', 0)}")
        print(f"Passed       :  {summary.get('passed', 0)}  ({summary.get('pass_rate', 0)*100:.1f}%)")
        print(f"Flagged      :  {summary.get('flagged', 0)}  ({(1-summary.get('pass_rate', 0))*100:.1f}%)")
        
        # Find flagged chunks
        flagged = []
        for chunk_id, result in report.get('chunks', {}).items():
            if result.get('flagged', False):
                flagged.append(chunk_id)
        
        if flagged:
            print(f"\nFlagged chunks: {', '.join(flagged)}")
            print(f"→ Review files in working_data/translated_chunks/")
        
        print(f"{'='*60}\n")
        
    except FileNotFoundError:
        print(f"Report file not found: {report_path}")
    except Exception as e:
        logger.error(f"Error printing report summary: {e}")


def check_file(translated_file, source_file=None):
    """
    Check a single translated file for Myanmar readability.
    
    Args:
        translated_file: Path to translated Burmese text file
        source_file: Optional path to source Chinese text file
        
    Returns:
        Dictionary with check results
    """
    try:
        translated_path = Path(translated_file)
        
        if not translated_path.exists():
            raise FileNotFoundError(f"Translated file not found: {translated_path}")
        
        # Read translated text
        try:
            with open(translated_path, 'r', encoding='utf-8') as f:
                translated_text = f.read()
        except Exception as e:
            logger.error(f"Error reading translated file: {e}")
            raise
        
        # Read source text if provided
        source_text = None
        if source_file:
            source_path = Path(source_file)
            if source_path.exists():
                try:
                    with open(source_path, 'r', encoding='utf-8') as f:
                        source_text = f.read()
                except Exception as e:
                    logger.warning(f"Could not read source file: {e}")
        
        # Run checks
        config = load_config()
        results = check_readability(translated_text, source_text, config)
        
        # Extract chunk identifier
        chunk_id = translated_path.stem
        novel_name = chunk_id.rsplit('_chunk_', 1)[0] if '_chunk_' in chunk_id else 'unknown'
        
        # Save to report
        save_readability_report(novel_name, {chunk_id: results})
        
        return results
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error checking file: {e}")
        raise


def main():
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        description='Check Myanmar readability of translated text'
    )
    parser.add_argument('translated_file', nargs='?', help='Path to translated Burmese file')
    parser.add_argument('source_file', nargs='?', help='Optional path to source Chinese file')
    parser.add_argument('--report', help='Print summary of existing report file')
    
    args = parser.parse_args()
    
    # Handle report viewing mode
    if args.report:
        print_report_summary(args.report)
        return
    
    # Handle file checking mode
    if not args.translated_file:
        parser.print_help()
        sys.exit(1)
    
    try:
        results = check_file(args.translated_file, args.source_file)
        
        status = "PASS" if results['passed'] else "FLAGGED"
        print(f"[CHECKER] {args.translated_file} → {status}")
        
        if results['flagged']:
            # Print details of failed checks
            for check_name, check_data in results['checks'].items():
                if not check_data.get('passed', True):
                    print(f"  → Failed: {check_name}")
        
        sys.exit(0 if results['passed'] else 1)
        
    except Exception as e:
        print(f"✗ Readability check failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
