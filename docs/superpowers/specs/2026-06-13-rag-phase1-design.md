# Phase 1: 知识检索架构升级设计文档

> **日期**: 2026-06-13
> **状态**: 待审阅
> **版本**: v1.0
> **项目**: gaobao-advisor (雪峰 Agent)

## 1. 背景与目标

### 1.1 当前问题

gaobao-advisor 的知识注入系统存在三个核心问题：

1. **Token 浪费严重**：knowledge_base.md（866 行，~23.6K tokens）每次 LLM 调用都全量注入，占固定成本的 50%+。一次典型查询的总上下文 47-68K tokens 中，system_prompt + knowledge_base 合计 45.4K tokens（83-97%），无论用户问什么都全量给。

2. **检索质量低下**：knowledge_loader.py 仅覆盖 4 个知识文件（53 个关键词精确匹配），quotes 匹配依赖 433 个 key 的子串匹配。典型查询中 70% 无法获得有效检索支持。

3. **同义词盲区**：无同义词/意图理解能力。"码农" ≠ "计算机"，"进体制" ≠ "考公"，"大模型冲击就业" ≠ "AI"。

### 1.2 Phase 1 目标

将知识注入从"全量注入"升级为"按需检索"，具体指标：

| 指标 | 当前值 | 目标值 |
|------|-------|-------|
| 每次调用 token 消耗 | 47-68K | 27-34K（节省 ~40%） |
| 检索覆盖率（7 个测试查询） | 2/7 | 6/7 |
| 知识文件覆盖 | 4 个 | 6 个知识组 + 675 条语录 |
| 同义词处理 | 0 | 通过 embedding 自然支持 |
| 回滚能力 | 无 | 环境变量一键切换 |

### 1.3 非目标

- 不改动 system_prompt.md（行为指令必须全量保留）
- 不改动 SQLite 结构化数据查询（已是最优方案）
- 不引入完整 RAG pipeline（向量数据库、chunk 索引服务等）
- 不改动对话历史压缩逻辑

## 2. 架构设计

### 2.1 整体架构

```
当前架构（全量注入）：
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│ 用户输入  │────▶│ agent.py     │────▶│ LLM API     │
└──────────┘     │ system_msg = │     └─────────────┘
                 │ prompt(21.8K)│
                 │ + KB(23.6K)  │  ← 固定 45.4K tokens
                 │ + 动态注入    │
                 └──────────────┘

Phase 1 架构（按需检索）：
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│ 用户输入  │────▶│ agent.py     │────▶│ LLM API     │
└──────────┘     │ system_msg = │     └─────────────┘
                 │ prompt(21.8K)│  ← 保持不变
                 │ + 检索结果    │  ← 动态 5-12K tokens
                 │ + 动态注入    │
                 └──────┬───────┘
                        │
              ┌─────────▼─────────┐
              │ kb_retriever.py   │
              │ (新增模块)         │
              ├───────────────────┤
              │ 1. query_embedder │ ← 用户查询 → embedding
              │ 2. vector_index   │ ← 知识组 + 语录索引
              │ 3. keyword_matcher│ ← 同义词扩展 + 关键词
              │ 4. hybrid_fusion  │ ← 关键词分数 + 向量分数融合
              └───────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │ knowledge/groups/          │ ← 6 个知识组文件
          │ knowledge/quotes/embeddings│ ← 675 条语录预计算向量
          └───────────────────────────┘
```

### 2.2 数据流

```
用户消息 + slots
    │
    ▼
kb_retriever.search(user_msg, slots)
    │
    ├──→ Step 1: Embedding
    │    user_msg → embedding API → 1536-dim vector
    │
    ├──→ Step 2: Knowledge Group Retrieval
    │    cosine_sim(query_emb, group_chunks)
    │    + keyword_match(query, group_triggers)
    │    → hybrid_score = 0.6×vector + 0.4×keyword
    │    → top-2 groups (score > 0.3)
    │
    ├──→ Step 3: Quote Retrieval
    │    cosine_sim(query_emb, quote_embs)
    │    + keyword精确匹配的候选提升
    │    → top-3 quotes (diversity filtered)
    │
    └──→ Output: groups_content + quotes
              │
              ▼
    system_msg = prompt + retrieved_content + dynamic_injections
              │
              ▼
         LLM API call
```

## 3. 知识组拆分方案

将 knowledge_base.md 的 16 个模块合并为 6 个知识组：

