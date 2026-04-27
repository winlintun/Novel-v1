"""
Ollama Client Module
Wrapper for Ollama API with retry logic, error handling, and proper resource cleanup.
Supports both /api/chat and /api/generate endpoints.
"""

import time
import logging
from typing import Iterator, Optional, Dict, Any
import ollama

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
        unload_on_cleanup: bool = False,
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
                # Unload model from GPU to free VRAM
                logger.info(f"Unloading model {self.model} from GPU...")
                try:
                    # Generate with keep_alive=0 to unload immediately
                    self.client.generate(
                        model=self.model,
                        prompt="",
                        keep_alive=0
                    )
                    logger.info(f"Model {self.model} unloaded from GPU")
                except Exception as e:
                    logger.warning(f"Could not unload model: {e}")
            
            self._is_connected = False
            logger.debug("OllamaClient cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during OllamaClient cleanup: {e}")
    
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False
    ) -> str:
        """
        Send chat request to Ollama with retry logic.
        Supports both /api/chat and /api/generate endpoints.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            stream: Whether to stream response
            
        Returns:
            Generated text response
        """
        for attempt in range(self.max_retries):
            try:
                # Adjust options based on model
                is_gemma = "gemma" in self.model.lower()
                
                # Use configurable num_ctx (default 8192 per need_fix.md)
                # and keep_alive (default 10m per need_fix.md)
                options = {
                    "temperature": self.temperature,
                    "num_predict": 1024 if is_gemma else 800,
                    "num_ctx": self.num_ctx,      # Configurable context window
                    "top_p": self.top_p,
                    "top_k": self.top_k,
                    "repeat_penalty": self.repeat_penalty
                }

                # Add GPU configuration if enabled
                if self.use_gpu:
                    if self.gpu_layers >= 0:
                        options["num_gpu"] = self.gpu_layers
                    options["main_gpu"] = self.main_gpu
                
                # Fixed: Support both /api/chat and /api/generate endpoints (per need_fix.md)
                if self.use_generate_endpoint:
                    # Use /api/generate for single-turn translation (no conversation history)
                    # This often yields more consistent results for pure translation tasks
                    full_prompt = ""
                    if system_prompt:
                        full_prompt = f"{system_prompt}\n\n"
                    full_prompt += prompt
                    
                    response = self.client.generate(
                        model=self.model,
                        prompt=full_prompt,
                        options=options,
                        keep_alive=self.keep_alive
                    )
                    # Bug fix: padauk-gemma outputs in 'thinking' field, fallback
                    raw_response = response['response']
                    if not raw_response and response.get('thinking'):
                        raw_response = response['thinking']
                    return raw_response
                else:
                    # Use /api/chat (default, maintains conversation history)
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    
                    response = self.client.chat(
                        model=self.model,
                        messages=messages,
                        options=options,
                        keep_alive=self.keep_alive
                    )
                    # Bug fix: padauk-gemma outputs in 'thinking' field, fallback
                    raw_content = response['message']['content']
                    if not raw_content and response['message'].get('thinking'):
                        raw_content = response['message']['thinking']
                    return raw_content
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for rate limit errors (429 Too Many Requests)
                is_rate_limit = (
                    '429' in error_msg or
                    'rate limit' in error_msg or
                    'too many requests' in error_msg or
                    'request limit' in error_msg
                )
                
                # Calculate wait time with jitter
                if is_rate_limit:
                    base_wait = 2 ** attempt * 2  # Double backoff for rate limits
                    import random
                    wait_time = base_wait + random.uniform(1, 3)  # Add jitter
                    logger.warning(f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). Waiting {wait_time:.1f}s...")
                else:
                    wait_time = 2 ** attempt + random.uniform(0.5, 1.5)  # Standard exponential backoff
                    logger.warning(f"Ollama call failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Ollama failed after {self.max_retries} attempts")
                    raise RuntimeError(f"Ollama API error after {self.max_retries} retries: {e}")
        
        return ""
    
    def chat_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Iterator[str]:
        """
        Stream chat response from Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Yields:
            Text chunks as they arrive
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            # Build options with GPU configuration
            stream_options = {
                "temperature": self.temperature,
                "num_predict": 2048,
                "num_ctx": self.num_ctx,      # Configurable context window
                "top_p": self.top_p,
                "top_k": self.top_k,
                "repeat_penalty": self.repeat_penalty
            }

            # Add GPU configuration if enabled
            if self.use_gpu:
                if self.gpu_layers >= 0:
                    stream_options["num_gpu"] = self.gpu_layers
                stream_options["main_gpu"] = self.main_gpu

            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options=stream_options,
                keep_alive=self.keep_alive  # Configurable keep_alive
            )
            
            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
    
    def check_model_available(self) -> bool:
        """Check if the configured model is available."""
        try:
            models = self.client.list()
            model_list = models.get('models', [])
            
            # Handle different API response formats
            available = []
            for m in model_list:
                # Try 'model' key first (newer API), then 'name' (older API)
                model_name = m.get('model') or m.get('name')
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
                keep_alive=0
            )
            logger.info(f"Model {self.model} unloaded from GPU")
            return True
        except Exception as e:
            logger.error(f"Failed to unload model: {e}")
            return False
