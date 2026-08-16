"""Two-pass chunk translator (SPEC §2.? / PRD FR-13, SKILL_translator.md).

For one chunk: analyze (MP1) -> draft (MP2) -> polish (MP3) -> deterministic
normalize (MP4, postprocessor).  Role-specific models come from
``roles`` (NEW_TODO §4): analyzer / draft / polish each use their assigned
model + temperature; the caller's ``--model`` is the fallback for all roles.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import jsonparse, postprocessor, prompt_builder
from .models import Chunk
from .ollama_client import OllamaClient


class Translator:
    def __init__(
        self,
        client: OllamaClient,
        *,
        two_pass: bool = True,
        temperature: float = 0.2,
        max_ctx: int = 8192,
        roles: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.client = client
        self.two_pass = two_pass
        self.temperature = temperature
        self.max_ctx = max_ctx
        self.roles = roles or {}

    # -- role resolution ------------------------------------------------ #
    def _role(self, name: str) -> Dict[str, Any]:
        role = self.roles.get(name) or {}
        return {
            "model": role.get("model") or self.client.model,
            "temperature": role.get("temperature") or self.temperature,
        }

    @staticmethod
    def _model_kwargs(model: str, base_model: str) -> Dict[str, str]:
        """Pass an explicit model only when it differs from the client default."""
        if model and model != base_model:
            return {"model": model}
        return {}

    # -- MP1 ------------------------------------------------------------- #
    def analyze_chunk(
        self,
        chunk: Chunk,
        *,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """Micro-Prompt 1: classify speakers / tone / scene type (JSON)."""
        role = self._role("analyzer")
        raw = self.client.generate(
            prompt_builder.build_analyze_prompt(chunk),
            system=system_prompt,
            temperature=role["temperature"],
            num_predict=512,
            **self._model_kwargs(role["model"], self.client.model),
        )
        parsed = jsonparse.load_json(raw.strip())
        return parsed if isinstance(parsed, dict) else {}

    def translate_chunk(
        self,
        chunk: Chunk,
        *,
        system_prompt: str = "",
        glossary_section: str = "",
        context_section: str = "",
        few_shot_section: str = "",
        style_guide_section: str = "",
        analyze: bool = False,
        fix_issues: Optional[List[str]] = None,
    ) -> Tuple[str, List[str]]:
        used: List[str] = []
        draft_role = self._role("draft")

        if analyze:
            analyze_role = self._role("analyzer")
            raw_analyze = self.client.generate(
                prompt_builder.build_analyze_prompt(chunk),
                system=system_prompt,
                temperature=analyze_role["temperature"],
                num_predict=512,
                **self._model_kwargs(analyze_role["model"], self.client.model),
            )
            used.append("analyze")

        draft_prompt = prompt_builder.assembled_prompt(
            chunk,
            glossary_section=glossary_section,
            context_section=context_section,
            few_shot_section=few_shot_section,
            max_ctx=self.max_ctx,
        )
        if fix_issues:
            draft_prompt += "\n\nFIX MODE: fix these verified issues and re-output the full Burmese text:\n- " + "\n- ".join(fix_issues)
            used.append("fix")

        raw_draft = self.client.generate(
            draft_prompt,
            system=system_prompt,
            temperature=draft_role["temperature"],
            **self._model_kwargs(draft_role["model"], self.client.model),
        )
        draft = postprocessor.clean_my_text(raw_draft)
        used.append("draft")

        text = draft
        if self.two_pass:
            polish_role = self._role("polish")
            polish_prompt = prompt_builder.build_polish_prompt(
                chunk, draft, style_guide=style_guide_section
            )
            raw_polish = self.client.generate(
                polish_prompt,
                system=system_prompt,
                temperature=polish_role["temperature"],
                **self._model_kwargs(polish_role["model"], self.client.model),
            )
            polished = postprocessor.clean_my_text(raw_polish)
            if polished:
                text = polished
            used.append("polish")

        # MP4 (deterministic) happens in the orchestrator with full context.
        return text, used