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
    """Get the optimized system prompt with clear identity and task definition.
    
    Based on translation best practices:
    - Clear identity: Professional literary translator fluent in Chinese and Burmese
    - Specific task: Chinese web novel translation
    - Strict output constraints to prevent hallucination
    """
    # Load glossary
    glossary_text = ""
    try:
        import json
        import os
        if os.path.exists("names.json"):
            with open("names.json", "r", encoding="utf-8") as f:
                names = json.load(f)
                if names:
                    glossary_text = "\n\nTERMINOLOGY MAPPING (Use these exact Burmese translations for names and terms):\n"
                    for zh, my in names.items():
                        glossary_text += f"- {zh} -> {my}\n"
    except Exception as e:
        logger.warning(f"Failed to load names.json: {e}")

    prompt = f"""You are a professional literary translator fluent in Chinese and Burmese, specializing in Chinese web novels (xianxia/cultivation genre).

TASK:
Translate the following Chinese novel excerpt into Burmese.

REQUIREMENTS:
1. Maintain the original literary style, emotional tone, and narrative voice of the Chinese text
2. Ensure terminology is consistent throughout (use the TERMINOLOGY MAPPING provided)
3. Translate cultivation terms, idioms (Chengyu), and genre-specific expressions contextually so they sound natural in Burmese
4. Translate character and place names using the provided TERMINOLOGY MAPPING
5. Output ONLY the Burmese translation - no explanations, notes, greetings, or meta-text
6. Use Myanmar Unicode script exclusively - NO English, NO Chinese, NO romanization
7. Do NOT add chapter titles, headings, or any conversational intro/outro text
8. If you cannot translate, respond only with: ဘာသာပြန်မရပါ

OUTPUT FORMAT:
- Provide ONLY the translated Burmese text
- No "Here is the translation" or similar phrases
- No markdown formatting unless present in original{glossary_text}"""
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


class DeepSeekTranslator(BaseTranslator):
    """DeepSeek Chat"""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not set in .env")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": True,
            "max_tokens": 4096  # Limit output tokens to avoid context window overflow
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
                                    # Check for API errors in stream
                                    if 'error' in data:
                                        error_msg = data['error'].get('message', 'Unknown API error')
                                        logger.error(f"DeepSeek API error: {error_msg}")
                                        raise ValueError(f"DeepSeek API error: {error_msg}")
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
            logger.error(f"HTTP error in DeepSeek: {e}")
            if e.response is not None:
                try:
                    error_text = e.response.text
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    raise ValueError(f"DeepSeek API error: {error_msg}")
                except json.JSONDecodeError:
                    # Show raw error text if not JSON
                    error_text = e.response.text[:500] if e.response.text else str(e)
                    raise ValueError(f"DeepSeek API error: {error_text}")
            raise
        except requests.exceptions.Timeout:
            logger.error("Request timeout in DeepSeek")
            raise ValueError("Request timeout - the API took too long to respond")
        except requests.exceptions.ConnectionError:
            logger.error("Connection error in DeepSeek")
            raise ValueError("Connection error - please check your internet connection")
    
    @property
    def name(self) -> str:
        return f"deepseek ({self.model})"


class QwenTranslator(BaseTranslator):
    """Alibaba Qwen via DashScope"""
    
    def __init__(self):
        self.api_key = os.getenv("QWEN_API_KEY")
        self.model = os.getenv("QWEN_MODEL", "qwen-max")
        
        if not self.api_key:
            raise ValueError("QWEN_API_KEY not set in .env")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": True,
            "max_tokens": 4096  # Limit output tokens to avoid context window overflow
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
            logger.error(f"HTTP error in Qwen: {e}")
            if e.response is not None:
                try:
                    error_text = e.response.text
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    raise ValueError(f"Qwen API error: {error_msg}")
                except json.JSONDecodeError:
                    # Show raw error text if not JSON
                    error_text = e.response.text[:500] if e.response.text else str(e)
                    raise ValueError(f"Qwen API error: {error_text}")
            raise
        except requests.exceptions.Timeout:
            logger.error("Request timeout in Qwen")
            raise ValueError("Request timeout - the API took too long to respond")
        except requests.exceptions.ConnectionError:
            logger.error("Connection error in Qwen")
            raise ValueError("Connection error - please check your internet connection")
    
    @property
    def name(self) -> str:
        return f"qwen ({self.model})"


