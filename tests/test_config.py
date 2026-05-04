import pytest
from src.config.loader import load_config_from_dict, get_default_config
from src.config.models import AppConfig
from src.exceptions import ConfigurationError

def test_load_config_from_dict():
    config_dict = {"models": {"translator": "new_model"}}
    config = load_config_from_dict(config_dict)
    
    assert config.models.translator == "new_model"
    assert config.processing.chunk_size > 0  # Should use default

def test_load_config_from_dict_invalid():
    with pytest.raises(ConfigurationError):
        load_config_from_dict({"processing": {"chunk_size": "not_an_int"}})

def test_get_default_config():
    config = get_default_config()
    assert isinstance(config, AppConfig)
    assert config.models.translator is not None