```
knowledge/groups/
├── G1_core_method.md       # 核心方法论 (~180 行)
│   ├── 一、核心咨询哲学 (灵魂拷问法, 家庭矩阵)
│   ├── 二、志愿填报方法论 (冲稳保规则, 位次法)
│   └── 七、咨询表达风格 (语言风格要素)
│
├── G2_major_school.md      # 专业与学校 (~260 行, 最大组)
│   ├── 三、专业选择知识库 (12 大学科, 同名专业差异)
│   ├── 四、学校选择方法论 (排名体系, 层次评估)
│   ├── 十、推荐/不推荐专业
│   └── 十一、行业名校分类 (院校联盟)
│
├── G3_career_future.md     # 就业与前景 (~200 行)
│   ├── 六、考研方法论
│   ├── 十三、稳定就业路径详解 (考公/教师/医生/国企)
│   └── 十六、2025-2026 最新趋势 (AI 冲击, 政策变化)
│
├── G4_life_planning.md     # 规划与选择 (~100 行)
│   ├── 五、城市选择逻辑 (城市-产业匹配)
│   ├── 十四、专科志愿策略
│   └── 十五、高中阶段规划
│
├── G5_data_format.md       # 数据与格式 (~80 行)
│   ├── 八、数据可信度分级 (T1-T4)
│   └── 九、Output 格式 (推荐模板)
│
└── G6_quick_ref.md         # 速查 (~70 行)
    └── 十二、速查 (选科/职业路径/分数线速查表)
```

### 3.1 分组逻辑

| 知识组 | 覆盖话题 | 预估行数 | 检索频率 |
|--------|---------|---------|---------|
| G1_core_method | 咨询方法、填报规则、表达风格 | ~180 | 高（每次咨询） |
| G2_major_school | 专业选择、学校评估、学科排名 | ~260 | 高（核心话题） |
| G3_career_future | 就业路径、考研、AI 冲击、政策趋势 | ~200 | 高（高频话题） |
| G4_life_planning | 城市选择、专科策略、高中规划 | ~100 | 中 |
| G5_data_format | 数据分级、输出模板 | ~80 | 低 |
| G6_quick_ref | 速查表 | ~70 | 低 |

### 3.2 每组的触发词设计

每个知识组配置 8-15 个触发关键词，用于混合检索中的关键词匹配部分：

```python
GROUP_TRIGGERS = {
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
```

## 4. 轻量向量引擎

### 4.1 模块设计

新增文件 `kb_retriever.py`（~250 行），职责：

1. **初始化时**加载并索引知识组和语录
2. **查询时**执行混合检索（向量 + 关键词）
3. **容错**：embedding 失败时降级为关键词匹配

### 4.2 Embedding 模型选择

| 候选模型 | 中文效果 | 维度 | 本地/云端 | 费用 |
|---------|---------|------|----------|------|
| text-embedding-3-small（推荐） | 好 | 1536 | 云端 | ~$0.0001/次 |
| BGE-M3 (via Ollama) | 最好 | 1024 | 本地 | 免费（需 2GB 模型） |
| all-MiniLM-L6-v2 | 一般 | 384 | 本地 | 免费（需 80MB） |

默认使用 text-embedding-3-small，通过 Ollama 支持本地模式。

**⚠️ 注意**：gaobao-advisor 的 LLM 和 embedding 使用独立的 API key。当前支持的 LLM 提供商（DeepSeek/Qwen/GLM）中，Qwen (DashScope) 同时提供 text-embedding 兼容接口。具体配置：

```bash
# 方案 1: OpenAI embedding（需要 OPENAI_API_KEY）
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-xxx

# 方案 2: Qwen DashScope embedding（使用现有 DASHSCOPE_API_KEY）
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v3

# 方案 3: Ollama 本地（无需 API key）
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
```

### 4.3 向量索引

```
内存数据结构：
├── group_chunks: List[Chunk]       # ~200 个知识 chunks
│   ├── chunk.text: str             # chunk 文本内容
│   ├── chunk.group_id: str         # 所属知识组 ID
│   ├── chunk.embedding: np.array   # 1536-dim vector
│   └── chunk.start_line: int       # 原始行号（可追溯）
│
├── quote_chunks: List[Chunk]       # 675 条语录
│   ├── chunk.text: str             # 语录文本
│   ├── chunk.major: str            # 所属专业
│   ├── chunk.tags: List[str]       # 标签
│   └── chunk.embedding: np.array   # 1536-dim vector
│
└── keyword_index: Dict[str, Set]   # 关键词倒排索引
    ├── group_triggers → group_id
    └── quote_keys → quote_id
```

