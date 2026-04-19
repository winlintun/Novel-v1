"""
╔══════════════════════════════════════════════════════════╗
║           Novel Translator - Chinese to Myanmar          ║
║  Supports: Gemini | DeepSeek | Qwen | OpenCode | Ollama  ║
║     Switch via .env file - All with streaming support    ║
╚══════════════════════════════════════════════════════════╝

Usage:
    python translator.py input.md
    python translator.py input.md --output output.md
    python translator.py input.md --model deepseek
    python translator.py input.md --chunk-size 20 --stream
"""

import os
import sys
import time
import json
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import Iterator, Optional

# Load .env file
load_dotenv()

# ─────────────────────────────────────────────
# ANSI Colors for terminal output
# ─────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def info(msg):    print(f"{CYAN}[INFO]{RESET} {msg}")
def success(msg): print(f"{GREEN}[OK]{RESET} {msg}")
def warn(msg):    print(f"{YELLOW}[WARN]{RESET} {msg}")
def error(msg):   print(f"{RED}[ERROR]{RESET} {msg}")
def stream_msg(msg): print(f"{BLUE}[STREAM]{RESET} {msg}", end='', flush=True)


# ─────────────────────────────────────────────
# SYSTEM PROMPT for translation
# ─────────────────────────────────────────────
def get_system_prompt(target_lang: str, source_lang: str) -> str:
    return f"""You are an expert literary translator specializing in {source_lang} to {target_lang} translation.
You are translating a Chinese xianxia/cultivation fantasy novel.

Rules:
1. Translate naturally and fluently into {target_lang} so readers enjoy it
2. Keep the narrator's casual, humorous, lively tone intact
3. Preserve Chinese character names in Pinyin (e.g., 罗青 → Luo Qing)
4. Preserve place names in Pinyin (e.g., 小戎镇 → Xiaorong Town)
5. Keep cultivation/xianxia terms meaningful (translate with context)
6. Do NOT add explanations or notes — just translate
7. Keep paragraph structure identical to the original
8. Return ONLY the translated text, nothing else"""


# ─────────────────────────────────────────────
# MODEL ADAPTERS with STREAMING SUPPORT
# ─────────────────────────────────────────────

class GeminiTranslator:
    """Google Gemini via REST API - Free in AI Studio - with streaming"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY not set in .env file!\nGet free key: https://aistudio.google.com/app/apikey")

    def translate(self, text: str, system_prompt: str) -> str:
        """Non-streaming translation"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192}
        }
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected Gemini response: {data}") from e

    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Streaming translation - yields tokens as they arrive"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192}
        }
        
        response = requests.post(url, json=payload, timeout=120, stream=True)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    # Gemini streams JSON objects
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
    def name(self): return f"Gemini ({self.model})"


class DeepSeekTranslator:
    """DeepSeek via OpenAI-compatible API - Free tier available - with streaming"""

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if not self.api_key or self.api_key == "your_deepseek_api_key_here":
            raise ValueError("DEEPSEEK_API_KEY not set in .env file!\nGet free key: https://platform.deepseek.com/api_keys")

    def translate(self, text: str, system_prompt: str) -> str:
        """Non-streaming translation"""
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected DeepSeek response: {data}") from e

    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Streaming translation - yields tokens as they arrive"""
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
            "stream": True
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
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
    def name(self): return f"DeepSeek ({self.model})"


class QwenTranslator:
    """Alibaba Qwen via DashScope API - Free tier available - with streaming"""

    def __init__(self):
        self.api_key = os.getenv("QWEN_API_KEY", "")
        self.model   = os.getenv("QWEN_MODEL", "qwen-max")
        if not self.api_key or self.api_key == "your_qwen_api_key_here":
            raise ValueError("QWEN_API_KEY not set in .env file!\nGet free key: https://dashscope.aliyun.com/")

    def translate(self, text: str, system_prompt: str) -> str:
        """Non-streaming translation"""
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected Qwen response: {data}") from e

    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Streaming translation - yields tokens as they arrive"""
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
            "stream": True
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
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
    def name(self): return f"Qwen ({self.model})"


class OpenCodeTranslator:
    """OpenCode AI - with streaming support"""

    def __init__(self):
        self.api_key = os.getenv("OPENCODE_API_KEY", "")
        if not self.api_key or self.api_key == "your_opencode_api_key_here":
            raise ValueError("OPENCODE_API_KEY not set in .env file!\nGet key: https://opencode.ai/workspace/")

    def translate(self, text: str, system_prompt: str) -> str:
        """Non-streaming translation"""
        url = "https://opencode.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "opencode-default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected OpenCode response: {data}") from e

    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Streaming translation - yields tokens as they arrive"""
        url = "https://opencode.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "opencode-default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
            "stream": True
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
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
    def name(self): return "OpenCode AI"


class OpenRouterTranslator:
    """OpenRouter - Access to multiple models - with streaming"""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            raise ValueError("OPENROUTER_API_KEY not set in .env file!\nGet key: https://openrouter.ai/workspaces/default/keys")

    def translate(self, text: str, system_prompt: str) -> str:
        """Non-streaming translation"""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected OpenRouter response: {data}") from e

    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Streaming translation - yields tokens as they arrive"""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
            "stream": True
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
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
    def name(self): return f"OpenRouter ({self.model})"


