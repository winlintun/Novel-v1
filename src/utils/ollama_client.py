"""
Ollama Client Module
Wrapper for Ollama API with retry logic and error handling.
"""

import time
import logging
from typing import Iterator, Optional, Dict, Any
import ollama

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama LLM API with robust error handling."""
    
    def __init__(
        self,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        max_retries: int = 3,
        timeout: int = 300
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Configure ollama client
        self.client = ollama.Client(host=base_url)
    
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
                        "num_predict": 4096,
                        "top_p": 0.92,
                        "top_k": 50,
                        "repeat_penalty": 1.1
                    }
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
                    "num_predict": 4096
                }
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
