"""Tests for Multi-Model Routing (M6)."""

import pytest
from core.routing import ModelRouter
from core.providers import ProviderRouter, OllamaProvider, GoogleProvider, AnthropicProvider

def test_model_router_default_routes():
    """Test that default cost-optimized routes are correctly established."""
    router = ModelRouter()
    
    # Architect uses Gemini Flash
    provider, model = router.get_route("Architect")
    assert isinstance(provider, GoogleProvider)
    assert model == "gemini-1.5-flash-latest"
    
    # Builder uses Claude Opus
    provider, model = router.get_route("Builder")
    assert isinstance(provider, AnthropicProvider)
    assert model == "claude-3-opus-20240229"
    
    # Tester uses Claude Sonnet
    provider, model = router.get_route("Tester")
    assert isinstance(provider, AnthropicProvider)
    assert model == "claude-3-sonnet-20240229"
    
    # Unknown agent falls back to Ollama
    provider, model = router.get_route("UnknownAgent")
    assert isinstance(provider, OllamaProvider)
    assert model == "qwen3.5:4b"

def test_provider_router_registration():
    """Test that providers can be registered and retrieved."""
    pr = ProviderRouter()
    
    # Register a dummy provider
    dummy = OllamaProvider(endpoint="http://dummy")
    pr.register_provider("dummy", dummy)
    
    assert pr.get_provider("dummy") == dummy
    
    with pytest.raises(KeyError):
        pr.get_provider("nonexistent")
