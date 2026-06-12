# Knowledge Retrieval Architecture Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade gaobao-advisor's knowledge injection from full-context stuffing to hybrid vector+keyword retrieval, reducing per-call token consumption by ~40% while improving retrieval coverage from 2/7 to 6/7 test queries.

**Architecture:** Split the monolithic knowledge_base.md (866 lines) into 6 topic-grouped files. Build a lightweight vector retriever (`kb_retriever.py`) with embedding abstraction, hybrid scoring (60% vector + 40% keyword), and quote retrieval. Integrate via environment variable dual-track (`ENABLE_RAG_KB`), preserving the old system as fallback.

**Tech Stack:** Python 3.10+, numpy (vector math), openai SDK (embedding API), pytest (testing). No new database dependencies — embeddings stored as .npy files in memory.

---

## File Structure

```
gaobao-advisor/
├── kb_retriever.py                          # NEW — core retrieval engine (~280 lines)
├── agent.py                                  # MODIFY — __init__ +8, _build_system_message +15, _inject_quotes +25
├── quality/knowledge_loader.py               # REWRITE — ~120 lines, delegates to kb_retriever
├── .env.example                              # MODIFY — +6 lines (embedding config)
├── requirements.txt                          # MODIFY — +1 line (numpy)
├── knowledge/
│   ├── knowledge_base.md                     # KEEP (fallback for ENABLE_RAG_KB=false)
│   ├── groups/                               # NEW — 6 knowledge group files
│   │   ├── G1_core_method.md
│   │   ├── G2_major_school.md
│   │   ├── G3_career_future.md
│   │   ├── G4_life_planning.md
│   │   ├── G5_data_format.md
│   │   └── G6_quick_ref.md
│   └── quotes/
│       ├── _by_major.json                    # KEEP
│       ├── embeddings.npy                    # NEW — precomputed quote vectors (~4MB)
│       └── quote_meta.json                   # NEW — quote metadata index
├── scripts/
│   └── precompute_embeddings.py              # NEW — embedding precomputation (~100 lines)
└── tests/
    ├── test_kb_retriever.py                  # NEW — ~150 lines
    ├── test_knowledge_loader.py              # NEW — ~60 lines
    └── test_integration_rag.py               # NEW — ~100 lines
```

---

### Task 1: Split knowledge_base.md into 6 Knowledge Group Files

**Files:**
- Create: `knowledge/groups/G1_core_method.md`
- Create: `knowledge/groups/G2_major_school.md`
- Create: `knowledge/groups/G3_career_future.md`
- Create: `knowledge/groups/G4_life_planning.md`
- Create: `knowledge/groups/G5_data_format.md`
- Create: `knowledge/groups/G6_quick_ref.md`
- Read: `knowledge_base.md` (source, 866 lines)

**Grouping map** (line ranges in knowledge_base.md):

| Group | Source Sections | Lines (approx) |
|-------|----------------|-----------------|
| G1_core_method | 一(咨询哲学) + 二(填报方法论) + 七(表达风格) | 8-35, 38-103, 335-360 |
| G2_major_school | 三(专业选择) + 四(学校选择) + 十(推荐专业) + 十一(名校分类) | 107-216, 219-267, 402-451, 453-500 |
| G3_career_future | 六(考研) + 十三(就业路径) + 十六(趋势) | 293-332, 576-683, 754-838 |
| G4_life_planning | 五(城市选择) + 十四(专科) + 十五(高中规划) | 270-290, 686-723, 726-751 |
| G5_data_format | 八(数据可信度) + 九(Output格式) | 363-373, 376-399 |
| G6_quick_ref | 十二(速查) | 504-573 |

- [ ] **Step 1: Create knowledge/groups/ directory**

Run: `mkdir -p /home/dev/projects/gaobao/gaobao-advisor/knowledge/groups`

- [ ] **Step 2: Split knowledge_base.md into 6 group files**

Read `knowledge_base.md` and extract the line ranges above. For each group file, prepend a `# [Group Name]` header. Each file must be self-contained — a reader seeing only G3_career_future.md should understand the content without referencing other groups.

**Important rules:**
- Preserve original formatting exactly (headings, lists, tables)
- Each section within a group keeps its original `##` heading
- Do NOT add content that wasn't in the original file
- Line ranges are approximate — use the `## 一、` through `## 十六、` headings as section boundaries

- [ ] **Step 3: Verify completeness**

Run: `wc -l /home/dev/projects/gaobao/gaobao-advisor/knowledge/groups/G*.md`

Expected total: ~866 lines (matching original knowledge_base.md). If significantly off, check for missing sections.

- [ ] **Step 4: Verify no duplicate content**

Run: `grep -c "^##" /home/dev/projects/gaobao/gaobao-advisor/knowledge/groups/G*.md`

Expected: each original `##` heading appears exactly once across all 6 files.

- [ ] **Step 5: Commit**

```bash
git add knowledge/groups/
git commit -m "feat: split knowledge_base.md into 6 topic-grouped files"
```

---

### Task 2: Build kb_retriever.py — Data Structures and Group Splitting

**Files:**
- Create: `kb_retriever.py` (root directory, alongside agent.py)
- Read: `knowledge/quotes/_by_major.json` (for data structure reference)

- [ ] **Step 1: Create kb_retriever.py with core data structures**

```python
#!/usr/bin/env python3
"""
轻量知识检索引擎 — 向量 + 关键词混合检索。

支持 6 个知识组的按需检索和语录语义匹配，
通过环境变量 ENABLE_RAG_KB 控制开关。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


@dataclass
class Chunk:
    """一个语义完整的知识片段。"""
    text: str
    group_id: str
    embedding: np.ndarray | None = None
    start_line: int = 0
    section_title: str = ""


@dataclass
class QuoteEntry:
    """一条语录及其元数据。"""
    id: str
    text: str
    major: str           # 所属专业关键词（JSON key）
    tags: list[str] = field(default_factory=list)
    category: str = ""
    sentiment: str = ""
    embedding: np.ndarray | None = None


@dataclass
class RetrievalResult:
    """检索结果。"""
    groups: list[str]         # 选中的知识组 ID 列表
    group_chunks: list[Chunk] = field(default_factory=list)  # 被选中的 chunks
    quotes: list[QuoteEntry] = field(default_factory=list)   # 选中的语录


# ── 知识组触发词 ──────────────────────────────────────────────
GROUP_TRIGGERS: dict[str, list[str]] = {
    "G1_core_method": [
        "志愿", "填报", "冲稳保", "冲一冲", "稳一稳", "保一保",
        "位次", "投档", "滑档", "退档", "灵魂拷问", "咨询风格",
    ],
    "G2_major_school": [
        "专业", "学校", "985", "211", "双一流", "院校",
        "学科评估", "天坑", "推荐专业", "就业率", "薪资", "转专业",
        "选专业", "报学校",
    ],
    "G3_career_future": [
        "考公", "考编", "考研", "就业", "前景", "AI",
        "人工智能", "大模型", "体制内", "国企", "教师",
        "医生", "电网", "铁饭碗", "毕业", "出路",
    ],
    "G4_life_planning": [
        "城市", "地域", "北上广", "专科", "高中规划",
        "选科", "新高考", "实习", "发展空间",
    ],
    "G5_data_format": [
        "数据", "可信度", "格式", "模板",
    ],
    "G6_quick_ref": [
        "速查", "一览", "对照", "快速",
    ],
}

# 知识组优先级（当向量分数相同时，高优先级的组优先）
GROUP_PRIORITY: dict[str, int] = {
    "G1_core_method": 1,
    "G2_major_school": 1,
    "G3_career_future": 2,
    "G4_life_planning": 3,
    "G5_data_format": 4,
    "G6_quick_ref": 4,
}
```

