#!/usr/bin/env python3
"""
Translation Engine - All model adapters with streaming
"""

import os
import json
import logging
import time
import signal
import requests
import urllib3
import warnings
from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any, List
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# NLLB200 language codes mapping
NLLB_LANG_CODES = {
    "chinese": "zho_Hans",      # Simplified Chinese
    "chinese_simplified": "zho_Hans",
    "chinese_traditional": "zho_Hant",
    "english": "eng_Latn",
    "myanmar": "mya_Mymr",
    "burmese": "mya_Mymr",
}

# Configure logging
logger = logging.getLogger(__name__)

# SSL verification setting - only disable for local Ollama
# Set VERIFY_SSL=false in .env only if you have certificate issues
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() != "false"

# Disable SSL warnings only if verification is disabled
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn("SSL verification is disabled. This is insecure and should only be used for local development.", RuntimeWarning)

# Connection pool for HTTP requests
_session_pool: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Get or create a requests session with connection pooling."""
    global _session_pool
    if _session_pool is None:
        _session_pool = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=3
        )
        _session_pool.mount('https://', adapter)
        _session_pool.mount('http://', adapter)
    return _session_pool


@contextmanager
def managed_request(method: str, url: str, **kwargs):
    """Context manager for HTTP requests to ensure proper resource cleanup.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        **kwargs: Additional arguments for requests
        
    Yields:
        Response object
    """
    session = get_session()
    response = None
    try:
        response = session.request(method, url, **kwargs)
        yield response
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise
    finally:
        if response is not None:
            response.close()


def get_system_prompt(target_lang: str = "Myanmar (Burmese)", source_lang: str = "Chinese", 
                      novel_name: str = None, glossary_manager=None) -> str:
    """Get the optimized system prompt from AGENTS.md.
    
    Args:
        target_lang: Target language for translation
        source_lang: Source language of text
        novel_name: Name of novel (for loading per-novel glossary)
        glossary_manager: Pre-loaded GlossaryManager instance (optional)
    """
    # Normalize language names
    source_lang_lower = source_lang.lower()
    target_lang_lower = target_lang.lower()

    # Determine source language display name
    if "chinese" in source_lang_lower:
        source_display = "Chinese"
        style_note = "Maintain the literary style and tone appropriate for a Chinese web novel (xianxia/wuxia/urban)."
    elif "english" in source_lang_lower:
        source_display = "English"
        style_note = "Maintain the literary style and tone of the original English novel."
    else:
        source_display = source_lang
        style_note = "Maintain the literary style and tone of the source text."

    # Load glossary - priority: glossary_manager > novel_name > names.json
    glossary_text = ""
    glossary_loaded = False
    
    # 1. Try provided glossary manager first
    if glossary_manager is not None:
        try:
            glossary_text = glossary_manager.get_glossary_text()
            if glossary_text:
                glossary_loaded = True
                logger.info(f"Using provided glossary manager: {len(glossary_manager.names)} names")
        except Exception as e:
            logger.warning(f"Failed to load glossary from manager: {e}")
    
    # 2. Try novel-specific glossary file (if no glossary manager or it was empty)
    if not glossary_loaded and novel_name:
        try:
            from scripts.glossary_manager import GlossaryManager
            glossary = GlossaryManager(novel_name, auto_create=False)
            if glossary.names:  # Only use if glossary has entries
                glossary_text = glossary.get_glossary_text()
                glossary_loaded = True
                logger.info(f"Loaded glossary for novel '{novel_name}': {len(glossary.names)} names")
        except Exception as e:
            logger.warning(f"Failed to load novel glossary for '{novel_name}': {e}")
    
    # 3. Fallback to global names.json (always try this if nothing else worked)
    if not glossary_loaded:
        try:
            import os
            if os.path.exists("names.json"):
                with open("names.json", "r", encoding="utf-8") as f:
                    names = json.load(f)
                    if names:
                        glossary_text = "\n\nTERMINOLOGY MAPPING (Use these exact Burmese translations):\n"
                        for src, my in names.items():
                            glossary_text += f"- {src} -> {my}\n"
                        glossary_loaded = True
                        logger.info(f"Loaded global names.json: {len(names)} names")
        except Exception as e:
            logger.warning(f"Failed to load names.json: {e}")
    
    if not glossary_loaded:
        logger.warning("No glossary loaded - translations may have inconsistent names")

    prompt = f"""You are a skilled Burmese literary writer who is also fluent in {source_display}. Your goal is to translate the provided {source_display} novel text into natural, conversational, and emotionally resonant Burmese.