内存占用：~5-8 MB（875 向量 × 1536 维 × 4 字节 ≈ 5.4MB + 元数据）

### 4.4 检索算法

```python
def search(user_msg: str, slots: dict) -> RetrievalResult:
    """混合检索：向量 + 关键词"""

    # Step 1: 查询 embedding
    query_emb = embed(user_msg)  # 1536-dim

    # Step 2: 知识组检索
    group_scores = {}
    for group_id, chunks in group_chunks.items():
        # 向量分数：取该组所有 chunks 的最高 cosine similarity
        vec_score = max(cosine_sim(query_emb, c.embedding) for c in chunks)

        # 关键词分数：触发词命中率
        kw_score = keyword_match(user_msg, GROUP_TRIGGERS[group_id])

        # 混合分数
        group_scores[group_id] = 0.6 * vec_score + 0.4 * kw_score

    # 选择 top-2 知识组（score > 0.3）
    selected = sorted(group_scores.items(), key=lambda x: -x[1])[:2]
    selected_groups = [g for g, s in selected if s > 0.3]

    # Fallback: 如果没有超过阈值的，选 top-2
    if not selected_groups:
        selected_groups = [g for g, _ in sorted(
            group_scores.items(), key=lambda x: -x[1]
        )[:2]]

    # Step 3: 语录检索
    quote_scores = [
        (i, cosine_sim(query_emb, q.embedding))
        for i, q in enumerate(quote_chunks)
    ]
    # 关键词精确匹配的候选加分
    for i, q in enumerate(quote_chunks):
        if keyword_exact_match(user_msg, q.major):
            quote_scores[i] = (i, quote_scores[i][1] + 0.3)

    # Top-3，确保多样性（不同 tag）
    top_quotes = select_diverse(quote_scores, n=3, diversity_key="tags")

    return RetrievalResult(
        groups=selected_groups,
        quotes=top_quotes,
    )
```

### 4.5 Chunk 切分策略

知识组文件按 `##` 标题切分为 chunks。每个 chunk 是一个语义完整的段落，通常 50-200 行：

```python
@dataclass
class Chunk:
    text: str           # chunk 文本内容
    group_id: str       # 所属知识组 ID (e.g. "G2_major_school")
    embedding: np.ndarray  # 1536-dim vector (预计算后填充)
    start_line: int     # 在原始 .md 文件中的起始行号
    section_title: str  # ## 标题文本

def split_group(content: str, group_id: str) -> List[Chunk]:
    """按 ## 标题切分知识组"""
    chunks = []
    current_section = ""
    current_title = ""
    start_line = 1

    for i, line in enumerate(content.split("\n"), start=1):
        if line.startswith("## "):
            if current_section.strip():
                chunks.append(Chunk(
                    text=current_section.strip(),
                    group_id=group_id,
                    embedding=None,  # 预计算阶段填充
                    start_line=start_line,
                    section_title=current_title,
                ))
            current_title = line[3:].strip()  # 去掉 "## " 前缀
            current_section = line + "\n"
            start_line = i
        else:
            current_section += line + "\n"

    # 最后一个 section
    if current_section.strip():
        chunks.append(Chunk(
            text=current_section.strip(),
            group_id=group_id,
            embedding=None,
            start_line=start_line,
            section_title=current_title,
        ))

    return chunks
```

## 5. 语录匹配改造

### 5.1 当前问题

- 433 个 key 子串匹配，短 key 假阳性（"选择"、"努力"等泛化词）
- 具体概念漏匹配（"码农"无对应 key）
- 675 条语录的 tags 字段完全未被利用

### 5.2 改造方案：关键词 + 向量混合

```
用户消息
    │
    ├──→ 关键词精确匹配
    │    保留原有 key 匹配（高置信度）
    │    新增：短 key (<2字) 需上下文验证
    │    新增：同义词扩展匹配
    │    命中 → score +1.0
    │
    ├──→ 向量语义匹配
    │    cosine_sim(query_emb, 675_quote_embs)
    │    → top-5 candidates
    │    score = cosine similarity
    │
    └──→ 融合排序
         final_score = max(keyword_score, vector_score)
         → top-3 quotes
         → 多样性过滤：确保 top-3 不来自同一 tag/major
```