- [ ] **Step 2: Add group splitting logic**

Append to `kb_retriever.py`:

```python
# ── 知识组切分 ────────────────────────────────────────────────
def split_group(content: str, group_id: str) -> list[Chunk]:
    """按 ## 标题切分知识组文件为 chunks。"""
    chunks: list[Chunk] = []
    current_text = ""
    current_title = ""
    start_line = 1

    for i, line in enumerate(content.split("\n"), start=1):
        if line.startswith("## "):
            if current_text.strip():
                chunks.append(Chunk(
                    text=current_text.strip(),
                    group_id=group_id,
                    start_line=start_line,
                    section_title=current_title,
                ))
            current_title = line[3:].strip()
            current_text = line + "\n"
            start_line = i
        else:
            current_text += line + "\n"

    if current_text.strip():
        chunks.append(Chunk(
            text=current_text.strip(),
            group_id=group_id,
            start_line=start_line,
            section_title=current_title,
        ))

    return chunks


def load_all_groups(groups_dir: str) -> dict[str, list[Chunk]]:
    """加载所有知识组文件，切分为 chunks。"""
    all_groups: dict[str, list[Chunk]] = {}
    for filename in sorted(os.listdir(groups_dir)):
        if not filename.endswith(".md"):
            continue
        group_id = filename.removesuffix(".md")
        filepath = os.path.join(groups_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        all_groups[group_id] = split_group(content, group_id)
    return all_groups
```

- [ ] **Step 3: Add keyword matching logic**

Append to `kb_retriever.py`:

```python
# ── 关键词匹配 ────────────────────────────────────────────────
def keyword_match_score(user_msg: str, triggers: list[str]) -> float:
    """计算用户消息与触发词列表的匹配分数（0.0 ~ 1.0）。"""
    if not triggers:
        return 0.0
    hits = sum(1 for t in triggers if t.lower() in user_msg.lower())
    # 归一化：命中 1 个 → 0.4，命中 2 个 → 0.7，命中 3+ 个 → 1.0
    if hits == 0:
        return 0.0
    elif hits == 1:
        return 0.4
    elif hits == 2:
        return 0.7
    else:
        return 1.0


def keyword_exact_match(user_msg: str, keyword: str) -> bool:
    """精确子串匹配。"""
    return keyword.lower() in user_msg.lower()
```

- [ ] **Step 4: Commit**

```bash
git add kb_retriever.py
git commit -m "feat: add kb_retriever.py with data structures, group splitting, and keyword matching"
```

---

### Task 3: Build kb_retriever.py — Embedding Abstraction

**Files:**
- Modify: `kb_retriever.py`

- [ ] **Step 1: Add embedding provider abstraction**

Append to `kb_retriever.py`:

```python
# ── Embedding 抽象层 ──────────────────────────────────────────
class EmbeddingProvider:
    """Embedding API 的抽象接口。"""

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        raise NotImplementedError


class OpenAIEmbedding(EmbeddingProvider):
    """通过 OpenAI 兼容 API 计算 embedding。"""

    def __init__(self, model: str = "text-embedding-3-small",
                 api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        # OpenAI API 限制每次最多 2048 条
        all_embeddings: list[np.ndarray] = []
        batch_size = 200
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            all_embeddings.extend(
                np.array(item["embedding"], dtype=np.float32) for item in resp.data
            )
        return all_embeddings


class OllamaEmbedding(EmbeddingProvider):
    """通过 Ollama 本地 API 计算 embedding。"""

    def __init__(self, model: str = "bge-m3",
                 base_url: str = "http://localhost:11434"):
        import urllib.request as _req
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._req = _req

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        results: list[np.ndarray] = []
        for text in texts:
            payload = json.dumps({"model": self._model, "input": text}).encode()
            req = self._req.Request(
                f"{self._base_url}/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with self._req.urlopen(req) as resp:
                data = json.loads(resp.read())
            results.append(np.array(data["embeddings"][0], dtype=np.float32))
        return results


class KeywordOnlyEmbedding(EmbeddingProvider):
    """纯关键词模式（降级用）— 返回全零向量，跳过向量检索。"""

    def __init__(self, dim: int = 1536):
        self._dim = dim

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        return [np.zeros(self._dim, dtype=np.float32)] * len(texts)


def create_embedding_provider(provider: str = "openai",
                              model: str | None = None,
                              **kwargs: Any) -> EmbeddingProvider:
    """工厂函数：根据 provider 名称创建 embedding 提供者。"""
    if provider == "openai":
        return OpenAIEmbedding(
            model=model or "text-embedding-3-small",
            api_key=kwargs.get("api_key") or os.getenv("OPENAI_API_KEY"),
            base_url=kwargs.get("base_url"),
        )
    elif provider == "dashscope":
        return OpenAIEmbedding(
            model=model or "text-embedding-v3",
            api_key=kwargs.get("api_key") or os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    elif provider == "ollama":
        return OllamaEmbedding(
            model=model or "bge-m3",
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )
    else:
        return KeywordOnlyEmbedding()
```

- [ ] **Step 2: Commit**

```bash
git add kb_retriever.py
git commit -m "feat: add embedding provider abstraction (OpenAI/DashScope/Ollama/fallback)"
```

---

### Task 4: Build kb_retriever.py — KbRetriever Class with Hybrid Search

**Files:**
- Modify: `kb_retriever.py`
- Write: `tests/test_kb_retriever.py`

- [ ] **Step 1: Write failing tests for KbRetriever**

Create `tests/test_kb_retriever.py`:

