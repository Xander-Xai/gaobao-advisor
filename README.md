# gaobao — AI 高考志愿顾问

> 一个基于 **LangGraph + Hybrid RAG + 结构化高考数据** 构建的 AI 志愿填报顾问。
>
> 它不是“把用户问题直接丢给大模型”的 ChatBot，而是把真实志愿咨询拆成 **画像采集 → 数据查询 → 知识检索 → 决策推理 → 来源标注 → 质量检查 → 多轮记忆** 的完整工作流。

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Workflow-orange.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 项目定位

高考志愿填报不是一个单轮问答问题。

真正的咨询过程通常需要同时处理：

- 省份、分数、位次、选科等硬约束；
- 院校和专业的历史录取数据；
- 地域、家庭条件、职业目标等个体偏好；
- “冲 / 稳 / 保”风险控制；
- 专业就业、考研、考公、行业趋势等非结构化知识；
- 用户信息不完整时的多轮追问；
- 数据来源、回答可信度和风险提示。

`gaobao-advisor` 的目标是把这些步骤显式工程化，让大模型负责它擅长的理解、归纳和表达，而不是让它凭记忆“猜学校”。

---

## v3.0 架构

当前版本已经从早期单体原型迁移为完整 Web 应用：

```text
Browser / Mobile
       │
       ▼
     Nginx
       │
       ├── /            → Vue 3 SPA
       ├── /api/*       → FastAPI
       └── /ws/*        → WebSocket Voice
                            │
                            ▼
                       LangGraph
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
     SQLite Data       Hybrid RAG        LLM Provider
     Schools           Knowledge         DeepSeek/Qwen/
     Scores            Expert Quotes     GLM/GPT/Ollama
     YiFenYiDuan
```

核心技术栈：

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Pinia + Vue Router + Tailwind CSS + Vite |
| API | FastAPI + Pydantic + SSE + WebSocket |
| Agent 编排 | LangGraph StateGraph |
| 数据库 | SQLite + SQLAlchemy + WAL |
| RAG | Dense Embedding + Keyword Hybrid Retrieval |
| Embedding | SiliconFlow / OpenAI / DashScope / Ollama |
| LLM | OpenAI Compatible API，可切换 DeepSeek / Qwen / GLM / GPT / Ollama |
| 语音 | DashScope ASR + TTS + WebSocket |
| 可观测性 | Prometheus + Sentry + Analytics Event Tracker |
| 部署 | Docker Compose + Nginx |

---

## LangGraph：把咨询流程变成状态机

项目的核心不是单次 LLM 调用，而是一条可观测、可测试的 Agent Workflow。

当前主链路：

```text
security_scan
    ↓
intent_detect
    ↓
scene_route
    ↓
slot_extract
    ↓
profile_check
    ├── 信息不足 ─→ question_generate ──────────────┐
    ├── 已有直接回复 ───────────────────────────────┤
    │                                               ▼
    └── 信息完整 → quality_orchestrate          render_reply
                      ↓                            ↓
                  data_query                source_attribution
                      ↓                            ↓
                  rag_retrieve              quality_post_check
                      ↓                            ↓
                    reason                  quality_judge
                      ↓                            ↓
               structure_output              feedback
                                                   ↓
                                              memory_update
                                                   ↓
                                                  END
```

### 为什么要这么拆？

例如用户只输入：

> “广东 600 分，想学计算机，怎么报？”

系统不会立即让模型生成答案，而是依次完成：

1. 识别咨询场景与意图；
2. 抽取省份、分数、选科、兴趣等槽位；
3. 判断画像是否完整，不完整就继续追问；
4. 查询一分一段和历史录取数据；
5. 检索计算机就业、院校选择、AI 时代风险等知识；
6. 将结构化数据、RAG 证据、用户画像和决策启发组合成 reasoning context；
7. 再由 LLM 生成最终回复；
8. 对输出做来源标注、质量检查和会话记忆更新。

可以把它理解为：

```text
Answer = LLM(Profile + AdmissionData + RAG + DecisionRules + Memory)
```

