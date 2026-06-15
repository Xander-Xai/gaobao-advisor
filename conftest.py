"""Pytest conftest — ensure project root is on sys.path for all imports."""

import sys
from pathlib import Path

# Add project root to sys.path so both `server.*` and root-level modules
# (constants, agent, db, etc.) are importable during testing.
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