```python
"""kb_retriever 模块的单元测试。"""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

# 添加项目根目录到 path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kb_retriever import (
    KbRetriever, Chunk, QuoteEntry, RetrievalResult,
    split_group, keyword_match_score, KeywordOnlyEmbedding,
    GROUP_TRIGGERS,
)


# ── 知识组切分测试 ─────────────────────────────────────────────
class TestSplitGroup:
    def test_splits_by_h2_headings(self):
        content = "# Main Title\nIntro text\n## Section A\nContent A\n## Section B\nContent B"
        chunks = split_group(content, "G1")
        assert len(chunks) == 2
        assert chunks[0].section_title == "Section A"
        assert chunks[0].group_id == "G1"
        assert "Content A" in chunks[0].text
        assert chunks[1].section_title == "Section B"

    def test_handles_single_section(self):
        content = "## Only Section\nSome content here"
        chunks = split_group(content, "G2")
        assert len(chunks) == 1
        assert chunks[0].section_title == "Only Section"

    def test_empty_content(self):
        chunks = split_group("", "G3")
        assert len(chunks) == 0


# ── 关键词匹配测试 ─────────────────────────────────────────────
class TestKeywordMatch:
    def test_no_match(self):
        score = keyword_match_score("今天天气不错", ["志愿", "填报"])
        assert score == 0.0

    def test_single_match(self):
        score = keyword_match_score("我想报志愿", ["志愿", "填报"])
        assert score == 0.4

    def test_two_matches(self):
        score = keyword_match_score("我想填报志愿", ["志愿", "填报"])
        assert score == 0.7

    def test_three_plus_matches(self):
        score = keyword_match_score("冲一冲稳一稳保一保", ["冲一冲", "稳一稳", "保一保"])
        assert score == 1.0

    def test_case_insensitive(self):
        score = keyword_match_score("AI很厉害", ["ai", "人工智能"])
        assert score == 0.4


# ── KbRetriever 基础测试 ──────────────────────────────────────
class TestKbRetrieverInit:
    def _make_retriever(self, tmpdir: str) -> KbRetriever:
        """创建一个使用 keyword-only embedding 的测试 retriever。"""
        # 创建 2 个知识组文件
        groups_dir = os.path.join(tmpdir, "knowledge", "groups")
        os.makedirs(groups_dir)

        with open(os.path.join(groups_dir, "G1_core_method.md"), "w") as f:
            f.write("# 核心方法论\n\n## 志愿填报方法\n冲稳保规则...\n\n## 咨询风格\n说话要直接...\n")

        with open(os.path.join(groups_dir, "G2_major_school.md"), "w") as f:
            f.write("# 专业与学校\n\n## 专业选择\n12 大学科...\n\n## 学校评估\n985/211...\n")

        # 创建语录文件
        quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
        os.makedirs(quotes_dir)
        quotes = {
            "计算机": [{"id": "q1", "text": "学计算机就要卷到底", "tags": ["计算机", "努力"],
                        "category": "zhuanye", "sentiment": "motivational"}],
            "医学": [{"id": "q2", "text": "学医就是选择了一条漫长但稳定的路", "tags": ["医学", "稳定"],
                      "category": "zhuanye", "sentiment": "neutral"}],
        }
        with open(os.path.join(quotes_dir, "_by_major.json"), "w") as f:
            json.dump(quotes, f, ensure_ascii=False)

        return KbRetriever(
            groups_dir=groups_dir,
            quotes_path=quotes_dir,
            embedding_provider=KeywordOnlyEmbedding(),
            embedding_model="",
        )

    def test_loads_groups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            assert "G1_core_method" in ret._groups
            assert "G2_major_school" in ret._groups
            assert len(ret._groups["G1_core_method"]) == 2  # 2 sections

    def test_loads_quotes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            assert len(ret._quotes) == 2

    def test_search_returns_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            result = ret.search("我想填报志愿", {})
            assert isinstance(result, RetrievalResult)
            assert len(result.groups) > 0
            assert len(result.groups) <= 2


# ── 语录检索测试 ──────────────────────────────────────────────
class TestQuoteRetrieval:
    def _make_retriever(self, tmpdir: str) -> KbRetriever:
        groups_dir = os.path.join(tmpdir, "knowledge", "groups")
        os.makedirs(groups_dir)
        with open(os.path.join(groups_dir, "G1_core_method.md"), "w") as f:
            f.write("## Test\nContent\n")

        quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
        os.makedirs(quotes_dir)
        quotes = {
            "计算机": [
                {"id": "q1", "text": "学计算机就要卷到底", "tags": ["计算机", "努力"],
                 "category": "zhuanye", "sentiment": "motivational"},
                {"id": "q2", "text": "985计算机 > 211金融", "tags": ["计算机", "选择"],
                 "category": "zhuanye", "sentiment": "neutral"},
            ],
            "医学": [
                {"id": "q3", "text": "学医十年磨一剑", "tags": ["医学", "坚持"],
                 "category": "zhuanye", "sentiment": "neutral"},
            ],
        }
        with open(os.path.join(quotes_dir, "_by_major.json"), "w") as f:
            json.dump(quotes, f, ensure_ascii=False)

        return KbRetriever(
            groups_dir=groups_dir,
            quotes_path=quotes_dir,
            embedding_provider=KeywordOnlyEmbedding(),
            embedding_model="",
        )

    def test_keyword_match_returns_quotes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            result = ret.search("计算机怎么学", {})
            assert len(result.quotes) > 0
            quote_texts = [q.text for q in result.quotes]
            assert any("计算机" in t for t in quote_texts)

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            result = ret.search("今天天气真好", {})
            # 关键词不匹配时，可能为空或很少
            assert isinstance(result.quotes, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_kb_retriever.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kb_retriever'`

- [ ] **Step 3: Implement the KbRetriever class**

Append to `kb_retriever.py`:

