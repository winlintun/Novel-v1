"""
QA Tester Agent - Automated Validation
- Regex checks for name consistency, markdown validity
- Myanmar Unicode ratio validation
- Chapter structure verification
"""
import re
import logging
from typing import Optional, Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class QATesterAgent(BaseAgent):
    """Automated quality assurance for translated chapters."""
    
    # Myanmar Unicode block ranges
    MYANMAR_UNICODE_RANGES = [
        (0x1000, 0x109F),   # Myanmar
        (0xAA60, 0xAA7F),   # Myanmar Extended-A
        (0xA9E0, 0xA9FF),   # Myanmar Extended-B
    ]
    
    def __init__(self, memory_manager: MemoryManager, config: Dict[str, Any] = None):
        super().__init__(memory_manager=memory_manager, config=config)
    
    def validate_output(self, text: str, chapter_num: int) -> Dict[str, Any]:
        """
        Run all QA checks. Returns validation report.
        """
        report = {
            "chapter": chapter_num,
            "passed": True,
            "issues": [],
            "metrics": {}
        }
        
        # Check 1: Markdown structure
        md_issues = self._check_markdown(text)
        if md_issues:
            report["issues"].extend(md_issues)
            report["passed"] = False
        
        # Check 2: Glossary consistency (names/terms)
        glossary_issues = self._check_glossary_consistency(text)
        if glossary_issues:
            report["issues"].extend(glossary_issues)
            report["passed"] = False
        
        # Check 3: Myanmar Unicode ratio
        mm_ratio = self._calculate_myanmar_ratio(text)
        report["metrics"]["myanmar_ratio"] = mm_ratio
        if mm_ratio < 0.70:  # <70% Myanmar chars = suspicious
            report["issues"].append(f"Myanmar ratio too low: {mm_ratio:.2%}")
            report["passed"] = False
        
        # Check 4: Placeholder detection
        placeholders = self._find_placeholders(text)
        if placeholders:
            report["issues"].append(f"Unresolved placeholders: {placeholders}")
            # Note: placeholders may be intentional, don't auto-fail
        
        # Check 5: Chapter title format
        if not self._validate_chapter_title(text, chapter_num):
            report["issues"].append("Chapter title format invalid")
            report["passed"] = False
        
        return report
    
    def _check_markdown(self, text: str) -> List[str]:
        """Validate markdown structure."""
        issues = []
        
        # Check for single H1 (chapter title)
        h1_count = len(re.findall(r'^#\s+.+$', text, re.MULTILINE))
        if h1_count != 1:
            issues.append(f"Expected 1 chapter title (H1), found {h1_count}")
        
        # Check for unclosed formatting
        if text.count('**') % 2 != 0:
            issues.append("Unclosed bold formatting (**)" )
        if text.count('*') % 2 != 0 and text.count('**') == 0:
            issues.append("Unclosed italic formatting (*)")
        
        return issues
    
    def _check_glossary_consistency(self, text: str) -> List[str]:
        """Check that verified glossary terms appear in approved form."""
        issues = []
        glossary = self.memory.get_all_terms()

        for term_data in glossary:
            source = term_data.get("source", "")
            target = term_data.get("target")
            if not target:
                continue

            # Check all terms, not just verified — the MemoryManager
            # already validates target via _is_valid_myanmar_text() before
            # storage, so unverified terms are still valid translations.
            # If the Chinese source term appears in the Myanmar text, it was never translated
            if source and len(source) >= 2:
                if source in text:
                    issues.append(f"Untranslated term '{source}' — expected '{target}'")

        # Placeholder check — hoisted outside loop (once, not N times)
        if "【?term?】" in text:
            issues.append("Unresolved 【?term?】 placeholders found")

        return issues
    
    def _calculate_myanmar_ratio(self, text: str) -> float:
        """Calculate ratio of Myanmar Unicode characters."""
        if not text.strip():
            return 0.0
        
        myanmar_chars = 0
        total_chars = 0
        
        for char in text:
            code = ord(char)
            # Count if in Myanmar Unicode blocks
            if any(start <= code <= end for start, end in self.MYANMAR_UNICODE_RANGES):
                myanmar_chars += 1
            # Count printable chars (exclude markdown, punctuation)
            if char.isprintable() and not char.isspace() and char not in '#*`[]()':
                total_chars += 1
        
        return myanmar_chars / total_chars if total_chars > 0 else 0.0
    
    def _find_placeholders(self, text: str) -> List[str]:
        """Find unresolved 【?term?】 placeholders."""
        return re.findall(r'【\?[^?]+\?】', text)
    
    def _validate_chapter_title(self, text: str, expected_chapter: int) -> bool:
        """Validate chapter title format matches expected number."""
        match = re.search(r'^#\s+.*?(?:အခန်း|Chapter)?\s*(\d+)', text, re.MULTILINE | re.IGNORECASE)
        if not match:
            return False
        found_chapter = int(match.group(1))
        return found_chapter == expected_chapter
