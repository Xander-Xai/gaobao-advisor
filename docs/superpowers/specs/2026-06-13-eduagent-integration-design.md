# gaobao-advisor 增强整合方案设计文档

> **目标：** 将 EduAgent 的四大差异化能力（语音交互、LangGraph 工作流、Vue 3 前端、多场景扩展）整合到 gaobao-advisor 主项目中，提升其架构可维护性和功能覆盖面。

---

## 1. 项目背景

### 现状对比

| 维度 | gaobao-advisor（主项目） | EduAgent（补充项目） |
|---|---|---|
| 成熟度 | v2.7/2.8，333 测试，生产部署 | 早期原型 |
| 后端 | agent.py 2000+ 行单文件 + Streamlit | FastAPI + LangGraph 14 节点 |
| 前端 | Streamlit（Python 全栈） | Vue 3 + Tailwind（组件化） |
| 数据层 | SQLite 10 表，3016 院校，70000+ 录取分 | ArangoDB（conversations/profiles/traces） |
| 质量模块 | 7 个：情绪/交叉验证/AI风险/决策框架/反模式/模型选择/知识加载 | 模板驱动，正则提取 |
| 安全层 | 17 模式注入检测 + SSRF + XSS + 限流 | 无 |
| 语音 | 无 | 完整 ASR→LLM→TTS 管线 |
| 场景 | 仅高考志愿 | 高考 + 考研 + 职业规划 |
| 测试 | 333 个，20 个测试文件 | 无 |
| 部署 | Docker + Nginx + Streamlit Cloud | 本地开发 |

### 整合目标

以 gaobao-advisor 为主体，吸收 EduAgent 的优势能力：
1. 语音交互能力（ASR → 规划 → TTS 实时通话）
2. LangGraph 工作流编排（14 节点状态图，条件分支，可中断追问）
3. 现代前端替换 Streamlit（Vue 3 + Tailwind + 组件化）
4. 多场景扩展（高考 → 高考 + 考研 + 职业规划）

### 技术约束

- 保留 gaobao-advisor 的 SQLite 数据层和 SQLAlchemy 模型
- 保留全部 7 个 quality 模块
- 保留安全层（注入检测、SSRF、XSS、限流）
- 保留 333 个测试，更新导入路径
- LLM 调用兼容 OpenAI API（多 provider 支持保留）
- 允许架构升级（Streamlit → FastAPI + Vue 3）

---

## 2. 整体架构

### 架构图

```
┌─────────────────────────────────────────────────────┐
│                  Vue 3 Frontend                      │
│  Chat UI │ Onboarding │ Reports │ Voice Modal       │
│  (替代 Streamlit，复用 EduAgent 的 Vue 设计模式)     │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (JSON) + SSE + WebSocket
┌──────────────────────▼──────────────────────────────┐
│                FastAPI Backend                        │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐             │
│  │ /chat   │ │ /voice   │ │ /admin   │             │
│  │ routes  │ │ ws/call  │ │ routes   │             │
│  └────┬────┘ └────┬─────┘ └──────────┘             │
│       │           │                                  │
│  ┌────▼───────────▼──────────────────────┐          │
│  │      LangGraph Planning Engine        │          │
│  │  intent → route → extract → check     │          │
│  │  → question/gather → retrieve →       │          │
│  │  → reason → structure → render        │          │
│  └────────────────┬──────────────────────┘          │
│                   │                                  │
│  ┌────────────────▼──────────────────────┐          │
│  │        Service Layer (保留业务逻辑)    │          │
│  │  GaokaoData │ KbRetriever │ Quality   │          │
│  │  EmotionDetector │ CrossValidator     │          │
│  │  AiEraRisk │ DecisionFramework       │          │
│  │  AntiPatternChecker │ ModelSelector   │          │
│  └────────────────┬──────────────────────┘          │
│                   │                                  │
│  ┌────────────────▼──────────────────────┐          │
│  │        Infrastructure Layer           │          │
│  │  SQLite + SQLAlchemy │ DashScope/     │          │
│  │  OpenAI API │ Analytics DB            │          │
│  └───────────────────────────────────────┘          │
└─────────────────────────────────────────────────────┘
```

