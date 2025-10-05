"""
FSD: Autonomous Overnight Coding Agent System

A Feature-Sliced Design system that enables a CLI-based coding agent to work
autonomously overnight, executing multi-step development tasks with checkpoints,
recovery mechanisms, and human-in-the-loop safeguards.
"""

__version__ = "0.1.0"
__author__ = "FSD Team"
__email__ = "fsd@example.com"

from fsd.core.exceptions import FSDError

__all__ = ["FSDError", "__version__"]
