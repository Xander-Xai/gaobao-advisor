"""Pytest conftest — project path setup and test data isolation.

The application resolves its SQLite path from ``GAOBAO__DB_PATH`` when
``db.database`` is first imported. Tests that exercise the memory or quality
nodes write conversation rows, so without redirection an ordinary ``pytest`` run
would append rows to whatever database the developer has in ``data/``. That is
how a test suite quietly mutates real (or real-looking) data.

This module points the test run at a throwaway directory *before* anything
imports the application, so the working database is never written to. Set
``GAOBAO_TEST_USE_LIVE_DB=1`` to opt out and test against the configured
database on purpose.
"""

import os
import sys
import tempfile
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


def _redirect_data_paths() -> None:
    if os.environ.get("GAOBAO_TEST_USE_LIVE_DB") == "1":
        return
    if os.environ.get("GAOBAO_TEST_DATA_DIR"):
        return

    sandbox = Path(tempfile.mkdtemp(prefix="gaobao-tests-"))
    os.environ["GAOBAO_TEST_DATA_DIR"] = str(sandbox)
    os.environ.setdefault("GAOBAO__DATA_DIR", str(sandbox))
    os.environ.setdefault("GAOBAO__DB_PATH", str(sandbox / "gaokao.db"))
    os.environ.setdefault("GAOBAO__ANALYTICS_DB_PATH", str(sandbox / "analytics.db"))
    os.environ.setdefault("GAOBAO__REPORTS_DIR", str(sandbox / "reports"))
    os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")


_redirect_data_paths()