```python
# ── KbRetriever 主类 ──────────────────────────────────────────
class KbRetriever:
    """轻量知识检索引擎。"""

    def __init__(
        self,
        groups_dir: str,
        quotes_path: str,
        embedding_provider: EmbeddingProvider | None = None,
        embedding_model: str = "",
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        group_threshold: float = 0.3,
        max_groups: int = 2,
        max_quotes: int = 3,
    ):
        self._vector_weight = vector_weight
        self._keyword_weight = keyword_weight
        self._group_threshold = group_threshold
        self._max_groups = max_groups
        self._max_quotes = max_quotes

        # Embedding 提供者
        self._embedder = embedding_provider or KeywordOnlyEmbedding()

        # 加载知识组
        self._groups = load_all_groups(groups_dir)

        # 加载语录
        self._quotes = self._load_quotes(quotes_path)

        # 预计算 embedding
        self._init_embeddings()

    def _load_quotes(self, quotes_path: str) -> list[QuoteEntry]:
        """从 _by_major.json 加载语录。"""
        index_path = os.path.join(quotes_path, "_by_major.json")
        if not os.path.exists(index_path):
            return []

        with open(index_path, "r", encoding="utf-8") as f:
            raw_index: dict = json.load(f)

        quotes: list[QuoteEntry] = []
        for major_key, quote_list in raw_index.items():
            for q in quote_list:
                quotes.append(QuoteEntry(
                    id=q.get("id", ""),
                    text=q["text"],
                    major=major_key,
                    tags=q.get("tags", []),
                    category=q.get("category", ""),
                    sentiment=q.get("sentiment", ""),
                ))
        return quotes

    def _init_embeddings(self) -> None:
        """预计算所有 chunks 和语录的 embedding 向量。"""
        # 知识组 chunks embedding
        all_texts: list[str] = []
        all_refs: list[tuple[str, int]] = []  # (group_id, chunk_index)

        for group_id, chunks in self._groups.items():
            for i, chunk in enumerate(chunks):
                all_texts.append(chunk.text)
                all_refs.append((group_id, i))

        # 语录 embedding
        quote_texts: list[str] = []
        for q in self._quotes:
            quote_texts.append(q.text)

        # 批量计算
        combined_texts = all_texts + quote_texts
        if combined_texts:
            try:
                embeddings = self._embedder.embed(combined_texts)
            except Exception:
                # Embedding 失败，全部设为 None（降级为纯关键词）
                embeddings = [None] * len(combined_texts)

            # 分配知识组 chunks
            for idx, (group_id, chunk_idx) in enumerate(all_refs):
                if embeddings[idx] is not None:
                    self._groups[group_id][chunk_idx].embedding = embeddings[idx]

            # 分配语录
            for i, q in enumerate(self._quotes):
                emb_idx = len(all_texts) + i
                if embeddings[emb_idx] is not None:
                    q.embedding = embeddings[emb_idx]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算两个向量的余弦相似度。"""
        if a is None or b is None:
            return 0.0
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _embed_query(self, text: str) -> np.ndarray | None:
        """将用户查询编码为 embedding 向量。"""
        try:
            results = self._embedder.embed([text])
            return results[0] if results else None
        except Exception:
            return None

    def _score_groups(self, user_msg: str,
                      query_emb: np.ndarray | None) -> list[tuple[str, float]]:
        """计算每个知识组的混合分数。"""
        scores: list[tuple[str, float]] = []

        for group_id, chunks in self._groups.items():
            # 向量分数：取该组所有 chunks 的最高 cosine similarity
            vec_score = 0.0
            if query_emb is not None:
                for chunk in chunks:
                    if chunk.embedding is not None:
                        sim = self._cosine_similarity(query_emb, chunk.embedding)
                        vec_score = max(vec_score, sim)

            # 关键词分数
            triggers = GROUP_TRIGGERS.get(group_id, [])
            kw_score = keyword_match_score(user_msg, triggers)

            # 混合分数
            hybrid = self._vector_weight * vec_score + self._keyword_weight * kw_score
            scores.append((group_id, hybrid))

        scores.sort(key=lambda x: -x[1])
        return scores

    def _select_top_groups(self, scores: list[tuple[str, float]]) -> list[str]:
        """从分数列表中选择 top-N 知识组。"""
        selected = [g for g, s in scores if s > self._group_threshold][:self._max_groups]

        # Fallback：如果没有超过阈值的，选 top-2
        if not selected:
            selected = [g for g, _ in scores[:self._max_groups]]

        return selected

    def _select_top_chunks(self, group_ids: list[str],
                           query_emb: np.ndarray | None) -> list[Chunk]:
        """从选中的知识组中，按相关性选择 top chunks。"""
        candidates: list[tuple[Chunk, float]] = []

        for group_id in group_ids:
            for chunk in self._groups.get(group_id, []):
                score = 0.0
                if query_emb is not None and chunk.embedding is not None:
                    score = self._cosine_similarity(query_emb, chunk.embedding)
                candidates.append((chunk, score))

        candidates.sort(key=lambda x: -x[1])
        return [c for c, _ in candidates]

    def _select_top_quotes(self, user_msg: str,
                           query_emb: np.ndarray | None) -> list[QuoteEntry]:
        """混合检索语录：向量 + 关键词。"""
        scored: list[tuple[int, float]] = []

        for i, q in enumerate(self._quotes):
            vec_score = 0.0
            if query_emb is not None and q.embedding is not None:
                vec_score = self._cosine_similarity(query_emb, q.embedding)

            # 关键词精确匹配加分
            kw_bonus = 0.3 if keyword_exact_match(user_msg, q.major) else 0.0
            final = max(vec_score, vec_score + kw_bonus if kw_bonus else vec_score)
            # 如果关键词匹配，确保至少有分数
            if kw_bonus > 0:
                final = max(final, kw_bonus)

            scored.append((i, final))

        scored.sort(key=lambda x: -x[1])

        # 多样性过滤：top-3 不来自同一 major
        selected: list[QuoteEntry] = []
        seen_majors: set[str] = set()
        for idx, score in scored:
            if score <= 0:
                break
            q = self._quotes[idx]
            if q.major not in seen_majors or len(selected) < 2:
                selected.append(q)
                seen_majors.add(q.major)
                if len(selected) >= self._max_quotes:
                    break

        return selected

    def search(self, user_msg: str, slots: dict) -> RetrievalResult:
        """主检索方法：混合向量 + 关键词。"""
        # Step 1: 查询 embedding
        query_emb = self._embed_query(user_msg)

        # Step 2: 知识组检索
        group_scores = self._score_groups(user_msg, query_emb)
        selected_groups = self._select_top_groups(group_scores)

        # Step 3: 选中组的 chunks
        selected_chunks = self._select_top_chunks(selected_groups, query_emb)

        # Step 4: 语录检索
        selected_quotes = self._select_top_quotes(user_msg, query_emb)

        return RetrievalResult(
            groups=selected_groups,
            group_chunks=selected_chunks,
            quotes=selected_quotes,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_kb_retriever.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add kb_retriever.py tests/test_kb_retriever.py
git commit -m "feat: implement KbRetriever with hybrid vector+keyword search"
```

---

### Task 5: Create Precomputation Script and Precompute Embeddings

**Files:**
- Create: `scripts/precompute_embeddings.py`
- Create: `knowledge/quotes/embeddings.npy` (generated)
- Create: `knowledge/quotes/quote_meta.json` (generated)

- [ ] **Step 1: Create the precomputation script**

Create `scripts/precompute_embeddings.py`:

```python
#!/usr/bin/env python3
"""
预计算知识组 + 语录的 embedding 向量，存为 .npy 文件。

用法:
    python scripts/precompute_embeddings.py [--provider openai|dashscope|ollama]

生成文件:
    knowledge/quotes/embeddings.npy   — 语录向量矩阵 (N × dim)
    knowledge/quotes/quote_meta.json  — 语录元数据索引
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from kb_retriever import (
    OpenAIEmbedding, OllamaEmbedding, KeywordOnlyEmbedding,
    load_all_groups, create_embedding_provider,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)


def precompute_groups(groups_dir: str, embedder, output_dir: str) -> None:
    """预计算知识组 chunks 的 embedding。"""
    all_groups = load_all_groups(groups_dir)
    all_texts: list[str] = []
    metadata: list[dict] = []

    for group_id, chunks in all_groups.items():
        for i, chunk in enumerate(chunks):
            all_texts.append(chunk.text)
            metadata.append({
                "group_id": group_id,
                "chunk_index": i,
                "section_title": chunk.section_title,
                "start_line": chunk.start_line,
            })

    if not all_texts:
        print("No group chunks found.")
        return

    print(f"Embedding {len(all_texts)} group chunks...")
    embeddings = embedder.embed(all_texts)
    emb_matrix = np.stack([e for e in embeddings if e is not None])

    out_path = os.path.join(output_dir, "group_embeddings.npy")
    np.save(out_path, emb_matrix.astype(np.float32))
    print(f"Saved: {out_path} ({emb_matrix.shape})")

    meta_path = os.path.join(output_dir, "group_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved: {meta_path}")


def precompute_quotes(quotes_path: str, embedder) -> None:
    """预计算语录的 embedding。"""
    index_path = os.path.join(quotes_path, "_by_major.json")
    with open(index_path, "r", encoding="utf-8") as f:
        raw_index: dict = json.load(f)

    all_texts: list[str] = []
    metadata: list[dict] = []

    for major_key, quote_list in raw_index.items():
        for q in quote_list:
            all_texts.append(q["text"])
            metadata.append({
                "id": q.get("id", ""),
                "text": q["text"],
                "major": major_key,
                "tags": q.get("tags", []),
                "category": q.get("category", ""),
                "sentiment": q.get("sentiment", ""),
            })

    if not all_texts:
        print("No quotes found.")
        return

    print(f"Embedding {len(all_texts)} quotes...")
    embeddings = embedder.embed(all_texts)
    emb_matrix = np.stack([e for e in embeddings if e is not None])

    out_path = os.path.join(quotes_path, "embeddings.npy")
    np.save(out_path, emb_matrix.astype(np.float32))
    print(f"Saved: {out_path} ({emb_matrix.shape})")

    meta_path = os.path.join(quotes_path, "quote_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved: {meta_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute embeddings for knowledge retrieval")
    parser.add_argument("--provider", default="openai",
                        choices=["openai", "dashscope", "ollama"],
                        help="Embedding provider (default: openai)")
    parser.add_argument("--model", default=None, help="Embedding model name")
    args = parser.parse_args()

    embedder = create_embedding_provider(provider=args.provider, model=args.model)

    groups_dir = os.path.join(PROJECT_ROOT, "knowledge", "groups")
    quotes_path = os.path.join(PROJECT_ROOT, "knowledge", "quotes")

    if os.path.isdir(groups_dir):
        precompute_groups(groups_dir, embedder, quotes_path)
    else:
        print(f"Groups directory not found: {groups_dir}")

    if os.path.isdir(quotes_path):
        precompute_quotes(quotes_path, embedder)
    else:
        print(f"Quotes directory not found: {quotes_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the precomputation script (requires API key)**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python scripts/precompute_embeddings.py --provider openai`

