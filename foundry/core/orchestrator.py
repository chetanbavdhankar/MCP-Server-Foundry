"""
Agent orchestration and pipeline coordination.

This module manages the sequential execution of agents in the Foundry pipeline,
handling context passing, error recovery, and execution flow control.
"""

from typing import List, Optional
import json
from pathlib import Path

from .agent_interface import Agent, AgentContext, AgentExecutionError


class Orchestrator:
    """
    Coordinates the execution of multiple agents in sequence.
    
    The orchestrator manages the pipeline flow, ensuring each agent
    receives the updated context from the previous agent and handling
    any errors that occur during execution.
    """
    
    def __init__(self, agents: List[Agent], output_dir: str = "./output"):
        """
        Initialize the orchestrator.
        
        Args:
            agents: List of agents to execute in sequence
            output_dir: Base directory for output artifacts
        """
        self.agents = agents
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute_pipeline(self, context: AgentContext) -> AgentContext:
        """
        Execute all agents in sequence.
        
        Args:
            context: Initial execution context
            
        Returns:
            Final context after all agents have executed
            
        Raises:
            AgentExecutionError: If any agent fails and cannot recover
        """
        print(f"\n{'='*60}")
        print(f"Starting Foundry pipeline execution")
        print(f"Execution ID: {context.execution_id}")
        print(f"{'='*60}\n")
        
        for i, agent in enumerate(self.agents, 1):
            print(f"[{i}/{len(self.agents)}] Executing agent: {agent.name}")
            
            try:
                context = await agent.execute(context)
                print(f"  [OK] {agent.name} completed successfully\n")
            except AgentExecutionError as e:
                print(f"  [FAIL] {agent.name} failed: {e.message}\n")
                context.add_error(agent.name, str(e), e.details)
                
                # For now, stop on first error
                # Future: implement retry logic and error recovery
                raise
            except Exception as e:
                print(f"  ✗ {agent.name} encountered unexpected error: {str(e)}\n")
                context.add_error(agent.name, f"Unexpected error: {str(e)}")
                raise AgentExecutionError(agent.name, str(e))
        
        # Save execution trace
        self._save_trace(context)
        
        print(f"{'='*60}")
        print(f"Pipeline execution completed successfully")
        print(f"Output directory: {context.output_dir}")
        print(f"{'='*60}\n")
        
        return context
    
    def _save_trace(self, context: AgentContext):
        """Save execution trace to output directory."""
        trace_file = self.output_dir / "execution_trace.json"
        
        trace_data = {
            "execution_id": context.execution_id,
            "spec_path": context.spec_path,
            "output_dir": context.output_dir,
            "agents_executed": [entry["agent"] for entry in context.agent_trace],
            "trace": context.agent_trace,
            "errors": context.errors,
            "summary": context.to_dict()
        }
        
        with open(trace_file, 'w', encoding='utf-8') as f:
            json.dump(trace_data, f, indent=2)
        
        print(f"Execution trace saved to: {trace_file}")
    
    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get an agent by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None
    
    def add_agent(self, agent: Agent, position: Optional[int] = None):
        """
        Add an agent to the pipeline.
        
        Args:
            agent: Agent to add
            position: Optional position to insert at (default: append)
        """
        if position is None:
            self.agents.append(agent)
        else:
            self.agents.insert(position, agent)
    
    def remove_agent(self, name: str) -> bool:
        """
        Remove an agent from the pipeline by name.
        
        Args:
            name: Name of the agent to remove
            
        Returns:
            True if agent was removed, False if not found
        """
        for i, agent in enumerate(self.agents):
            if agent.name == name:
                self.agents.pop(i)
                return True
        return False


class PipelineBuilder:
    """
    Builder pattern for constructing orchestrated pipelines.
    
    Provides a fluent interface for configuring the agent pipeline.
    """
    
    def __init__(self):
        self.agents: List[Agent] = []
        self.output_dir: str = "./output"
    
    def add_agent(self, agent: Agent) -> 'PipelineBuilder':
        """Add an agent to the pipeline."""
        self.agents.append(agent)
        return self
    
    def set_output_dir(self, output_dir: str) -> 'PipelineBuilder':
        """Set the output directory."""
        self.output_dir = output_dir
        return self
    
    def build(self) -> Orchestrator:
        """Build and return the orchestrator."""
        if not self.agents:
            raise ValueError("Pipeline must have at least one agent")
        return Orchestrator(self.agents, self.output_dir)

# Made with Bob
