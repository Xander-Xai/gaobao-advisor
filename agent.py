"""
DEPRECATED: This module has been moved to legacy/agent.py.
Please update imports to use server/ package modules.
"""
import os
import sys
import warnings

# Ensure legacy/ is on sys.path so inter-dependencies resolve
_legacy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "legacy")
if _legacy_dir not in sys.path:
    sys.path.insert(0, _legacy_dir)

warnings.warn(
    "agent.py is deprecated. Use server/ package modules instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Forward all imports to the legacy module
from legacy.agent import *  # noqa: F401,F403,E402