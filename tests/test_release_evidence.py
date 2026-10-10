"""Tests for the release evidence gate and lock-consistency checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_lock_consistency import compare, load_lock, load_manifest
from scripts.check_lock_consistency import main as lock_main
from scripts.check_release_evidence import (
    APPROVED,
    AttestationError,
    evaluate,
    load_attestation,
)
from scripts.check_release_evidence import main as evidence_main

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestReleaseEvidence:
    def test_repository_attestation_is_currently_blocked(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = evidence_main(["--attestation", str(REPO_ROOT / "config/compliance_attestation.yaml")])

        assert code == 1
        output = capsys.readouterr().out
        assert "BLOCKED" in output
        assert "data_rights" in output

    def test_missing_attestation_file_is_blocked_not_approved(self, tmp_path: Path) -> None:
        code = evidence_main(["--attestation", str(tmp_path / "absent.yaml")])

        assert code == 2

    def test_parser_reads_items_and_folded_reasons(self, tmp_path: Path) -> None:
        attestation = tmp_path / "att.yaml"
        attestation.write_text(
            "version: 1\n"
            "reviewer: null\n"
            "items:\n"
            "  data_rights: blocked\n"
            "  privacy_disclosure: blocked\n"
            "reasons:\n"
            "  data_rights: >-\n"
            "    first line\n"
            "    second line\n",
            encoding="utf-8",
        )

        parsed = load_attestation(attestation)

        assert parsed["version"] == "1"
        assert parsed["items"]["data_rights"] == "blocked"
        assert parsed["reasons"]["data_rights"] == "first line second line"

    def test_unapproved_item_blocks_even_with_a_reviewer(self) -> None:
        attestation = {
            "reviewer": "someone",
            "reviewed_at": "2026-01-01",
            "items": {
                "data_rights": APPROVED,
                "privacy_disclosure": "blocked",
                "public_redistribution": APPROVED,
                "third_party_notices": APPROVED,
            },
            "reasons": {},
        }

        result = evaluate(attestation, REPO_ROOT)

        assert result["status"] == "blocked"
        assert any(blocker["item"] == "privacy_disclosure" for blocker in result["blockers"])

    def test_all_items_approved_with_reviewer_passes(self) -> None:
        attestation = {
            "reviewer": "someone",
            "reviewed_at": "2026-01-01",
            "items": {
                name: APPROVED
                for name in (
                    "data_rights",
                    "privacy_disclosure",
                    "public_redistribution",
                    "third_party_notices",
                )
            },
            "reasons": {},
        }

        assert evaluate(attestation, REPO_ROOT)["status"] == APPROVED

    def test_reviewer_without_date_blocks(self) -> None:
        attestation = {
            "reviewer": "someone",
            "reviewed_at": None,
            "items": {
                name: APPROVED
                for name in (
                    "data_rights",
                    "privacy_disclosure",
                    "public_redistribution",
                    "third_party_notices",
                )
            },
            "reasons": {},
        }

        result = evaluate(attestation, REPO_ROOT)

        assert result["status"] == "blocked"
        assert any(blocker["item"] == "reviewed_at" for blocker in result["blockers"])

    def test_attestation_error_is_raised_for_unparseable_input(self, tmp_path: Path) -> None:
        with pytest.raises(AttestationError):
            load_attestation(tmp_path / "nope.yaml")


class TestLockConsistency:
    def test_repository_lock_matches_manifest(self) -> None:
        problems = compare(
            load_lock(REPO_ROOT / "requirements.lock"),
            load_manifest(REPO_ROOT / "requirements.txt"),
        )

        assert problems == []

    def test_upper_bound_violation_is_detected(self, tmp_path: Path) -> None:
        manifest = tmp_path / "requirements.txt"
        manifest.write_text("langsmith>=0.8.18,<0.9.0\n", encoding="utf-8")
        lock = tmp_path / "requirements.lock"
        lock.write_text("langsmith==0.14.7\n", encoding="utf-8")

        problems = compare(load_lock(lock), load_manifest(manifest))

        assert len(problems) == 1
        assert "violates" in problems[0]

    def test_missing_pin_is_detected(self, tmp_path: Path) -> None:
        manifest = tmp_path / "requirements.txt"
        manifest.write_text("fastapi>=0.115.0\n", encoding="utf-8")
        lock = tmp_path / "requirements.lock"
        lock.write_text("sqlalchemy==2.0.0\n", encoding="utf-8")

        problems = compare(load_lock(lock), load_manifest(manifest))

        assert any("not pinned" in problem for problem in problems)

    def test_lower_bound_satisfied_passes(self, tmp_path: Path) -> None:
        manifest = tmp_path / "requirements.txt"
        manifest.write_text("fastapi>=0.115.0\n", encoding="utf-8")
        lock = tmp_path / "requirements.lock"
        lock.write_text("fastapi==0.143.0\n", encoding="utf-8")

        assert compare(load_lock(lock), load_manifest(manifest)) == []

    def test_main_returns_nonzero_on_drift(self, tmp_path: Path) -> None:
        manifest = tmp_path / "requirements.txt"
        manifest.write_text("fastapi>=0.115.0\n", encoding="utf-8")
        lock = tmp_path / "requirements.lock"
        lock.write_text("fastapi==0.100.0\n", encoding="utf-8")

        code = lock_main(["--manifest", str(manifest), "--lock", str(lock)])

        assert code == 1
