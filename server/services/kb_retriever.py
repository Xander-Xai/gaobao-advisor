#!/usr/bin/env python3
"""
轻量知识检索引擎 — 向量 + 关键词混合检索。

支持 6 个知识组的按需检索和语录语义匹配，
通过环境变量 ENABLE_RAG_KB 控制开关。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

import numpy as np  # noqa: E402

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
    major: str  # 所属专业关键词（JSON key）
    tags: list[str] = field(default_factory=list)
    category: str = ""
    sentiment: str = ""
    embedding: np.ndarray | None = None
    source: str = ""  # 出处（节目/直播/讲座）
    year: int = 0  # 发表年份（0=长期/未知）


@dataclass
class RetrievalResult:
    """检索结果。"""

    groups: list[str]  # 选中的知识组 ID 列表
    group_chunks: list[Chunk] = field(default_factory=list)
    quotes: list[QuoteEntry] = field(default_factory=list)


GROUP_TRIGGERS: dict[str, list[str]] = {
    "G1_core_method": [
        "志愿",
        "填报",
        "冲稳保",
        "冲一冲",
        "稳一稳",
        "保一保",
        "位次",
        "投档",
        "滑档",
        "退档",
        "灵魂拷问",
        "咨询风格",
    ],
    "G2_major_school": [
        "专业",
        "学校",
        "985",
        "211",
        "双一流",
        "院校",
        "学科评估",
        "天坑",
        "推荐专业",
        "就业率",
        "薪资",
        "转专业",
        "选专业",
        "报学校",
    ],
    "G3_career_future": [
        "就业",
        "前景",
        "AI",
        "人工智能",
        "大模型",
        "毕业",
        "出路",
        "行业",
        "趋势",
        "市场",
        "薪资",
        "体制内",
        "考公",
        "考编",
    ],
    "G4_life_planning": [
        "城市",
        "地域",
        "北上广",
        "专科",
        "高中规划",
        "选科",
        "新高考",
        "实习",
        "发展空间",
    ],
    "G5_data_format": [
        "数据",
        "可信度",
        "格式",
        "模板",
    ],
    "G6_quick_ref": [
        "速查",
        "一览",
        "对照",
        "快速",
    ],
    "G7_employment_paths": [
        "教师",
        "医生",
        "公务员",
        "考公",
        "考编",
        "国企",
        "央企",
        "电网",
        "铁路",
        "烟草",
        "军工",
        "航天",
        "银行",
        "编制",
        "稳定就业",
        "铁饭碗",
        "央国企",
        "石油",
        "就业路径",
    ],
    "G8_graduate_and_vocational": [
        "考研",
        "研究生",
        "专硕",
        "学硕",
        "研招",
        "二战",
        "读研",
        "专科",
        "双高",
        "高职",
        "专升本",
        "升本率",
    ],
    "G9_zhangxuefeng_methodology_origin": [
        "张雪峰",
        "雪峰",
        "方法论溯源",
        "为什么这么说",
        "张雪峰的故事",
        "张雪峰的经历",
        "他的人生",
        "他者视角",
        "批评",
        "盲点",
        "局限",
        "访谈",
        "说过",
        "行为模式",
        "决策",
        "《演说家》",
        "综艺",
        "直播",
        "讲座",
        "雪峰蔚来",
    ],
}


# 张雪峰原版金句触发词——提及这些时优先召回 zhangxuefeng 金句
# 谨慎选择:只保留"非他不可"的强信号,避免"他说的""综艺"等宽泛词误触
_ZX_TRIGGERS: list[str] = [
    "张雪峰",
    "雪峰",
    "演说家",
    "直播里讲",
    "主播说",
    "讲座说过",
    "他者视角",
    "盲点",
]


def split_group(content: str, group_id: str) -> list[Chunk]:
    """按 ## 标题切分知识组文件为 chunks。"""
    chunks: list[Chunk] = []
    current_text = ""
    current_title = ""
    start_line = 1

    for i, line in enumerate(content.split("\n"), start=1):
        if line.startswith("## "):
            if current_text.strip():
                chunks.append(
                    Chunk(
                        text=current_text.strip(),
                        group_id=group_id,
                        start_line=start_line,
                        section_title=current_title,
                    )
                )
            current_title = line[3:].strip()
            current_text = line + "\n"
            start_line = i
        else:
            current_text += line + "\n"

    if current_text.strip():
        chunks.append(
            Chunk(
                text=current_text.strip(),
                group_id=group_id,
                start_line=start_line,
                section_title=current_title,
            )
        )

    return chunks