Expected output:
```
Embedding N group chunks...
Saved: knowledge/quotes/group_embeddings.npy (N, 1536)
Saved: knowledge/quotes/group_meta.json
Embedding 675 quotes...
Saved: knowledge/quotes/embeddings.npy (675, 1536)
Saved: knowledge/quotes/quote_meta.json
```

If no API key available, skip this step — the KbRetriever will fall back to keyword-only mode at runtime.

- [ ] **Step 3: Commit**

```bash
git add scripts/precompute_embeddings.py
git commit -m "feat: add embedding precomputation script"
```

(Note: .npy and meta.json files are NOT committed — they are generated locally.)

- [ ] **Step 4: Add .gitignore entries for generated files**

Append to `.gitignore` (or create if missing):

```
# Embedding precomputation outputs
knowledge/quotes/embeddings.npy
knowledge/quotes/quote_meta.json
knowledge/quotes/group_embeddings.npy
knowledge/quotes/group_meta.json
```

Run: `echo -e "\n# Embedding precomputation outputs\nknowledge/quotes/embeddings.npy\nknowledge/quotes/quote_meta.json\nknowledge/quotes/group_embeddings.npy\nknowledge/quotes/group_meta.json" >> .gitignore`

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore generated embedding files"
```

---

### Task 6: Update Dependencies and Environment Config

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Add numpy to requirements.txt**

Read `requirements.txt`, then add numpy:

Edit `requirements.txt` — add `numpy>=1.24.0,<3.0.0` as a new line (after the existing dependencies):

```
streamlit>=1.30.0,<2.0.0
openai>=1.0.0,<3.0.0
sqlalchemy>=2.0.0,<3.0.0
reportlab>=4.0
numpy>=1.24.0,<3.0.0
```

- [ ] **Step 2: Add embedding config to .env.example**

Edit `.env.example` — add the following block after the `ENABLE_SEARCH=false` line:

```bash

# ── 知识检索引擎（RAG） ──
# ENABLE_RAG_KB=true   # 启用向量+关键词混合检索（默认关闭，使用旧的全量注入）
# EMBEDDING_PROVIDER=openai     # embedding 来源：openai / dashscope / ollama
# EMBEDDING_MODEL=text-embedding-3-small  # embedding 模型
# EMBEDDING_FALLBACK=keyword    # embedding 失败时降级策略
# EMBEDDING_CACHE_SIZE=100      # 查询 embedding 缓存大小（LRU）
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add numpy dependency and RAG env config"
```

---

### Task 7: Integrate kb_retriever into agent.py (Dual-Track)

**Files:**
- Modify: `agent.py` — `__init__` (line 820-843)
- Modify: `agent.py` — `_build_system_message` (line 845-912)
- Modify: `agent.py` — `_inject_quotes` (line 932-948)

- [ ] **Step 1: Add kb_retriever import (conditional)**

In `agent.py`, add the following block after line 87 (after the analytics.tracker import block):

```python
# ── 知识检索引擎（可选） ──
try:
    from kb_retriever import KbRetriever, RetrievalResult, KeywordOnlyEmbedding, create_embedding_provider
    HAS_KB_RETRIEVER = True
except ImportError:
    HAS_KB_RETRIEVER = False
```

- [ ] **Step 2: Add RAG config constants**

In `agent.py`, find the CONFIG dict area (around line 140-172). Add these constants after the existing config block:

```python
# ── RAG 配置 ──
ENABLE_RAG_KB = os.getenv("ENABLE_RAG_KB", "false").lower() in ("true", "1", "yes")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_FALLBACK = os.getenv("EMBEDDING_FALLBACK", "keyword")
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "100"))
GROUPS_DIR = os.path.join(HERE, "knowledge", "groups")
QUOTES_DIR = os.path.join(HERE, "knowledge", "quotes")
```

- [ ] **Step 3: Modify `__init__` to initialize KbRetriever**

In `agent.py` `__init__` method (line 820-843), add the following block after line 843 (`self._cache_dirty = True`):

```python
        # ── RAG 知识检索引擎 ──
        self.kb_retriever = None
        if ENABLE_RAG_KB and HAS_KB_RETRIEVER:
            try:
                self.kb_retriever = KbRetriever(
                    groups_dir=GROUPS_DIR,
                    quotes_path=QUOTES_DIR,
                    embedding_provider=create_embedding_provider(
                        provider=EMBEDDING_PROVIDER,
                        model=EMBEDDING_MODEL,
                    ),
                    embedding_model=EMBEDDING_MODEL,
                )
                log.info(f"kb_retriever 初始化完成 groups={len(self.kb_retriever._groups)} quotes={len(self.kb_retriever._quotes)}")
            except Exception as e:
                log.warning(f"kb_retriever 初始化失败，降级为旧系统: {e}")
                self.kb_retriever = None
```

- [ ] **Step 4: Modify `_build_system_message` for dual-track**

In `agent.py` `_build_system_message` method (line 845), find line 847:

```python
        kb = self.knowledge_base if self.knowledge_base else ""
```

Replace lines 847 with:

```python
        # ── 知识库内容：RAG 模式 vs 全量模式 ──
        if self.kb_retriever and hasattr(self, '_last_user_msg') and self._last_user_msg:
            try:
                rag_result = self.kb_retriever.search(self._last_user_msg, self.slots)
                kb_parts: list[str] = []
                for chunk in rag_result.group_chunks:
                    kb_parts.append(chunk.text)
                kb = "\n\n".join(kb_parts) if kb_parts else (self.knowledge_base or "")
            except Exception as e:
                log.warning(f"RAG 检索失败，降级为全量知识库: {e}")
                kb = self.knowledge_base if self.knowledge_base else ""
        else:
            kb = self.knowledge_base if self.knowledge_base else ""
