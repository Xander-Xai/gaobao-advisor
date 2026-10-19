"""RAG corpus-integrity and provider-selection guarantees.

Covers the P1 findings:
* a missing default manifest must fail closed (not be silently skipped);
* added / renamed corpus files must be detected as an integrity failure;
* manifest-declared hashes and byte counts are enforced;
* manifest filenames cannot escape the corpus directory;
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
    def test_default_corpus_validates(self) -> None:
        ok, reason, stats = rag.validate_corpus(rag.DEFAULT_GROUPS_DIR, rag.DEFAULT_MANIFEST_PATH)
        assert ok, reason
        assert stats["documents"] == 8

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