CRITICAL INSTRUCTIONS:
1. Translate in a conversational, modern Burmese tone. Avoid archaic or overly stiff/formal language.
2. Output ONLY the Burmese translation. NO English. NO {source_display}. NO filler phrases.
3. {style_note}
4. Do not summarize; translate everything contextually to preserve the "flavor" of the story.
5. Keep all Markdown formatting (headings, line breaks) intact.

STYLE RULES WITH EXAMPLES:

**1. DIALOGUE - Make it Sound Real**
- ❌ WRONG: "သင်သည် ဤနေရာသို့ အဘယ်ကြောင့် ရောက်ရှိလာသနည်း" ဟု သူမသည် မေးမြန်းလေသည်။
- ✅ RIGHT: "မင်း ဘာကြောင့် ဒီကို လာတာလဲ" လို့ သူမ မေးလိုက်တယ်
- Keep spoken words SHORT, DIRECT, and EMOTIONALLY HONEST
- Format: "..."လို့ [character] ပြောတယ် / မေးတယ် / တိုးတိုးပြောတယ်

**2. EMOTIONS - Show, Don't Tell**
- ❌ WRONG (describing): သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်
- ✅ RIGHT (showing): သူ့ရင်ထဲမှာ တစ်ခုခု နာကျင်နေသလိုပဲ။ မျက်ရည်တွေ မသိမသာ စီးကျလာတယ်
- Express feelings through PHYSICAL SENSATIONS and SHORT FRAGMENTED SENTENCES
- Example: chest tightening, hands trembling, tears falling, heart pounding

**3. SENTENCE STRUCTURE - Break Long Sentences**
- ❌ WRONG (one long sentence): သူသည် တောင်ထိပ်သို့ တက်ရောက်ရောက်ချင်း အနောက်ဘက်တွင် နေဝင်ရောင်ခြည်များ ထိုးဖောက်ကာ တောအုပ်ကြီးများပေါ်သို့ ရောင်ခြည်ကျရောက်လျက် တည်ရှိသောမြင်ကွင်းကို မြင်တွေ့ခဲ့ရသည်
- ✅ RIGHT (broken into 2-3 short sentences):
  တောင်ထိပ်ကို ရောက်တာနဲ့ သူ ရပ်မိသွားတယ်။
  နေဝင်ရောင်က တောအုပ်ကြီးကို ရွှေရောင်ဆိုးထားသလို ဖုံးလွှမ်းနေတယ်။
  လှပါတယ်။ ဒါပေမဲ့ ရင်ထဲမှာ တစ်ဆုပ်ကြည်ကြည်လည်း ဖြစ်မိတယ်။
- Break long sentences into 2-3 short sentences
- Each sentence should carry ONE idea or ONE image
- Short sentences create RHYTHM. Rhythm creates EMOTION.

**4. LANGUAGE - Modern and Conversational**
- ❌ AVOID ARCHAIC: သင်သည်၊ ထိုသို့သော၊ အလွန်မူ၊ ရှိပါသည်၊ ဟူ၍၊ ထိုသို့
- ✅ USE MODERN: မင်း၊ အဲ့လိုမျိုး၊ သိပ်ကို၊ ရှိတယ်၊ လို့၊ အဲ့ဒါကြောင့်
- Write the way a Burmese storyteller would tell it around a fire
- Make it feel like it was originally written in Burmese

**5. ACTION SCENES - Active Verbs**
- Use vivid, active verbs
- Avoid passive constructions
- Make the action immediate and visceral

**6. CULTURAL ADAPTATION**
- If a direct translation feels foreign, use a culturally familiar Burmese expression
- Keep the MEANING and EMOTION, not the literal words{glossary_text}

