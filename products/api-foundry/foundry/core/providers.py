"""
Provider abstraction layer for multi-model routing.

This module defines an interface for delegating LLM tasks to different 
providers (Anthropic, Google, OpenAI, Ollama) and tracks token usage/costs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
import os

try:
    import httpx
except ImportError:
    httpx = None


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class ModelResponse:
    content: str
    usage: TokenUsage
    model_name: str
    provider_name: str


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""
    
    def __init__(self, name: str, default_model: str, api_key: Optional[str] = None):
        self.name = name
        self.default_model = default_model
        self.api_key = api_key
        
    @abstractmethod
    async def generate(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None, **kwargs) -> ModelResponse:
        """Generate text from the LLM."""
        pass
        
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Calculate the estimated cost in USD based on known pricing."""
        # Derived classes implement specific pricing logic
        return 0.0


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API Provider."""
    
    # Costs per 1M tokens (as of early 2024)
    PRICING = {
        "claude-3-opus-20240229": {"in": 15.0, "out": 75.0},
        "claude-3-sonnet-20240229": {"in": 3.0, "out": 15.0},
        "claude-3-haiku-20240307": {"in": 0.25, "out": 1.25},
    }
    
    def __init__(self, api_key: Optional[str] = None, default_model: str = "claude-3-haiku-20240307"):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        super().__init__("Anthropic", default_model, api_key)
        
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        pricing = self.PRICING.get(model, {"in": 0.0, "out": 0.0})
        return (prompt_tokens / 1_000_000) * pricing["in"] + (completion_tokens / 1_000_000) * pricing["out"]
        
    async def generate(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None, **kwargs) -> ModelResponse:
        if not httpx:
            raise ImportError("httpx is required to use the Anthropic provider. Install with: pip install httpx")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
            
        target_model = model or self.default_model
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": target_model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.0),
            "messages": [{"role": "user", "content": prompt}]
        }
        
        if system:
            payload["system"] = system
            
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            content = data["content"][0]["text"]
            usage_data = data.get("usage", {})
            in_tokens = usage_data.get("input_tokens", 0)
            out_tokens = usage_data.get("output_tokens", 0)
            
            usage = TokenUsage(
                prompt_tokens=in_tokens,
                completion_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                estimated_cost_usd=self._calculate_cost(in_tokens, out_tokens, target_model)
            )
            
            return ModelResponse(content=content, usage=usage, model_name=target_model, provider_name=self.name)


class GoogleProvider(LLMProvider):
    """Google Gemini API Provider."""
    
    # Costs per 1M tokens
    PRICING = {
        "gemini-1.5-pro-latest": {"in": 3.50, "out": 10.50},
        "gemini-1.5-flash-latest": {"in": 0.35, "out": 1.05},
    }
    
    def __init__(self, api_key: Optional[str] = None, default_model: str = "gemini-1.5-flash-latest"):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        super().__init__("Google", default_model, api_key)
        
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        pricing = self.PRICING.get(model, {"in": 0.0, "out": 0.0})
        return (prompt_tokens / 1_000_000) * pricing["in"] + (completion_tokens / 1_000_000) * pricing["out"]
        
    async def generate(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None, **kwargs) -> ModelResponse:
        if not httpx:
            raise ImportError("httpx is required to use the Google provider.")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
            
        target_model = model or self.default_model
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.api_key}"
        
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"System directive: {system}"}]})
            contents.append({"role": "model", "parts": [{"text": "Acknowledged."}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.0),
                "maxOutputTokens": kwargs.get("max_tokens", 8192)
            }
        }
            
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage_data = data.get("usageMetadata", {})
            in_tokens = usage_data.get("promptTokenCount", 0)
            out_tokens = usage_data.get("candidatesTokenCount", 0)
            
            usage = TokenUsage(
                prompt_tokens=in_tokens,
                completion_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                estimated_cost_usd=self._calculate_cost(in_tokens, out_tokens, target_model)
            )
            
            return ModelResponse(content=content, usage=usage, model_name=target_model, provider_name=self.name)


class OllamaProvider(LLMProvider):
    """Local Ollama Provider (Zero Cost)."""
    
    def __init__(self, endpoint: Optional[str] = None, default_model: Optional[str] = None):
        endpoint = endpoint or os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434")
        default_model = default_model or os.environ.get("OLLAMA_DEFAULT_MODEL", "qwen3.5:4b")
        
        super().__init__("Ollama", default_model, api_key="local")
        self.endpoint = endpoint
        
    async def generate(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None, **kwargs) -> ModelResponse:
        if not httpx:
            raise ImportError("httpx is required to use the Ollama provider.")
            
        target_model = model or self.default_model
        url = f"{self.endpoint}/api/generate"
        
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.0)
            }
        }
        
        if system:
            payload["system"] = system
            
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=120.0)
            response.raise_for_status()
            data = response.json()
            
            content = data["response"]
            in_tokens = data.get("prompt_eval_count", 0)
            out_tokens = data.get("eval_count", 0)
            
            usage = TokenUsage(
                prompt_tokens=in_tokens,
                completion_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                estimated_cost_usd=0.0  # Local inference is free
            )
            
            return ModelResponse(content=content, usage=usage, model_name=target_model, provider_name=self.name)


class ProviderRouter:
    """Routes requests to the appropriate provider based on configuration."""
    
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        
        # Auto-register available providers
        self.providers["anthropic"] = AnthropicProvider()
        self.providers["google"] = GoogleProvider()
        self.providers["ollama"] = OllamaProvider()
            
    def register_provider(self, alias: str, provider: LLMProvider):
        self.providers[alias] = provider
        
    def get_provider(self, alias: str) -> LLMProvider:
        if alias not in self.providers:
            raise KeyError(f"Provider '{alias}' not found or not configured.")
        return self.providers[alias]
