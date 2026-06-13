# gaobao-advisor 二次开发记录

> 基于 EduAgent 项目的分析，对 gaobao-advisor 进行方法论体系模块化和结构化输出升级。

## 日期

2026-06-13

## 背景

gaobao-advisor 是一个高考志愿 AI 顾问项目，基于大量高考志愿填报方法论和院校数据构建，具有完整的方法论体系（5 大心智模型、8 条决策启发式、表达引擎等）、RAG 知识检索、质量控制模块和多渠道部署能力。

EduAgent 是另一个面向教育规划场景的智能 Agent 项目，聚焦高考志愿、考研规划和职业方向评估，具有实时语音通话、Vue3 前端、用户画像沉淀等能力。

本次二次开发的目的是：从 EduAgent 中提取可复用的架构设计，增强 gaobao-advisor 的方法论管理和结构化输出能力。

## 需求分析过程

### 两个项目能力对照

| 能力维度 | gaobao-advisor | EduAgent | 判断 |
|---------|---------------|----------|------|
| 数据层 | 3000+院校/70K+分数线/30省 | 依赖网络抓取，无结构化DB | gaobao 远领先 |
| 知识库/RAG | 17+模块/105语录/混合检索 | 无 | gaobao 远领先 |
| 质量控制 | 7个模块 | 无 | gaobao 远领先 |
| Prompt工程 | v2.7(5心智模型/8启发式/表达引擎) | zhangxuefeng-skill | 两者互补 |
| LangGraph | 13节点图 | 14节点图 | 结构相似 |
| 实时语音 | Stub实现 | 完整DashScope ASR+TTS | EduAgent领先 |
| 前端UI | Streamlit(原型级) | Vue3三栏布局 | EduAgent领先 |
| 结构化输出 | 仅数据查询结果 | StructuredPlanningCard | EduAgent更完整 |
| 多场景 | 高考为主 | 高考/考研/职业三场景 | EduAgent更完整 |
| 部署 | CLI/Web/API/Docker | 仅本地开发 | gaobao更成熟 |
| 安全 | 注入检测/SSRF/XSS/限流 | 无 | gaobao远领先 |

### 5 个改进方向的评估

| 方向 | 结论 | 理由 |
|------|------|------|
| 实时语音通话 | ❌ 不做 | 集成复杂、场景不匹配（用户需要留档查阅而非通话）、引入DashScope强耦合 |
| Vue3前端替换Streamlit | ❌ 不做 | 范式不兼容、维护成本翻倍、Streamlit Cloud免费部署优势丧失 |
| 多场景扩展(高考+考研+职业) | ⏳ 以后做 | 数据层未到位、开发资源分散、高考主场景需先做到极致 |
| **结构化规划输出** | **✅ 做** | 低风险、利用已有数据、不改变交互、API协议已支持 |
| **Skill方法论体系** | **✅ 做** | 内部重构、对外零感知、为未来扩展打基础 |

## 实施方案

### 方向四：结构化规划输出

**目标**：让每次推荐输出都包含结构化的 `StructuredPlanningCard`（title/summary/facts/suggestions/risks/next_actions），通过 SSE 发送给前端。

**架构**：
```
用户输入
  → quality_orchestrate_node
  → data_query → rag_retrieve
  → reason_node（提取 facts/suggestions/risks）
  → structure_output_node（组装 StructuredPlanningCard）
  → render_reply（纯文本，不变）
  → SSE 响应（文本 + structured_card）
```

### 方向五：Skill 方法论体系

**目标**：将 system_prompt.md 中 653 行的方法论内容拆成可独立加载的 skill 文件，由 SkillService 按场景拼接注入。

**目录结构**：
```
skills/
├── __init__.py
├── service.py          # SkillService：加载 + 策略构建 + context 拼接
├── bootstrap.py        # 预热加载
└── gaokao/
    ├── mental_models.md      # 5 大心智模型
    ├── heuristics.md         # 8 条决策启发式
    ├── anti_patterns.md      # 8 条决策反模式
    ├── expression_engine.md  # 表达引擎
    └── safety_rules.md       # 安全边界
```

**SkillService 核心方法**：
- `load_assets()` — 加载 skill md 文件（幂等）
- `build_strategy(scene)` — 返回结构化策略（heuristics/output_style/answer_rules）
- `build_context(scene)` — 返回 LLM 注入上下文字符串
- `build_question_reply(scene, missing_fields)` — 自然语言追问

