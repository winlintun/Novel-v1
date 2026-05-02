#!/usr/bin/env python3
"""
Translation Quality Reviewer — Post-translation quality analysis module.

Reads a translated .mm.md output file and its associated log file,
then runs all quality checks defined in working_data/translation_rules.md.
Generates a structured report in logs/report/ for AI agent consumption.
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Unicode Ranges ────────────────────────────────────────────────
MYANMAR_RANGES = [
    (0x1000, 0x109F),
    (0xAA60, 0xAA7F),
    (0xA9E0, 0xA9FF),
]
CHINESE_RANGES = [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)]
BENGALI_RANGES = [(0x0980, 0x09FF)]
THAI_RANGES = [(0x0E00, 0x0E7F)]
KOREAN_RANGES = [(0xAC00, 0xD7FF)]


def _in_ranges(code: int, ranges: List[Tuple[int, int]]) -> bool:
    return any(lo <= code <= hi for lo, hi in ranges)


# ── Data Classes ──────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    score_deduction: int = 0
    details: str = ""
    severity: str = "INFO"  # CRITICAL / WARNING / INFO


@dataclass
class ReviewReport:
    output_file: str
    novel: str
    chapter: int
    pipeline_mode: str
    model: str
    duration_seconds: float
    total_score: int = 100
    checks: List[CheckResult] = field(default_factory=list)
    critical_fixes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)
    todo_items: List[str] = field(default_factory=list)

    def add_check(self, result: CheckResult) -> None:
        self.checks.append(result)
        if not result.passed:
            self.total_score = max(0, self.total_score - result.score_deduction)
            if result.severity == "CRITICAL":
                self.critical_fixes.append(result.details)
            else:
                self.warnings.append(result.details)
        else:
            self.passed_checks.append(f"{result.name}: {result.details}")


# ── Quantitative Checks ───────────────────────────────────────────

def _check_myanmar_ratio(text: str) -> CheckResult:
    """Q1: Myanmar character ratio check."""
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return CheckResult("Myanmar Ratio", False, 50, "Empty text", "CRITICAL")
    mm_count = sum(1 for c in non_ws if _in_ranges(ord(c), MYANMAR_RANGES))
    ratio = mm_count / len(non_ws)

    if ratio >= 0.70:
        return CheckResult("Myanmar Ratio", True, 0, f"{ratio:.1%} — PASS")
    elif ratio >= 0.30:
        return CheckResult("Myanmar Ratio", False, 15, f"{ratio:.1%} — below 70% threshold", "WARNING")
    else:
        return CheckResult("Myanmar Ratio", False, 30, f"{ratio:.1%} — critically low", "CRITICAL")


def _check_foreign_scripts(text: str) -> List[CheckResult]:
    """Q2: Foreign script leakage check."""
    results = []
    non_ws = [c for c in text if not c.isspace()]

    for script_name, ranges, penalty in [
        ("Chinese Leakage", CHINESE_RANGES, 5),
        ("Bengali Leakage", BENGALI_RANGES, 5),
        ("Thai Leakage", THAI_RANGES, 5),
        ("Korean Leakage", KOREAN_RANGES, 5),
    ]:
        count = sum(1 for c in non_ws if _in_ranges(ord(c), ranges))
        if count == 0:
            results.append(CheckResult(script_name, True, 0, "No leakage"))
        else:
            results.append(CheckResult(script_name, False, penalty,
                                       f"{count} characters found", "CRITICAL"))
    return results


def _check_latin_leakage(text: str) -> CheckResult:
    """Q3: English/Latin word leakage check."""
    latin_words = re.findall(r"[a-zA-Z]{3,}", text)
    common_english = re.findall(
        r'\b(the|and|for|are|but|not|you|all|can|had|her|was|one|our|out|day|get|has|him|his|how|its|may|new|now|old|see|two|who|boy|did|she|use|way|many|oil|sit|set|run|eat|far|sea|eye|ago|off|too|any|say|man|try|ask|end|why|let|put|tell|very|when|much|would|there|their|what|said|each|which|will|about|could|other|after|first|never|these|think|where|being|every|great|might|shall|still|those|while|this|that|with|from|they|have|were|been|time|than|them|into|just|like|over|also|back|only|know|take|year|good|some|come|make|well|look|down|most|long|find|here|both|made|part|even|more|such|work|life|right)\b',
        text, re.IGNORECASE)

    total_words = len(latin_words) + len(common_english)

    if total_words <= 5:
        return CheckResult("Latin/English Leakage", True, 0, f"{total_words} words — acceptable")
    elif total_words <= 20:
        return CheckResult("Latin/English Leakage", False, 5,
                           f"{total_words} words (Latin:{len(latin_words)}, Common:{len(common_english)})", "WARNING")
    else:
        return CheckResult("Latin/English Leakage", False, 15,
                           f"{total_words} words — excessive English", "CRITICAL")


def _check_markdown_structure(text: str, expected_chapter: Optional[int] = None) -> List[CheckResult]:
    """Q4: Markdown structure check."""
    results = []
    lines = text.split('\n')
    h1_count = sum(1 for line in lines if re.match(r'^#\s+အခန်း\s+', line.strip()))
    _ = sum(1 for line in lines if re.match(r'^##\s+', line.strip()))

    if h1_count == 1:
        results.append(CheckResult("H1 Count", True, 0, f"{h1_count} heading"))
    elif h1_count == 0:
        results.append(CheckResult("H1 Count", False, 10, "No chapter heading found", "CRITICAL"))
    else:
        results.append(CheckResult("H1 Count", False, 10,
                                   f"{h1_count} headings (duplicates)", "CRITICAL"))

    # Bold balance
    bold_markers = text.count('**')
    if bold_markers % 2 == 0:
        results.append(CheckResult("Bold Balance", True, 0, "Even ** count"))
    else:
        results.append(CheckResult("Bold Balance", False, 3,
                                   f"Odd ** count ({bold_markers}) — unmatched pair", "WARNING"))

    # Chapter title format
    chapter_heading = next((line.strip() for line in lines if re.match(r'^#\s+အခန်း\s+', line.strip())), "")
    if chapter_heading and ':' not in chapter_heading:
        results.append(CheckResult("Chapter Title Format", True, 0, "Proper format"))
    elif chapter_heading:
        results.append(CheckResult("Chapter Title Format", False, 2,
                                   "Title has ':' — should be H1 on its own line", "WARNING"))

    return results


def _check_content_completeness(text: str) -> CheckResult:
    """Q5: Content completeness check."""
    if len(text) < 100:
        return CheckResult("Content Completeness", False, 30,
                           f"Only {len(text)} chars — too short", "CRITICAL")
    error_markers = text.count('[TRANSLATION ERROR]')
    placeholders = text.count('【?term?】')
    issues = []
    if error_markers:
        issues.append(f"{error_markers} error markers")
    if placeholders > 3:
        issues.append(f"{placeholders} placeholders")
    if issues:
        return CheckResult("Content Completeness", False, len(issues) * 5,
                           "; ".join(issues), "WARNING")
    return CheckResult("Content Completeness", True, 0,
                       f"{len(text)} chars, no errors")


def _check_paragraph_structure(text: str) -> CheckResult:
    """Q6: Paragraph structure check."""
    lines = text.split('\n')
    content_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
    para_breaks = text.count('\n\n')

    if para_breaks == 0:
        return CheckResult("Paragraph Structure", False, 10,
                           "No paragraph breaks — text is one block", "CRITICAL")
    ratio = para_breaks / max(len(content_lines), 1)
    if ratio >= 0.3:
        return CheckResult("Paragraph Structure", True, 0,
                           f"{para_breaks} breaks, {len(content_lines)} content lines")
    elif para_breaks >= 2:
        return CheckResult("Paragraph Structure", False, 5,
                           f"Only {para_breaks} breaks for {len(content_lines)} lines", "WARNING")
    else:
        return CheckResult("Paragraph Structure", False, 5,
                           f"Only {para_breaks} breaks — hard to read", "WARNING")


# ── Linguistic Checks ─────────────────────────────────────────────

def _check_archaic_words(text: str) -> CheckResult:
    """L1: Archaic word detection."""
    archaic = [
        '\u101e\u1004\u103a\u101e\u100a\u103a',              # သင်သည်
        '\u1024',                                             # ဤ
        '\u1011\u102d\u102f',                                 # ထို
        '\u101e\u100a\u103a\u101e\u100a\u103a\u1000\u102d\u102f',  # သည်သည်ကို
    ]
    found = []
    for word in archaic:
        count = text.count(word)
        if count:
            found.append(f"{word}({count})")
    if not found:
        return CheckResult("Archaic Words", True, 0, "No archaic words")
    return CheckResult("Archaic Words", False, min(len(found) * 5, 20),
                       f"Found: {', '.join(found)} — use modern alternatives", "WARNING")


def _check_particle_repetition(text: str) -> CheckResult:
    """L2: Particle repetition (hallucination sentinel).
    
    Detects the SAME particle appearing 3+ times consecutively.
    Uses backreference to enforce same-particle rule per translation_rules.md L2.
    """
    pattern = re.compile(r'(သည်)\1{2,}|(ကို)\2{2,}|(မှာ)\3{2,}|(အတွက်)\4{2,}|(ဖြင့်)\5{2,}|(၍)\6{2,}')
    matches = pattern.findall(text)
    if not matches:
        return CheckResult("Particle Repetition", True, 0, "No hallucination loops")
    return CheckResult("Particle Repetition", False, 10,
                       f"{len(matches)} hallucination loop(s) detected", "CRITICAL")


def _check_register_consistency(text: str) -> CheckResult:
    """L4: Register consistency check."""
    formal = re.findall(r'(သည်|၏|သော|ဖြင့်)', text)
    colloquial = re.findall(r'(တယ်|ဘူး|မယ်|ရဲ့)', text)
    if not formal or not colloquial:
        return CheckResult("Register Consistency", True, 0, "Single register — consistent")
    # Both formal and colloquial detected = potential mixing
    ratio = min(len(formal), len(colloquial)) / max(len(formal), len(colloquial), 1)
    if ratio > 0.3:
        return CheckResult("Register Consistency", False, 10,
                           f"Mixed registers: {len(formal)} formal + {len(colloquial)} casual particles", "WARNING")
    return CheckResult("Register Consistency", True, 0, "Register appears consistent")


def _check_sentence_enders(text: str) -> CheckResult:
    """L8: Check paragraphs end with proper Myanmar enders."""
    lines = text.split('\n')
    content_lines = [line.strip() for line in lines
                     if line.strip() and not line.strip().startswith('#')
                     and not line.strip().startswith('---')]
    # Only Myanmar sentence enders: ။ ၏ ၊ and closing Myanmar quotes
    unended = 0
    for line in content_lines:
        if line and not line.endswith(('။', '၏', '၊', '"', '\u201d')):
            unended += 1
    if unended <= 3:
        return CheckResult("Sentence Enders", True, 0, f"{unended} lines without enders — acceptable")
    elif unended <= 8:
        return CheckResult("Sentence Enders", False, 5,
                           f"{unended} lines without sentence-enders — possible truncation", "WARNING")
    else:
        return CheckResult("Sentence Enders", False, 10,
                           f"{unended} lines without sentence-enders — significant truncation", "CRITICAL")


def _check_overlong_sentences(text: str) -> CheckResult:
    """L7: Check for overlong sentences (>50 words)."""
    sentences = re.split(r'[။၏၊\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    overlong = [s for s in sentences if len(s.split()) > 50]
    if not overlong:
        return CheckResult("Sentence Length", True, 0, "No overlong sentences")
    count = len(overlong)
    return CheckResult("Sentence Length", False, min(count * 3, 15),
                       f"{count} sentences > 50 words — consider splitting", "WARNING")


def _check_paragraph_duplication(text: str) -> CheckResult:
    """Check for duplicated sentences at paragraph boundaries.
    
    Detects when the same sentence appears at the end of one paragraph
    and the start of the next (chunk boundary duplication artifact).
    """
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) < 2:
        return CheckResult("Paragraph Duplication", True, 0, "Only one paragraph")

    dups = 0
    for i in range(len(paragraphs) - 1):
        prev_sentences = re.split(r'[။၏]+', paragraphs[i])
        next_sentences = re.split(r'[။၏]+', paragraphs[i + 1])
        if prev_sentences and next_sentences:
            prev_last = prev_sentences[-1].strip()
            next_first = next_sentences[0].strip()
            if prev_last and next_first and len(prev_last) > 10 and len(next_first) > 10:
                # Check similarity (same Myanmar chars, minor variation)
                prev_set = set(prev_last)
                next_set = set(next_first)
                if prev_set and next_set:
                    overlap = len(prev_set & next_set) / len(prev_set | next_set)
                    if overlap > 0.8:
                        dups += 1

    if dups == 0:
        return CheckResult("Paragraph Duplication", True, 0, "No duplicated paragraphs")
    return CheckResult("Paragraph Duplication", False, dups * 5,
                       f"{dups} duplicated paragraph boundary(ies) found — chunk overlap artifact", "WARNING")


# ── Fluency Score (Custom Burmese Heuristic) ──────────────────────

def _check_fluency(text: str) -> CheckResult:
    """F0: Burmese fluency heuristic score — reference-free quality metric.

    Uses custom statistical heuristics (no BLEU/COMET reference needed):
    - Lexical diversity (Type-Token Ratio)
    - Particle diversity
    - Sentence flow and length variance
    - Syllable richness (compound word density)
    - Paragraph rhythm
    - Punctuation health
    - Hallucination repetition penalty
    """
    try:
        from src.utils.fluency_scorer import score_fluency
        report = score_fluency(text)
        score = report.composite_score

        if score >= 80:
            return CheckResult("Fluency Score", True, 0,
                               f"{score:.0f}/100 — {report.grade}", "INFO")
        elif score >= 70:
            return CheckResult("Fluency Score", True, 0,
                               f"{score:.0f}/100 — {report.grade} (borderline)", "INFO")
        elif score >= 50:
            details = f"{score:.0f}/100 — {report.grade}"
            if report.issues:
                details += f" ({len(report.issues)} issues)"
            return CheckResult("Fluency Score", False, 10,
                               details, "WARNING")
        else:
            details = f"{score:.0f}/100 — {report.grade}"
            if report.recommendations:
                details += f" | Fix: {report.recommendations[0]}"
            return CheckResult("Fluency Score", False, 20,
                               details, "CRITICAL")
    except ImportError:
        return CheckResult("Fluency Score", False, 0,
                           "Fluency scorer not available — skipping", "INFO")
    except Exception as e:
        return CheckResult("Fluency Score", False, 0,
                           f"Error computing fluency: {e}", "WARNING")


# ── Main Review Function ──────────────────────────────────────────

def review_translation(
    output_file: str,
    log_file: Optional[str] = None,
    chapter: Optional[int] = None,
    novel: Optional[str] = None,
) -> ReviewReport:
    """Run full quality review on a translated output file.

    Args:
        output_file: Path to the .mm.md translated output file
        log_file: Optional path to the translation log file
        chapter: Optional chapter number
        novel: Optional novel name

    Returns:
        ReviewReport with scores, issues, and todo items
    """
    output_path = Path(output_file)

    # Read output file
    try:
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(output_path, 'r', encoding='utf-8') as f:
            text = f.read()

    # Extract info from meta.json if available
    meta_path = output_path.with_suffix('.meta.json')
    pipeline_mode = "unknown"
    model = "unknown"
    duration_seconds = 0.0
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8-sig'))
            pipeline_mode = meta.get('pipeline', 'unknown')
            model = meta.get('model', 'unknown')
            duration_seconds = meta.get('duration_seconds', 0)
            chapter = chapter or meta.get('chapter')
            novel = novel or meta.get('novel')
        except Exception:
            pass

    # Extract chapter from filename if not provided
    if chapter is None:
        m = re.search(r'(\d{3,4})', output_path.stem)
        if m:
            chapter = int(m.group(1))
        else:
            chapter = 0

    # Extract novel from path if not provided
    if novel is None:
        parts = output_path.parts
        for i, part in enumerate(parts):
            if part == 'output' and i + 1 < len(parts):
                novel = parts[i + 1]
                break
        if novel is None:
            novel = output_path.parent.name

    # Create report
    report = ReviewReport(
        output_file=str(output_path),
        novel=novel or "unknown",
        chapter=chapter,
        pipeline_mode=pipeline_mode,
        model=model,
        duration_seconds=duration_seconds,
    )

    # ── Run all checks ──

    # Fluency heuristic (new — reference-free quality metric)
    report.add_check(_check_fluency(text))

    # Quantitative
    report.add_check(_check_myanmar_ratio(text))
    for r in _check_foreign_scripts(text):
        report.add_check(r)
    report.add_check(_check_latin_leakage(text))
    for r in _check_markdown_structure(text, chapter):
        report.add_check(r)
    report.add_check(_check_content_completeness(text))
    report.add_check(_check_paragraph_structure(text))

    # Linguistic
    report.add_check(_check_archaic_words(text))
    report.add_check(_check_particle_repetition(text))
    report.add_check(_check_register_consistency(text))
    report.add_check(_check_overlong_sentences(text))
    report.add_check(_check_sentence_enders(text))
    report.add_check(_check_paragraph_duplication(text))

    # Generate TODO items
    if report.critical_fixes:
        report.todo_items.append("🔴 Fix critical issues first:")
        for item in report.critical_fixes:
            report.todo_items.append(f"  - {item}")
    if report.warnings:
        report.todo_items.append("🟡 Address warnings:")
        for item in report.warnings[:5]:  # limit to 5
            report.todo_items.append(f"  - {item}")
    if report.total_score >= 70:
        report.todo_items.append(f"✅ Overall score {report.total_score}/100 — PASS")
    else:
        report.todo_items.append(f"❌ Overall score {report.total_score}/100 — NEEDS FIX")

    return report


def save_review_report(report: ReviewReport, report_dir: str = "logs/report") -> Path:
    """Save the review report as a markdown file.

    Args:
        report: ReviewReport from review_translation()
        report_dir: Directory to save reports

    Returns:
        Path to saved report file
    """
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{report.novel}_chapter_{report.chapter:03d}_review_{timestamp}.md"
    filepath = Path(report_dir) / filename

    # Build report markdown
    lines = [
        "# Translation Quality Report",
        "",
        "## 📋 File Info",
        f"- **Output file**: `{report.output_file}`",
        f"- **Novel**: {report.novel}",
        f"- **Chapter**: {report.chapter}",
        f"- **Pipeline**: {report.pipeline_mode}",
        f"- **Model**: {report.model}",
        f"- **Duration**: {report.duration_seconds:.0f}s",
        f"- **Reviewed at**: {datetime.now().isoformat()}",
        "",
        f"## 📊 Overall Score: {report.total_score}/100",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| ✅ Passed | {len(report.passed_checks)} |",
        f"| ⚠️ Warnings | {len(report.warnings)} |",
        f"| 🔴 Critical | {len(report.critical_fixes)} |",
        "",
    ]

    # Detail table
    lines.append("## 📋 Detailed Checks")
    lines.append("")
    lines.append("| Check | Result | Deduction | Details |")
    lines.append("|-------|--------|-----------|---------|")
    for check in report.checks:
        status = "✅" if check.passed else ("🔴" if check.severity == "CRITICAL" else "⚠️")
        lines.append(f"| {check.name} | {status} | -{check.score_deduction} | {check.details} |")

    # Critical issues
    if report.critical_fixes:
        lines.append("")
        lines.append("## 🔴 CRITICAL ISSUES (Must Fix)")
        for item in report.critical_fixes:
            lines.append(f"- [ ] {item}")

    # Warnings
    if report.warnings:
        lines.append("")
        lines.append("## 🟡 WARNINGS (Should Fix)")
        for item in report.warnings:
            lines.append(f"- [ ] {item}")

    # Passed
    if report.passed_checks:
        lines.append("")
        lines.append("## 🟢 PASSED CHECKS")
        for item in report.passed_checks:
            lines.append(f"- {item}")

    # TODO for agent
    if report.todo_items:
        lines.append("")
        lines.append("## 📝 AGENT TODO")
        for item in report.todo_items:
            lines.append(f"{item}")

    content = '\n'.join(lines) + '\n'
    filepath.write_text(content, encoding='utf-8-sig')

    logger.info(f"Review report saved: {filepath}")
    return filepath


def review_and_report(
    output_file: str,
    log_file: Optional[str] = None,
    chapter: Optional[int] = None,
    novel: Optional[str] = None,
) -> Tuple[ReviewReport, Path]:
    """Run review and save report. Convenience wrapper.

    Returns:
        Tuple of (ReviewReport, path to saved report)
    """
    report = review_translation(output_file, log_file, chapter, novel)
    report_path = save_review_report(report)
    return report, report_path


# ── CLI Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Review translation quality")
    parser.add_argument("output_file", help="Path to .mm.md output file")
    parser.add_argument("--log", help="Path to translation log file")
    parser.add_argument("--novel", help="Novel name override")
    parser.add_argument("--chapter", type=int, help="Chapter number override")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    report, path = review_and_report(
        args.output_file, args.log, args.chapter, args.novel
    )

    print(f"\n{'='*60}")
    print("  Translation Quality Report")
    print(f"{'='*60}")
    print(f"  Novel:   {report.novel}")
    print(f"  Chapter: {report.chapter}")
    print(f"  Score:   {report.total_score}/100")
    print(f"  Passed:  {len(report.passed_checks)}")
    print(f"  Warnings:{len(report.warnings)}")
    print(f"  Critical:{len(report.critical_fixes)}")
    print(f"{'='*60}")
    print(f"  Report saved: {path}")
