"""
MCP Server Foundry - Agent implementations

This module contains the concrete agent implementations for the Foundry pipeline:
- Architect: Spec parsing and planning
- Builder: Code generation
- Tester: Test suite generation (Milestone 4)
- Documenter: Documentation generation (Milestone 5)
"""

from .architect import ArchitectAgent
from .builder import BuilderAgent

__all__ = ['ArchitectAgent', 'BuilderAgent']

# Made with Bob