### 5.3 语录 Embedding 预计算

```python
# scripts/precompute_quote_embeddings.py
# - 读取 knowledge/quotes/_by_major.json
# - 对每条语录计算 embedding
# - 存储到 knowledge/quotes/embeddings.npy (675×1536)
# - 元数据存到 knowledge/quotes/quote_meta.json
```

文件清单：
- `knowledge/quotes/embeddings.npy` (~4MB)
- `knowledge/quotes/quote_meta.json` (~200KB)

## 6. 双轨集成

### 6.1 环境变量

```bash
# .env 新增
ENABLE_RAG_KB=false          # 新系统开关（默认关闭）
EMBEDDING_PROVIDER=openai    # embedding 来源：openai / dashscope / ollama
EMBEDDING_MODEL=text-embedding-3-small  # embedding 模型
EMBEDDING_FALLBACK=keyword   # embedding 失败时降级策略
EMBEDDING_CACHE_SIZE=100     # 查询 embedding 缓存大小（LRU）
```

**注意**：`_last_user_msg` 字段需要在 `chat()` 方法的用户消息处理入口处设置（约在 slot 提取之前），供 `_build_system_message()` 调用检索时使用。

### 6.2 agent.py 改造

```python
# __init__() 新增 ~5 行
if self.enable_rag_kb:
    from kb_retriever import KbRetriever
    self.kb_retriever = KbRetriever(
        groups_dir="knowledge/groups",
        quotes_path="knowledge/quotes",
        embedding_provider=config["embedding_provider"],
        embedding_model=config["embedding_model"],
    )

# _build_system_message() 修改 ~10 行
if self.enable_rag_kb and hasattr(self, 'kb_retriever'):
    result = self.kb_retriever.search(
        self._last_user_msg, self.slots
    )
    kb_content = self._format_retrieved(result)
else:
    kb_content = self.knowledge_base  # 旧路径完全保留

# _inject_quotes() 修改 ~30 行
if self.enable_rag_kb and hasattr(self, 'kb_retriever'):
    quotes = self.kb_retriever.search_quotes(user_msg)
else:
    quotes = self._legacy_quote_match(user_msg)  # 旧路径
```

### 6.3 容错机制

| 故障场景 | 处理策略 | 用户影响 |
|---------|---------|---------|
| Embedding API 调用失败 | 降级为纯关键词匹配 | 知识检索退化，对话继续 |
| 所有检索 score < threshold | fallback 到 G1 + G2 | 注入基础方法论+专业知识 |
| 启动时预计算失败 | 自动 ENABLE_RAG_KB=false | 回退到旧系统 |
| 语录 embedding 加载失败 | 降级为旧的 key 匹配 | 语录匹配退化 |
| Embedding API 限流 | 本地缓存最近 100 次查询 | 延迟增加 |

## 7. 文件变更清单

### 7.1 新增文件

| 文件 | 行数（预估） | 职责 |
|------|------------|------|
| `kb_retriever.py` | ~250 | 向量索引 + 混合检索 + 知识组管理 |
| `scripts/precompute_quote_embeddings.py` | ~80 | 语录 embedding 预计算 |
| `scripts/precompute_group_embeddings.py` | ~60 | 知识组 embedding 预计算 |
| `knowledge/groups/G1_core_method.md` | ~180 | 核心方法论知识组 |
| `knowledge/groups/G2_major_school.md` | ~260 | 专业与学校知识组 |
| `knowledge/groups/G3_career_future.md` | ~200 | 就业与前景知识组 |
| `knowledge/groups/G4_life_planning.md` | ~100 | 规划与选择知识组 |
| `knowledge/groups/G5_data_format.md` | ~80 | 数据与格式知识组 |
| `knowledge/groups/G6_quick_ref.md` | ~70 | 速查知识组 |
| `knowledge/quotes/embeddings.npy` | ~4MB | 语录 embedding 向量 |
| `knowledge/quotes/quote_meta.json` | ~200KB | 语录元数据 |

### 7.2 修改文件

| 文件 | 改动范围 | 改动说明 |
|------|---------|---------|
| `agent.py` | `__init__()` | +5 行：初始化 kb_retriever |
| `agent.py` | `_build_system_message()` | +10 行：if/else 分支 |
| `agent.py` | `_inject_quotes()` | ~30 行：改为调用混合匹配 |
| `quality/knowledge_loader.py` | 整体重写 | ~120 行：接入 kb_retriever，替代旧的关键词匹配逻辑 |
| `.env.example` | +5 行 | 新增配置项 |

