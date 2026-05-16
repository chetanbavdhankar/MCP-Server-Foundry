"""Pytest configuration for foundry tests."""
import sys
from pathlib import Path

# Add foundry root to sys.path so bare imports (core.*, agents.*) resolve
sys.path.insert(0, str(Path(__file__).parent.parent))
