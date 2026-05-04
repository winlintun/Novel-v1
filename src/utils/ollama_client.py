"""
Ollama Client Module
Wrapper for Ollama API with retry logic, error handling, and proper resource cleanup.
Supports both /api/chat and /api/generate endpoints.
"""

import time
import random
import logging
from typing import Iterator, Optional
import ollama

from src.exceptions import ModelError

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama LLM API with robust error handling and resource cleanup."""

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.5,
        top_p: float = 0.92,
        top_k: int = 50,
        repeat_penalty: float = 1.3,
        max_retries: int = 3,
        timeout: int = 300,
        unload_on_cleanup: bool = True,  # Default to True to free RAM after translation
        use_generate_endpoint: bool = False,  # New: Option to use /api/generate instead of /api/chat
        num_ctx: int = 8192,  # New: Configurable context window (default 8192 per need_fix.md)
        keep_alive: str = "10m",  # New: Configurable keep_alive (default 10m per need_fix.md)
        use_gpu: bool = True,  # New: Enable GPU acceleration
        gpu_layers: int = -1,  # New: Number of layers to offload to GPU (-1 = auto)
        main_gpu: int = 0  # New: Primary GPU device index
    ):
        """
        Initialize Ollama client.

        Args:
            model: Model name to use
            base_url: Ollama server URL
            temperature: Sampling temperature (0.2 recommended for Myanmar translation per need_fix.md)
            top_p: Nucleus sampling parameter (0.95 recommended per need_fix.md)
            top_k: Top-k sampling parameter
            repeat_penalty: Penalty for token repetition (1.0 recommended per need_fix.md)
            max_retries: Max retry attempts on failure
            timeout: Request timeout in seconds
            unload_on_cleanup: Whether to unload model from GPU on cleanup (frees VRAM)
            use_generate_endpoint: Whether to use /api/generate instead of /api/chat (per need_fix.md)
            num_ctx: Context window size (8192 recommended per need_fix.md)
            keep_alive: How long to keep model loaded ("10m" recommended per need_fix.md)
            use_gpu: Whether to use GPU acceleration (True = use GPU if available)
            gpu_layers: Number of model layers to offload to GPU (-1 = auto/all)
            main_gpu: Primary GPU device index for multi-GPU setups
        """
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.max_retries = max_retries
        self.timeout = timeout
        self.unload_on_cleanup = unload_on_cleanup
        self.use_generate_endpoint = use_generate_endpoint
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.use_gpu = use_gpu
        self.gpu_layers = gpu_layers
        self.main_gpu = main_gpu
        self._is_connected = False

        # Configure ollama client
        self.client = ollama.Client(host=base_url)
        self._is_connected = True

        # Log GPU configuration
        gpu_info = f"GPU: enabled (layers={gpu_layers}, main_gpu={main_gpu})" if use_gpu else "GPU: disabled (CPU only)"
        logger.debug(f"OllamaClient initialized for model: {model}, endpoint: {'/api/generate' if use_generate_endpoint else '/api/chat'}, num_ctx: {num_ctx}, {gpu_info}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.cleanup()
        return False

    def cleanup(self) -> None:
        """
        Cleanup resources and optionally unload model from GPU.
        
        This method should be called when translation is complete or
        when the client is no longer needed to free up memory.
        """
        if not self._is_connected:
            return

        try:
            if self.unload_on_cleanup:
                # Unload model from GPU/CPU to free RAM/VRAM
                logger.info(f"Unloading model {self.model} from memory to free RAM...")
                try:
                    # Method 1: Use API to unload this specific model
                    self._unload_model(self.model)

                    # Method 2: Also try to unload via direct API call with keep_alive=0
                    try:
                        import requests
                        response = requests.post(
                            f"{self.base_url}/api/generate",
                            json={
                                "model": self.model,
                                "prompt": "",
                                "keep_alive": 0,
                                "options": {"num_predict": 1}
                            },
                            timeout=10
                        )
                        if response.status_code == 200:
                            logger.info(f"Successfully sent unload request for {self.model}")
                    except Exception as api_err:
                        logger.debug(f"Direct API unload attempt: {api_err}")

                    logger.info(f"Model {self.model} unloaded from memory")
                except Exception as e:
                    logger.warning(f"Could not unload model: {e}")

            self._is_connected = False
            logger.debug("OllamaClient cleanup complete")

        except Exception as e:
            logger.error(f"Error during OllamaClient cleanup: {e}")

    def _unload_model(self, model_name: str) -> None:
        """
        Explicitly unload a model from Ollama memory.
        
        Args:
            model_name: Name of the model to unload
        """
        try:
            # Use the Ollama API to unload by setting keep_alive to 0
            self.client.generate(
                model=model_name,
                prompt="",
                keep_alive=0,
                options={"num_predict": 1, "timeout": min(self.timeout, 30)}
            )
            logger.info(f"Model {model_name} scheduled for unload")
        except Exception as e:
            logger.warning(f"Model unload API call failed: {e}")

    def unload_all_models(self) -> None:
        """
        Force unload all loaded models from Ollama to free all RAM.
        This is useful after batch translations or when memory is critical.
        """
        logger.info("Unloading all models from Ollama to free RAM...")
        try:
            import requests

            # Get list of loaded models
            try:
                response = requests.get(f"{self.base_url}/api/ps", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get('models', [])

                    for model_info in models:
                        model_name = model_info.get('name', '')
                        if model_name:
                            logger.info(f"Unloading model: {model_name}")
                            self._unload_model(model_name)
                else:
                    logger.warning(f"Could not get running models list: HTTP {response.status_code}")
            except Exception as e:
                logger.warning(f"Could not query running models: {e}")

            # Also try to unload the current model
            self._unload_model(self.model)

            logger.info("All models unload requests sent")

        except Exception as e:
            logger.error(f"Error unloading all models: {e}")

    def _get_fallback_model(self, current_model: str) -> Optional[str]:
        """
        Get a smaller/faster fallback model when primary model fails (OOM, timeout).
        
        Returns:
            Fallback model name or None if no fallback available
        """
        fallback_map = {
            "padauk-gemma:q8_0": "padauk-gemma:2b",
            "padauk-gemma:2b": "qwen:7b",
            "sailor2:20b": "sailor2:8b",
            "sailor2:8b": "qwen:7b",
            "qwen2.5:14b": "qwen:7b",
            "qwen2.5:7b": "qwen:7b",
            "qwen:14b": "qwen:7b",
            "alibayram/hunyuan:7b": "qwen:7b",
        }
        
        return fallback_map.get(current_model)

    @staticmethod
    def _extract_generate_response(response) -> str:
        """Extract text from generate response (dict or GenerateResponse object)."""
        # ollama >= 0.5 returns GenerateResponse object
        if hasattr(response, 'response'):
            return (getattr(response, 'response', '') or
                    getattr(response, 'thinking', ''))
        # older ollama returns dict
        if isinstance(response, dict):
            return response.get('response', '') or response.get('thinking', '')
        return str(response) if response else ''

    @staticmethod
    def _extract_chat_response(response) -> str:
        """Extract text from chat response (dict or ChatResponse object)."""
        # ollama >= 0.5 returns ChatResponse object
        if hasattr(response, 'message'):
            msg = getattr(response, 'message', None)
            if msg is not None:
                return (getattr(msg, 'content', '') or
                        getattr(msg, 'thinking', ''))
        # older ollama returns dict
        if isinstance(response, dict):
            msg = response.get('message', {})
            if isinstance(msg, dict):
                return msg.get('content', '') or msg.get('thinking', '')
        return str(response) if response else ''

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        model: Optional[str] = None
    ) -> str:
        """
        Send chat request to Ollama with retry + timeout + typed exceptions.
        Supports both /api/chat and /api/generate endpoints.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            stream: Whether to stream response (use chat_stream() instead)
            model: Override model name per-call (stateless — never mutates self.model)
            
        Returns:
            Generated text response
            
        Raises:
            ModelError: If all retries exhausted
        """
        effective_model = model if model else self.model

        for attempt in range(self.max_retries):
            try:
                # Adjust options based on model
                is_gemma = "gemma" in effective_model.lower()
                is_padauk = "padauk" in effective_model.lower()

                # Use configurable num_ctx (default 8192 per need_fix.md)
                # and keep_alive (default 10m per need_fix.md)
                options = {
                    "temperature": self.temperature,
                    "num_predict": 2048 if is_gemma or is_padauk else 1024,
                    "num_ctx": self.num_ctx,
                    "top_p": self.top_p,
                    "top_k": self.top_k,
                    "repeat_penalty": self.repeat_penalty,
                    "timeout": int(self.timeout),  # explicitly enforce timeout per AGENTS.md
                }

                # Add GPU configuration if enabled
                if self.use_gpu:
                    if self.gpu_layers >= 0:
                        options["num_gpu"] = self.gpu_layers
                    options["main_gpu"] = self.main_gpu

                # Fixed: Support both /api/chat and /api/generate endpoints (per need_fix.md)
                if self.use_generate_endpoint:
                    full_prompt = ""
                    if system_prompt:
                        full_prompt = f"{system_prompt}\n\n"
                    full_prompt += prompt

                    response = self.client.generate(
                        model=effective_model,
                        prompt=full_prompt,
                        options=options,
                        keep_alive=self.keep_alive
                    )
                    # Parse response: handles both dict (old) and object (ollama>=0.5)
                    raw_response = self._extract_generate_response(response)
                    return raw_response
                else:
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                    response = self.client.chat(
                        model=effective_model,
                        messages=messages,
                        options=options,
                        keep_alive=self.keep_alive
                    )
                    # Parse response: handles both dict (old) and object (ollama>=0.5)
                    raw_content = self._extract_chat_response(response)

                    # Auto-fallback: if chat endpoint returns empty, retry with generate endpoint
                    if not raw_content and not self.use_generate_endpoint:
                        logger.warning(
                            f"Chat endpoint returned empty content for {effective_model}. "
                            f"Model may lack chat template. Auto-falling back to /api/generate..."
                        )
                        full_prompt = ""
                        if system_prompt:
                            full_prompt = f"{system_prompt}\n\n"
                        full_prompt += prompt
                        fallback_resp = self.client.generate(
                            model=effective_model,
                            prompt=full_prompt,
                            options=options,
                            keep_alive=self.keep_alive
                        )
                        raw_content = self._extract_generate_response(fallback_resp)
                        if raw_content:
                            logger.info(f"Auto-fallback to /api/generate succeeded for {effective_model}")

                    return raw_content

            except (ConnectionError, ConnectionAbortedError, ConnectionRefusedError) as e:
                # Do NOT retry connection failures — raise immediately
                logger.error(f"Ollama unreachable: {e}")
                raise ModelError(f"Ollama connection failed: {e}") from e
            except Exception as e:
                error_msg = str(e).lower()

                # Check for specific error types
                is_timeout = (
                    'timeout' in error_msg or
                    'timed out' in error_msg or
                    'request timeout' in error_msg
                )

                is_rate_limit = (
                    '429' in error_msg or
                    'rate limit' in error_msg or
                    'too many requests' in error_msg or
                    'request limit' in error_msg
                )

                is_oom = (
                    'memory' in error_msg or
                    'out of memory' in error_msg or
                    'oom' in error_msg or
                    'cuda error' in error_msg
                )

                # Handle OOM - switch to smaller model immediately
                if is_oom and attempt < self.max_retries - 1:
                    fallback_model = self._get_fallback_model(effective_model)
                    if fallback_model and fallback_model != effective_model:
                        logger.warning(f"OOM detected with {effective_model}. Falling back to {fallback_model}...")
                        effective_model = fallback_model
                        attempt += 1
                        if attempt < self.max_retries:
                            logger.info(f"Retrying with fallback model in {2**(attempt-1):.1f}s...")
                            time.sleep(2 ** (attempt - 1) + random.uniform(0.5, 1.5))
                        continue

                # Calculate wait time with jitter based on error type
                if is_rate_limit:
                    base_wait = 2 ** attempt * 2
                    wait_time = base_wait + random.uniform(1, 3)
                    logger.warning(f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). Waiting {wait_time:.1f}s...")
                elif is_timeout:
                    wait_time = 2 ** attempt + random.uniform(1, 2)
                    logger.warning(f"Timeout detected (attempt {attempt + 1}/{self.max_retries}). Waiting {wait_time:.1f}s...")
                else:
                    wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
                    logger.warning(f"Ollama call failed (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Ollama failed after {self.max_retries} attempts")
                    raise ModelError(f"Ollama API error after {self.max_retries} retries on model {effective_model}: {e}") from e

        raise ModelError(f"Ollama failed after {self.max_retries} attempts on model {effective_model}")

    def chat_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None
    ) -> Iterator[str]:
        """
        Stream chat response from Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Override model name per-call (stateless)
            
        Yields:
            Text chunks as they arrive
        """
        effective_model = model if model else self.model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Build options with GPU configuration
            stream_options = {
                "temperature": self.temperature,
                "num_predict": 2048,
                "num_ctx": self.num_ctx,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "repeat_penalty": self.repeat_penalty,
                "timeout": int(self.timeout),
            }

            # Add GPU configuration if enabled
            if self.use_gpu:
                if self.gpu_layers >= 0:
                    stream_options["num_gpu"] = self.gpu_layers
                stream_options["main_gpu"] = self.main_gpu

            stream = self.client.chat(
                model=effective_model,
                messages=messages,
                stream=True,
                options=stream_options,
                keep_alive=self.keep_alive
            )

            for chunk in stream:
                try:
                    content = self._extract_chat_response(chunk)
                    if content:
                        yield content
                except Exception:
                    continue

        except (ConnectionError, ConnectionAbortedError, ConnectionRefusedError) as e:
            logger.error(f"Ollama streaming connection error: {e}")
            raise ModelError(f"Ollama connection failed during streaming: {e}") from e
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise ModelError(f"Ollama streaming error: {e}") from e

    def check_model_available(self) -> bool:
        """Check if the configured model is available."""
        try:
            models = self.client.list()
            # Handle both dict (old) and ListResponse object (ollama>=0.5)
            if hasattr(models, 'models'):
                model_list = getattr(models, 'models', [])
            elif isinstance(models, dict):
                model_list = models.get('models', [])
            else:
                model_list = []

            available = []
            for m in model_list:
                if hasattr(m, 'model'):
                    model_name = getattr(m, 'model', '') or getattr(m, 'name', '')
                elif isinstance(m, dict):
                    model_name = m.get('model') or m.get('name')
                else:
                    model_name = str(m)
                if model_name:
                    available.append(model_name)

            if self.model in available:
                return True
            else:
                logger.warning(f"Model '{self.model}' not found. Available: {available}")
                return False

        except Exception as e:
            logger.error(f"Cannot connect to Ollama: {e}")
            return False

    def unload_model(self) -> bool:
        """
        Explicitly unload model from GPU to free VRAM.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Unloading model {self.model} from GPU...")
            self.client.generate(
                model=self.model,
                prompt="",
                keep_alive=0,
                options={"num_predict": 1, "timeout": min(self.timeout, 30)}
            )
            logger.info(f"Model {self.model} unloaded from GPU")
            return True
        except Exception as e:
            logger.error(f"Failed to unload model: {e}")
            return False
