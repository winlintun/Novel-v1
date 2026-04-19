#!/usr/bin/env python3
"""
Translation Engine - All model adapters with streaming
"""

import os
import json
import requests
import urllib3
import warnings
from abc import ABC, abstractmethod
from typing import Iterator, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# SSL verification setting - only disable for local Ollama
# Set VERIFY_SSL=false in .env only if you have certificate issues
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() != "false"

# Disable SSL warnings only if verification is disabled
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn("SSL verification is disabled. This is insecure and should only be used for local development.", RuntimeWarning)


def get_system_prompt(target_lang: str = "Myanmar (Burmese)", source_lang: str = "Chinese") -> str:
    """Get the shared system prompt template."""
    return f"""You are an expert literary translator specializing in {source_lang} to {target_lang} translation.
Translate the following Chinese xianxia/cultivation novel text into Myanmar language using Myanmar Unicode characters.

CRITICAL INSTRUCTIONS:
1. You MUST translate into MYANMAR LANGUAGE (Burmese) using Myanmar Unicode script
2. Example of correct output: "ရှေးခေတ်လမ်းကြောင်းပေါ်တွင် လူသားများသည်..."
3. Example of WRONG output: "The ancient path was where humans..." (English is NOT acceptable)
4. Example of WRONG output: "古代的道路上，人类..." (Chinese is NOT acceptable)
5. Your output MUST contain Myanmar characters like: က ခ ဂ ဃ င စ ဆ ဇ ဈ ဉ ည ဋ ဌ ဍ ဎ ဏ တ ထ ဒ ဓ န ပ ဖ ဗ ဘ မ ယ ရ လ ဝ ဠ ဟ အ

Rules:
1. Translate the entire text into Myanmar (Burmese) language
2. Preserve the narrator's tone, style, and emotion exactly
3. Keep character names in Pinyin (罗青 → Luo Qing)
4. Keep place names in Pinyin with Myanmar suffix
5. Translate cultivation terms meaningfully with context
6. Output ONLY the translated Myanmar text
7. No commentary, no explanations, no notes
8. If you cannot translate, respond with "ဘာသာပြန်မရပါ" (cannot translate)"""


class BaseTranslator(ABC):
    """Base class for all translators."""
    
    @abstractmethod
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Yield tokens as they arrive from API."""
        pass
    
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
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=300, verify=VERIFY_SSL)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
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
                        continue
    
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
            "generationConfig": {"temperature": 0.3}
        }
        
        response = requests.post(url, json=payload, stream=True, timeout=300, verify=VERIFY_SSL)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        line_str = line_str[6:]
                    data = json.loads(line_str)
                    
                    if 'candidates' in data and data['candidates']:
                        candidate = data['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            for part in candidate['content']['parts']:
                                if 'text' in part:
                                    yield part['text']
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    
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
            "stream": True
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=300, verify=VERIFY_SSL)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
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
                        continue
    
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
            "stream": True
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=300, verify=VERIFY_SSL)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
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
                        continue
    
    @property
    def name(self) -> str:
        return f"qwen ({self.model})"


class OllamaTranslator(BaseTranslator):
    """Ollama Local - no API key needed"""
    
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    
    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": True
        }
        
        response = requests.post(url, json=payload, stream=True, timeout=300, verify=False)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if 'message' in data and 'content' in data['message']:
                        yield data['message']['content']
                except json.JSONDecodeError:
                    continue
    
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