### 关键设计决策

1. **保留 SQLite 数据层**：gaobao-advisor 的 10 张表（School、Major、AdmissionScore 等）和 SQLAlchemy 模型不变
2. **保留质量模块**：7 个 quality 模块以独立服务层方式保留
3. **agent.py 拆解**：2000+ 行单文件拆解为 LangGraph 图定义 + 各节点实现 + FastAPI 路由
4. **LLM 兼容**：保留 OpenAI 兼容接口（DeepSeek/Qwen/GLM/Moonshot/GPT-4o/Ollama）
5. **语音 LLM 分离**：语音管线中的 Voice Rendering 用 DashScope（专为语音优化），主对话推理走 OpenAI 兼容接口
6. **向后兼容**：保留旧 agent.py 和 app.py（标记 deprecated），确保 Streamlit 模式仍可运行

---

## 3. Module 1 — FastAPI 后端重构

### 文件结构

```
gaobao-advisor/
├── server/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app 入口，替代 app.py + api_server.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py                # POST /api/v1/chat — SSE 流式对话
│   │   ├── onboarding.py          # POST /api/v1/onboarding — 3步引导
│   │   ├── knowledge.py           # POST /api/v1/knowledge/search
│   │   ├── data.py                # GET /api/v1/data/schools, /scores 等
│   │   ├── admin.py               # /api/v1/admin — 分析面板
│   │   ├── health.py              # GET /api/v1/health
│   │   └── voice.py               # WS /ws/call — 语音通话
│   ├── services/
│   │   ├── __init__.py
│   │   ├── advisor.py             # 核心顾问逻辑（从 agent.py 提取）
│   │   ├── slot_extractor.py      # 槽位提取（从 agent.py 提取）
│   │   ├── emotion.py             # 情绪检测（包装 quality/emotion_detector.py）
│   │   ├── data_query.py          # 数据查询（包装 gaokao_data.py）
│   │   ├── rag.py                 # RAG 检索（包装 kb_retriever.py）
│   │   ├── quality.py             # 质量模块编排（包装 7 个 quality 模块）
│   │   ├── voice.py               # 语音服务（从 EduAgent 移植）
│   │   └── profile.py             # 用户画像服务（从 EduAgent 移植）
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py               # LangGraph State 定义
│   │   ├── graph.py               # LangGraph StateGraph 定义
│   │   └── nodes/                 # 各节点实现
│   │       ├── __init__.py
│   │       ├── intent.py          # 意图识别
│   │       ├── route.py           # 场景路由
│   │       ├── extract.py         # 信息提取
│   │       ├── check.py           # 信息完整性检查
│   │       ├── question.py        # 追问生成
│   │       ├── retrieve.py        # 知识检索
│   │       ├── reason.py          # 推理决策
│   │       ├── structure.py       # 结构化输出
│   │       └── render.py          # 响应渲染
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── ratelimit.py           # 限流（保留 gaobao-advisor 的 token bucket）
│   │   ├── security.py            # 安全中间件（注入检测、SSRF、XSS）
│   │   └── cors.py                # CORS 配置
│   └── deps.py                    # 依赖注入（DB session、LLM client 等）
├── quality/                       # 保留不动
├── db/                            # 保留不动（models.py, crud.py, database.py）
├── scrapers/                      # 保留不动
├── knowledge/                     # 保留不动
├── prompts/                       # 保留不动
├── tests/                         # 更新导入路径
├── scripts/                       # 保留不动
├── analytics/                     # 保留不动
├── frontend/                      # 新增：Vue 3 前端（Module 3）
├── agent.py                       # 保留旧版作为 fallback（标记 deprecated）
├── app.py                         # 保留旧版作为 fallback
├── requirements.txt               # 更新：添加 fastapi, uvicorn, langgraph, websockets
└── .env                           # 不变
```

### 设计原则