而不是：

```text
Answer = LLM(UserQuery)
```

---

## Hybrid RAG

知识库目前按领域拆为 G1-G9 九个知识组：

```text
knowledge/groups/
├── G1_core_method.md
├── G2_major_school.md
├── G3_career_future.md
├── G4_life_planning.md
├── G5_data_format.md
├── G6_quick_ref.md
├── G7_employment_paths.md
├── G8_graduate_and_vocational.md
└── G9_zhangxuefeng_methodology_origin.md
```

此外还有独立的专家观点 / 语录库：

```text
knowledge/quotes/
├── _by_major.json
├── zhangxuefeng_originals.json
└── ...
```

### 检索流程

```text
User Query
    │
    ├── Dense Embedding Similarity
    │
    └── Keyword / Trigger Score
              │
              ▼
       Hybrid Group Score
              │
              ▼
       Top Knowledge Groups
              │
              ├── Top Chunks
              └── Expert Quotes
                     │
                     ▼
              Agent Reasoning Context
```

默认知识组打分使用：

```text
hybrid_score = 0.6 × vector_score + 0.4 × keyword_score
```

Embedding Provider 已抽象，可通过配置切换：

- `siliconflow`：默认推荐中文向量模型；
- `openai`；
- `dashscope`；
- `ollama`：本地 Embedding；
- `keyword`：Embedding 不可用时自动降级。

RAG 查询结果会按照 `query + slots` 缓存，减少重复 Embedding 与检索开销。

---

## 结构化高考数据

相比只做知识问答，本项目另外维护独立的结构化数据层。

当前数据包括：

| 数据 | 当前规模 / 范围 |
|---|---|
| 全国院校 | 3,016+ 所 |
| 历史录取数据 | 35 万+ 条 |
| 省份覆盖 | 30 个省份 |
| 年份 | 2022–2025 |
| 一分一段表 | 30 省份 |
| 专业 / 就业知识 | 多学科门类 |
| RAG 知识模块 | 20+ |
| 专家语录 | 155+ |

数据查询节点会根据用户槽位执行：

- 分数 → 位次查询；
- 院校匹配；
- 专业对应院校查询；
- 专业信息查询；
- 冲 / 稳 / 保候选集生成。

### 数据来源与采集

项目内置数据导入脚本：

```bash
# 全量导入
python scripts/import_baidu_gaokao.py --full --provinces ALL --top-n 3000

# 断点续传
python scripts/import_baidu_gaokao.py --full --provinces ALL --resume

# 导入一分一段
python scripts/import_yi_fen_yi_duan.py

# 数据校验
python scripts/validate_data.py
```

采集器支持 checkpoint / resume，便于大规模数据任务中断恢复。

> 高考录取政策和招生计划每年都会变化。历史数据只能作为决策依据之一，真实填报应以当年各省考试院、院校招生章程和正式招生计划为准。

---

## 用户画像与多轮咨询

系统维护一组高考咨询槽位，例如：

```text
province   省份
score      分数
subject    科类 / 选科
interest   兴趣 / 目标专业
region     地域偏好
family     家庭条件
career     就业 / 考研 / 考公目标
```

`profile_check` 会根据当前信息决定：

```text
信息不足 → 继续追问
信息完整 → 进入完整推荐链路
```

因此项目支持真正的多轮决策，而不仅是聊天历史拼接。

---

## 决策与质量控制

项目把志愿推荐中的部分业务判断从 Prompt 中拆成独立模块。

当前 Quality / Skill 层包括：

- 情绪状态检测；
- 决策启发式；
- 认知模型选择；
- AI 时代专业风险提示；
- 反模式检查；
- 数据交叉验证能力；
- 上下文知识加载；
- 来源标注；
- 生成后质量检查；
- 用户反馈记录。

`reason_node` 最终会把以下信息组合为统一推理上下文：

```text
用户画像
+ 结构化院校 / 位次数据
+ RAG Knowledge Chunks
+ Expert Quotes
+ Emotion State
+ Cognitive Model
+ Decision Heuristics
```

