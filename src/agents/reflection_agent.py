#!/usr/bin/env python3
"""
Reflection Agent for Self-Correction.
Analyzes translations and suggests improvements.
"""

import logging
from typing import Dict, Optional, Any

from src.utils.ollama_client import OllamaClient
from src.agents.base_agent import BaseAgent
from src.memory.memory_manager import MemoryManager
from src.utils.postprocessor import myanmar_char_ratio
from src.agents.prompts.language_guards import LANGUAGE_GUARD

logger = logging.getLogger(__name__)


REFLECTION_SYSTEM_PROMPT = LANGUAGE_GUARD + """

You are a self-correction specialist for novel translation.
Your job is to analyze translations and identify areas for improvement.

CRITICAL RULES:
1. Analyze the Myanmar translation for quality issues
2. Check for: awkward phrasing, unnatural flow, missing context, tone inconsistency
3. Provide specific, actionable feedback
4. Never change the meaning - only improve expression
5. GLOSSARY: NEVER change character names, place names, or cultivation terms.
   Use EXACTLY the approved glossary spellings. These are authoritative, not suggestions.

LANGUAGE IDENTITY RULE (ZERO TOLERANCE):
- Verify the text is in Myanmar (Burmese) script
- If text is NOT in Myanmar, mark as CRITICAL issue
- Do NOT attempt to improve English text — it must be retranslated to Myanmar

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
        # reflection_model lives under translation_pipeline in the configs; the old
        # top-level lookup always missed it and fell back to 'qwen:7b' (often not
        # installed → 404). Resolve from the right place and fall back to the
        # refiner/translator model so reflection never targets an absent model.
        pipeline = self.config.get('translation_pipeline', {})
        models = self.config.get('models', {})
        self.model = (
            pipeline.get('reflection_model')
            or self.config.get('reflection_model')   # legacy top-level
            or models.get('refiner')
            or models.get('translator')
            or 'padauk-gemma:q8_0'
        )
        self.temperature = (
            pipeline.get('reflection_temperature')
            or self.config.get('reflection_temperature')
            or 0.3
        )

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
        # Language pre-check: if text is not Myanmar, bail immediately
        mm_ratio = myanmar_char_ratio(text)
        if mm_ratio < 0.70:
            return {
                "has_issues": True,
                "improvements": ["CRITICAL: Not Myanmar language"],
                "final_text": None,
                "language_error": True,
            }

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

            # Language error: model output is NOT Myanmar — cannot fix via reflection
            if result.get("language_error"):
                self.log_warning("Language error — reflection cannot fix wrong-language output")
                return current_text  # orchestrator quality gate will reject

            if not result.get("has_issues") or not result.get("final_text"):
                self.log_info("No more improvements found")
                break

            if result["final_text"] != current_text:
                current_text = result["final_text"]
                self.log_info(f"Applied improvements: {len(result.get('improvements', []))}")
            else:
                break

        return current_text


