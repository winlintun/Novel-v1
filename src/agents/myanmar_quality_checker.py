#!/usr/bin/env python3
"""
Myanmar Quality Checker.
Checks for tone, naturalness, and Myanmar-specific quality issues.
"""

import re
import logging
from typing import Dict, List, Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class MyanmarQualityChecker(BaseAgent):
    """
    Custom checker for Myanmar translation quality.
    Checks tone, naturalness, and Myanmar-specific issues.
    """

    # Common awkward Myanmar phrases that should be avoided
    AWKWARD_PHRASES = [
        "သင်သည်", "ဤ", "ထို", "သည်သည်ကို",  # Archaic words
    ]

    # Modern alternatives
    MODERN_ALTERNATIVES = {
        "သင်သည်": "မင်း",
        "ဤ": "ဒီ",
        "ထို": "အဲဒါ",
    }

    # Required particles for proper grammar
    REQUIRED_PARTICLES = ["သည်", "ကို", "မှာ", "အတွက်", "ဖြင့်", "၍"]

    def __init__(
        self,
        ollama_client: Any = None,
        memory_manager: Any = None,
        config: Dict[str, Any] = None
    ):
        super().__init__(config=config)
        self.ollama_client = ollama_client
        self.memory_manager = memory_manager

    def check_quality(self, text: str) -> Dict[str, Any]:
        """
        Comprehensive quality check for Myanmar text.
        
        Returns:
            Dictionary with quality issues and scores
        """
        issues = []
        score = 100

        # Check for archaic words
        archaic_issues = self._check_archaic_words(text)
        if archaic_issues:
            issues.extend(archaic_issues)
            score -= len(archaic_issues) * 5

        # Check for repetition
        repetition_issues = self._check_repetition(text)
        if repetition_issues:
            issues.extend(repetition_issues)
            score -= 10

        # Check for sentence flow
        flow_issues = self._check_sentence_flow(text)
        if flow_issues:
            issues.extend(flow_issues)
            score -= len(flow_issues) * 3

        # Check for missing particles
        particle_issues = self._check_particles(text)
        if particle_issues:
            issues.extend(particle_issues)
            score -= len(particle_issues) * 2

        # Check for unnatural phrasing
        unnatural_issues = self._check_unnatural_phrasing(text)
        if unnatural_issues:
            issues.extend(unnatural_issues)
            score -= len(unnatural_issues) * 5

        # Check for register mixing within paragraphs
        tone = self._check_tone(text)
        if tone.get("register_mixed_paragraphs", 0) > 0:
            issues.append(
                f"Register mixing: {tone['register_mixed_paragraphs']} paragraph(s) "
                f"mix formal (သည်) and casual (တယ်) particles"
            )
            score -= tone["register_mixed_paragraphs"] * 5

        # Calculate final score
        score = max(0, score)

        return {
            "score": score,
            "issues": issues,
            "passed": score >= 70,
            "tone_check": self._check_tone(text),
            "naturalness_score": self._calculate_naturalness(text)
        }

    def _check_archaic_words(self, text: str) -> List[str]:
        """Check for archaic words that should be replaced."""
        issues = []
        for archaic in self.AWKWARD_PHRASES:
            if archaic in text:
                modern = self.MODERN_ALTERNATIVES.get(archaic, "modern word")
                issues.append(
                    f"Archaic word '{archaic}' found. Consider using '{modern}'"
                )
        return issues

    def _check_repetition(self, text: str) -> List[str]:
        """Check for excessive word repetition."""
        issues = []
        words = text.split()

        # Check for 3+ repeated words
        for i in range(len(words) - 2):
            if words[i] == words[i+1] == words[i+2]:
                issues.append(f"Repeated word: '{words[i]}' appears 3+ times")

        # Check for particle repetition (e.g., သည်သည်သည်)
        particle_pattern = r'(သည်|ကို|မှာ|အတွက်|ဖြင့်|၍){3,}'
        if re.search(particle_pattern, text):
            issues.append("Repeated particles detected - likely model hallucination")

        return issues

    def _check_sentence_flow(self, text: str) -> List[str]:
        """Check for sentence flow issues."""
        issues = []

        # Check for sentences that are too long
        sentences = re.split(r'[။၌]', text)
        for i, sent in enumerate(sentences):
            words = sent.split()
            if len(words) > 50:
                issues.append(f"Sentence {i+1} is too long ({len(words)} words)")

        # Check for missing sentence endings
        if text and not re.search(r'[။၌]$', text.strip()):
            issues.append("Text missing proper sentence ending")

        return issues

    def _check_particles(self, text: str) -> List[str]:
        """Check for particle usage."""
        issues = []

        # This is a basic check - more sophisticated analysis would be better
        if text:
            # Check if text has at least some particles
            particle_count = sum(1 for p in self.REQUIRED_PARTICLES if p in text)
            words = len(text.split())

            # Expect at least 1 particle per 10 words
            expected_min = words / 10
            if particle_count < expected_min * 0.5:
                issues.append(
                    f"Low particle usage ({particle_count} particles for {words} words)"
                )

        return issues

    def _check_unnatural_phrasing(self, text: str) -> List[str]:
        """Check for unnatural phrasing patterns."""
        issues = []

        # Check for English word order in Myanmar
        # This is a simple heuristic - proper analysis would require NLP
        unnatural_patterns = [
            (r'သည်\s+နဲ့\s+သည်', "Repeated 'သည် နဲ့ သည်' pattern"),
            (r'ကို\s+ကို\s+ကို', "Repeated 'ကို' pattern"),
        ]

        for pattern, desc in unnatural_patterns:
            if re.search(pattern, text):
                issues.append(desc)

        # Check for mixed language (too much English)
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        total_words = len(text.split())
        if total_words > 0 and english_words / total_words > 0.3:
            issues.append(f"Too much English ({english_words}/{total_words} words)")

        # Check for Bengali script leakage (U+0980–U+09FF)
        bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
        if bengali_chars > 0:
            issues.append(f"CRITICAL: Bengali script leaked ({bengali_chars} chars) - must be removed")

        return issues

    def _check_tone(self, text: str) -> Dict[str, Any]:
        """Check for tone consistency across paragraphs.

        Detects register mixing: uses သည်/၏/ဖြင့် (formal narration) AND
        တယ်/ဘူး/မှာ (casual narration) within the same narration paragraph.
        Dialogue paragraphs are allowed to use casual register.
        """
        # Check for mixed formality
        has_formal = any(p in text for p in ["သည်ကို", "အတွက်", "၏"])
        has_informal = any(p in text for p in ["မင်း", "ဒီ", "အဲဒါ"])

        # Per-paragraph register mixing: detects တယ်/ဘူး (casual)
        # and သည်/ဖြင့်/ပေသည် (formal) in the same paragraph
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        mixed_paragraphs = 0
        FORMAL_MARKERS = ['သည်', '၏', 'ဖြင့်', 'ပေသည်', 'သော', '၍']
        CASUAL_MARKERS = ['တယ်', 'ဘူး', 'လို့', 'နဲ့', 'ပါတယ်', 'မယ်']

        for para in paragraphs:
            has_para_formal = any(m in para for m in FORMAL_MARKERS)
            has_para_casual = any(m in para for m in CASUAL_MARKERS)
            if has_para_formal and has_para_casual:
                mixed_paragraphs += 1

        return {
            "has_formal": has_formal,
            "has_informal": has_informal,
            "mixed_tone": has_formal and has_informal,
            "register_mixed_paragraphs": mixed_paragraphs,
            "tone_consistent": not (has_formal and has_informal) and mixed_paragraphs == 0
        }

    def _calculate_naturalness(self, text: str) -> float:
        """Calculate naturalness score (0-100)."""
        score = 100

        # Penalize for issues
        score -= len(self._check_archaic_words(text)) * 10
        score -= len(self._check_repetition(text)) * 15
        score -= len(self._check_unnatural_phrasing(text)) * 10

        # Tone consistency
        tone = self._check_tone(text)
        if tone.get("mixed_tone"):
            score -= 10

        return max(0, min(100, score))

    def check_dialogue_tone(
        self,
        text: str,
        character_hierarchy: Dict[str, str] = None
    ) -> List[str]:
        """
        Check dialogue uses appropriate pronouns and honorifics.
        
        Args:
            text: Myanmar text
            character_hierarchy: Dict of character -> status (superior/inferior/equal)
            
        Returns:
            List of issues
        """
        issues = []

        # Check for appropriate pronouns in dialogue
        # This is a simplified check
        if '"' in text or '"' in text or '「' in text:
            # Has dialogue
            if "ကျွန်တော်" in text and "မင်း" not in text:
                issues.append(
                    "Dialogue uses 'ကျွန်တော်' but no 'မင်း' response - possible hierarchy issue"
                )

        return issues

    def suggest_improvements(self, text: str) -> List[str]:
        """Generate specific improvement suggestions."""
        suggestions = []

        quality = self.check_quality(text)

        for issue in quality.get("issues", []):
            if "archaic" in issue.lower():
                suggestions.append("Replace archaic words with modern equivalents")
            if "repetition" in issue.lower():
                suggestions.append("Rewrite to reduce word repetition")
            if "particle" in issue.lower():
                suggestions.append("Add proper Myanmar grammatical particles")
            if "tone" in issue.lower():
                suggestions.append("Maintain consistent formality level")

        return suggestions