class OllamaTranslator(BaseTranslator):
    def get_ollama_system_prompt(self, source_lang: str = "Chinese", target_lang: str = "Burmese") -> str:
        glossary_text = ""
        try:
            import json
            import os
            if os.path.exists("names.json"):
                with open("names.json", "r", encoding="utf-8") as f:
                    names = json.load(f)
                    if names:
                        glossary_text = "\n\nTERMINOLOGY MAPPING (Use these exact Burmese translations for names and specific terms):\n"
                        for zh, my in names.items():
                            glossary_text += f"- {zh} -> {my}\n"
        except Exception as e:
            logger.warning(f"Failed to load names.json for Ollama prompt: {e}")

        prompt = f"""You are an expert literary translator specializing in {source_lang} to {target_lang} translation, specifically for xianxia/cultivation novels.
Your goal is to accurately convey the meaning, tone, style, and emotions of the original Chinese text while adhering to Burmese grammar, vocabulary, and cultural sensitivities.

CRITICAL INSTRUCTIONS:
1. Translate the following Chinese text into MYANMAR LANGUAGE (Burmese) using Myanmar Unicode script.
2. Output MUST contain ONLY Myanmar characters and punctuation. NO English. NO Chinese. NO romanization.
3. Maintain the literary tone, style, and emotional depth of the original Chinese xianxia novel. Do not summarize or simplify.
4. Translate cultivation terms, idioms (Chengyu), and specific genre expressions contextually so they sound natural and appropriate in Burmese xianxia literature. Avoid literal word-for-word translation if it compromises literary flow or meaning.
5. Use the provided TERMINOLOGY MAPPING for character names, place names, and specific terms. If a term is in the mapping, you MUST use its exact Burmese translation.
6. Do NOT add any chapter titles, headings, explanations, or introductory/concluding remarks. Provide only the translated text.
7. If you encounter untranslatable content or are unsure, respond with "ဘာသာပြန်မရပါ" (cannot translate) and nothing else.

Here are a few examples to guide your translation style and ensure high quality:

Example 1 (Chinese):
罗青深吸一口气，眼中闪过一丝坚定。他知道，这条修仙之路，注定坎坷不平。
Example 1 (Burmese):
လော်ချင်သည် လေကိုပြင်းပြင်းရှူသွင်းလိုက်ပြီး မျက်လုံးထဲတွင် ခိုင်မာသောအရိပ်အယောင်တစ်ခု ဖြတ်ပြေးသွားသည်။ ဤကျင့်ကြံခြင်းလမ်းကြောင်းသည် ကြမ်းတမ်းခက်ခဲမည်ကို သူသိသည်။

Example 2 (Chinese):
“小六子，你可愿随我一同前往月波湖，探寻那传说中的灵药？”古堂主抚须笑道。
Example 2 (Burmese):
“ရှောင်လျိုဇီ၊ မင်းငါနဲ့အတူ လအိုင်ကိုသွားပြီး ဒဏ္ဍာရီလာဆေးဖက်ဝင်အပင်ကို ရှာဖွေချင်သလား” ဂိုဏ်းခွဲမှူး ကု က မုတ်ဆိတ်သပ်ရင်း ရယ်မောပြောဆိုလိုက်သည်။

Now, translate the following Chinese text into Burmese:
"""
        return prompt
    
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        url = f"{self.base_url}/api/chat"
        
        ollama_system_prompt = self.get_ollama_system_prompt()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": ollama_system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": True,
            "options": {
                "temperature": 0.15,   # Changed from 0.3 for higher accuracy
                "num_predict": -1,
                "num_ctx": 8192,       # Added to prevent context overflow
                "top_p": 0.9,          # Added for better sampling
                "top_k": 40            # Added for better sampling
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
        'deepseek': DeepSeekTranslator,
        'qwen': QwenTranslator,
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
        print(f"Available models: openrouter, gemini, deepseek, qwen, ollama")
        sys.exit(1)
    
    model = sys.argv[1]
    translator = get_translator(model)
    print(f"Loaded translator: {translator.name}")