再交给 LLM 负责自然语言生成。

---

## 两阶段 SSE Streaming

聊天接口采用两阶段架构，避免同一个请求重复调用 LLM：

```text
Phase 1
LangGraph.invoke()
→ slots / emotion / structured metadata

Phase 2
llm_node_stream()
→ token-by-token SSE streaming
```

SSE 事件包括：

```text
slots
emotion
structured
token
degraded
done
```

LLM 调用同时实现：

- 429 / 5xx 自动重试；
- 指数退避；
- 上下文裁剪；
- 历史会话加载；
- Provider 可切换；
- 失败降级回复。

---

## Voice Pipeline

除了文字聊天，项目还提供语音交互链路：

```text
Microphone
   ↓
WebSocket
   ↓
DashScope ASR
   ↓
LangGraph Advisor
   ↓
LLM Response
   ↓
DashScope TTS
   ↓
Audio Playback
```

接口：

```text
WS /ws/call
```

通过环境变量可以独立开关语音功能。

---

## API

FastAPI 默认文档：

```text
http://localhost:8000/docs
```

主要接口：

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/chat` | LangGraph + SSE 聊天 |
| `GET` | `/api/v1/data/schools` | 院校查询 |
| `GET` | `/api/v1/data/scores` | 录取分数查询 |
| `GET` | `/api/v1/data/plans` | 招生计划查询 |
| `POST` | `/api/v1/knowledge/search` | RAG 检索 |
| `GET` | `/api/v1/knowledge/quotes` | 专家语录查询 |
| `POST` | `/api/v1/onboarding` | 用户初始化 |
| `GET/PUT` | `/api/v1/profile/{session_id}` | 用户画像 |
| `WS` | `/ws/call` | 实时语音咨询 |
| `GET` | `/metrics` | Prometheus Metrics |

---

## 项目结构

```text
.
├── server/
│   ├── main.py                 # FastAPI 入口
│   ├── graph/                  # LangGraph 状态机
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── nodes/
│   ├── routes/                 # REST / SSE / WebSocket API
│   ├── services/
│   │   ├── rag.py
│   │   ├── kb_retriever.py
│   │   ├── data_query.py
│   │   └── voice.py
│   └── agent/                  # LLM reliability / context
├── frontend/                   # Vue 3 SPA
├── db/                         # SQLite / SQLAlchemy
├── quality/                    # 质量控制模块
├── skills/                     # 咨询方法论 / 决策技能
├── knowledge/
│   ├── groups/                 # G1-G9 RAG Knowledge Groups
│   └── quotes/                 # Expert Quotes
├── slots/                      # 用户信息槽位抽取
├── scrapers/                   # 高考数据采集器
├── scripts/                    # 导入 / 校验 / Embedding 脚本
├── tests/                      # 单元 / 集成 / E2E 测试
├── prompts/                    # Prompt 版本管理
├── data/gaokao.db              # SQLite 数据库
├── system_prompt.md
├── docker-compose.yml
├── nginx.conf
└── README.md
```

---

## 快速开始

### 1. Clone

```bash
git clone https://github.com/yandexuanxuan/gaobao-advisor.git
cd gaobao-advisor
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

至少配置一个 LLM：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

如果需要向量 RAG：

```env
RAG_EMBEDDING_PROVIDER=siliconflow
SILICONFLOW_API_KEY=your-key
```

如果不配置 Embedding Provider，系统可降级为关键词检索。

### 3. Docker Compose

```bash
docker compose up -d --build
```

访问：

```text
Web:      http://localhost
API:      http://localhost:8000
API Docs: http://localhost:8000/docs
Metrics:  http://localhost:8000/metrics
```

Docker Compose 当前包含：

```text
api       FastAPI :8000
frontend  Vue/nginx :3080
nginx     Reverse Proxy :80
```

---

## 本地开发

### Backend

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn server.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

默认前端开发端口由 Vite 提供，API 服务运行在 `localhost:8000`。

---

## 模型切换

