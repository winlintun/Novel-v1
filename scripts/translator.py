#!/usr/bin/env python3
"""
Translation Engine - All model adapters with streaming
"""

import os
import json
import logging
import time
import requests
import urllib3
import warnings
from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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


def get_system_prompt(target_lang: str = "Myanmar (Burmese)", source_lang: str = "Chinese") -> str:
    """Get the optimized system prompt from AGENTS.md."""
    # Load glossary
    glossary_text = ""
    try:
        import json
        import os
        if os.path.exists("names.json"):
            with open("names.json", "r", encoding="utf-8") as f:
                names = json.load(f)
                if names:
                    glossary_text = "\n\nTERMINOLOGY MAPPING (Use these exact Burmese translations):\n"
                    for zh, my in names.items():
                        glossary_text += f"- {zh} -> {my}\n"
    except Exception as e:
        logger.warning(f"Failed to load names.json: {e}")

    prompt = f"""You are an expert literary translator specializing in Chinese to Myanmar (Burmese) translation.
CRITICAL INSTRUCTIONS:
1. Translate the provided Chinese text into MYANMAR LANGUAGE using Myanmar Unicode script.
2. Output ONLY the raw Burmese translation. NO filler. NO English. NO Chinese.
3. Maintain the literary style and tone of a xianxia/wuxia novel.
4. Do not summarize; translate everything contextually.
5. Keep all Markdown formatting (headings, line breaks) intact.{glossary_text}"""
    return prompt


class BaseTranslator(ABC):
    """Base class for all translators."""
    
    @abstractmethod
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Yield tokens as they arrive from API."""
        pass
    
    def translate(self, text: str, system_prompt: str) -> str:
        """Translate text and return the full result.
        
        This is a non-streaming wrapper around translate_stream.
        Collects all tokens and returns the complete translated text.
        
        Args:
            text: Text to translate
            system_prompt: System prompt for translation
            
        Returns:
            Complete translated text as a string
        """
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
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
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
        
        try:
            # Ollama is local, so we use verify=False and a shorter timeout
            with managed_request('POST', url, json=payload, stream=True, 
                               timeout=300, verify=False) as response:
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


def get_translator(model_name: str) -> BaseTranslator:
    """Factory function to get translator by name."""
    translators = {
        'openrouter': OpenRouterTranslator,
        'gemini': GeminiTranslator,
        'ollama': OllamaTranslator,
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
