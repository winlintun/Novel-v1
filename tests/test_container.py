from src.core.container import Container
from src.config.models import AppConfig

def test_container_initialization():
    config = AppConfig()
    container = Container(config)
    assert container.config == config

def test_container_dependency_injection():
    config = AppConfig()
    container = Container(config)
    
    # Test lazy initialization of dependencies via get methods
    assert container.get_ollama_client() is not None
    assert container.get_memory_manager() is not None
    assert container.get_translator() is not None
    assert container.get_refiner() is not None
    assert container.get_checker() is not None