class OllamaTranslator:
    """Ollama - Local or Cloud - with streaming support"""

    def __init__(self):
        self.model = os.getenv("OLLAMA_MODEL", "qwen:7b")
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        
        # Test connection
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            resp.raise_for_status()
        except Exception as e:
            warn(f"Could not connect to Ollama at {self.host}: {e}")

    def translate(self, text: str, system_prompt: str) -> str:
        """Non-streaming translation"""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": text,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": -1
            }
        }
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    def translate_stream(self, text: str, system_prompt: str) -> Iterator[str]:
        """Streaming translation - yields tokens as they arrive"""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": text,
            "stream": True,
            "options": {
                "temperature": 0.3,
                "num_predict": -1
            }
        }
        
        response = requests.post(url, json=payload, timeout=300, stream=True)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if 'response' in data:
                        yield data['response']
                except json.JSONDecodeError:
                    continue

    @property
    def name(self): return f"Ollama ({self.model})"


# ─────────────────────────────────────────────
# MODEL FACTORY
# ─────────────────────────────────────────────

MODELS = {
    "gemini":      GeminiTranslator,
    "deepseek":    DeepSeekTranslator,
    "qwen":        QwenTranslator,
    "opencode":    OpenCodeTranslator,
    "openrouter":  OpenRouterTranslator,
    "ollama":      OllamaTranslator,
}

def get_translator(model_name: str):
    model_name = model_name.lower().strip()
    if model_name not in MODELS:
        raise ValueError(f"Unknown model '{model_name}'. Choose from: {', '.join(MODELS.keys())}")
    return MODELS[model_name]()


# ─────────────────────────────────────────────
# TEXT CHUNKING
# ─────────────────────────────────────────────

def chunk_lines(lines: list, chunk_size: int) -> list:
    """Split lines into chunks for API calls"""
    chunks = []
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i:i + chunk_size]
        chunks.append("\n".join(chunk))
    return chunks


# ─────────────────────────────────────────────
# MAIN TRANSLATION FUNCTION with STREAMING
# ─────────────────────────────────────────────

