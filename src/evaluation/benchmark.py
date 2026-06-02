#!/usr/bin/env python3
"""
Benchmark: Compare model output vs human reference translation.
Uses existing translation_reviewer checks + semantic similarity.
"""

import re
import sys
import json
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import Optional, List

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.translation_reviewer import review_translation  # noqa: E402
from src.utils.file_handler import FileHandler  # noqa: E402

DATASET_DIR = project_root.parent.parent / "DownloadNovel" / "CreateNovelDataSet"
OUTPUT_DIR = project_root / "data" / "output"

NOVEL_MAP = {
    "outside-of-time": "outside-of-time",
    "a-will-eternal": "a-will-eternal",
    "eternal-sacred-king": "eternal-sacred-king",
    "renegade-immortal": "renegade-immortal",
    "daoist-master-of-qing-xuan": "daoist-master-of-qing-xuan",
    "we-agreed-on-experiencing": "we-agreed-on-experiencing-life-so-why-did-you-immortals-become-real",
}

HUMAN_FILE_PATTERNS = {
    "outside-of-time": "{novel}_myanmar_chapter_{ch:04d}.md",
    "a-will-eternal": "{novel}_chapter_{ch:04d}.md",
    "default": "{novel}_chapter_{ch:04d}.md",
}

# Per-novel MM file naming patterns for glossary miner
MM_FILE_PATTERNS = {
    "outside-of-time": lambda n, ch: f"{n}_myanmar_chapter_{ch:04d}.md",
    "a-will-eternal": lambda n, ch: f"{n}_chapter_{ch:04d}.md",
    "we-agreed-on-experiencing-life-so-why-did-you-immortals-become-real": lambda n, ch: None,
    "default": lambda n, ch: f"{n}_chapter_{ch:04d}.md",
}


