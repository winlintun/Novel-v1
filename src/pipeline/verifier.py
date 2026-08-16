"""Verifier subagent — deterministic term-level quality gate (SKILL_verifier.md).

Checks (in order):
1. glossary scan — every glossary term whose alias appears in the SOURCE must
   appear *exactly* in the output; a known wrong variant is a FATAL
   (TEST-RULE-001), a missing canonical term an ERROR
2. overlap identity — output must start with the previous chunk's exact text
   (R-STRUCT-04)
3. format — straight quotes, zero-width spaces, thinking tags, paragraph count
4. register mixing — literary + spoken endings in the same sentence
5. untranslated English fragments (glossary-aware)
6. voice continuity vs ContextBuffer active speakers (R-CTX-01 / R-STYLE-03)
7. new-term detection (pending glossary, R-GLOSS-03)

Auto-fix applies only to unambiguous glossary variants, capped by
``max_auto_fix`` (TEST-RULE-002).  Voice/register issues are *never* auto-fixed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from . import postprocessor
from .models import Issue, IssueCategory, IssueSeverity
from .postprocessor import BURMESE_CLOSE, BURMESE_OPEN, ZWSP, has_foreign_script

LITERARY_ENDINGS = ("လေသည်", "ရလေသည်", "ကြလေသည်", "ခြင်း ဖြစ်သည်")
SPOKEN_PARTICLES = ("တယ်", "လား", "ကွာ", "နော်", "ဗျာ", "ပဲ")
# Burmese consonants are word chars but vowel signs/Marks are not, so ``\b``
# fails around Myanmar particles.  Match a spoken particle only when followed
# by a sentence/pause terminator (punctuation, space, opening/closing quote).
_SPOKEN_RE = re.compile(
    r"(တယ်|လား|ကွာ|နော်|ဗျာ|ပဲ)"
    r"(?=[။.!?…၀“”]|$|\s)"
)

_EN_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_ALLOWED_LATIN = {"OK", "Mr", "Mrs", "Ms", "Dr", "No", "Yes", "A", "B", "C", "D", "F"}


class VerificationResult:
    def __init__(
        self,
        pass_: bool,
        issues: List[Issue],
        corrected_text: str,
        glossary_hits: int,
        glossary_misses: int,
        auto_fixed: int,
        new_terms: List[str],
    ):
        self.pass_ = pass_
        self.issues = issues
        self.corrected_text = corrected_text
        self.glossary_hits = glossary_hits
        self.glossary_misses = glossary_misses
        self.auto_fixed = auto_fixed
        self.new_terms = new_terms

    @property
    def passv(self) -> bool:
        return self.pass_

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pass": self.pass_,
            "issues": [i.to_dict() for i in self.issues],
            "corrected_text": self.corrected_text,
            "glossary_hits": self.glossary_hits,
            "glossary_misses": self.glossary_misses,
            "auto_fixed": self.auto_fixed,
            "new_terms": self.new_terms,
        }


def _split_sentences(text: str) -> List[str]:
    raw = re.split(r"(?<=[。.!?])\s+|\n+", text or "")
    return [s.strip() for s in raw if s.strip()]


def verify(
    source_text: str,
    translated_text: str,
    glossary_index: Sequence[dict],
    context: Optional[Dict[str, Any]] = None,
    preceding_overlap: str = "",
    auto_fix_enabled: bool = True,
    max_auto_fix: int = 10,
) -> VerificationResult:
    issues: List[Issue] = []
    new_terms: List[str] = []

    text = postprocessor.clean_my_text(translated_text)
    auto_fixed = 0
    if auto_fix_enabled:
        text, auto_fixed = postprocessor.enforce_glossary(
            text, glossary_index, max_fixes=max_auto_fix
        )
        text = postprocessor.normalize_quotes(text)
        text = postprocessor.remove_zwsp(text)

    # 1. glossary scan ------------------------------------------------------ #
    hits = 0
    misses = 0
    for entry in glossary_index:
        aliases = list(entry.get("aliases") or [entry.get("en") or ""])
        present_in_source = any(a and a in source_text for a in aliases)
        if not present_in_source:
            continue
        canonical = entry.get("my") or ""
        if canonical and canonical in text:
            hits += 1
            continue
        misses += 1
        variant = next((v for v in entry.get("my_variants") or [] if v and v in text), None)
        if variant:
            issues.append(
                Issue(
                    severity=IssueSeverity.FATAL,
                    category=IssueCategory.GLOSSARY,
                    rule_id="R-GLOSS-01",
                    location={"snippet": variant},
                    message=(
                        f"Glossary term '{entry.get('en')}' rendered as '{variant}' "
                        f"instead of canonical '{canonical}'"
                    ),
                    suggestion=f"Use '{canonical}' exactly",
                )
            )
        else:
            issues.append(
                Issue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.GLOSSARY,
                    rule_id="R-GLOSS-01",
                    message=(
                        f"Glossary term '{entry.get('en')}' appears in source but "
                        f"'{canonical}' is missing from the output"
                    ),
                    suggestion=f"Insert '{canonical}' where the source uses '{entry.get('en')}'",
                )
            )

    # 2. overlap identity ---------------------------------------------------- #
    if preceding_overlap and not text.startswith(preceding_overlap):
        issues.append(
            Issue(
                severity=IssueSeverity.FATAL,
                category=IssueCategory.COHERENCE,
                rule_id="R-STRUCT-04",
                message="Overlap paragraph with the previous chunk is not character-identical",
                suggestion="Start the output with the exact overlap paragraph",
            )
        )

    # 3. format --------------------------------------------------------------- #
    if has_foreign_script(text):
        issues.append(
            Issue(
                severity=IssueSeverity.FATAL,
                category=IssueCategory.FORMAT,
                rule_id="R-FORBID-05",
                message="Foreign script (Thai/Bengali/Devanagari/Hangul/...) present in output",
                suggestion="Output must be standard Myanmar Unicode only",
            )
        )
    if '"' in text:
        issues.append(
            Issue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.FORMAT,
                rule_id="R-FORMAT-01",
                location={"snippet": '"'},
                message="Straight ASCII quotes remain in output",
                suggestion="Use Burmese quotes " + BURMESE_OPEN + "/" + BURMESE_CLOSE,
            )
        )
    if ZWSP in text:
        issues.append(
            Issue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.FORMAT,
                rule_id="R-FORMAT-04",
                message="Zero-width space (U+200B) present",
                suggestion="Strip all zero-width spaces",
            )
        )
    if re.search(r"<thinking>|^\s*thinking\b", text, re.IGNORECASE):
        issues.append(
            Issue(
                severity=IssueSeverity.ERROR,
                category=IssueCategory.FORMAT,
                message="Thinking tags or meta-commentary leaked into output",
            )
        )
    src_paras = len([p for p in source_text.split("\n\n") if p.strip()])
    out_paras = len([p for p in text.split("\n\n") if p.strip()])
    if out_paras != src_paras:
        issues.append(
            Issue(
                severity=IssueSeverity.WARNING if abs(out_paras - src_paras) <= 1 else IssueSeverity.ERROR,
                category=IssueCategory.FORMAT,
                rule_id="R-STRUCT-02",
                message=f"Paragraph count mismatch: source={src_paras}, output={out_paras}",
                suggestion="One source paragraph must equal one output paragraph",
            )
        )

    # 4. register mixing ------------------------------------------------------ #
    for sentence in _split_sentences(text):
        has_literary = any(ending in sentence for ending in LITERARY_ENDINGS)
        has_spoken = bool(_SPOKEN_RE.search(sentence))
        if has_literary and has_spoken:
            issues.append(
                Issue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.REGISTER,
                    rule_id="R-FORBID-04",
                    location={"snippet": sentence[:60]},
                    message="Sentence mixes literary and spoken endings",
                    suggestion="Split register: keep literary endings in narration, spoken in dialogue",
                )
            )
            break

    # 5. untranslated English fragments ---------------------------------------- #
    allowed = set(_ALLOWED_LATIN)
    for entry in glossary_index:
        allowed.add(entry.get("en") or "")
        allowed.update(entry.get("aliases") or [])
    seen_english: set = set()
    for word in _EN_WORD_RE.findall(text):
        if word in allowed or word in seen_english:
            continue
        seen_english.add(word)
        issues.append(
            Issue(
                severity=IssueSeverity.FATAL,
                category=IssueCategory.COHERENCE,
                rule_id="R-FORBID-03",
                location={"snippet": word},
                message=f"Untranslated English fragment: '{word}'",
                suggestion="Translate to Burmese or confirm it is a glossary proper noun",
            )
        )

    # 6. voice continuity ------------------------------------------------------- #
    if context:
        active = context.get("active_speakers") or {}
        dialogue_spans = " ".join(
            re.findall(BURMESE_OPEN + r"(.*?)" + BURMESE_CLOSE, text, re.DOTALL)
        )
        for name, info in active.items():
            expected = info.get("pronoun") or info.get("last_used_pronoun") or ""
            if not expected or name not in source_text:
                continue
            wrong = [o for o in active
                     if (active[o].get("pronoun") or active[o].get("last_used_pronoun"))
                     and (active[o].get("pronoun") or active[o].get("last_used_pronoun")) != expected]
            other_pronouns = [active[o].get("pronoun") or active[o].get("last_used_pronoun") for o in wrong]
            if any(p and p in dialogue_spans for p in other_pronouns) and expected not in dialogue_spans:
                issues.append(
                    Issue(
                        severity=IssueSeverity.ERROR,
                        category=IssueCategory.VOICE,
                        rule_id="R-CTX-01",
                        message=f"'{name}' expected pronoun '{expected}' missing; another speaker's pronoun used in dialogue",
                        suggestion=f"Use '{expected}' for {name}'s dialogue consistently",
                    )
                )

    # 7. new-term detection ----------------------------------------------------- #
    glossary_tokens = set()
    for entry in glossary_index:
        glossary_tokens.add(entry.get("en") or "")
        glossary_tokens.update(entry.get("aliases") or [])
    for word in re.findall(r"\b[A-Z][A-Za-z']{1,40}\b", source_text or ""):
        if word not in glossary_tokens and word not in new_terms:
            new_terms.append(word)

    blocks = any(i.blocks_approval for i in issues)
    return VerificationResult(
        pass_=not blocks,
        issues=_rank(issues),
        corrected_text=text,
        glossary_hits=hits,
        glossary_misses=misses,
        auto_fixed=auto_fixed,
        new_terms=new_terms,
    )


def _rank(issues: List[Issue]) -> List[Issue]:
    order = {"critical": 0, "fatal": 0, "error": 1, "warning": 2, "info": 3}
    return sorted(issues, key=lambda i: order.get(i.severity, 9))