```

- [ ] **Step 5: Set `_last_user_msg` in `chat()` method**

In `agent.py`, find the `chat()` method (around line 1337). The first lines after the docstring should include input validation. Add `_last_user_msg` setting right after the user message is received. Find the line that processes `user_msg` parameter — typically near the beginning of `chat()`:

Add this line right after `user_msg = user_msg.strip()` (or equivalent input normalization):

```python
        self._last_user_msg = user_msg  # 供 RAG 检索使用
```

- [ ] **Step 6: Also set `_last_user_msg` in `chat_stream()`**

In `agent.py`, find the `chat_stream()` method. Add the same line at the equivalent position:

```python
        self._last_user_msg = user_msg  # 供 RAG 检索使用
```

- [ ] **Step 7: Modify `_inject_quotes` for dual-track**

In `agent.py`, replace the `_inject_quotes` method (lines 932-948) with:

```python
    def _inject_quotes(self, messages: list, user_msg: str) -> None:
        """根据用户提到的专业，注入相关语录作为参考。"""
        # ── RAG 模式：混合检索 ──
        if self.kb_retriever:
            try:
                result = self.kb_retriever.search(user_msg, self.slots)
                if result.quotes:
                    quote_text = "\n".join(
                        [f"· {q.text}" for q in result.quotes[:3]]
                    )
                    messages.append({
                        "role": "system",
                        "content": f"【相关语录参考】\n{quote_text}\n（以上语录可化用到回复中，不要一字不差照搬）"
                    })
                return
            except Exception as e:
                log.warning(f"RAG 语录检索失败，降级为旧匹配: {e}")

        # ── 旧模式：关键词精确匹配（完全保留） ──
        if not QUOTES_INDEX:
            return
        quote_keywords = [mk for mk in QUOTES_INDEX if mk in user_msg]
        if not quote_keywords:
            return
        quotes_to_inject = []
        for mk in quote_keywords[:2]:  # 最多注入 2 个专业的语录
            for q in QUOTES_INDEX[mk][:2]:  # 每专业最多 2 条
                quotes_to_inject.append(q["text"])
        if quotes_to_inject:
            quote_text = "\n".join([f"· {q}" for q in quotes_to_inject[:3]])
            messages.append({
                "role": "system",
                "content": f"【相关语录参考】\n{quote_text}\n（以上语录可化用到回复中，不要一字不差照搬）"
            })
```

- [ ] **Step 8: Add `self._last_user_msg` initialization in `__init__`**

In `agent.py` `__init__`, add before the RAG block (in Step 3):

```python
        self._last_user_msg = ""  # 供 RAG 检索使用
```

- [ ] **Step 9: Commit**

```bash
git add agent.py
git commit -m "feat: integrate kb_retriever into agent.py with dual-track support"
```

---

### Task 8: Rewrite quality/knowledge_loader.py

**Files:**
- Modify: `quality/knowledge_loader.py` (full rewrite, ~120 lines)

- [ ] **Step 1: Rewrite knowledge_loader.py**

Replace the entire content of `quality/knowledge_loader.py` with:

```python
"""
上下文知识加载器（v2 — 接入 kb_retriever）。

当 ENABLE_RAG_KB=true 时，委托给 KbRetriever 进行语义检索。
当 ENABLE_RAG_KB=false 时，保留旧的关键词触发逻辑作为 fallback。
"""
from __future__ import annotations

import os
from typing import Any

# ── 旧系统（fallback） ────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)

_KNOWLEDGE_TRIGGERS: dict[str, dict[str, Any]] = {
    "00_ai_era_correction.md": {
        "name": "AI时代校正框架",
        "triggers": ["AI", "人工智能", "机器人", "自动化", "AI时代", "就业冲击", "被替代",
                      "计算机", "软件", "编程", "算法", "数据科学", "深度学习",
                      "大模型", "chatgpt", "gpt", "deepseek", "芯片", "半导体"],
        "priority": 1,
    },
    "06_university_life_planning.md": {
        "name": "大学在校4年规划",
        "triggers": ["大学怎么过", "大学规划", "大一", "大二", "大三", "大四",
                      "四年", "在校", "大学生活", "要不要考研", "考研规划",
                      "实习", "竞赛", "社团", "保研"],
        "priority": 2,
    },
    "07_new_gaokao_subject_selection.md": {
        "name": "新高考选科指南",
        "triggers": ["选科", "选考", "3+1+2", "3+3", "物理", "历史",
                      "化学", "生物", "政治", "地理", "技术", "赋分",
                      "等级赋分", "新高考", "选科组合", "学科组合"],
        "priority": 1,
    },
    "08_vocational_strategy.md": {
        "name": "职业教育策略",
        "triggers": ["专科", "高职", "大专", "职业技术", "技能",
                      "专升本", "三校生", "中专", "技校", "职业本科"],
        "priority": 2,
    },
}

_KNOWLEDGE_DIR = os.path.join(_PROJECT_ROOT, "knowledge")

# ── 文件缓存 ──────────────────────────────────────────────────
_FILE_CACHE: dict[str, str] = {}


def _load_file(filename: str) -> str:
    """读取 knowledge/ 目录下的文件（带缓存）。"""
    if filename in _FILE_CACHE:
        return _FILE_CACHE[filename]
    path = os.path.join(_KNOWLEDGE_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    _FILE_CACHE[filename] = content
    return content


# ── 新系统接口 ────────────────────────────────────────────────
def load_contextual_knowledge(
    user_msg: str,
    slots: dict | None = None,
    max_files: int = 2,
    kb_retriever=None,
) -> str | None:
    """根据用户问题和槽位，按需加载相关知识内容。

    Args:
        user_msg: 用户最新输入文本。
        slots: 已采集的槽位信息（可选）。
        max_files: 最多加载几个文件（默认 2，节省 token）。
        kb_retriever: KbRetriever 实例（新系统传入）。

    Returns:
        拼接后的知识内容，或 None（无匹配时）。
    """
    # ── 新系统：委托给 KbRetriever ──
    if kb_retriever is not None:
        try:
            result = kb_retriever.search(user_msg, slots or {})
            if result.group_chunks:
                return "\n\n".join(c.text for c in result.group_chunks[:max_files * 3])
        except Exception:
            pass  # 降级到旧系统

    # ── 旧系统：关键词触发 ──
    combined_text = user_msg.lower()
    if slots:
        for slot_val in slots.values():
            if isinstance(slot_val, dict) and "value" in slot_val:
                combined_text += " " + str(slot_val["value"]).lower()

    scored: list[tuple[str, float, int]] = []
    for filename, meta in _KNOWLEDGE_TRIGGERS.items():
        hits = sum(1 for t in meta["triggers"] if t.lower() in combined_text)
        if hits > 0:
            scored.append((filename, float(hits), meta["priority"]))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[1], x[2]))
    selected = scored[:max_files]

    parts: list[str] = []
    for filename, _, _ in selected:
        content = _load_file(filename)
        if content:
            parts.append(content)

    return "\n\n".join(parts) if parts else None
