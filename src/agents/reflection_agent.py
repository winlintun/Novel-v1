#!/usr/bin/env python3
"""
Reflection Agent for Self-Correction.
Analyzes translations and suggests improvements.
"""

import logging
from typing import Dict, List, Optional, Any

from src.utils.ollama_client import OllamaClient
from src.agents.base_agent import BaseAgent
from src.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


REFLECTION_SYSTEM_PROMPT = """You are a self-correction specialist for novel translation.
Your job is to analyze translations and identify areas for improvement.

CRITICAL RULES:
1. Analyze the Myanmar translation for quality issues
2. Check for: awkward phrasing, unnatural flow, missing context, tone inconsistency
3. Provide specific, actionable feedback
4. Never change the meaning - only improve expression
5. GLOSSARY: NEVER change character names, place names, or cultivation terms.
   Use EXACTLY the approved glossary spellings. These are authoritative, not suggestions.

GLOSSARY (approved terms — NEVER change these):
{glossary}

Output format:
IMPROVEMENTS: [List of specific issues found]
SUGGESTIONS: [How to fix each issue]
FINAL_TEXT: [Improved version if needed, or same as input if no issues]

Input text to analyze:
{text}

Analysis:"""


class ReflectionAgent(BaseAgent):
    """
    Self-correction agent that analyzes translations and suggests improvements.
    Based on Andrew Ng's translation-agent pattern.
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        config: Optional[Dict[str, Any]] = None,
        memory_manager: Optional[MemoryManager] = None
    ):
        super().__init__(ollama_client, config=config, memory_manager=memory_manager)
        self.model = self.config.get('reflection_model', 'qwen:7b')
        self.temperature = self.config.get('reflection_temperature', 0.3)

    def _get_glossary_for_prompt(self) -> str:
        """Fetch glossary terms for injection."""
        if hasattr(self, 'memory') and self.memory:
            try:
                return self.memory.get_glossary_for_prompt(limit=20)
            except Exception:
                pass
        return "No glossary entries yet."

    def analyze(self, text: str, source_text: str = "") -> Dict[str, Any]:
        """
        Analyze translation for issues.
        
        Args:
            text: Myanmar translation to analyze
            source_text: Original source text (optional)
            
        Returns:
            Dictionary with analysis results
        """
        glossary_text = self._get_glossary_for_prompt()
        prompt = REFLECTION_SYSTEM_PROMPT.format(text=text, glossary=glossary_text)

        if source_text:
            prompt = prompt.replace(
                "Input text to analyze:",
                f"Original source:\n{source_text}\n\nTranslated text to analyze:"
            )

        try:
            # Use the model from config — never mutate shared state on OllamaClient.
            # Pass model per-call so OllamaClient stays stateless.
            response = self.client.chat(
                prompt=prompt,
                system_prompt="You are a meticulous translation quality checker.",
                model=self.model
            )

            # Parse response
            result = self._parse_response(response, text)
            return result

        except Exception as e:
            self.log_error("Analysis failed", e)
            return {
                "has_issues": False,
                "improvements": [],
                "suggestions": [],
                "final_text": text,
                "error": str(e)
            }

    def _parse_response(self, response: str, original: str) -> Dict[str, Any]:
        """Parse LLM response for improvements."""
        improvements = []
        suggestions = []
        final_text = original

        lines = response.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("IMPROVEMENTS:"):
                current_section = "improvements"
            elif line.startswith("SUGGESTIONS:"):
                current_section = "suggestions"
            elif line.startswith("FINAL_TEXT:"):
                current_section = "final_text"
            elif line and current_section:
                if current_section == "improvements":
                    improvements.append(line.lstrip('- '))
                elif current_section == "suggestions":
                    suggestions.append(line.lstrip('- '))
                elif current_section == "final_text" and len(line) > 50:
                    final_text = line

        return {
            "has_issues": len(improvements) > 0,
            "improvements": improvements,
            "suggestions": suggestions,
            "final_text": final_text if final_text != original else None
        }

    def reflect_and_improve(
        self,
        text: str,
        source_text: str = "",
        max_iterations: int = 2
    ) -> str:
        """
        Iteratively improve translation through reflection.
        
        Args:
            text: Initial translation
            source_text: Original source text
            max_iterations: Maximum reflection cycles
            
        Returns:
            Improved translation
        """
        current_text = text

        for i in range(max_iterations):
            self.log_info(f"Reflection iteration {i+1}/{max_iterations}")

            result = self.analyze(current_text, source_text)

            if not result.get("has_issues") or not result.get("final_text"):
                self.log_info("No more improvements found")
                break

            if result["final_text"] != current_text:
                current_text = result["final_text"]
                self.log_info(f"Applied improvements: {len(result.get('improvements', []))}")
            else:
                break

        return current_text

    def check_consistency(
        self,
        text: str,
        glossary_terms: List[Dict[str, str]]
    ) -> List[str]:
        """
        Check consistency with glossary terms.
        
        Args:
            text: Translation to check
            glossary_terms: List of approved terms
            
        Returns:
            List of consistency issues
        """
        issues = []

        for term in glossary_terms:
            source = term.get("source", "")
            target = term.get("target", "")

            if source in text and target not in text:
                issues.append(
                    f"Term '{source}' found but translation '{target}' not used"
                )

        return issues

    def compare_with_source(
        self,
        source: str,
        translation: str
    ) -> Dict[str, Any]:
        """
        Compare translation with source for completeness.
        
        Args:
            source: Original text
            translation: Translated text
            
        Returns:
            Comparison results
        """
        source_words = len(source.split())
        trans_words = len(translation.split())

        ratio = trans_words / max(source_words, 1)

        return {
            "source_words": source_words,
            "translation_words": trans_words,
            "word_ratio": ratio,
            "suspicious": ratio < 0.5 or ratio > 3.0,
            "warning": "Translation may be too short or too long" if ratio < 0.5 or ratio > 3.0 else None
        }
