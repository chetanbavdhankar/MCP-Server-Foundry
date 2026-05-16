"""
MCP Server Foundry - Agent implementations

This module contains the concrete agent implementations for the Foundry pipeline:
- Architect: Spec parsing and planning
- Builder: Code generation
- Tester: Adversarial test suite generation (Milestone 4)
- Documenter: Documentation generation (Milestone 5)
"""

from .architect import ArchitectAgent
from .builder import BuilderAgent
from .tester import TesterAgent

__all__ = ['ArchitectAgent', 'BuilderAgent', 'TesterAgent']


# Made with Bob