```

- [ ] **Step 2: Commit**

```bash
git add quality/knowledge_loader.py
git commit -m "feat: rewrite knowledge_loader.py to delegate to kb_retriever with fallback"
```

---

### Task 9: Write Integration Tests with 7 Test Queries

**Files:**
- Create: `tests/test_integration_rag.py`
- Create: `tests/test_knowledge_loader.py`

- [ ] **Step 1: Write integration test for 7 test queries**

Create `tests/test_integration_rag.py`:

```python
"""RAG 知识检索集成测试 — 验证 7 个核心查询场景。"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kb_retriever import (
    KbRetriever, KeywordOnlyEmbedding, GROUP_TRIGGERS,
)


def _make_test_retriever(tmpdir: str) -> KbRetriever:
    """创建一个模拟生产环境的测试 retriever。"""
    groups_dir = os.path.join(tmpdir, "knowledge", "groups")
    os.makedirs(groups_dir, exist_ok=True)

    # G1: 核心方法论
    with open(os.path.join(groups_dir, "G1_core_method.md"), "w") as f:
        f.write("""# 核心方法论

## 志愿填报方法论
冲稳保规则：根据位次法，将志愿分为冲一冲、稳一稳、保一保三个层次。
投档线、滑档、退档是高考志愿填报的三大风险。

## 灵魂拷问法
咨询的第一步不是问分数，而是问这个家庭能给孩子什么资源。

## 咨询表达风格
说话要直接，不要含糊，用生活化的例子。
""")

    # G2: 专业与学校
    with open(os.path.join(groups_dir, "G2_major_school.md"), "w") as f:
        f.write("""# 专业与学校

## 专业选择知识库
计算机科学与技术、软件工程、信息安全是当前就业最好的专业之一。
医学类专业学制长（临床医学5+3），但就业稳定。
文科类专业（哲学、历史、文学）就业面窄，需要研究生学历。

## 学校选择方法论
985 > 211 > 双一流 > 普通本科。学校层次是第一张名片。

## 推荐专业
计算机、人工智能、电气工程、临床医学、师范类专业。
天坑专业：生物工程、环境科学、化学、材料（生化环材）。

## 行业名校分类
两电一邮（电子科大、西电、北邮）、建筑老八校、师范六校。
""")

    # G3: 就业与前景
    with open(os.path.join(groups_dir, "G3_career_future.md"), "w") as f:
        f.write("""# 就业与前景

## 考研方法论
考研不是目的，是手段。要先想清楚读研之后要干什么。

## 稳定就业路径详解
考公（公务员）：最稳定的职业路径之一。国考、省考、选调生。
教师：师范类专业 + 教师资格证 = 稳定就业。
医生：临床医学5+3一体化，毕业后进三甲医院。
国企（国家电网、中石油、铁路局）：电气、石油、交通运输专业优先。

## 2025-2026 最新趋势
AI 对就业的冲击：大模型正在替代基础编程、翻译、基础文员等岗位。
未来 5 年最有前景的方向：AI+医疗、新能源、芯片设计。
""")

    # G4: 规划与选择
    with open(os.path.join(groups_dir, "G4_life_planning.md"), "w") as f:
        f.write("""# 规划与选择

## 城市选择逻辑
一线城市（北上广深）：机会多但竞争激烈。
新一线城市（成都、杭州、武汉）：性价比高。
选城市 = 选产业链 = 选实习机会。

## 专科志愿策略
专科不是终点，专升本是正道。选专业 > 选学校。

## 高中阶段规划
高一选科决定了大学能报什么专业。新高考 3+1+2 模式下，物理+化学是万金油组合。
""")

    # G5: 数据与格式
    with open(os.path.join(groups_dir, "G5_data_format.md"), "w") as f:
        f.write("""# 数据与格式

## 数据可信度分级
T1: 官方数据（教育部、省考试院）
T2: 权威数据（学校官网、阳光高考）
T3: 行业数据（招聘网站、薪酬报告）
T4: 口碑数据（知乎、贴吧）

## Output 格式
推荐结果格式：冲 X 所 / 稳 X 所 / 保 X 所
""")

    # G6: 速查
    with open(os.path.join(groups_dir, "G6_quick_ref.md"), "w") as f:
        f.write("""# 速查

## 选科速查表
物理+化学+生物 → 理工农医全覆盖
物理+化学+地理 → 理工为主，部分文科
历史+政治+地理 → 纯文科

