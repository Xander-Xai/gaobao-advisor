"""RAG corpus-integrity and provider-selection guarantees.

Covers the P1 findings:
* a missing default manifest must fail closed (not be silently skipped);
* added / renamed corpus files must be detected as an integrity failure;
* manifest-declared hashes and byte counts are enforced;
* manifest filenames cannot escape the corpus directory;
* the shipped SYNTHETIC_DEMO manifest is *strict*: every entry must carry a
  valid sha256 and a non-negative integer byte length (missing/malformed
  metadata is rejected, not skipped);
* symlinked corpus files and backslash/absolute names are rejected;
* configuring an LLM key must not implicitly select a network embedding
  provider — the demo stays offline unless RAG_EMBEDDING_PROVIDER is explicit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from server.services import rag


@pytest.fixture(autouse=True)
def _reset_rag(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "ENABLE_RAG_KB",
        "SILICONFLOW_API_KEY",
        "OPENAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "RAG_EMBEDDING_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)
    rag.reset()
    yield
    rag.reset()


def _write_corpus(root: Path, files: dict[str, str]) -> Path:
    groups = root / "groups"
    groups.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (groups / name).write_text(body, encoding="utf-8")
    return groups


def _file_meta(path: Path) -> dict:
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _manifest(path: Path, files: dict[str, dict]) -> Path:
    path.write_text(json.dumps({"marker": rag.CORPUS_MARKER, "files": files}), encoding="utf-8")
    return path


BODY_A = f"<!-- {rag.CORPUS_MARKER} -->\n## 规则\n平行志愿投档规则示例。\n"
BODY_B = f"<!-- {rag.CORPUS_MARKER} -->\n## 说明\n补充说明示例。\n"


class TestManifestIntegrity:
    def test_default_corpus_validates_strict(self) -> None:
        ok, reason, stats = rag.validate_corpus(rag.DEFAULT_GROUPS_DIR, rag.DEFAULT_MANIFEST_PATH, strict=True)
        assert ok, reason
        assert stats["documents"] == 8

    def test_initialize_default_uses_strict_validation(self) -> None:
        # The shipped corpus passes strict, so startup reaches RAG_ENABLED.
        assert rag.initialize_default() is True
        assert rag.status()["state"] == "RAG_ENABLED"

    def test_missing_manifest_is_rejected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        ok, reason, _ = rag.validate_corpus(str(groups), str(tmp_path / "does-not-exist.json"))
        assert not ok
        assert "manifest is missing" in reason

    def test_added_corpus_file_is_detected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A, "G2_injected.md": BODY_B})
        manifest = _manifest(tmp_path / "manifest.json", {"G1_a.md": _file_meta(groups / "G1_a.md")})
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest))
        assert not ok
        assert "absent from the manifest" in reason
        assert "G2_injected.md" in reason

    def test_hash_tamper_is_detected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = _file_meta(groups / "G1_a.md")
        meta["sha256"] = "0" * 64
        manifest = _manifest(tmp_path / "manifest.json", {"G1_a.md": meta})
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest))
        assert not ok
        assert "integrity hash" in reason

    def test_byte_count_mismatch_is_detected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = _file_meta(groups / "G1_a.md")
        meta["bytes"] = meta["bytes"] + 5
        manifest = _manifest(tmp_path / "manifest.json", {"G1_a.md": meta})
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest))
        assert not ok
        assert "size mismatch" in reason

    def test_manifest_path_escape_is_rejected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        manifest = _manifest(tmp_path / "manifest.json", {"../evil.md": {"sha256": "x"}})
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest))
        assert not ok
        assert "unsafe path" in reason

    def test_configure_missing_manifest_is_fail_closed(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        quotes = tmp_path / "quotes"
        quotes.mkdir()
        with pytest.raises(rag.RagCorpusError):
            rag.configure(str(groups), str(quotes), manifest_path=str(tmp_path / "missing.json"))
        assert rag.status()["state"] == "RAG_ERROR"

    # ── Hardening: symlinks / separators ─────────────────────────────────
    def test_symlinked_corpus_file_is_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text(BODY_A, encoding="utf-8")
        groups = tmp_path / "groups"
        groups.mkdir()
        (groups / "G1_link.md").symlink_to(outside)
        ok, reason, _ = rag.validate_corpus(str(groups))
        assert not ok
        assert "symlink" in reason

    def test_backslash_filename_is_rejected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        (groups / "..\\evil.md").write_text(BODY_A, encoding="utf-8")
        ok, reason, _ = rag.validate_corpus(str(groups))
        assert not ok
        assert "unsafe filename" in reason

    def test_manifest_symlink_is_rejected(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        real = _manifest(tmp_path / "real.json", {"G1_a.md": _file_meta(groups / "G1_a.md")})
        link = tmp_path / "manifest.json"
        link.symlink_to(real)
        ok, reason, _ = rag.validate_corpus(str(groups), str(link))
        assert not ok
        assert "symlink" in reason


class TestStrictManifestContract:
    """The shipped corpus manifest must pin every file by sha256 + bytes."""

    def _valid_entry(self, groups: Path, name: str) -> dict:
        return _file_meta(groups / name)

    def _validate(self, groups: Path, files: dict, manifest_path: Path | None = None, strict: bool = True):
        manifest = _manifest(
            manifest_path or (groups.parent / "manifest.json"),
            files,
        )
        return rag.validate_corpus(str(groups), str(manifest), strict=strict)

    def test_strict_accepts_complete_manifest(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        ok, reason, _ = self._validate(groups, {"G1_a.md": self._valid_entry(groups, "G1_a.md")})
        assert ok, reason

    def test_strict_rejects_missing_sha256(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = self._valid_entry(groups, "G1_a.md")
        del meta["sha256"]
        ok, reason, _ = self._validate(groups, {"G1_a.md": meta})
        assert not ok
        assert "sha256" in reason

    def test_strict_rejects_missing_bytes(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = self._valid_entry(groups, "G1_a.md")
        del meta["bytes"]
        ok, reason, _ = self._validate(groups, {"G1_a.md": meta})
        assert not ok
        assert "bytes" in reason

    @pytest.mark.parametrize("bad_sha", ["", "xyz", "0" * 63, "g" * 64, 12345, None, ["a"]])
    def test_strict_rejects_invalid_sha256_format(self, tmp_path: Path, bad_sha) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = self._valid_entry(groups, "G1_a.md")
        meta["sha256"] = bad_sha
        ok, reason, _ = self._validate(groups, {"G1_a.md": meta})
        assert not ok

    @pytest.mark.parametrize("bad_bytes", [-1, 3.5, "12", True, None])
    def test_strict_rejects_invalid_bytes(self, tmp_path: Path, bad_bytes) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = self._valid_entry(groups, "G1_a.md")
        meta["bytes"] = bad_bytes
        ok, reason, _ = self._validate(groups, {"G1_a.md": meta})
        assert not ok
        assert "bytes" in reason or "size mismatch" in reason

    def test_strict_rejects_non_object_metadata(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        ok, reason, _ = self._validate(groups, {"G1_a.md": "not-an-object"})
        assert not ok
        assert "metadata is not an object" in reason

    def test_strict_rejects_files_not_an_object(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"marker": rag.CORPUS_MARKER, "files": ["G1_a.md"]}), encoding="utf-8")
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest), strict=True)
        assert not ok
        assert "must be an object" in reason

    def test_strict_rejects_non_object_manifest(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest), strict=True)
        assert not ok
        assert "not a JSON object" in reason

    def test_strict_rejects_group_count_mismatch(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "marker": rag.CORPUS_MARKER,
                    "group_count": 5,
                    "files": {"G1_a.md": self._valid_entry(groups, "G1_a.md")},
                }
            ),
            encoding="utf-8",
        )
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest), strict=True)
        assert not ok
        assert "group_count" in reason

    def test_strict_rejects_tampered_file(self, tmp_path: Path) -> None:
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        meta = self._valid_entry(groups, "G1_a.md")
        (groups / "G1_a.md").write_text(BODY_A + "被篡改\n", encoding="utf-8")
        ok, reason, _ = self._validate(groups, {"G1_a.md": meta})
        assert not ok
        assert "integrity hash" in reason

    def test_custom_corpus_may_omit_hashes_when_not_strict(self, tmp_path: Path) -> None:
        """Authorised custom corpora keep the documented, looser contract."""
        groups = _write_corpus(tmp_path, {"G1_a.md": BODY_A})
        manifest = _manifest(tmp_path / "manifest.json", {"G1_a.md": {}})
        ok, reason, _ = rag.validate_corpus(str(groups), str(manifest), strict=False)
        assert ok, reason


class TestOfflineProviderSelection:
    def test_default_provider_is_keyword_even_with_llm_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-select-openai-embeddings")
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-should-not-select-siliconflow")
        assert rag._default_provider() == "keyword"

    def test_configure_uses_keyword_without_explicit_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-llm-only")
        assert rag.validate_corpus(rag.DEFAULT_GROUPS_DIR, rag.DEFAULT_MANIFEST_PATH)[0] is True
        rag.configure(rag.DEFAULT_GROUPS_DIR, rag.DEFAULT_QUOTES_DIR, manifest_path=rag.DEFAULT_MANIFEST_PATH)
        assert rag.status()["provider"] == "keyword"

    def test_explicit_provider_is_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "siliconflow")
        rag.configure(rag.DEFAULT_GROUPS_DIR, rag.DEFAULT_QUOTES_DIR, manifest_path=rag.DEFAULT_MANIFEST_PATH)
        assert rag.status()["provider"] == "siliconflow"
