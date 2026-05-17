"""
Model Routing Layer (Milestone 6).

Handles dynamic delegation of pipeline tasks to different LLMs based on 
stage requirements, token budgets, and cost-optimization profiles.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from core.providers import ProviderRouter, LLMProvider


class ModelRouter:
    """
    Cost-optimized multi-model routing engine.
    
    Reads a configuration defining which model provider and model string 
    to use for each agent in the pipeline. Allows falling back to cheaper 
    models or local inference (Ollama) depending on the stage.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.provider_router = ProviderRouter()
        self.stage_configs: Dict[str, Dict[str, str]] = {}
        
        # Default cost-optimized routing
        self.default_routes = {
            "Architect": {"provider": "google", "model": "gemini-1.5-flash-latest"},  # Fast, cheap JSON parsing
            "Builder": {"provider": "anthropic", "model": "claude-3-opus-20240229"},  # Heavy code generation
            "Tester": {"provider": "anthropic", "model": "claude-3-sonnet-20240229"}, # Smart but fast
            "Documenter": {"provider": "google", "model": "gemini-1.5-flash-latest"}, # Cheap markdown formatting
        }
        
        if config_path and Path(config_path).exists():
            self.load_config(config_path)
            
    def load_config(self, config_path: str):
        """Load stage routing configurations from a JSON file."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "routes" in data:
                self.stage_configs = data["routes"]
                
    def get_route(self, agent_name: str) -> tuple[LLMProvider, str]:
        """
        Get the configured provider and model for a specific agent.
        
        Returns:
            Tuple of (LLMProvider instance, model_name string)
        """
        route = self.stage_configs.get(agent_name) or self.default_routes.get(agent_name)
        
        if not route:
            # Fallback to local Ollama if no route is defined to save costs
            return self.provider_router.get_provider("ollama"), "qwen3.5:4b"
            
        provider_name = route.get("provider", "ollama")
        model_name = route.get("model", "qwen3.5:4b")
        
        provider = self.provider_router.get_provider(provider_name)
        return provider, model_name
        
    async def generate_for_agent(self, agent_name: str, prompt: str, system: Optional[str] = None, **kwargs):
        """
        Execute an LLM generation task routed for a specific agent.
        """
        provider, model_name = self.get_route(agent_name)
        
        # Pass model directly to provider
        response = await provider.generate(prompt, system=system, model=model_name, **kwargs)
        return response