项目使用 OpenAI Compatible API，因此不绑定单一模型。

可通过环境变量或配置文件切换：

```env
LLM_PROVIDER=deepseek
# LLM_PROVIDER=qwen
# LLM_PROVIDER=glm
# LLM_PROVIDER=moonshot
# LLM_PROVIDER=openai
# LLM_PROVIDER=ollama
```

生产环境建议优先选择中文指令遵循能力较好的中大型模型；较小模型在复杂多约束志愿决策场景中容易出现格式错误和约束遗漏。

---

## 测试

项目包含较完整的后端测试体系，覆盖：

- Agent 核心逻辑；
- LangGraph 工作流；
- SSE Streaming；
- RAG 集成；
- Security / Rate Limit Middleware；
- Quality Modules；
- Source Attribution；
- E2E Conversation Flow。

运行：

```bash
pytest
```

当前仓库包含约 **48 个测试文件 / 538 个测试用例**，并使用 `pytest-cov` 进行覆盖率约束。

前端测试：

```bash
cd frontend
npm run test
```

---

## Observability & Security

FastAPI 服务已接入：

```text
CORS
SecurityMiddleware
CSP Middleware
Rate Limiting
Prometheus Metrics
Sentry
Analytics Event Tracking
Session Token
```

生产环境建议务必配置：

```env
SESSION_SECRET=<strong-random-secret>
CORS_ORIGINS=https://your-domain.com
```

---

## 当前局限

这个项目目前仍然是持续迭代中的工程项目，主要还有以下优化方向：

1. **数据时效性**：历史录取数据、招生计划、专业组每年都会变化，需要进一步完善数据版本、更新时间和置信度管理；
2. **RAG 规模化**：当前是轻量 Hybrid Retrieval，未来知识规模扩大后可升级为 BM25 + Dense Retrieval + RRF + Reranker；
3. **推荐评测**：工程测试已经较完整，但还需要建立真实高考案例 Golden Set，系统评估 Recall@K、冲稳保准确率、数据引用正确率和人工专家评分；
4. **Quality Pipeline**：数据交叉验证、Evidence Gate 和生成后质量控制仍有进一步解耦空间；
5. **志愿表级优化**：当前重点是咨询和候选推荐，完整志愿表排序、专业调剂和组合风险优化仍在规划中。

---

## Roadmap

- [x] FastAPI API Server
- [x] Vue 3 SPA
- [x] LangGraph 多轮咨询状态机
- [x] SSE Streaming
- [x] Hybrid RAG
- [x] 一分一段 / 位次法
- [x] 30 省历史数据
- [x] SQLite 会话持久化
- [x] Source Attribution
- [x] Quality / Feedback Pipeline
- [x] WebSocket Voice
- [x] Docker Compose Deployment
- [ ] BM25 + Dense + RRF + Reranker
- [ ] Evidence Gate 独立化
- [ ] Golden Set / RAG & Recommendation Evaluation
- [ ] 完整志愿表自动排序
- [ ] 调剂与退档风险模拟
- [ ] 家庭多人协同决策

---

## 为什么这个项目不是“LLM 套壳”

```text
普通 ChatBot
User → Prompt → LLM → Answer

Gaobao Advisor
User
 → Security / Intent
 → Slot Extraction
 → Profile State
 → Structured Data Query
 → Hybrid RAG
 → Decision Context
 → LLM
 → Source Attribution
 → Quality Check
 → Feedback / Memory
 → Answer
```

LLM 是系统的一部分，而不是整个系统。

项目真正希望验证的是：**如何把 RAG、Agent Workflow、结构化业务数据、可靠性工程和产品交互组合成一个可落地的垂直 AI 应用。**

---

## Disclaimer

本项目用于 AI 工程研究、教育信息整理和志愿规划辅助，不构成任何录取承诺。

高考政策、招生计划、专业组、录取位次等信息可能发生变化，正式填报前请务必以 **教育部、各省教育考试院和目标院校当年官方招生信息** 为准。

---

## License

[MIT License](LICENSE)
