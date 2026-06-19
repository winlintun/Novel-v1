"""
Myanmar Syntax Editor Agent
Uses mig-burmese-llm (HuggingFace Gemma3-1B fine-tune) to check and fix
Myanmar syntax/grammar errors in translated text.
Model is lazy-loaded once (class-level singleton, thread-safe) and reused across calls.
"""

import logging
import threading
import time
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.utils.postprocessor import clean_output

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT = 120

SYNTAX_CHECK_PROMPT = """You are a Myanmar (Burmese) language expert specializing in literary syntax correction.

Check the following Myanmar text for:
1. Grammatical errors and incorrect particle usage (a/hke/mhar/ein/hte/ne)
2. SVO->SOV word order violations (Myanmar is SOV, not SVO)
3. Awkward or unnatural phrasing that doesn't flow naturally
4. Incorrect pronoun usage based on character status hierarchy
5. Missing or extra grammatical particles
6. Run-on or fragmented sentences

Fix ALL issues found. Preserve the original meaning, character names, place names,
and story details exactly. Do NOT change glossary terms or proper nouns.

CRITICAL RULES:
- Bengali script (U+0980-U+09FF) and ALL other Indic scripts are STRICTLY FORBIDDEN. Myanmar Unicode only.
- Preserve ALL [??] placeholders exactly as-is. Never resolve, translate, or replace them.
- Output ONLY the corrected Myanmar text. No explanations, no preambles.

TEXT TO CHECK:
{text}

CORRECTED MYANMAR TEXT:"""


class MyanmarSyntaxEditorError(Exception):
    """Raised when the Myanmar syntax editor fails to load or run."""


class MyanmarSyntaxEditor:
    """Uses mig-burmese-llm to check and fix Myanmar syntax errors.

    Loads the HF model once (lazy, class-level singleton, thread-safe) and reuses it.
    The model is a Gemma3-1B fine-tuned for Burmese, ideal for lightweight syntax checking.
    """

    _shared_model = None
    _shared_tokenizer = None
    _shared_device = None
    _load_lock = threading.Lock()
    _model_loaded = False

    def __init__(
        self,
        model_path: str = "models/mig-burmese-llm",
        device: str = "auto",
        max_new_tokens: int = 256,
        temperature: float = 0.1,
    ):
        self.model_path = model_path
        self._device_setting = device
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature

    def _load_model(self) -> None:
        """Load HF model and tokenizer (thread-safe, called once on first use)."""
        if MyanmarSyntaxEditor._model_loaded:
            return

        with MyanmarSyntaxEditor._load_lock:
            if MyanmarSyntaxEditor._model_loaded:
                return

            logger.info(f"Loading mig-burmese-llm from {self.model_path}...")
            t0 = time.time()

            device = self._device_setting
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"

            if device == "cuda":
                free_vram = self._get_free_vram()
                if free_vram is not None and free_vram < 2.0:
                    logger.warning(
                        f"Only {free_vram:.1f}GB VRAM free, falling back to CPU"
                    )
                    device = "cpu"

            dtype = torch.float16 if device == "cuda" else torch.float32

            try:
                tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    dtype=dtype,
                    device_map="auto" if device == "cuda" else None,
                )
                if device == "cpu":
                    model = model.to(device)

                MyanmarSyntaxEditor._shared_tokenizer = tokenizer
                MyanmarSyntaxEditor._shared_model = model
                MyanmarSyntaxEditor._shared_device = device
                MyanmarSyntaxEditor._model_loaded = True

                elapsed = time.time() - t0
                logger.info(
                    f"mig-burmese-llm loaded in {elapsed:.1f}s on {device} "
                    f"({model.num_parameters()/1e9:.2f}B params)"
                )
            except Exception as e:
                MyanmarSyntaxEditor._shared_tokenizer = None
                MyanmarSyntaxEditor._shared_model = None
                MyanmarSyntaxEditor._shared_device = None
                logger.error(f"Failed to load mig-burmese-llm: {e}")
                raise MyanmarSyntaxEditorError(
                    f"Could not load model from {self.model_path}: {e}"
                ) from e

    @staticmethod
    def _get_free_vram() -> Optional[float]:
        """Return free VRAM in GB, or None if not measurable."""
        try:
            if torch.cuda.is_available():
                free, _ = torch.cuda.mem_get_info()
                return free / (1024**3)
        except Exception:
            pass
        return None

    def check_and_fix(self, text: str) -> str:
        """Check Myanmar text for syntax errors and return corrected version."""
        if not text or not text.strip():
            return text

        try:
            self._load_model()
        except MyanmarSyntaxEditorError:
            logger.warning("Syntax editor unavailable — returning original text")
            return text

        prompt = SYNTAX_CHECK_PROMPT.format(text=text)
        inputs = MyanmarSyntaxEditor._shared_tokenizer(
            prompt, return_tensors="pt"
        ).to(MyanmarSyntaxEditor._shared_device)

        try:
            with torch.no_grad():
                out = MyanmarSyntaxEditor._shared_model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=True,
                    temperature=self.temperature,
                    pad_token_id=MyanmarSyntaxEditor._shared_tokenizer.eos_token_id,
                )

            full_output = MyanmarSyntaxEditor._shared_tokenizer.decode(
                out[0], skip_special_tokens=True
            )

            return self._extract_correction(full_output, text)
        except Exception as e:
            logger.error(f"Syntax correction inference failed: {e}")
            return text

    def _extract_correction(self, full_output: str, original: str) -> str:
        """Extract the corrected text from the model output.

        Strips the input prompt portion and returns only the generated
        correction. Falls back to original on parse failure.
        """
        marker = "CORRECTED MYANMAR TEXT:"
        if marker in full_output:
            corrected = full_output.split(marker, 1)[-1].strip()
            if corrected:
                return clean_output(corrected)
        return original

    def fix_chunk(self, text: str) -> str:
        """Fix a single chunk of Myanmar text."""
        try:
            return self.check_and_fix(text)
        except Exception as e:
            logger.error(f"MyanmarSyntaxEditor.fix_chunk failed: {e}")
            return text

    def fix_chapter(self, paragraphs: list[str]) -> list[str]:
        """Fix multiple paragraphs, returning corrected versions."""
        fixed = []
        total = len(paragraphs)
        for i, para in enumerate(paragraphs):
            if not para.strip():
                fixed.append(para)
                continue
            logger.debug(f"Syntax check paragraph {i+1}/{total}...")
            try:
                corrected = self.check_and_fix(para)
                fixed.append(corrected)
            except Exception as e:
                logger.warning(f"Syntax check failed for para {i+1}: {e}")
                fixed.append(para)
        return fixed

    def unload(self) -> None:
        """Unload model to free memory."""
        with MyanmarSyntaxEditor._load_lock:
            if MyanmarSyntaxEditor._shared_model is not None:
                del MyanmarSyntaxEditor._shared_model
                del MyanmarSyntaxEditor._shared_tokenizer
                MyanmarSyntaxEditor._shared_model = None
                MyanmarSyntaxEditor._shared_tokenizer = None
                MyanmarSyntaxEditor._shared_device = None
                MyanmarSyntaxEditor._model_loaded = False
                torch.cuda.empty_cache()
                logger.info("mig-burmese-llm unloaded from memory")
