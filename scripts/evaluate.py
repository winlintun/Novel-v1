#!/usr/bin/env python3
"""
Canonical test evaluator — runs all test paragraphs through a model
and scores the output against human reference translations.

Usage:
    python scripts/evaluate.py --model padauk-gemma:q8_0
    python scripts/evaluate.py --model padauk-gemma:q8_0 --test-set tests/canonical/test_paragraphs.json
    python scripts/evaluate.py --list-models          # show all models in registry
    python scripts/evaluate.py --compare              # compare all models
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_TEST_SET = Path("tests/canonical/test_paragraphs.json")
REGISTRY_PATH = Path("data/evaluation/model_registry.json")

MYANMAR_RANGES = [(0x1000, 0x109F), (0xAA60, 0xAA7F), (0xA9E0, 0xA9FF)]


def calc_myanmar_ratio(text: str) -> float:
    if not text:
        return 0.0
    mm = sum(1 for ch in text if not ch.isspace() and any(lo <= ord(ch) <= hi for lo, hi in MYANMAR_RANGES))
    total = sum(1 for ch in text if not ch.isspace())
    return mm / total if total > 0 else 0.0


def calc_fluency(text: str) -> float:
    """Heuristic fluency score based on Myanmar sentence ender density."""
    if not text:
        return 0.0
    sentence_enders = text.count("။") + text.count("?") + text.count("!")
    words = text.split()
    if len(words) < 3:
        return 50.0
    # Expect ~1 ender per 8-15 words
    ender_ratio = sentence_enders / max(len(words), 1)
    if 0.05 <= ender_ratio <= 0.20:
        return 90.0
    elif 0.03 <= ender_ratio <= 0.30:
        return 70.0
    else:
        return 50.0


def score_translation(output: str, reference: str) -> Dict[str, Any]:
    """Score a single translation against reference."""
    mm_ratio = calc_myanmar_ratio(output)
    fluency = calc_fluency(output)

    # Sequence similarity with reference
    similarity = SequenceMatcher(None, output.strip(), reference.strip()).ratio()

    # Composite score: weighted average
    # Note: SequenceMatcher similarity penalizes valid Myanmar word-order variation
    # (Myanmar allows flexible SOV word order). Reduced from 45% to 30% weight to
    # compensate. Consider BLEU/chrF for more robust scoring in the future.
    score = (
        min(mm_ratio * 100, 100) * 0.45 +
        fluency * 0.25 +
        similarity * 100 * 0.30
    )

    return {
        "myanmar_ratio": round(mm_ratio, 3),
        "fluency": round(fluency, 1),
        "similarity": round(similarity, 3),
        "composite_score": round(score, 1),
    }


def load_test_set(path: Path) -> List[Dict[str, Any]]:
    """Load canonical test paragraphs."""
    if not path.exists():
        logger.error(f"Test set not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def translate_paragraph(model: str, text: str, timeout: int = 120) -> Optional[str]:
    """Translate a single paragraph using Ollama."""
    try:
        import ollama
        response = ollama.chat(
            model=model,
            messages=[{
                "role": "user",
                "content": f"Translate the following text to literary Myanmar:\n\n{text}"
            }],
            options={"temperature": 0.2, "num_predict": 1024, "timeout": timeout},
        )
        return response["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return None


def evaluate_model(
    model: str,
    test_set: List[Dict[str, Any]],
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run all test paragraphs through the model and score results."""
    results = []
    total_score = 0.0
    total_mm_ratio = 0.0
    total_fluency = 0.0
    passed = 0
    failed = 0

    for i, case in enumerate(test_set, 1):
        case_id = case.get("id", f"case_{i}")
        source = case["source_text"]
        reference = case.get("reference_mm", "")
        difficulty = case.get("difficulty", "unknown")

        if verbose:
            print(f"\n[{i}/{len(test_set)}] {case_id} ({difficulty})...", end=" ", flush=True)

        output = translate_paragraph(model, source)
        if output is None:
            if verbose:
                print("FAILED")
            failed += 1
            continue

        scores = score_translation(output, reference)
        scores["id"] = case_id
        scores["difficulty"] = difficulty
        scores["output"] = output[:200]
        results.append(scores)

        total_score += scores["composite_score"]
        total_mm_ratio += scores["myanmar_ratio"]
        total_fluency += scores["fluency"]

        if scores["composite_score"] >= 70:
            passed += 1
        else:
            failed += 1

        if verbose:
            print(f"score={scores['composite_score']:.1f}")

    n = len(results)
    return {
        "model": model,
        "total_cases": len(test_set),
        "translated": n,
        "passed": passed,
        "failed": failed,
        "avg_composite_score": round(total_score / n, 1) if n > 0 else 0,
        "avg_myanmar_ratio": round(total_mm_ratio / n, 3) if n > 0 else 0,
        "avg_fluency": round(total_fluency / n, 1) if n > 0 else 0,
        "results": results,
    }


