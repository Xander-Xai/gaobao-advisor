# RAG 演示与健康检查（SYNTHETIC_DEMO）

本文档描述默认演示环境中的知识检索（RAG）能力：语料、启用规则、检索实现、
引用格式、健康检查、fail-closed 行为、可复现演示命令，以及**实测结果与剩余限制**。
所有数字均来自本仓库实际运行输出，未做推算或美化。

## 1. 语料

* 位置：`knowledge/synthetic_demo/`
* 性质：**原创、机器编写、合成**（虚构院校规则、录取政策示例、志愿填报 FAQ、
  说明性文档）；院校名带「（合成）」，与 `scripts/seed_demo_data.py` 一致。
* 许可：CC0-1.0（见 [`DATA_LICENSE.md`](../DATA_LICENSE.md)）。
* 标记：每个 `groups/*.md` 带 `SYNTHETIC_DEMO` 提示；`manifest.json` 记录
  marker / 版本 / 许可 / 逐文件 sha256。
* 规模（实测）：**documents=8，chunks=31**。
* 不含：上游人物化方法论语料、任何语录合集、任何真实招生政策或数据。

未经授权的第三方语料不得随仓库分发或用于演示；真实数据需走单独授权导入链路。

## 2. 启用规则

| 场景 | 行为 |
|---|---|
| 默认 SYNTHETIC_DEMO | `ENABLE_RAG_KB` 默认 `true`；启动时自动校验并初始化随仓语料 |
| 显式关闭 | `ENABLE_RAG_KB=false` → `RAG_DISABLED` |
| 语料缺失 | `RAG_ERROR`，检索请求抛 `RagCorpusError`，`/api/v1/knowledge/search` 返回 `503` |
| 语料损坏 / 未带 marker | 同上（fail-closed，绝不假装命中） |
| 真实数据环境 | 必须配置**已授权语料**并通过完整性检查后才启用 |

## 3. 检索实现

复用现有 `server/services/kb_retriever.py::KbRetriever`（未新建平行 RAG 框架）：

* **BM25 关键词检索**：中文按相邻双字组（bigram）+ ASCII 词元建索引，始终可用、
  离线、无 Key。函数词双字组（如「的关」「与暗」）被过滤以降噪。
* **Dense Retrieval（可选）**：配置 `RAG_EMBEDDING_PROVIDER`
  （siliconflow / openai / dashscope / ollama）时叠加；无 Key 时自动使用
  `keyword`，不发任何付费请求。
* **证据判定**：片段需通过 BM25 阈值 + 命中词数 + 查询 idf 覆盖度，
  或通过 dense 余弦阈值，才算证据；否则返回空证据（`has_evidence=false`）。
* **排序**：组得分 = 向量分 + 触发词分 + 归一化 BM25；片段按组合分排序取 top-k。
* **职责分离**：知识问题路由到检索链路；含画像的混合问题同时执行
  `data_query`（结构化 SQL）与 `rag_retrieve`。

## 4. 引用格式

每个命中片段带稳定标识：

```json
{
  "chunk_id": "G1_core_method#L20",
  "group_id": "G1_core_method",
  "section_title": "平行志愿规则（合成示例）",
  "source": "G1_core_method § 平行志愿规则（合成示例）",
  "start_line": 20
}
```

`knowledge_context` 中以 `[来源: <source>]` 标注证据；SSE 聊天在证据存在时发送
`{"type":"sources","data":[...],"has_evidence":true}` 事件。无证据时
`build_llm_context` 注入「严禁编造、明确说明当前知识库无法验证」的指令。

## 5. 健康检查

`GET /api/v1/health` 如实返回（Docker 无 Key 默认启动实测）：

```json
{
  "status": "ok",
  "version": "3.0.0",
  "database": "connected",
  "data_profile": "SYNTHETIC_DEMO",
  "optional_services": {
    "rag": {
      "state": "RAG_ENABLED",
      "reason": "",
      "corpus_configured": true,
      "documents": 8,
      "chunks": 31,
      "integrity_ok": true
    }
  },
  "degraded_services": []
}
```

`state` 取值：`RAG_ENABLED` / `RAG_DISABLED` / `RAG_ERROR`。非 `RAG_ENABLED` 时
会出现在 `degraded_services`。

## 6. 复现命令与样例

```bash
docker build -t gb-advisor .
docker run --rm -p 8000:8000 gb-advisor

# 健康检查
curl http://localhost:8000/api/v1/health

# 已知合成问题 → 非空证据 + 引用
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"平行志愿的投档规则是什么"}'
# → has_evidence=true, count=4, citations[0].source="G1_core_method § 平行志愿规则（合成示例）"

# 无对应证据 → 不编造
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"量子缠结与超导磁悬浮技术前沿"}'
# → has_evidence=false, count=0
```

### 样例 Query → 证据（实测）

| Query | 命中组 | 首条来源 |
|---|---|---|
| 平行志愿的投档规则是什么 | G1_core_method | G1_core_method § 平行志愿规则（合成示例） |
| 冲稳保怎么分配 | G1_core_method | G1_core_method § 冲稳保策略 |
| 临床医学要读几年 | G7_employment_paths | G7_employment_paths § 医生路径 |
| 专科可以专升本吗 | G8_graduate_and_vocational | G8_graduate_and_vocational § 专升本说明 |
| 考公务员哪些专业合适 | G7_employment_paths | G7_employment_paths § 公务员与国企路径 |
| 量子缠结与超导磁悬浮技术前沿 | — | 无证据（`has_evidence=false`）|

## 7. 最小 RAG 质量评测（实测）

标注集：`knowledge/synthetic_demo/eval_queries.json`（12 条查询 → 预期知识组，
均为虚构示例）。

* 指标：组级命中率（预期组是否进入 top-k 组）。
* 实测：**12/12 = 1.000**。

**重要说明：** 这是小规模合成标注集的**链路可用性**检查，用于验证检索能命中
正确知识组，**不代表**真实数据上的 RAG 质量、召回率或准确率。项目仍**未做**
生产级 RAG 质量评测（无真实标注语料、无跨领域评测集）。

## 8. 剩余限制与后续工作

* 检索为无监督的词法（BM25）+ 可选向量混合，中文分词使用 bigram 近似，
  存在词法假阳性/假阴性的可能（例如「关系」这类通用词可能误命中）。
* 合成语料刻意很小（8 文档 / 31 片段），只覆盖演示问题，不覆盖真实政策全貌。
* 无真实、规模化、人工标注的检索评测集；若后续具备授权评测数据，再运行
  召回率/准确率评测并如实记录（当前**不编造任何百分比**）。
* Dense 路径依赖外部 embedding API（有 Key 时）；未验证各 provider 的中文效果差异。
* 引用为「片段来源」级，不提供句子级或页码级定位。