1. **服务层封装**：gaobao-advisor 的业务逻辑（agent.py、gaokao_data.py、kb_retriever.py）以 Service 类包装，暴露干净接口
2. **LangGraph 图与服务解耦**：图节点调用服务层，服务层可独立测试
3. **向后兼容**：保留旧 agent.py 和 app.py（标记 deprecated），确保 Streamlit 模式仍可运行
4. **路由职责单一**：每个路由文件只处理 HTTP 协议层，业务逻辑全在 Service 层

### 路由清单

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/v1/chat | SSE 流式对话（核心） |
| POST | /api/v1/onboarding | 3 步引导流程 |
| POST | /api/v1/knowledge/search | 知识库搜索 |
| GET | /api/v1/data/schools | 院校数据查询 |
| GET | /api/v1/data/scores | 录取分数查询 |
| GET | /api/v1/data/plans | 招生计划查询 |
| GET | /api/v1/health | 健康检查 |
| POST | /api/v1/admin/login | 管理面板登录 |
| GET | /api/v1/admin/analytics | 分析数据 |
| WS | /ws/call | 语音通话 |

---

## 4. Module 2 — LangGraph 工作流引擎

### State 定义

```python
class AdvisorState(TypedDict):
    # --- 输入 ---
    session_id: str
    user_id: str
    input_text: str
    scene: Literal["gaokao", "kaoyan", "career", "general"]
    
    # --- 对话历史 ---
    messages: list[dict]
    
    # --- 槽位/画像 ---
    slots: dict
    profile_snapshot: dict
    missing_fields: list[str]
    
    # --- 质量模块 ---
    emotion_state: str            # crisis / anxiety / normal
    cognitive_model: str
    decision_heuristics: list[str]
    anti_pattern_violations: list
    
    # --- 知识检索 ---
    rag_chunks: list[dict]
    expert_quotes: list[dict]
    data_query_results: dict
    knowledge_context: str
    
    # --- 推理 ---
    reasoning: str
    structured_result: dict
    reply: str
    confidence: float
    
    # --- 追踪 ---
    trace: list[dict]
```

### 图结构

```
START
  → security_scan (安全扫描，17 模式注入检测)
  → intent_detect (意图识别)
  → scene_route (场景路由：gaokao/kaoyan/career)
  → slot_extract (槽位提取，regex + LLM)
  → profile_check (信息完整性检查)
  ├─ [incomplete] → question_generate → render_reply → END
  └─ [complete]  → quality_orchestrate
                   → data_query (场景特定数据查询)
                   → rag_retrieve (知识检索)
                   → reason (推理决策)
                   → structure_output (结构化输出)
                   → render_reply (响应渲染)
                   → memory_update
                   → END
```

### 节点与现有能力映射

| LangGraph 节点 | gaobao-advisor 现有实现 | EduAgent 补充 |
|---|---|---|
| `security_scan` | 17 regex 模式 (agent.py) | — |
| `intent_detect` | `is_consultation_intent()` | — |
| `scene_route` | 无（仅高考） | `scene_route_node`，多场景路由 |
| `slot_extract` | `extract_slots()` (agent.py) | `profile_extract_node`，regex 提取 |
| `profile_check` | 内嵌在 chat() 中 | 结构化缺口检测 |
| `question_generate` | 硬编码追问逻辑 | 张雪峰风格题库系统 |
| `quality_orchestrate` | 7 个模块直接调用 | 统一编排为一个节点 |
| `data_query` | `gaokao_data.py` 三级查询 | 网络检索补充 |
| `rag_retrieve` | `kb_retriever.py` 混合检索 | — |
| `reason` | 内嵌在 prompt 构建中 | 显式推理步骤 |
| `structure_output` | 无（纯文本输出） | 结构化规划卡 |
| `render_reply` | Markdown 后处理 | 多模态渲染 |
| `memory_update` | Conversation 表写入 | 画像 + 记忆更新 |

### 场景配置

```python
SCENE_CONFIGS = {
    "gaokao": {
        "required_slots": ["province", "score", "subject", "interest"],
        "data_query_fn": "gaokao_data_query",
        "rag_groups": ["G1", "G2", "G3"],
        "quality_config": "full",
    },
    "kaoyan": {
        "required_slots": ["target_school", "target_major", "current_major", "gpa"],
        "data_query_fn": "kaoyan_data_query",
        "rag_groups": ["G1", "G3"],
        "quality_config": "standard",
    },
    "career": {
        "required_slots": ["education", "skills", "interest", "family_background"],
        "data_query_fn": "career_data_query",
        "rag_groups": ["G3", "G4"],
        "quality_config": "standard",
    }
}
```