def save_evaluation(result: Dict[str, Any]):
    """Save evaluation result to model registry."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry = {}
    if REGISTRY_PATH.exists():
        try:
            registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "entry_type": "canonical",
        "model": result["model"],
        "avg_composite_score": result["avg_composite_score"],
        "avg_myanmar_ratio": result["avg_myanmar_ratio"],
        "avg_fluency": result["avg_fluency"],
        "total_cases": result["total_cases"],
        "passed": result["passed"],
        "failed": result["failed"],
    }
    registry.setdefault("models_tested", []).append(entry)
    registry["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Evaluation saved to {REGISTRY_PATH}")


def list_models():
    """Show all models with recorded eval runs."""
    if not REGISTRY_PATH.exists():
        print("No eval results yet. Run: python scripts/evaluate.py --model <name>")
        return
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("Corrupted registry file.")
        return

    runs = [e for e in registry.get("models_tested", []) if e.get("entry_type") == "canonical"]
    if not runs:
        print("No canonical eval runs recorded.")
        return

    by_model: Dict[str, List[float]] = {}
    for r in runs:
        by_model.setdefault(r["model"], []).append(r["avg_composite_score"])

    print(f"{'Model':<30} {'Runs':>5} {'Avg Score':>10}")
    print("-" * 50)
    for model, scores in sorted(by_model.items()):
        avg = sum(scores) / len(scores)
        last = scores[-1]
        trend = "↑" if last >= avg else "↓" if len(scores) > 1 else " "
        print(f"{model:<30} {len(scores):>5} {avg:>8.1f} {trend}")


def compare_models():
    """Compare all models that have canonical eval results."""
    if not REGISTRY_PATH.exists():
        print("No eval results yet.")
        return
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("Corrupted registry file.")
        return

    runs = [e for e in registry.get("models_tested", []) if e.get("entry_type") == "canonical"]
    if not runs:
        print("No canonical eval runs recorded.")
        return

    # Group by model, take latest run per model
    latest: Dict[str, Dict] = {}
    for r in runs:
        model = r["model"]
        if model not in latest or r["timestamp"] > latest[model]["timestamp"]:
            latest[model] = r

    print(f"{'Model':<30} {'Score':>7} {'Ratio':>7} {'Fluency':>8} {'Pass':>5}")
    print("-" * 60)
    for model, r in sorted(latest.items(), key=lambda x: x[1]["avg_composite_score"], reverse=True):
        print(f"{model:<30} {r['avg_composite_score']:>7.1f} {r['avg_myanmar_ratio']:>7.1%} "
              f"{r['avg_fluency']:>8.1f} {r.get('passed', 0):>3}/{r.get('total_cases', 0)}")


def main():
    parser = argparse.ArgumentParser(description="Canonical translation evaluator")
    parser.add_argument("--model", type=str, help="Ollama model name")
    parser.add_argument("--test-set", type=str, default=str(DEFAULT_TEST_SET), help="Test set JSON path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-case results")
    parser.add_argument("--list-models", action="store_true", help="List all models with eval results")
    parser.add_argument("--compare", action="store_true", help="Compare all evaluated models")
    args = parser.parse_args()

    if args.list_models:
        list_models()
        return

    if args.compare:
        compare_models()
        return

    if not args.model:
        parser.print_help()
        sys.exit(1)

    test_set = load_test_set(Path(args.test_set))
    logger.info(f"Loaded {len(test_set)} test cases from {args.test_set}")
    logger.info(f"Evaluating model: {args.model}")
    logger.info("This will take a few minutes (one Ollama call per test case)...")

    result = evaluate_model(args.model, test_set, verbose=args.verbose)

    print(f"\n{'=' * 50}")
    print(f"Model: {result['model']}")
    print(f"{'=' * 50}")
    print(f"Cases translated:   {result['translated']}/{result['total_cases']}")
    print(f"Passed (≥70):      {result['passed']}")
    print(f"Failed (<70):      {result['failed']}")
    print(f"Avg Composite:     {result['avg_composite_score']}")
    print(f"Avg Myanmar Ratio: {result['avg_myanmar_ratio']:.1%}")
    print(f"Avg Fluency:       {result['avg_fluency']}")

    save_evaluation(result)


if __name__ == "__main__":
    main()