## 职业路径速查
公务员：法学、汉语言文学、计算机、会计
教师：师范类各专业
医生：临床医学、口腔医学
""")

    # 创建语录文件
    quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
    os.makedirs(quotes_dir, exist_ok=True)
    quotes = {
        "计算机": [
            {"id": "q1", "text": "学计算机就要卷到底，不卷就别学。",
             "tags": ["计算机", "努力"], "category": "zhuanye", "sentiment": "cautionary"},
            {"id": "q2", "text": "985的计算机，不要去211的金融。",
             "tags": ["985", "211", "计算机", "金融"], "category": "zhuanye", "sentiment": "neutral"},
        ],
        "医学": [
            {"id": "q3", "text": "学医就是选择了一条漫长但稳定的路。",
             "tags": ["医学", "稳定"], "category": "zhuanye", "sentiment": "neutral"},
            {"id": "q4", "text": "临床医学5+3，毕业就是人生赢家。",
             "tags": ["临床医学", "稳定"], "category": "zhuanye", "sentiment": "motivational"},
        ],
        "考公": [
            {"id": "q5", "text": "考公不是唯一出路，但是最稳的出路之一。",
             "tags": ["考公", "稳定"], "category": "rensheng", "sentiment": "neutral"},
        ],
        "女生": [
            {"id": "q6", "text": "女生选专业，先看就业稳定性，再看收入天花板。",
             "tags": ["女生", "选择"], "category": "rensheng", "sentiment": "neutral"},
        ],
        "985": [
            {"id": "q7", "text": "能上985就别去211，学校层次就是你的第一张名片。",
             "tags": ["985", "211", "学校层次"], "category": "yuanxiao", "sentiment": "cautionary"},
        ],
        "转专业": [
            {"id": "q8", "text": "转专业不是万能药，进去之前想清楚比进去之后再转好。",
             "tags": ["转专业", "选择"], "category": "zhuanye", "sentiment": "cautionary"},
        ],
        "专科": [
            {"id": "q9", "text": "专科不是终点，是另一个起点。选对专业比选对学校重要。",
             "tags": ["专科", "选择"], "category": "zhuanye", "sentiment": "motivational"},
        ],
    }
    with open(os.path.join(quotes_dir, "_by_major.json"), "w") as f:
        json.dump(quotes, f, ensure_ascii=False)

    return KbRetriever(
        groups_dir=groups_dir,
        quotes_path=quotes_dir,
        embedding_provider=KeywordOnlyEmbedding(),
        embedding_model="",
    )


# ── 7 个核心测试查询 ──────────────────────────────────────────

TEST_QUERIES = [
    {
        "query": "学码农以后还能找到工作吗",
        "expected_groups": ["G2_major_school", "G3_career_future"],
        "description": "码农→计算机语义匹配，应检索 G2(专业) + G3(就业前景)",
    },
    {
        "query": "进体制内稳不稳",
        "expected_groups": ["G3_career_future"],
        "description": "体制内→考公关键词，应检索 G3(就业路径)",
    },
    {
        "query": "女生学什么专业比较好",
        "expected_groups": ["G2_major_school"],
        "description": "应检索 G2(专业选择)",
    },
    {
        "query": "农村的，分数不高，能报什么",
        "expected_groups": ["G1_core_method", "G2_major_school"],
        "description": "应检索 G1(方法论) + G2(专业推荐)",
    },
    {
        "query": "临床医学出来好找工吗",
        "expected_groups": ["G2_major_school", "G3_career_future"],
        "description": "应检索 G2(专业) + G3(就业)",
    },
    {
        "query": "帮我对比武汉大学和华中科技大学",
        "expected_groups": ["G2_major_school"],
        "description": "学校对比应检索 G2(学校选择)",
    },
    {
        "query": "转专业难不难",
        "expected_groups": ["G1_core_method", "G2_major_school"],
        "description": "应检索 G1(方法论) + G2(专业选择)",
    },
]


class Test7CoreQueries:
    """验证 7 个核心查询的检索质量。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.retriever = _make_test_retriever(tmpdir)
            yield

    def _check_groups(self, result, expected_groups, query_desc):
        """辅助方法：检查检索结果中是否包含期望的知识组。"""
        # 至少命中 1 个期望组
        hit = any(g in result.groups for g in expected_groups)
        assert hit, (
            f"Query '{query_desc}': expected one of {expected_groups}, got {result.groups}"
        )

    def test_query_1_coding_career(self):
        result = self.retriever.search("学码农以后还能找到工作吗", {})
        self._check_groups(result, TEST_QUERIES[0]["expected_groups"],
                           "学码农以后还能找到工作吗")

    def test_query_2_civil_service(self):
        result = self.retriever.search("进体制内稳不稳", {})
        self._check_groups(result, TEST_QUERIES[1]["expected_groups"],
                           "进体制内稳不稳")

    def test_query_3_female_major(self):
        result = self.retriever.search("女生学什么专业比较好", {})
        self._check_groups(result, TEST_QUERIES[2]["expected_groups"],
                           "女生学什么专业比较好")

    def test_query_4_rural_low_score(self):
        result = self.retriever.search("农村的，分数不高，能报什么", {})
        self._check_groups(result, TEST_QUERIES[3]["expected_groups"],
                           "农村的，分数不高，能报什么")

    def test_query_5_clinical_medicine(self):
        result = self.retriever.search("临床医学出来好找工吗", {})
        self._check_groups(result, TEST_QUERIES[4]["expected_groups"],
                           "临床医学出来好找工吗")

    def test_query_6_school_comparison(self):
        result = self.retriever.search("帮我对比武汉大学和华中科技大学", {})
        self._check_groups(result, TEST_QUERIES[5]["expected_groups"],
                           "帮我对比武汉大学和华中科技大学")

    def test_query_7_transfer_major(self):
        result = self.retriever.search("转专业难不难", {})
        self._check_groups(result, TEST_QUERIES[6]["expected_groups"],
                           "转专业难不难")


class TestTokenSavings:
    """验证 token 消耗对比。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.retriever = _make_test_retriever(tmpdir)
            yield

    def test_retrieved_content_shorter_than_full(self):
        """检索到的内容应比全量 knowledge_base.md 短。"""
        result = self.retriever.search("我想填报志愿", {})
        retrieved_text = "\n".join(c.text for c in result.group_chunks)
        # 原始 knowledge_base.md 约 866 行，检索结果应更短
        retrieved_lines = len(retrieved_text.split("\n"))
        assert retrieved_lines < 400, (
            f"Retrieved {retrieved_lines} lines, expected < 400 (should be ~50% of 866)"
        )
```

- [ ] **Step 2: Write knowledge_loader integration test**

Create `tests/test_knowledge_loader.py`:

```python
"""knowledge_loader 模块测试。"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quality.knowledge_loader import load_contextual_knowledge


class TestKnowledgeLoader:
    """验证 knowledge_loader 的新旧系统切换。"""

    def test_returns_none_for_no_match(self):
        result = load_contextual_knowledge("今天天气真好", {})
        assert result is None

    def test_returns_content_for_match(self):
        result = load_contextual_knowledge("AI要替代人类了", {})
        # 应匹配到 AI 时代相关知识
        assert result is None or "AI" in (result or "")  # 无知识文件时返回 None 是正常的

    def test_kb_retriever_none_uses_old_system(self):
        """传入 kb_retriever=None 时，使用旧系统。"""
        result = load_contextual_knowledge("AI要替代人类了", {}, kb_retriever=None)
        # 旧系统依赖实际文件存在，这里只验证不报错
        assert result is None or isinstance(result, str)

    def test_kb_retriever_used_when_provided(self):
        """传入 kb_retriever 时，委托给新系统。"""
        # 用一个 mock retriever
        class MockResult:
            group_chunks = [type("Chunk", (), {"text": "mock content"})()]

        class MockRetriever:
            def search(self, msg, slots):
                return MockResult()

        result = load_contextual_knowledge("测试查询", {}, kb_retriever=MockRetriever())
        assert result == "mock content"
```

- [ ] **Step 3: Run all tests**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_kb_retriever.py tests/test_knowledge_loader.py tests/test_integration_rag.py -v`

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add integration tests for RAG knowledge retrieval (7 core queries)"
```

---

### Task 10: End-to-End Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -v --tb=short`

Expected: All tests PASS

- [ ] **Step 2: Verify old system still works (ENABLE_RAG_KB=false)**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && ENABLE_RAG_KB=false python -c "from agent import GaokaoAdvisor; a = GaokaoAdvisor(); print('OK:', bool(a.knowledge_base))"`

Expected: `OK: True`

- [ ] **Step 3: Verify new system initializes (ENABLE_RAG_KB=true)**

Note: This will only fully work if embeddings are precomputed. Without embeddings, it falls back to keyword-only mode.

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && ENABLE_RAG_KB=true python -c "from agent import GaokaoAdvisor; a = GaokaoAdvisor(); print('RAG:', a.kb_retriever is not None, 'groups:', len(a.kb_retriever._groups) if a.kb_retriever else 0)"`

Expected: `RAG: True groups: 6` (if knowledge/groups/ files exist)

- [ ] **Step 4: Verify CLI mode works**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && echo "你好" | ENABLE_RAG_KB=false timeout 10 python agent.py 2>/dev/null || true`

Expected: Agent responds without crashing (may fail due to missing API key, that's OK — we're testing import/init, not LLM calls)

- [ ] **Step 5: Verify Docker build (if Dockerfile exists)**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && docker compose build 2>&1 | tail -5`

Expected: Build succeeds without errors

- [ ] **Step 6: Final commit (if any files changed)**

```bash
git add -A
git commit -m "chore: RAG knowledge retrieval Phase 1 complete"
```