---

## 5. Module 3 — Vue 3 前端

### 组件结构

```
frontend/
├── package.json
├── vite.config.js
├── index.html
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── router/index.js
│   ├── stores/
│   │   ├── chat.js                 # 对话状态：消息、会话、SSE 连接
│   │   ├── profile.js              # 用户画像状态
│   │   ├── onboarding.js           # 引导流程状态
│   │   ├── voice.js                # 语音状态：WebSocket、音频流
│   │   └── scene.js                # 场景状态：gaokao/kaoyan/career
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppSidebar.vue      # 左侧会话列表
│   │   │   ├── AppHeader.vue       # 顶部导航：场景切换
│   │   │   └── AppRightPanel.vue   # 右侧面板：画像/报告
│   │   ├── chat/
│   │   │   ├── ChatArea.vue        # 聊天消息区域
│   │   │   ├── MessageBubble.vue   # 单条消息气泡
│   │   │   ├── MessageInput.vue    # 输入框 + 发送按钮
│   │   │   └── QuickQuestions.vue  # 动态快捷问题
│   │   ├── onboarding/
│   │   │   ├── OnboardingWizard.vue
│   │   │   ├── ProvinceSelect.vue
│   │   │   ├── ScoreInput.vue
│   │   │   └── SubjectSelect.vue
│   │   ├── voice/
│   │   │   ├── VoiceModal.vue      # 语音浮动窗口（可拖拽）
│   │   │   ├── VoiceRipple.vue     # 声波动画
│   │   │   └── LiveSubtitle.vue    # 实时字幕
│   │   ├── report/
│   │   │   ├── ReportView.vue      # 结构化规划报告
│   │   │   ├── FactsColumn.vue
│   │   │   ├── SuggestColumn.vue
│   │   │   └── RiskColumn.vue
│   │   └── profile/
│   │       ├── ProfilePanel.vue
│   │       ├── ProfileSummary.vue
│   │       └── ProfileFacts.vue
│   ├── composables/
│   │   ├── useSSE.js               # SSE 流式响应处理
│   │   ├── useVoice.js             # 语音 WebSocket 管理
│   │   └── useScene.js             # 场景切换逻辑
│   ├── api/client.js
│   └── styles/main.css
```

### API 契约

**对话接口（SSE）：**
```
POST /api/v1/chat
Body: { session_id, scene, message, slots? }
Response: SSE stream
  data: {"type": "token", "content": "..."}        // 逐 token 流式
  data: {"type": "structured", "result": {...}}     // 结构化结果
  data: {"type": "emotion", "state": "normal"}      // 情绪状态
  data: {"type": "done", "message_id": "..."}       // 结束
```

**引导接口：**
```
POST /api/v1/onboarding
Body: { step: 1-3, data: {...} }
Response: { next_step, profile_update, suggestions? }
```

**语音接口：**
```
WS /ws/call?session_id=...&scene=...
Browser → Server: PCM 8kHz 音频帧 (binary)
Server → Browser: PCM 24kHz TTS 音频帧 (base64) + JSON 控制消息
```

---

## 6. Module 4 — 语音交互

### 管线架构

```
Browser (Vue VoiceModal)
  │  PCM 8kHz 音频帧 (binary)
  ▼
WebSocket /ws/call
  │
  ▼
VoiceService (server/services/voice.py)
  │
  ├── ASR: DashScope paraformer-realtime-8k-v2
  │   └── 实时语音 → 文字
  │
  ├── 完整句子触发 → LangGraph Planning Engine
  │   └── 复用同一套工作流，scene 参数控制场景
  │
  ├── Voice Rendering: DashScope Chat (qwen-plus)
  │   └── 将结构化回复改写为口语化表达
  │
  └── TTS: DashScope qwen-tts-realtime (Cherry voice)
      └── 文字 → PCM 24kHz 音频 → base64 回传
```