FINAL REMINDER: You are not a translation machine. You are a Burmese novelist retelling this story. Make the reader FEEL the story — don't just translate the words."""
    return prompt


class BaseTranslator(ABC):
    """Base class for all translators."""

    @abstractmethod
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Yield tokens as they arrive from API."""
        pass

    def translate(self, text: str, system_prompt: str) -> str:
        """Translate text and return the full result.

        Args:
            text: Text to translate
            system_prompt: System prompt for translation

        Returns:
            Complete translated text as a string

        Raises:
            ValueError: If text is empty or None
        """
        # Edge case: Handle empty or None text input
        if text is None:
            raise ValueError("Cannot translate None text")

        text = text.strip()
        if not text:
            logger.warning("Empty text provided for translation, returning empty string")
            return ""

        # Edge case: Handle very long text (warn but don't block)
        if len(text) > 50000:
            logger.warning(f"Very long text provided ({len(text)} chars), translation may take a while")

        return ''.join(self.translate_stream(text, system_prompt))
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return translator name."""
        pass


class OpenRouterTranslator(BaseTranslator):
    """OpenRouter - one key = many free models"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in .env")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/novel-translator",
            "X-Title": "Novel Translator"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": True
            # Note: max_tokens removed as some OpenRouter models (e.g., minimax) have provider-side issues with it
        }

        try:
            with managed_request('POST', url, json=payload, headers=headers, 
                               stream=True, timeout=300, verify=VERIFY_SSL) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        try:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                line_str = line_str[6:]
                                if line_str == '[DONE]':
                                    break
                                try:
                                    data = json.loads(line_str)
                                    if 'choices' in data and data['choices']:
                                        delta = data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            yield delta['content']
                                except json.JSONDecodeError:
                                    logger.debug(f"JSON decode error for line: {line_str[:50]}")
                                    continue
                        except UnicodeDecodeError as e:
                            logger.warning(f"Unicode decode error: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing stream line: {e}")
                            continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error in OpenRouter: {e}")
            if e.response is not None:
                try:
                    error_text = e.response.text
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    raise ValueError(f"OpenRouter API error: {error_msg}")
                except json.JSONDecodeError:
                    # Show raw error text if not JSON
                    error_text = e.response.text[:500] if e.response.text else str(e)
                    raise ValueError(f"OpenRouter API error: {error_text}")
            raise
        except requests.exceptions.Timeout:
            logger.error("Request timeout in OpenRouter")
            raise ValueError("Request timeout - the API took too long to respond")
        except requests.exceptions.ConnectionError:
            logger.error("Connection error in OpenRouter")
            raise ValueError("Connection error - please check your internet connection")
    
    @property
    def name(self) -> str:
        return f"openrouter ({self.model})"


class GeminiTranslator(BaseTranslator):
    """Google Gemini via AI Studio"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}"
        
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096  # Limit output tokens for consistency
            }
        }
        
        try:
            with managed_request('POST', url, json=payload, stream=True, 
                               timeout=300, verify=VERIFY_SSL) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        try:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                line_str = line_str[6:]
                            data = json.loads(line_str)
                            
                            # Handle API errors in response
                            if 'error' in data:
                                error_msg = data.get('error', {}).get('message', 'Unknown API error')
                                logger.error(f"Gemini API error: {error_msg}")
                                raise ValueError(f"Gemini API error: {error_msg}")
                            
                            if 'candidates' in data and data['candidates']:
                                candidate = data['candidates'][0]
                                # Check for safety blocks
                                if 'finishReason' in candidate and candidate['finishReason'] == 'SAFETY':
                                    logger.warning("Response blocked by safety settings")
                                    raise ValueError("Translation blocked by safety settings")
                                if 'content' in candidate and 'parts' in candidate['content']:
                                    for part in candidate['content']['parts']:
                                        if 'text' in part:
                                            yield part['text']
                        except (json.JSONDecodeError, KeyError, IndexError) as e:
                            logger.debug(f"Parse error in Gemini stream: {e}")
                            continue
                        except UnicodeDecodeError as e:
                            logger.warning(f"Unicode decode error: {e}")
                            continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error in Gemini: {e}")
            if e.response is not None:
                try:
                    error_text = e.response.text
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    raise ValueError(f"Gemini API error: {error_msg}")
                except json.JSONDecodeError:
                    # Show raw error text if not JSON
                    error_text = e.response.text[:500] if e.response.text else str(e)
                    raise ValueError(f"Gemini API error: {error_text}")
            raise
        except requests.exceptions.Timeout:
            logger.error("Request timeout in Gemini")
            raise ValueError("Request timeout - the API took too long to respond")
        except requests.exceptions.ConnectionError:
            logger.error("Connection error in Gemini")
            raise ValueError("Connection error - please check your internet connection")
    
    @property
    def name(self) -> str:
        return f"gemini ({self.model})"


