"""
Agent orchestration and pipeline coordination.

This module manages the sequential execution of agents in the Foundry pipeline,
handling context passing, error recovery, execution flow control, and M3
governance features (audit logging, approval gates, provenance tracking).
"""

import json
import hashlib
import time
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime, timezone

from .agent_interface import Agent, AgentContext, AgentExecutionError
from .audit import AuditLogger, AuditEvent, AuditSeverity, compute_file_hash
from .approval_gates import (
    gate_plan_review,
    gate_code_review,
    ApprovalDecision,
    GateRejectedError,
)


class Orchestrator:
    """
    Coordinates the execution of multiple agents in sequence.
    
    The orchestrator manages the pipeline flow, ensuring each agent
    receives the updated context from the previous agent and handling
    any errors that occur during execution.
    
    M3 additions:
    - AuditLogger records every pipeline event to a JSON Lines file
    - Approval gates pause between agents for human review
    - Provenance manifest tracks content hashes of all generated files
    """
    
    def __init__(
        self,
        agents: List[Agent],
        output_dir: str = "./output",
        auto_approve: bool = False,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            agents: List of agents to execute in sequence
            output_dir: Base directory for output artifacts
            auto_approve: Skip interactive approval gates (for CI/CD)
        """
        self.agents = agents
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.auto_approve = auto_approve

        # Initialize audit logger — one per pipeline run, set in execute_pipeline
        self._audit: Optional[AuditLogger] = None
    
    async def execute_pipeline(self, context: AgentContext) -> AgentContext:
        """
        Execute all agents in sequence with governance controls.
        
        Args:
            context: Initial execution context
            
        Returns:
            Final context after all agents have executed
            
        Raises:
            AgentExecutionError: If any agent fails and cannot recover
            GateRejectedError: If an approval gate is rejected
        """
        # Initialize audit logger for this execution
        audit_path = self.output_dir / "audit.jsonl"
        self._audit = AuditLogger(audit_path, context.execution_id)

        pipeline_start = time.monotonic()

        self._audit.log(
            AuditEvent.PIPELINE_START,
            message="Foundry pipeline started",
            details={
                "spec_path": context.spec_path,
                "output_dir": context.output_dir,
                "agents": [a.name for a in self.agents],
                "auto_approve": self.auto_approve,
            },
        )

        print(f"\n{'='*60}")
        print(f"Starting Foundry pipeline execution")
        print(f"Execution ID: {context.execution_id}")
        print(f"Audit log:    {audit_path}")
        print(f"{'='*60}\n")
        
        for i, agent in enumerate(self.agents, 1):
            print(f"[{i}/{len(self.agents)}] Executing agent: {agent.name}")

            agent_start = time.monotonic()
            self._audit.log(
                AuditEvent.AGENT_START,
                agent=agent.name,
                message=f"Agent '{agent.name}' starting",
            )
            
            try:
                context = await agent.execute(context)
                duration_ms = (time.monotonic() - agent_start) * 1000

                self._audit.log(
                    AuditEvent.AGENT_COMPLETE,
                    agent=agent.name,
                    message=f"Agent '{agent.name}' completed",
                    duration_ms=round(duration_ms, 2),
                )
                print(f"  [OK] {agent.name} completed successfully\n")

                # --- Approval Gates (M3) ---
                self._run_post_agent_gate(agent.name, context)

            except GateRejectedError:
                # Gate rejection is a controlled abort, not an error
                self._audit.log(
                    AuditEvent.PIPELINE_FAIL,
                    severity=AuditSeverity.WARN,
                    message="Pipeline aborted by approval gate rejection",
                    duration_ms=round((time.monotonic() - pipeline_start) * 1000, 2),
                )
                raise

            except AgentExecutionError as e:
                duration_ms = (time.monotonic() - agent_start) * 1000
                print(f"  [FAIL] {agent.name} failed: {e.message}\n")
                context.add_error(agent.name, str(e), e.details)

                self._audit.log(
                    AuditEvent.AGENT_FAIL,
                    severity=AuditSeverity.ERROR,
                    agent=agent.name,
                    message=str(e),
                    duration_ms=round(duration_ms, 2),
                    details=e.details,
                )
                raise

            except Exception as e:
                print(f"  [FAIL] {agent.name} encountered unexpected error: {str(e)}\n")
                context.add_error(agent.name, f"Unexpected error: {str(e)}")

                self._audit.log(
                    AuditEvent.AGENT_FAIL,
                    severity=AuditSeverity.ERROR,
                    agent=agent.name,
                    message=f"Unexpected: {str(e)}",
                )
                raise AgentExecutionError(agent.name, str(e))
        
        # Save provenance manifest (replaces old execution trace)
        total_ms = (time.monotonic() - pipeline_start) * 1000
        self._save_provenance(context, total_ms)
        
        self._audit.log(
            AuditEvent.PIPELINE_COMPLETE,
            message="Pipeline completed successfully",
            duration_ms=round(total_ms, 2),
        )

        print(f"{'='*60}")
        print(f"Pipeline execution completed successfully")
        print(f"Output directory: {context.output_dir}")
        print(f"{'='*60}\n")
        
        return context

    def _run_post_agent_gate(self, agent_name: str, context: AgentContext):
        """Run the appropriate approval gate after an agent completes."""
        if agent_name == "Architect" and context.plan:
            gate_plan_review(context.plan, self._audit, self.auto_approve)

        elif agent_name == "Builder" and context.generated_code:
            semgrep_passed = None
            # Extract Semgrep status from the last trace entry
            for entry in reversed(context.agent_trace):
                if entry.get("agent") == "Builder" and "semgrep_passed" in entry.get("details", {}):
                    semgrep_passed = entry["details"]["semgrep_passed"]
                    break
            gate_code_review(
                context.generated_code,
                semgrep_passed,
                self._audit,
                self.auto_approve,
            )

    def _save_provenance(self, context: AgentContext, total_ms: float):
        """Save full provenance manifest — replaces the old execution_trace.json."""
        manifest_file = self.output_dir / "provenance.json"

        # Hash every generated file
        server_dir = self.output_dir / "server"
        file_hashes = {}
        if server_dir.exists():
            for f in sorted(server_dir.iterdir()):
                if f.is_file():
                    file_hashes[f.name] = compute_file_hash(f)

        # Hash the input spec
        spec_hash = None
        spec_path = Path(context.spec_path)
        if spec_path.exists():
            spec_hash = compute_file_hash(spec_path)

        manifest = {
            "schema_version": "1.0.0",
            "execution_id": context.execution_id,
            "timestamp": context.timestamp,
            "duration_ms": round(total_ms, 2),
            "spec": {
                "path": context.spec_path,
                "sha256": spec_hash,
            },
            "agents_executed": [
                {
                    "agent": entry["agent"],
                    "action": entry["action"],
                    "timestamp": entry["timestamp"],
                    "details": entry.get("details", {}),
                }
                for entry in context.agent_trace
            ],
            "generated_files": file_hashes,
            "errors": context.errors,
            "summary": context.to_dict(),
        }

        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"Provenance manifest saved to: {manifest_file}")

        # Also keep backward-compatible execution_trace.json
        trace_file = self.output_dir / "execution_trace.json"
        trace_data = {
            "execution_id": context.execution_id,
            "spec_path": context.spec_path,
            "output_dir": context.output_dir,
            "agents_executed": [entry["agent"] for entry in context.agent_trace],
            "trace": context.agent_trace,
            "errors": context.errors,
            "summary": context.to_dict(),
        }
        with open(trace_file, "w", encoding="utf-8") as f:
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
        self._auto_approve: bool = False
    
    def add_agent(self, agent: Agent) -> 'PipelineBuilder':
        """Add an agent to the pipeline."""
        self.agents.append(agent)
        return self
    
    def set_output_dir(self, output_dir: str) -> 'PipelineBuilder':
        """Set the output directory."""
        self.output_dir = output_dir
        return self

    def auto_approve(self, enabled: bool = True) -> 'PipelineBuilder':
        """Enable auto-approve mode (skip interactive gates)."""
        self._auto_approve = enabled
        return self
    
    def build(self) -> Orchestrator:
        """Build and return the orchestrator."""
        if not self.agents:
            raise ValueError("Pipeline must have at least one agent")
        return Orchestrator(self.agents, self.output_dir, self._auto_approve)

# Made with Bob
