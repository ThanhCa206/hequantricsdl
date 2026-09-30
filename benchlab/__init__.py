"""
Root-level benchlab package forwarding to backend/benchlab
Enables `python -m benchlab ...` to run directly from workspace root.
"""

from backend.benchlab.cli import main

__all__ = ["main"]