class OllamaTranslator(BaseTranslator):
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen:7b")
        # Check if this is a cloud model that needs special handling
        self.is_cloud_model = ":cloud" in self.model or "kimi" in self.model.lower()
        # Get cloud API key if available
        self.cloud_api_key = os.getenv("OLLAMA_CLOUD_API_KEY", "")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        # Cloud models like kimi-k2.6:cloud work better with /api/generate endpoint
        if self.is_cloud_model:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{text}",
                "stream": True,
                "options": {
                    "temperature": 0.15,
                    "num_predict": -1,
                    "top_p": 0.9,
                    "top_k": 40
                }
            }
        else:
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "stream": True,
                "options": {
                    "temperature": 0.15,
                    "num_predict": -1,
                    "num_ctx": 8192,
                    "top_p": 0.9,
                    "top_k": 40
                }
            }
        
        # Prepare headers - cloud models may need authentication
        headers = {}
        if self.is_cloud_model and self.cloud_api_key:
            headers["Authorization"] = f"Bearer {self.cloud_api_key}"
        
        try:
            # Ollama is local, so we use verify=False and a shorter timeout
            with managed_request('POST', url, json=payload, stream=True, 
                               timeout=300, verify=False, headers=headers) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            # Check for errors
                            if 'error' in data:
                                error_msg = data['error']
                                logger.error(f"Ollama error: {error_msg}")
                                raise ValueError(f"Ollama error: {error_msg}")
                            
                            # Handle different response formats (chat vs generate)
                            if self.is_cloud_model:
                                # /api/generate format
                                if 'response' in data:
                                    yield data['response']
                            else:
                                # /api/chat format
                                if 'message' in data and 'content' in data['message']:
                                    yield data['message']['content']
                            
                            # Check for done signal
                            if data.get('done', False):
                                break
                        except json.JSONDecodeError as e:
                            logger.debug(f"JSON decode error in Ollama: {e}")
                            continue
                        except UnicodeDecodeError as e:
                            logger.warning(f"Unicode decode error: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing Ollama stream: {e}")
                            continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error in Ollama: {e}")
            # Special handling for cloud model 403 errors
            if e.response is not None and e.response.status_code == 403 and self.is_cloud_model:
                raise ValueError(
                    f"Cloud model '{self.model}' requires authentication.\n"
                    f"Please either:\n"
                    f"1. Set OLLAMA_CLOUD_API_KEY in your .env file\n"
                    f"2. Switch to a local model like 'qwen2.5:14b' or 'translategemma:12b'\n"
                    f"3. Use OpenRouter or Gemini API instead"
                )
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', str(e))
                    raise ValueError(f"Ollama API error: {error_msg}")
                except json.JSONDecodeError:
                    raise ValueError(f"Ollama API error: {e}")
            raise
        except requests.exceptions.Timeout:
            logger.error("Request timeout in Ollama")
            raise ValueError("Request timeout - Ollama took too long to respond. Check if model is loaded.")
        except requests.exceptions.ConnectionError:
            logger.error("Connection error in Ollama")
            raise ValueError(
                "Cannot connect to Ollama. Please ensure:\n"
                "1. Ollama is running (run 'ollama serve')\n"
                "2. The base URL is correct (current: {self.base_url})\n"
                "3. The model '{self.model}' is pulled (run 'ollama pull {self.model}')"
            )
    
    @property
    def name(self) -> str:
        return f"ollama ({self.model})"