## 实施结果

### 新增文件（14个）

| 文件 | 说明 |
|------|------|
| `skills/__init__.py` | 包标记 |
| `skills/gaokao/__init__.py` | 包标记 |
| `skills/gaokao/mental_models.md` | 5 大心智模型 + 调度规则 + 降级触发器 |
| `skills/gaokao/heuristics.md` | 8 条决策启发式 |
| `skills/gaokao/anti_patterns.md` | 8 条决策反模式黑名单 |
| `skills/gaokao/expression_engine.md` | 表达引擎（开场模板/节奏/金句/禁词） |
| `skills/gaokao/safety_rules.md` | 安全边界 + 输出规则 |
| `skills/service.py` | SkillService 类 |
| `skills/bootstrap.py` | 预热加载函数 |
| `server/domain/__init__.py` | 包标记 |
| `server/domain/schemas.py` | StructuredPlanningCard schema |
| `tests/test_skill_service.py` | SkillService 测试（10个） |
| `tests/test_structured_card.py` | schema + structure_output_node 测试（7个） |
| `tests/test_skill_integration.py` | 集成测试（3个） |
| `tests/test_chat_sse.py` | SSE 端点测试（1个） |

### 修改文件（5个）

| 文件 | 改动 |
|------|------|
| `server/graph/nodes/structure.py` | 重写：从 reasoning 提取 facts/suggestions/risks/next_actions |
| `server/graph/nodes/quality_nodes.py` | 集成 SkillService，注入 skill context |
| `server/graph/nodes/reason.py` | 注入方法论上下文到 reasoning 字符串 |
| `system_prompt.md` | 精简：652行 → 469行（-28%），方法论迁移到 skill 文件 |
| `tests/test_langgraph.py` | 新增 2 个集成测试 |

### 测试结果

```
478 passed, 0 failed, 1 warning
```

### 修复的预存问题

| 问题 | 根因 | 修复 |
|------|------|------|
| `test_admission_returns_empty_with_confidence_fields` flaky failure | `test_enrollment_plans.py` 的 `_set_crud()` 直接替换 `gaokao_data._crud` 但没有恢复，mock 跨测试泄漏 | 添加 `autouse` fixture 在每个测试后恢复 `_crud` |

## Git Commit 历史

```
42ca246 fix: restore gaokao_data._crud after enrollment plan tests to prevent cross-test mock pollution
c7050df test: add integration tests for skill system + structured output
955c20f refactor: simplify system_prompt.md by extracting methodology to skill files
4e49589 test: verify SSE endpoint emits complete StructuredPlanningCard
8250215 fix: add thread-safe locking to quality_nodes singletons, improve test assertions
64a1b92 feat: integrate SkillService into quality orchestration and reasoning
f86870b fix: extract magic numbers into named constants in structure_output_node
2e01f89 feat: rewrite structure_output_node to produce StructuredPlanningCard
66f1051 feat: add StructuredPlanningCard Pydantic schema
cda8c3f fix: address code quality issues in SkillService
9318f54 feat: add SkillService for pluggable methodology injection
4ffef68 feat: extract methodology from system_prompt into pluggable skill files
```

## 关键设计决策

1. **skill context 通过 LangGraph 注入，而非硬编码在 system prompt 中** — 修改方法论只需编辑 `skills/gaokao/*.md`，不需要改 system_prompt.md
2. **结构化卡片和纯文本回复并行生成** — 如果卡片生成失败，用户仍然拿到纯文本
3. **SkillService 有 graceful fallback** — skill 文件不存在时降级为空字符串，不影响现有功能
4. **Thread-safe 单例模式** — quality_nodes.py 使用 double-checked locking 保证并发安全
5. **不引入新依赖** — 所有改动仅使用项目已有的 Pydantic、LangGraph、FastAPI

## 后续扩展建议

1. **考研场景 skill 文件**：新建 `skills/kaoyan/` 目录，复用同一套 SkillService 架构
2. **职业规划 skill 文件**：新建 `skills/career/` 目录
3. **前端结构化卡片展示**：在 Streamlit 或 Vue3 前端中展示 StructuredPlanningCard 的 facts/suggestions/risks/next_actions
4. **语音通话**：待高考数据层做到极致后，可考虑引入 EduAgent 的语音实现
5. **多场景扩展**：先建设考研数据层（院校/专业/分数线），再扩展场景