def translate_file(
    input_path: str,
    output_path: str = None,
    model_name: str = None,
    chunk_size: int = None,
    delay: float = None,
    stream: bool = True,
    checkpoint_file: str = None
):
    # Load settings (CLI args override .env)
    model_name = model_name or os.getenv("AI_MODEL", "gemini")
    chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "30"))
    delay      = delay or float(os.getenv("REQUEST_DELAY", "1"))
    target_lang = os.getenv("TARGET_LANGUAGE", "Myanmar (Burmese)")
    source_lang = os.getenv("SOURCE_LANGUAGE", "Chinese")
    output_dir  = os.getenv("OUTPUT_DIR", "translated")

    # Default output path
    if not output_path:
        input_stem = Path(input_path).stem
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{input_stem}_myanmar.md")

    # Print header
    print(f"\n{BOLD}{'═'*70}{RESET}")
    print(f"{BOLD}   Novel Translator: {source_lang} → {target_lang}{RESET}")
    print(f"{BOLD}   Model: {model_name} | Streaming: {'ON' if stream else 'OFF'}{RESET}")
    print(f"{BOLD}{'═'*70}{RESET}")

    # Load translator
    info(f"Loading model: {BOLD}{model_name}{RESET}")
    try:
        translator = get_translator(model_name)
        success(f"Using: {translator.name}")
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    # Read input file
    info(f"Reading: {input_path}")
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        error(f"File not found: {input_path}")
        sys.exit(1)

    lines = content.split("\n")
    total_lines = len(lines)
    info(f"Total lines: {total_lines} | Chunk size: {chunk_size} lines")

    # Create chunks
    chunks = chunk_lines(lines, chunk_size)
    total_chunks = len(chunks)
    info(f"Total chunks: {total_chunks}")
    print(f"{BOLD}{'─'*70}{RESET}\n")

    # System prompt
    system_prompt = get_system_prompt(target_lang, source_lang)

    # Load checkpoint if exists
    start_chunk = 1
    if checkpoint_file and os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            start_chunk = checkpoint.get('last_completed_chunk', 0) + 1
            info(f"Resuming from chunk {start_chunk}")
        except Exception as e:
            warn(f"Could not load checkpoint: {e}")

    # Translate chunk by chunk
    translated_chunks = []
    failed_chunks = []

    for i in range(start_chunk - 1, total_chunks):
        chunk_num = i + 1
        chunk = chunks[i]
        chunk_preview = chunk[:60].replace("\n", " ").strip()
        
        print(f"\n{BOLD}[{chunk_num}/{total_chunks}]{RESET} Translating chunk...")
        print(f"   Preview: {chunk_preview}...")

        try:
            if stream and hasattr(translator, 'translate_stream'):
                # Streaming translation
                translated_text = ""
                token_count = 0
                char_count = 0
                
                print(f"   {CYAN}Streaming:{RESET} ", end='', flush=True)
                
                for token in translator.translate_stream(chunk, system_prompt):
                    translated_text += token
                    token_count += 1
                    char_count += len(token)
                    
                    # Print token to terminal
                    print(token, end='', flush=True)
                    
                    # Print progress every 50 tokens
                    if token_count % 50 == 0:
                        print(f"\n   {YELLOW}... [{char_count} chars]{RESET} ", end='', flush=True)
                
                print()  # New line after streaming
                translated_chunks.append(translated_text)
                success(f"Chunk {chunk_num} complete: {char_count} chars, {token_count} tokens")
            else:
                # Non-streaming translation
                result = translator.translate(chunk, system_prompt)
                translated_chunks.append(result)
                success(f"Chunk {chunk_num} done ✓")
        
        except requests.exceptions.HTTPError as e:
            error(f"HTTP Error on chunk {chunk_num}: {e}")
            failed_chunks.append(chunk_num)
            translated_chunks.append(f"[TRANSLATION FAILED - Chunk {chunk_num}]\n{chunk}")
        except requests.exceptions.Timeout:
            error(f"Timeout on chunk {chunk_num} - keeping original")
            failed_chunks.append(chunk_num)
            translated_chunks.append(f"[TIMEOUT - Chunk {chunk_num}]\n{chunk}")
        except Exception as e:
            error(f"Error on chunk {chunk_num}: {e}")
            failed_chunks.append(chunk_num)
            translated_chunks.append(f"[ERROR - Chunk {chunk_num}]\n{chunk}")

        # Save checkpoint after each chunk
        if checkpoint_file:
            try:
                checkpoint = {
                    'last_completed_chunk': chunk_num,
                    'total_chunks': total_chunks,
                    'failed_chunks': failed_chunks,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                with open(checkpoint_file, 'w') as f:
                    json.dump(checkpoint, f, indent=2)
            except Exception as e:
                warn(f"Could not save checkpoint: {e}")

        # Delay between requests
        if chunk_num < total_chunks:
            time.sleep(delay)

    # Write output
    print(f"\n{BOLD}{'─'*70}{RESET}")
    info(f"Writing output: {output_path}")

    header = f"# {Path(input_path).stem} - Myanmar Translation\n"
    header += f"# Translated by: {translator.name}\n"
    header += f"# Source: {input_path}\n\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n\n".join(translated_chunks))

    # Summary
    print(f"\n{BOLD}{'═'*70}{RESET}")
    success(f"Translation complete!")
    info(f"Output: {BOLD}{output_path}{RESET}")
    info(f"Chunks: {total_chunks - len(failed_chunks)}/{total_chunks} successful")
    if failed_chunks:
        warn(f"Failed chunks: {failed_chunks} (kept original text)")
    print(f"{BOLD}{'═'*70}{RESET}\n")


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Translate Chinese novels to Myanmar using free AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python translator.py chapter_001.md
  python translator.py chapter_001.md --model deepseek
  python translator.py chapter_001.md --model qwen --stream
  python translator.py chapter_001.md --checkpoint checkpoint.json

Available models (set in .env or pass --model):
  gemini     → Google Gemini 2.0 Flash (default, best free option)
  deepseek   → DeepSeek Chat (great Chinese understanding)
  qwen       → Alibaba Qwen Max (native Chinese AI)
  opencode   → OpenCode AI
  openrouter → OpenRouter (multiple models)
  ollama     → Ollama (local/cloud)
        """
    )
    parser.add_argument("input",        help="Input .md or .txt file path")
    parser.add_argument("--output",     help="Output file path (optional)")
    parser.add_argument("--model",      choices=list(MODELS.keys()),
                        help="AI model to use (overrides .env AI_MODEL)")
    parser.add_argument("--chunk-size", type=int,
                        help="Lines per API call (overrides .env CHUNK_SIZE)")
    parser.add_argument("--delay",      type=float,
                        help="Seconds between requests (overrides .env REQUEST_DELAY)")
    parser.add_argument("--stream",     action="store_true", default=True,
                        help="Enable streaming output (default: True)")
    parser.add_argument("--no-stream",  action="store_false", dest="stream",
                        help="Disable streaming")
    parser.add_argument("--checkpoint", help="Checkpoint file for resumable translation")

    args = parser.parse_args()

    translate_file(
        input_path     = args.input,
        output_path    = args.output,
        model_name     = args.model,
        chunk_size     = args.chunk_size,
        delay          = args.delay,
        stream         = args.stream,
        checkpoint_file = args.checkpoint
    )

if __name__ == "__main__":
    main()