### 关键特性

- **打断支持**：用户说话时自动停止 TTS 播放
- **场景感知语气**：高考=温暖鼓励型，考研=理性分析型，职业=务实直接型
- **情绪联动**：接入 emotion_detector.py，危机状态自动切换安抚语气
- **会话上下文**：保留最近 12 条消息作为上下文

### 配置

```env
DASHSCOPE_ASR_API_KEY=sk-xxx
DASHSCOPE_TTS_API_KEY=sk-xxx
DASHSCOPE_TTS_VOICE=Cherry
VOICE_ENABLED=true
```

---

## 7. Module 5 — 多场景扩展

### 场景差异矩阵

| 维度 | gaokao | kaoyan | career |
|---|---|---|---|
| 必填槽位 | 省份、分数、科目、兴趣 | 目标院校、目标专业、本科专业、GPA | 学历、技能、兴趣、家庭背景 |
| 数据源 | AdmissionScore + EnrollmentPlan（已有） | 新增：GraduateProgram + GraduateScore | 新增：CareerTrend |
| 知识库 | G1-G6（已有） | G1 方法论 + G3 就业 | G3 就业 + G4 规划 |
| 质量模块 | 全部 7 个 | emotion + decision + anti_pattern | emotion + ai_era_risk + decision |
| 认知模型 | 5 个（保留） | 3 个 | 3 个 |
| 输出 | StructuredPlanningCard | StructuredPlanningCard | StructuredPlanningCard |

### 新增数据表

```python
# db/models.py 新增
class GraduateProgram(Base):
    """考研院校专业"""
    __tablename__ = "graduate_program"
    id, school_name, school_level, province, major_name,
    major_category, degree_type  # 学硕/专硕
    acceptance_rate, avg_score    # 报录比, 平均分

class GraduateScore(Base):
    """考研分数线"""
    __tablename__ = "graduate_score"
    id, program_id, year, subject_type, total_score,
    politics_score, english_score, major_score

class CareerTrend(Base):
    """职业趋势数据"""
    __tablename__ = "career_trend"
    id, major_name, industry, job_title,
    salary_median, employment_rate, growth_rate, year
```

### 场景路由逻辑

```python
SCENE_KEYWORDS = {
    "gaokao": ["高考", "志愿", "填报", "录取", "投档", "分数线"],
    "kaoyan": ["考研", "研究生", "初试", "复试", "调剂", "学硕", "专硕"],
    "career": ["就业", "工作", "职业", "实习", "薪资", "转行"],
}
```

---

## 8. 安全层集成

| 安全机制 | 实现位置 | 说明 |
|---|---|---|
| Prompt 注入检测 | `security_scan` 节点 | 17 regex 模式，保留自 agent.py |
| Rate limiting | FastAPI middleware | Token bucket：20/hr, 40/day/IP |
| SSRF 防护 | `server/middleware/security.py` | DNS rebinding 保护 |
| XSS 净化 | `server/middleware/security.py` | HTML 标签净化 |
| 输入验证 | 路由层 | 3000 字符上限 |
| PII 保护 | 系统提示词 | 隐私护栏 |
| 数据库安全 | db/database.py | SQLite-only 白名单，文件权限 0600 |

---

## 9. 测试策略

- 更新现有 333 个测试的导入路径（从顶层模块 → server.services.*）
- 为每个 LangGraph 节点添加单元测试
- 为每个 FastAPI 路由添加 API 测试
- 为 LangGraph 图添加端到端集成测试
- 为语音管线添加 WebSocket 集成测试（mock DashScope）
- 为 Vue 前端添加组件测试（Vitest）

---

## 10. 部署变更

```yaml
# docker-compose.yml 更新
services:
  api:
    build: .
    command: uvicorn server.main:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
  
  frontend:
    build: ./frontend
    ports: ["3080:80"]
  
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    # 反向代理：/ → frontend, /api → api, /ws → api
```

保留 Streamlit 作为 legacy 模式（`streamlit run app.py`），通过环境变量 `DEPLOY_MODE=fastapi|streamlit` 切换。
