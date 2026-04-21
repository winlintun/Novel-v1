#!/usr/bin/env python3
"""
Pydantic-based Configuration Schema Validation

This module provides type-safe configuration management with validation
using Pydantic models.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, validator
from pathlib import Path
import json


class MyanmarReadabilityConfig(BaseModel):
    """Configuration for Myanmar readability checking."""
    
    enabled: bool = Field(default=True, description="Enable readability checking")
    min_myanmar_ratio: float = Field(
        default=0.7, 
        ge=0.0, 
        le=1.0,
        description="Minimum ratio of Myanmar characters required"
    )
    flag_on_fail: bool = Field(default=True, description="Flag translations that fail readability")
    block_on_fail: bool = Field(default=False, description="Block translations that fail readability")


class TranslationConfig(BaseModel):
    """Main translation configuration with validation."""
    
    # Model settings
    model: str = Field(default="qwen:7b", description="Model name/identifier")
    provider: Literal["ollama", "openrouter", "gemini"] = Field(
        default="ollama",
        description="Model provider"
    )
    
    # API endpoints
    ollama_endpoint: str = Field(
        default="http://localhost:11434/api/generate",
        description="Ollama API endpoint URL"
    )
    
    # Language settings
    source_language: str = Field(default="Chinese", description="Source language")
    target_language: str = Field(default="Burmese", description="Target language")
    
    # Chunking settings
    chunk_size: int = Field(
        default=1500, 
        ge=100, 
        le=5000,
        description="Maximum characters per chunk"
    )
    chunk_overlap: int = Field(
        default=100, 
        ge=0, 
        le=500,
        description="Character overlap between chunks"
    )
    
    # Streaming settings
    stream: bool = Field(default=True, description="Enable streaming responses")
    preview_update_every_n_tokens: int = Field(
        default=10, 
        ge=1, 
        le=100,
        description="Update preview every N tokens"
    )
    
    # Request settings
    request_timeout: int = Field(
        default=900, 
        ge=30, 
        le=3600,
        description="Request timeout in seconds"
    )
    
    auto_open_browser: bool = Field(
        default=True, 
        description="Automatically open browser on startup"
    )
    
    # Readability settings
    myanmar_readability: MyanmarReadabilityConfig = Field(
        default_factory=MyanmarReadabilityConfig,
        description="Myanmar readability checking configuration"
    )
    
    @validator('chunk_overlap')
    def overlap_less_than_chunk(cls, v, values):
        """Ensure overlap is less than chunk size."""
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('chunk_overlap must be less than chunk_size')
        return v
    
    @validator('ollama_endpoint')
    def validate_url(cls, v):
        """Ensure endpoint is a valid URL."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Endpoint must be a valid HTTP/HTTPS URL')
        return v
    
    @classmethod
    def from_json(cls, path: str) -> "TranslationConfig":
        """Load configuration from JSON file.
        
        Args:
            path: Path to JSON configuration file
            
        Returns:
            TranslationConfig instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If JSON is invalid or validation fails
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranslationConfig":
        """Load configuration from dictionary.
        
        Args:
            data: Dictionary containing configuration values
            
        Returns:
            TranslationConfig instance
        """
        return cls(**data)
    
    def to_json(self, path: str) -> None:
        """Save configuration to JSON file.
        
        Args:
            path: Path to save configuration
        """
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.dict(), f, indent=2, ensure_ascii=False)
    
    def get_model_config(self) -> dict:
        """Get model-specific configuration as dictionary."""
        return {
            'model': self.model,
            'provider': self.provider,
            'endpoint': self.ollama_endpoint if self.provider == 'ollama' else None,
            'timeout': self.request_timeout,
            'stream': self.stream
        }


def load_config(config_path: str = "config/config.json") -> TranslationConfig:
    """Load and validate configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Validated TranslationConfig instance
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    try:
        return TranslationConfig.from_json(config_path)
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return TranslationConfig()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        # Validate existing config file
        try:
            config = load_config()
            print("✓ Configuration is valid")
            print(f"  Model: {config.model}")
            print(f"  Provider: {config.provider}")
            print(f"  Chunk size: {config.chunk_size}")
            print(f"  Target language: {config.target_language}")
            print(f"  Readability enabled: {config.myanmar_readability.enabled}")
        except Exception as e:
            print(f"✗ Configuration validation failed: {e}")
            sys.exit(1)
    else:
        # Show default config
        config = TranslationConfig()
        print("Default Configuration:")
        print(config.json(indent=2))
