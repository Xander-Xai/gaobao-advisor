"""Dependency policy tests.

The runtime dependency set must not carry known-vulnerable packages, and the
optional legacy set must stay out of the runtime. These tests are offline and
deterministic: they check the *declared* dependency files, not a live advisory
feed. The live check is `pip-audit` in CI (see `.github/workflows/ci.yml`).

See `docs/dependency-exceptions.md` for the policy, the recorded exception and
the open decisions.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RUNTIME_REQUIREMENTS = REPO_ROOT / "requirements.txt"
RUNTIME_LOCK = REPO_ROOT / "requirements.lock"
RUNTIME_CONSTRAINTS = REPO_ROOT / "requirements.lock.constraints"
LEGACY_REQUIREMENTS = REPO_ROOT / "requirements-legacy-admin.txt"
LEGACY_LOCK = REPO_ROOT / "requirements-legacy-admin.lock"

#: Packages that carry the advisory chain this repository removed from the
#: runtime on 2026-10-21.
#:
#: * `pillow` — every release before 13.0.0 is affected by
#:   CVE-2026-112395/397/400/404/895/896/897/899, and 13.0.0 requires
#:   Python >= 3.11, so it is not a drop-in for a Python 3.10 target.
#: * `streamlit` — pins `pillow<13`; it is only needed by the optional legacy
#:   operations dashboard.
#: * `reportlab` — no module in this repository imports it.
VULNERABLE_RUNTIME_CHAIN = ("pillow", "streamlit", "reportlab")

_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)\s*$")


def _pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _PIN.match(line)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def _direct_requirements(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        names.add(re.split(r"[<>=!~\[ ]", line, maxsplit=1)[0].lower())
    return names


class TestRuntimeDependencySet:
    def test_runtime_lock_exists_and_is_pinned(self) -> None:
        pins = _pins(RUNTIME_LOCK)
        assert pins, "requirements.lock must contain pinned packages"
        assert "certifi" in pins
        assert all("=" in f"{k}=={v}" for k, v in pins.items())

    def test_runtime_set_carries_no_vulnerable_chain(self) -> None:
        """The runtime set must not contain pillow / streamlit / reportlab.

        `pillow` < 13.0.0 is affected by eight advisories that have no
        backportable fix; `streamlit` pins `pillow<13`; `reportlab` is the
        other route to `pillow` and is imported by nothing in this repository.

        Only the *declared* requirements are checked — the files may still
        mention these names in explanatory comments, which is intentional.
        """
        declared = _direct_requirements(RUNTIME_REQUIREMENTS)
        for name in VULNERABLE_RUNTIME_CHAIN:
            assert name not in declared, (
                f"{RUNTIME_REQUIREMENTS.name} must not declare {name}: it is "
                "either unused or the route to a dependency with unfixable advisories"
            )
        for path in (RUNTIME_LOCK, RUNTIME_CONSTRAINTS):
            pins = _pins(path)
            for name in VULNERABLE_RUNTIME_CHAIN:
                assert name not in pins, f"{name} must not be pinned in {path.name}"

    def test_runtime_lock_has_no_pillow_or_streamlit_package(self) -> None:
        pins = _pins(RUNTIME_LOCK)
        for name in VULNERABLE_RUNTIME_CHAIN:
            assert name not in pins, f"{name} must not be in the runtime lock"

    def test_certifi_is_past_the_pysec_advisory(self) -> None:
        """certifi <= 2026.5.20 bundles a compromised eSign root CA."""
        pins = _pins(RUNTIME_LOCK)
        assert "certifi" in pins, "certifi must stay pinned in the runtime lock"
        major, minor, patch = (int(part) for part in pins["certifi"].split(".")[:3])
        assert (major, minor, patch) >= (2026, 10, 19), (
            f"certifi {pins['certifi']} is affected by PYSEC-2026-4320; the first fixed release is 2026.10.19"
        )

    def test_runtime_lock_is_reproducible_from_the_constraints_file(self) -> None:
        """The lock must be regenerable without floating the whole stack.

        `make lock` runs uv with `requirements.lock.constraints`; the header of
        the lock records that command. A hand-edited lock would drift from it.
        """
        header = RUNTIME_LOCK.read_text(encoding="utf-8").splitlines()[:4]
        assert any("requirements.lock.constraints" in line for line in header), (
            "requirements.lock must record that it was compiled with the constraints file"
        )
        assert RUNTIME_CONSTRAINTS.exists()


class TestOptionalLegacySetIsSeparate:
    def test_legacy_requirements_exist(self) -> None:
        assert LEGACY_REQUIREMENTS.exists()
        assert LEGACY_LOCK.exists()

    def test_streamlit_is_not_a_runtime_dependency(self) -> None:
        runtime = _direct_requirements(RUNTIME_REQUIREMENTS)
        assert "streamlit" not in runtime, "streamlit belongs to the optional legacy set, not to the runtime"

    def test_legacy_set_declares_streamlit(self) -> None:
        legacy = _direct_requirements(LEGACY_REQUIREMENTS)
        assert "streamlit" in legacy, (
            "the legacy operations dashboard keeps its entry point; it must be "
            "installable from requirements-legacy-admin.txt"
        )

    def test_legacy_set_is_not_referenced_by_the_runtime_lock(self) -> None:
        lock_pins = _pins(RUNTIME_LOCK)
        for name in ("streamlit", "pillow", "reportlab"):
            assert name not in lock_pins, f"{name} must not be in the runtime lock"

    def test_legacy_entry_point_still_exists(self) -> None:
        """The dashboard is isolated, not deleted — deleting it is OWNER_DECISION D-1."""
        assert (REPO_ROOT / "legacy" / "admin.py").exists()
