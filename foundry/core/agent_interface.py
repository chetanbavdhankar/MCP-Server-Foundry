"""
Agent interface and base classes for the Foundry pipeline.

This module defines the abstract base class for all agents and provides
a clear abstraction layer that allows for both standalone execution and
future IBM Bob integration via adapter pattern.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import uuid


@dataclass
class AgentContext:
    """
    Shared context passed between agents in the pipeline.
    
    Each agent reads from and writes to this context, enabling
    clean handoffs and maintaining execution state.
    """
    
    # Input data
    spec_path: str
    spec_data: Optional[Dict[str, Any]] = None
    output_dir: str = "./output"
    
    # Agent artifacts
    plan: Optional[Dict[str, Any]] = None
    generated_code: Optional[Dict[str, str]] = None
    test_results: Optional[Dict[str, Any]] = None
    documentation: Optional[Dict[str, str]] = None
    
    # Metadata
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_trace: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    
    # Cost & Token Tracking (Milestone 6)
    llm_usage: Dict[str, Any] = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "calls_by_provider": {}
    })
    
    def add_trace(self, agent_name: str, action: str, details: Optional[Dict] = None):
        """Add an entry to the execution trace."""
        self.agent_trace.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "action": action,
            "details": details or {}
        })
        
    def add_llm_usage(self, provider_name: str, model_name: str, prompt_tokens: int, completion_tokens: int, cost: float):
        """Record LLM token usage and estimated cost."""
        self.llm_usage["prompt_tokens"] += prompt_tokens
        self.llm_usage["completion_tokens"] += completion_tokens
        self.llm_usage["total_tokens"] += (prompt_tokens + completion_tokens)
        self.llm_usage["total_cost_usd"] += cost
        
        provider_key = f"{provider_name}:{model_name}"
        if provider_key not in self.llm_usage["calls_by_provider"]:
            self.llm_usage["calls_by_provider"][provider_key] = 0
        self.llm_usage["calls_by_provider"][provider_key] += 1
    
    def add_error(self, agent_name: str, error: str, details: Optional[Dict] = None):
        """Record an error in the context."""
        self.errors.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "error": error,
            "details": details or {}
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "spec_path": self.spec_path,
            "output_dir": self.output_dir,
            "execution_id": self.execution_id,
            "has_plan": self.plan is not None,
            "has_code": self.generated_code is not None,
            "has_tests": self.test_results is not None,
            "has_docs": self.documentation is not None,
            "trace_entries": len(self.agent_trace),
            "error_count": len(self.errors),
            "llm_usage": self.llm_usage
        }


class Agent(ABC):
    """
    Abstract base class for all Foundry agents.
    
    Each agent implements the execute method which takes a context,
    performs its specific task, and returns an updated context.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentContext:
        """
        Execute the agent's logic.
        
        Args:
            context: The current execution context
            
        Returns:
            Updated context with agent's contributions
            
        Raises:
            AgentExecutionError: If agent execution fails
        """
        pass
    
    def log_start(self, context: AgentContext):
        """Log agent execution start."""
        context.add_trace(self.name, "started", {"agent": self.name})
    
    def log_complete(self, context: AgentContext, details: Optional[Dict] = None):
        """Log agent execution completion."""
        context.add_trace(self.name, "completed", details or {})
    
    def log_error(self, context: AgentContext, error: str, details: Optional[Dict] = None):
        """Log agent execution error."""
        context.add_error(self.name, error, details)


class StandaloneAgent(Agent):
    """
    Base class for standalone agent implementations.
    
    These agents execute locally without requiring IBM Bob integration.
    Used for initial development and testing.
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self.execution_mode = "standalone"


class BobAdapter(Agent):
    """
    Future: Adapter for IBM Bob mode integration.
    
    This class will wrap IBM Bob's Architect, Builder, Tester, and
    Documenter modes, translating between the Foundry's AgentContext
    and Bob's native interfaces.
    
    Not implemented in Milestone 1.
    """
    
    def __init__(self, name: str, bob_mode: str):
        super().__init__(name)
        self.bob_mode = bob_mode
        self.execution_mode = "bob"
    
    async def execute(self, context: AgentContext) -> AgentContext:
        """
        Execute via IBM Bob mode.
        
        This will be implemented when Bob integration is added.
        """
        raise NotImplementedError(
            f"Bob integration not yet implemented for mode: {self.bob_mode}"
        )


class AgentExecutionError(Exception):
    """Exception raised when agent execution fails."""
    
    def __init__(self, agent_name: str, message: str, details: Optional[Dict] = None):
        self.agent_name = agent_name
        self.message = message
        self.details = details or {}
        super().__init__(f"Agent '{agent_name}' failed: {message}")

# Made with Bob