def load_all_groups(groups_dir: str) -> dict[str, list[Chunk]]:
    """加载所有知识组文件，切分为 chunks。"""
    all_groups: dict[str, list[Chunk]] = {}
    if not os.path.isdir(groups_dir):
        return all_groups
    for filename in sorted(os.listdir(groups_dir)):
        if not filename.endswith(".md"):
            continue
        group_id = filename.removesuffix(".md")
        filepath = os.path.join(groups_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        all_groups[group_id] = split_group(content, group_id)
    return all_groups


def keyword_match_score(user_msg: str, triggers: list[str]) -> float:
    """计算用户消息与触发词列表的匹配分数（0.0 ~ 1.0）。"""
    if not triggers:
        return 0.0
    hits = sum(1 for t in triggers if t.lower() in user_msg.lower())
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


class EmbeddingProvider:
    """Embedding API 的抽象接口。"""

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        raise NotImplementedError


class OpenAIEmbedding(EmbeddingProvider):
    """通过 OpenAI 兼容 API 计算 embedding。"""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        all_embeddings: list[np.ndarray] = []
        # Batch size 32: SiliconFlow (and most OpenAI-compatible APIs) cap
        # the input array length at 32 per request.
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            all_embeddings.extend(np.array(item.embedding, dtype=np.float32) for item in resp.data)
        return all_embeddings


class OllamaEmbedding(EmbeddingProvider):
    """通过 Ollama 本地 API 计算 embedding。"""

    def __init__(self, model: str = "bge-m3", base_url: str = "http://localhost:11434"):
        import urllib.request as _req

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._req = _req

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        results: list[np.ndarray] = []
        batch_size = 200
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = json.dumps({"model": self._model, "input": batch}).encode()
            req = self._req.Request(
                f"{self._base_url}/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with self._req.urlopen(req) as resp:
                data = json.loads(resp.read())
            for emb in data["embeddings"]:
                results.append(np.array(emb, dtype=np.float32))
        return results


class KeywordOnlyEmbedding(EmbeddingProvider):
    """纯关键词模式（降级用）— 返回全零向量。"""

    def __init__(self, dim: int = 1536):
        self._dim = dim

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        return [np.zeros(self._dim, dtype=np.float32) for _ in range(len(texts))]


def create_embedding_provider(provider: str = "openai", model: str | None = None, **kwargs: Any) -> EmbeddingProvider:
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
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
    elif provider == "siliconflow":
        return OpenAIEmbedding(
            model=model or "BAAI/bge-large-zh-v1.5",
            api_key=kwargs.get("api_key") or os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv(
                "GAOBAO__EMBEDDING__BASE_URL", os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            ),
        )
    elif provider == "ollama":
        return OllamaEmbedding(
            model=model or "bge-m3",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    else:
        return KeywordOnlyEmbedding()


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
        from config.loader import load_tuning

        _tuning = load_tuning().get("rag", {})
        self._vector_weight = float(_tuning.get("vector_weight", vector_weight))
        self._keyword_weight = float(_tuning.get("keyword_weight", keyword_weight))
        self._group_threshold = group_threshold
        self._max_groups = max_groups
        self._max_quotes = max_quotes
        self._embedder = embedding_provider or KeywordOnlyEmbedding()
        self._groups = load_all_groups(groups_dir)
        self._quotes = self._load_quotes(quotes_path)
        self._init_embeddings()

    def _load_quotes(self, quotes_path: str) -> list[QuoteEntry]:
        quotes: list[QuoteEntry] = []
        # 主语录库（按专业索引）
        index_path = os.path.join(quotes_path, "_by_major.json")
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as f:
                raw_index: dict = json.load(f)
            for major_key, quote_list in raw_index.items():
                for q in quote_list:
                    quotes.append(
                        QuoteEntry(
                            id=q.get("id", ""),
                            text=q["text"],
                            major=major_key,
                            tags=q.get("tags", []),
                            category=q.get("category", ""),
                            sentiment=q.get("sentiment", ""),
                        )
                    )
        # 张雪峰原版金句（带出处/年份）—独立加载,不依赖主索引
        zx_path = os.path.join(quotes_path, "zhangxuefeng_originals.json")
        if os.path.exists(zx_path):
            with open(zx_path, encoding="utf-8") as f:
                zx_raw: list[dict] = json.load(f)
            for q in zx_raw:
                quotes.append(
                    QuoteEntry(
                        id=q["id"],
                        text=q["text"],
                        major=q.get("major", "zhangxuefeng"),
                        tags=q.get("tags", []),
                        category=q.get("category", ""),
                        sentiment=q.get("sentiment", ""),
                        source=q.get("source", ""),
                        year=q.get("year", 0),
                    )
                )
        return quotes

    def _init_embeddings(self) -> None:
        all_texts: list[str] = []
        all_refs: list[tuple[str, int]] = []
        for group_id, chunks in self._groups.items():
            for i, chunk in enumerate(chunks):
                all_texts.append(chunk.text)
                all_refs.append((group_id, i))
        quote_texts: list[str] = [q.text for q in self._quotes]
        combined_texts = all_texts + quote_texts
        if combined_texts:
            # Truncate each text to ~500 chars to stay under the
            # per-text token limit (bge-large-zh-v1.5 via SiliconFlow: ~512 tokens,
            # but some 500-char Chinese strings still exceed it).
            truncated = [t[:500] for t in combined_texts]
            try:
                embeddings = self._embedder.embed(truncated)
            except Exception as e:
                logger.warning(
                    "Embedding init failed (%s: %s) — falling back to keyword search only",
                    type(e).__name__,
                    e,
                )
                embeddings = [None] * len(combined_texts)
            for idx, (group_id, chunk_idx) in enumerate(all_refs):
                if embeddings[idx] is not None:
                    self._groups[group_id][chunk_idx].embedding = embeddings[idx]
            for i, q in enumerate(self._quotes):
                emb_idx = len(all_texts) + i
                if embeddings[emb_idx] is not None:
                    q.embedding = embeddings[emb_idx]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        if a is None or b is None:
            return 0.0
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _embed_query(self, text: str) -> np.ndarray | None:
        try:
            # Truncate to ~500 chars to stay under embedding token limits
            results = self._embedder.embed([text[:500]])
            return results[0] if results else None
        except Exception as e:
            logger.debug("Query embedding failed: %s", e)
            return None

    def _score_groups(self, user_msg: str, query_emb: np.ndarray | None) -> list[tuple[str, float]]:
        scores: list[tuple[str, float]] = []
        for group_id, chunks in self._groups.items():
            vec_score = 0.0
            if query_emb is not None:
                for chunk in chunks:
                    if chunk.embedding is not None:
                        sim = self._cosine_similarity(query_emb, chunk.embedding)
                        vec_score = max(vec_score, sim)
            triggers = GROUP_TRIGGERS.get(group_id, [])
            kw_score = keyword_match_score(user_msg, triggers)
            hybrid = self._vector_weight * vec_score + self._keyword_weight * kw_score
            scores.append((group_id, hybrid))
        scores.sort(key=lambda x: -x[1])
        return scores

    def _select_top_groups(self, scores: list[tuple[str, float]]) -> list[str]:
        selected = [g for g, s in scores if s > self._group_threshold][: self._max_groups]
        if not selected:
            selected = [g for g, _ in scores[: self._max_groups]]
        return selected

    def _select_top_chunks(self, group_ids: list[str], query_emb: np.ndarray | None) -> list[Chunk]:
        candidates: list[tuple[Chunk, float]] = []
        for group_id in group_ids:
            for chunk in self._groups.get(group_id, []):
                score = 0.0
                if query_emb is not None and chunk.embedding is not None:
                    score = self._cosine_similarity(query_emb, chunk.embedding)
                candidates.append((chunk, score))
        candidates.sort(key=lambda x: -x[1])
        return [c for c, _ in candidates]

    def _select_top_quotes(self, user_msg: str, query_emb: np.ndarray | None) -> list[QuoteEntry]:
        scored: list[tuple[int, float]] = []
        zx_triggered = any(t.lower() in user_msg.lower() for t in _ZX_TRIGGERS)
        for i, q in enumerate(self._quotes):
            vec_score = 0.0
            if query_emb is not None and q.embedding is not None:
                vec_score = self._cosine_similarity(query_emb, q.embedding)
            kw_bonus = 0.3 if keyword_exact_match(user_msg, q.major) else 0.0
            # 张雪峰触发词加权,略高于 kw_bonus=0.3
            # 当用户明确问张雪峰时,ZX 金句优先于同关键词其他金句
            zx_bonus = 0.4 if zx_triggered and q.id.startswith("zx_") else 0.0
            final = vec_score + kw_bonus + zx_bonus
            scored.append((i, final))
        scored.sort(key=lambda x: -x[1])
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
        query_emb = self._embed_query(user_msg)
        group_scores = self._score_groups(user_msg, query_emb)
        selected_groups = self._select_top_groups(group_scores)
        selected_chunks = self._select_top_chunks(selected_groups, query_emb)
        selected_quotes = self._select_top_quotes(user_msg, query_emb)
        result = RetrievalResult(
            groups=selected_groups,
            group_chunks=selected_chunks,
            quotes=selected_quotes,
        )
        logger.info(
            "RAG retrieval: query=%s, groups=%d, chunks=%d, quotes=%d",
            user_msg[:50],
            len(result.groups),
            len(result.group_chunks),
            len(result.quotes),
        )
        return result