@lru_cache(maxsize=1)
def _get_embedding_model():
    """Lazy-load sentence-transformers model (cached singleton)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2')


def find_human_reference(novel: str, chapter: int) -> Optional[Path]:
    dataset_novel = NOVEL_MAP.get(novel, novel)
    mm_dir = DATASET_DIR / dataset_novel / "mm"
    if not mm_dir.exists():
        return None

    pattern = HUMAN_FILE_PATTERNS.get(novel, HUMAN_FILE_PATTERNS["default"])
    fname = pattern.format(novel=novel, ch=chapter)
    fpath = mm_dir / fname
    if fpath.exists():
        return fpath

    for f in mm_dir.iterdir():
        if f.suffix in (".md", ".txt"):
            nums = re.findall(r'(\d+)', f.stem)
            if nums and int(nums[-1]) == chapter:
                return f

    return None


def find_model_output(novel: str, chapter: int) -> Optional[Path]:
    novel_dir = OUTPUT_DIR / novel
    if not novel_dir.exists():
        return None

    pattern = f"{novel}_chapter_{chapter:04d}.mm.md"
    fpath = novel_dir / pattern
    if fpath.exists():
        return fpath

    for f in novel_dir.iterdir():
        if f.suffix == ".md" and not f.name.endswith(".human.md"):
            nums = re.findall(r'(\d+)', f.stem)
            if nums and int(nums[-1]) == chapter:
                return f

    return None


def compute_semantic_similarity(text_a: str, text_b: str) -> dict:
    """Compute semantic similarity using sentence-transformers (model cached)."""
    try:
        import numpy as np
        model = _get_embedding_model()

        emb_a = model.encode(text_a, normalize_embeddings=True)
        emb_b = model.encode(text_b, normalize_embeddings=True)
        cosine = float(np.dot(emb_a, emb_b))

        paras_a = [p.strip() for p in text_a.split('\n\n') if p.strip() and not p.strip().startswith('#')]
        paras_b = [p.strip() for p in text_b.split('\n\n') if p.strip() and not p.strip().startswith('#')]

        if not paras_a or not paras_b:
            return {"cosine_similarity": cosine, "paragraph_similarity": None}

        emb_paras_a = model.encode(paras_a, normalize_embeddings=True)
        emb_paras_b = model.encode(paras_b, normalize_embeddings=True)
        sim_matrix = np.dot(emb_paras_a, emb_paras_b.T)
        best_matches = sim_matrix.max(axis=1)
        paragraph_sim = float(best_matches.mean())
        coverage = float((best_matches > 0.70).mean())

        return {
            "cosine_similarity": round(cosine, 4),
            "paragraph_similarity": round(paragraph_sim, 4),
            "paragraph_coverage": round(coverage, 4),
            "model_paragraphs": len(paras_a),
            "human_paragraphs": len(paras_b),
        }
    except ImportError:
        return {"cosine_similarity": None, "paragraph_similarity": None, "error": "sentence-transformers not available"}
    except Exception as e:
        return {"cosine_similarity": None, "paragraph_similarity": None, "error": str(e)}


def analyze_archaic(text: str) -> dict:
    """Count archaic words in text."""
    return {
        "ဤ": text.count('\u1024'),
        "ထို": text.count('\u1011\u102d\u102f'),
        "သင်သည်": text.count('\u101e\u1004\u103a\u101e\u100a\u103a'),
    }


def compute_myanmar_ratio(text: str) -> float:
    MYANMAR_RANGES = [(0x1000, 0x109F), (0xAA60, 0xAA7F), (0xA9E0, 0xA9FF)]
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return 0.0
    mm_count = sum(1 for c in non_ws if any(lo <= ord(c) <= hi for lo, hi in MYANMAR_RANGES))
    return round(mm_count / len(non_ws), 4)


def run_benchmark(novel: str, chapter: int) -> dict:
    """Run full benchmark for one chapter."""
    model_path = find_model_output(novel, chapter)
    human_path = find_human_reference(novel, chapter)

    result = {
        "novel": novel,
        "chapter": chapter,
        "model_path": str(model_path) if model_path else None,
        "human_path": str(human_path) if human_path else None,
        "model_quality": None,
        "human_quality": None,
        "semantic": None,
        "gap_analysis": {},
    }

    if not model_path:
        result["error"] = "Model output not found"
        return result
    if not human_path:
        result["error"] = "Human reference not found"
        return result

    model_text = model_path.read_text(encoding='utf-8-sig')
    human_text = human_path.read_text(encoding='utf-8-sig')

    try:
        model_report = review_translation(str(model_path), chapter=chapter, novel=novel)
        human_report = review_translation(str(human_path), chapter=chapter, novel=novel)
        result["model_quality"] = {
            "total_score": model_report.total_score,
            "critical_count": len(model_report.critical_fixes),
            "warning_count": len(model_report.warnings),
            "checks": {c.name: {"passed": c.passed, "details": c.details} for c in model_report.checks},
        }
        result["human_quality"] = {
            "total_score": human_report.total_score,
            "critical_count": len(human_report.critical_fixes),
            "warning_count": len(human_report.warnings),
            "checks": {c.name: {"passed": c.passed, "details": c.details} for c in human_report.checks},
        }
    except Exception as e:
        result["reviewer_error"] = str(e)

    result["gap_analysis"]["archaic"] = {
        "model": analyze_archaic(model_text),
        "human": analyze_archaic(human_text),
    }

    result["gap_analysis"]["myanmar_ratio"] = {
        "model": compute_myanmar_ratio(model_text),
        "human": compute_myanmar_ratio(human_text),
    }

    result["gap_analysis"]["length"] = {
        "model_chars": len(model_text),
        "human_chars": len(human_text),
        "model_paragraphs": len([p for p in model_text.split('\n\n') if p.strip()]),
        "human_paragraphs": len([p for p in human_text.split('\n\n') if p.strip()]),
        "ratio": round(len(model_text) / max(len(human_text), 1), 4),
    }

    try:
        result["semantic"] = compute_semantic_similarity(model_text, human_text)
    except Exception as e:
        result["semantic"] = {"error": str(e)}

    return result


def print_benchmark(results: List[dict], fmt: str = "table"):
    """Print benchmark results."""
    if fmt == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for r in results:
        print(f"\n{'='*70}")
        print(f"  BENCHMARK: {r['novel']} chapter {r['chapter']}")
        print(f"{'='*70}")

        if "error" in r:
            print(f"  ❌ {r['error']}")
            continue

        mq = r.get("model_quality") or {}
        hq = r.get("human_quality") or {}
        s = r.get("semantic") or {}
        gap = r.get("gap_analysis") or {}

        print("\n  📊 QUALITY SCORES")
        print(f"  {'Metric':<35} {'Model':>8} {'Human':>8} {'Diff':>8}")
        print(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*8}")

        model_score = mq.get("total_score", "N/A")
        human_score = hq.get("total_score", "N/A")
        diff = ""
        if isinstance(model_score, int) and isinstance(human_score, int):
            diff = f"{model_score - human_score:+d}"
        print(f"  {'Overall Score':<35} {str(model_score):>8} {str(human_score):>8} {diff:>8}")

        print(f"  {'Critical Issues':<35} {str(mq.get('critical_count', 'N/A')):>8} {str(hq.get('critical_count', 'N/A')):>8}")
        print(f"  {'Warnings':<35} {str(mq.get('warning_count', 'N/A')):>8} {str(hq.get('warning_count', 'N/A')):>8}")

        print("\n  🔤 ARCHAIC WORDS")
        arch = gap.get("archaic", {})
        m_arch = arch.get("model", {})
        h_arch = arch.get("human", {})
        for word in ['ဤ', 'ထို', 'သင်သည်']:
            print(f"  {word:<35} {str(m_arch.get(word, 0)):>8} {str(h_arch.get(word, 0)):>8}")

        print("\n  📐 CONTENT METRICS")
        length_info = gap.get("length", {})
        print(f"  {'Chars':<35} {str(length_info.get('model_chars', 'N/A')):>8} {str(length_info.get('human_chars', 'N/A')):>8}")
        print(f"  {'Paragraphs':<35} {str(length_info.get('model_paragraphs', 'N/A')):>8} {str(length_info.get('human_paragraphs', 'N/A')):>8}")
        print(f"  {'Length ratio (model/human)':<35} {str(length_info.get('ratio', 'N/A')):>8}")

        print("\n  🧠 SEMANTIC SIMILARITY")
        print(f"  {'Cosine similarity':<35} {str(s.get('cosine_similarity', 'N/A')):>8}")
        print(f"  {'Paragraph similarity (avg)':<35} {str(s.get('paragraph_similarity', 'N/A')):>8}")
        print(f"  {'Paragraph coverage (>.70)':<35} {str(s.get('paragraph_coverage', 'N/A')):>8}")

        model_checks = mq.get("checks", {})
        human_checks = hq.get("checks", {})
        if model_checks and human_checks:
            print("\n  ✅ DETAILED CHECKS")
            for name in ["Fluency Score", "Myanmar Ratio", "H1 Count", "Archaic Words", "Latin/English Leakage"]:
                mc = model_checks.get(name, {})
                hc = human_checks.get(name, {})
                m_p = "✅" if mc.get("passed") else "❌"
                h_p = "✅" if hc.get("passed") else "❌"
                print(f"  {name:<35} {m_p} {str(mc.get('details', ''))[:40]:<40} | {h_p} {str(hc.get('details', ''))[:40]}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark model vs human translation")
    parser.add_argument("--novel", help="Novel name")
    parser.add_argument("--chapter", type=int, nargs="+", help="Chapter number(s)")
    parser.add_argument("--all-chapters", action="store_true", help="Benchmark all available model outputs")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    results = []

    if args.all_chapters:
        for novel_dir in sorted(OUTPUT_DIR.iterdir()):
            if not novel_dir.is_dir() or novel_dir.name.startswith('.'):
                continue
            novel = novel_dir.name
            for f in sorted(novel_dir.iterdir()):
                if f.suffix == ".md" and ".mm.md" in f.name and not f.name.endswith(".human.md"):
                    nums = re.findall(r'(\d+)', f.stem)
                    if nums:
                        chapter = int(nums[-1])
                        r = run_benchmark(novel, chapter)
                        results.append(r)
                        print(f"  {'✅' if 'error' not in r else '❌'} {novel} ch{chapter}")
    elif args.novel and args.chapter:
        for ch in args.chapter:
            r = run_benchmark(args.novel, ch)
            results.append(r)
    else:
        parser.print_help()
        return

    print_benchmark(results, fmt="json" if args.json else "table")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = project_root / "logs" / "report" / f"benchmark_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    FileHandler.write_json(str(out_path), results)
    print(f"\n  💾 Results saved: {out_path}")


if __name__ == "__main__":
    main()