class NLLBTranslator(BaseTranslator):
    """Facebook NLLB200 - No Language Left Behind (Local HuggingFace).
    
    Supports 200 languages including Chinese (Simplified/Traditional), English, and Myanmar.
    Uses facebook/nllb-200-distilled-600M or facebook/nllb-200-3.3B model.
    
    Requirements:
        pip install transformers torch sentencepiece sacremoses
    
    Environment Variables:
        NLLB_MODEL_SIZE: Model size (distilled-600M, 1.3B, 3.3B, or distilled-1.3B)
        NLLB_DEVICE: Device to use (cpu, cuda, auto)
        NLLB_MAX_LENGTH: Maximum tokens per translation (default: 512)
    """
    
    def __init__(self):
        self.model_size = os.getenv("NLLB_MODEL_SIZE", "distilled-600M")
        self.device = os.getenv("NLLB_DEVICE", "auto")
        self.max_length = int(os.getenv("NLLB_MAX_LENGTH", "512"))
        self.source_lang = os.getenv("SOURCE_LANGUAGE", "Chinese").lower()
        self.target_lang = os.getenv("TARGET_LANGUAGE", "Myanmar (Burmese)").lower()
        
        # Model name mapping
        model_names = {
            "distilled-600M": "facebook/nllb-200-distilled-600M",
            "1.3B": "facebook/nllb-200-1.3B",
            "3.3B": "facebook/nllb-200-3.3B",
            "distilled-1.3B": "facebook/nllb-200-distilled-1.3B",
        }
        self.model_name = model_names.get(self.model_size, "facebook/nllb-200-distilled-600M")
        
        # Determine device
        if self.device == "auto":
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self._tokenizer = None
        self._model = None
        self._load_model()
    
    def _load_model(self):
        """Lazy load the NLLB model and tokenizer with timeout protection."""
        if self._model is not None:
            return

        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"NLLB model loading timed out after 300 seconds (5 minutes)")

        # Set timeout for model loading (5 minutes)
        # Note: This only works on Unix systems; Windows will ignore signal-based timeouts
        has_timeout = hasattr(signal, 'SIGALRM')
        if has_timeout:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(300)  # 5 minutes

        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            import torch

            logger.info(f"Loading NLLB200 model: {self.model_name}")
            logger.info(f"Device: {self.device}")
            logger.info(f"This may take a few minutes on first run...")

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self._model.to(self.device)
            self._model.eval()

            logger.info(f"NLLB200 model loaded successfully")

        except ImportError as e:
            raise ValueError(
                f"Missing dependencies for NLLB. Install with:\n"
                f"pip install transformers torch sentencepiece sacremoses\n"
                f"Error: {e}"
            )
        except TimeoutError:
            logger.error("NLLB model loading timed out")
            raise ValueError(
                f"NLLB model loading timed out after 5 minutes.\n"
                f"This usually happens when downloading the model for the first time.\n"
                f"Please check your internet connection and try again."
            )
        except Exception as e:
            raise ValueError(f"Failed to load NLLB model: {e}")
        finally:
            # Cancel timeout
            if has_timeout:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
    
    def _get_lang_code(self, lang: str) -> str:
        """Get NLLB language code from language name."""
        lang_lower = lang.lower()
        
        # Direct mapping
        if lang_lower in NLLB_LANG_CODES:
            return NLLB_LANG_CODES[lang_lower]
        
        # Partial matches
        if "chinese" in lang_lower or "中文" in lang:
            return "zho_Hans"  # Default to simplified
        if "english" in lang_lower or "英文" in lang:
            return "eng_Latn"
        if "myanmar" in lang_lower or "burmese" in lang_lower or "မြန်မာ" in lang:
            return "mya_Mymr"
        
        # Default fallback
        logger.warning(f"Unknown language '{lang}', defaulting to Chinese")
        return "zho_Hans"
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for better translation quality."""
        import re
        
        # Split on sentence boundaries
        sentences = re.split(r'([。！？.!?\n]+)', text)
        
        # Rejoin punctuation with sentences
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])
            else:
                result.append(sentences[i])
        
        if len(sentences) % 2 == 1:
            result.append(sentences[-1])
        
        # Filter empty strings
        return [s.strip() for s in result if s.strip()]
    
    def _translate_batch(self, texts: List[str], src_lang: str, tgt_lang: str) -> List[str]:
        """Translate a batch of texts."""
        if not texts:
            return []

        try:
            import torch

            # NLLB requires source language token prepended to input text
            # Format: "<src_lang_code> <text>"
            prefixed_texts = [f"{src_lang} {text}" for text in texts]

            # Tokenize
            inputs = self._tokenizer(
                prefixed_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length
            ).to(self.device)

            # Set target language token - NLLB uses convert_tokens_to_ids for language codes
            forced_bos_token = self._tokenizer.convert_tokens_to_ids(tgt_lang)
            if forced_bos_token == self._tokenizer.unk_token_id:
                logger.warning(f"Unknown language code: {tgt_lang}, using Myanmar as fallback")
                forced_bos_token = self._tokenizer.convert_tokens_to_ids("mya_Mymr")

            logger.debug(f"Translating batch of {len(texts)} texts from {src_lang} to {tgt_lang}")

            # Generate translation
            with torch.no_grad():
                translated = self._model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token,
                    max_length=self.max_length,
                    num_beams=4,
                    early_stopping=True
                )

            # Decode
            results = self._tokenizer.batch_decode(translated, skip_special_tokens=True)

            # Log sample result for debugging
            if results and len(results) > 0:
                logger.debug(f"Sample translation result: {results[0][:100]}...")

            return results

        except Exception as e:
            logger.error(f"Batch translation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Return empty strings on error (don't return original texts)
            return [""] * len(texts)
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Translate text using NLLB200 with sentence-level streaming.
        
        NLLB doesn't use system prompts, so we ignore it.
        """
        src_lang = self._get_lang_code(self.source_lang)
        tgt_lang = self._get_lang_code(self.target_lang)
        
        # Split into sentences for better translation
        sentences = self._split_into_sentences(text)
        
        if not sentences:
            yield ""
            return
        
        logger.info(f"Translating {len(sentences)} sentences from {src_lang} to {tgt_lang}")
        
        # Translate in batches for efficiency
        batch_size = 4
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            translated_batch = self._translate_batch(batch, src_lang, tgt_lang)
            
            for translated in translated_batch:
                yield translated + " "
    
    def translate(self, text: str, system_prompt: str = "") -> str:
        """Translate text and return the full result (non-streaming)."""
        src_lang = self._get_lang_code(self.source_lang)
        tgt_lang = self._get_lang_code(self.target_lang)
        
        # For longer texts, split into chunks
        if len(text) > self.max_length * 3:
            sentences = self._split_into_sentences(text)
            translated_sentences = []
            
            batch_size = 4
            for i in range(0, len(sentences), batch_size):
                batch = sentences[i:i + batch_size]
                translated_batch = self._translate_batch(batch, src_lang, tgt_lang)
                translated_sentences.extend(translated_batch)
            
            return " ".join(translated_sentences)
        else:
            # Single batch for short texts
            results = self._translate_batch([text], src_lang, tgt_lang)
            return results[0] if results else ""
    
    @property
    def name(self) -> str:
        return f"nllb200 ({self.model_size})"


def get_translator(model_name: str) -> BaseTranslator:
    """Factory function to get translator by name."""
    translators = {
        'openrouter': OpenRouterTranslator,
        'gemini': GeminiTranslator,
        'ollama': OllamaTranslator,
        'nllb': NLLBTranslator,
        'nllb200': NLLBTranslator,
    }

    model_name = model_name.lower().strip()
    if model_name not in translators:
        raise ValueError(f"Unknown model: {model_name}. Choose from: {', '.join(translators.keys())}")

    return translators[model_name]()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python translator.py <model_name>")
        print(f"Available models: openrouter, gemini, ollama")
        sys.exit(1)
    
    model = sys.argv[1]
    translator = get_translator(model)
    print(f"Loaded translator: {translator.name}")
