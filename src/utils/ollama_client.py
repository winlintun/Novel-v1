"""
Ollama Client Module
Wrapper for Ollama API with retry logic, error handling, and proper resource cleanup.
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
        unload_on_cleanup: bool = False
    ):
        """
        Initialize Ollama client.
        
        Args:
            model: Model name to use
            base_url: Ollama server URL
            temperature: Sampling temperature (0.5 recommended for Myanmar translation)
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            repeat_penalty: Penalty for token repetition (1.3-1.5 recommended for Myanmar)
            max_retries: Max retry attempts on failure
            timeout: Request timeout in seconds
            unload_on_cleanup: Whether to unload model from GPU on cleanup (frees VRAM)
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
        self._is_connected = False
        
        # Configure ollama client
        self.client = ollama.Client(host=base_url)
        self._is_connected = True
        logger.debug(f"OllamaClient initialized for model: {model}")
    
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
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            stream: Whether to stream response
            
        Returns:
            Generated text response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": self.temperature,
                        "num_predict": 800,   # Reduced for better Myanmar control
                        "top_p": self.top_p,
                        "top_k": self.top_k,
                        "repeat_penalty": self.repeat_penalty
                    },
                    keep_alive="5m"
                )
                
                return response['message']['content']
                
            except Exception as e:
                logger.warning(f"Ollama call failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Ollama failed after {self.max_retries} attempts")
                    raise RuntimeError(f"Ollama API error: {e}")
        
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
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options={
                    "temperature": self.temperature,
                    "num_predict": 2048,
                    "top_p": self.top_p,
                    "top_k": self.top_k,
                    "repeat_penalty": self.repeat_penalty
                },
                keep_alive="5m"
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