### 7.3 不改动的文件

| 文件 | 原因 |
|------|------|
| `system_prompt.md` | 行为指令必须全量保留 |
| `knowledge_base.md` | 保留作为 fallback（兼容模式） |
| `gaokao_data.py` | 结构化查询已是最优方案 |
| `app.py` / `admin.py` | 前端不涉及知识检索 |
| `db/` | 数据库层不变 |

### 7.4 扩展知识文件的处理

当前 `knowledge/` 目录下的 4 个扩展知识文件（`00_ai_era_correction.md`、`06_university_life_planning.md`、`07_new_gaokao_subject_selection.md`、`08_vocational_strategy.md`）的处理策略：

- **不改动这些文件本身**，它们仍然是独立的 markdown 文件
- 在 `kb_retriever.py` 初始化时，将这些扩展文件的内容**合并到对应的知识组 chunks 中**（通过内容匹配自动关联）：
  - `00_ai_era_correction.md` → 并入 `G3_career_future` 的 chunks
  - `06_university_life_planning.md` → 并入 `G4_life_planning` 的 chunks
  - `07_new_gaokao_subject_selection.md` → 并入 `G1_core_method` 的 chunks
  - `08_vocational_strategy.md` → 并入 `G4_life_planning` 的 chunks
- 这样 `quality/knowledge_loader.py` 可以完全重写为调用 `kb_retriever`，不再需要独立的关键词触发逻辑

## 8. 验证计划

### 8.1 单元测试

- `test_kb_retriever.py`：向量检索准确性、关键词匹配、混合融合、容错降级
- `test_quote_matcher.py`：语录混合匹配、多样性过滤
- `test_knowledge_loader.py`：新旧系统切换

### 8.2 集成测试

7 个测试查询验证（对应当前失败案例）：

| # | 查询 | 期望检索结果 |
|---|------|------------|
| 1 | "学码农以后还能找到工作吗" | G2 + G3，语录命中计算机相关 |
| 2 | "进体制内稳不稳" | G3（稳定就业路径），语录命中体制/考公 |
| 3 | "女生学什么专业比较好" | G2（专业选择），语录命中性别相关 |
| 4 | "农村的，分数不高" | G1 + G2，基础方法论 + 专业推荐 |
| 5 | "临床医学出来好找工吗" | G2 + G3，专业数据 + 就业路径 |
| 6 | "对比武汉大学和华科" | G2（学校选择），语录命中学校相关 |
| 7 | "转专业难不难" | G1 + G2，方法论 + 专业选择 |

### 8.3 Token 消耗对比

测量 7 个测试查询在新旧系统下的 token 消耗差异。

### 8.4 回归测试

- 确保 `ENABLE_RAG_KB=false` 时系统行为完全不变
- 确保 Docker 部署正常
- 确保 Streamlit / API / CLI 三种入口均正常

## 9. 实施顺序

```
Phase 1a: 知识组拆分（无代码改动，纯文件操作）
  → 拆分 knowledge_base.md 为 6 个知识组文件
  → 验证：人工检查内容完整性

Phase 1b: 向量引擎核心（kb_retriever.py）
  → 实现 embedding、索引、检索、混合融合
  → 验证：单元测试

Phase 1c: 预计算脚本
  → 语录 + 知识组 embedding 预计算
  → 验证：生成 embeddings.npy 和 quote_meta.json

Phase 1d: agent.py 集成
  → 新增 if/else 分支 + 容错逻辑
  → 验证：7 个测试查询 + token 对比

Phase 1e: knowledge_loader.py 重写
  → 接入 kb_retriever
  → 验证：新旧系统切换测试

Phase 1f: 端到端验证
  → Docker 部署测试
  → 三种入口测试（CLI/Web/API）
  → 回归测试
```

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Embedding API 不稳定 | 中 | 知识检索退化 | 降级为关键词 + 本地缓存 |
| 知识组切分遗漏内容 | 低 | 部分知识丢失 | 拆分后逐行对比原文件 |
| 混合检索阈值需调优 | 高 | 检索质量不达预期 | 提供 threshold 配置项，可热调整 |
| 新旧系统行为差异 | 中 | 回归 bug | 双轨运行 + 对比测试 |
| 内存占用增加 | 低 | 部署环境受限 | ~8MB 可忽略 |
