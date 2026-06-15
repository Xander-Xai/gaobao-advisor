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

---

# AI-character-skill 项目引用与知识资产整合

## 日期

2026-06-13

## 背景与目标

AI-character-skill（角色蒸馏工厂）是一个 AI 角色模拟项目，核心资产是基于 `dot-skill` 引擎蒸馏的名人 persona 文件。其中张雪峰 persona（高考志愿规划专家）的**表达方法论、决策启发式、研究方法论**与 gaobao-advisor 的顾问体系高度相关。

本次整合的目标是：**从 AI-character-skill 中提取可复用的知识资产，增强 gaobao-advisor 的专业推荐精度、知识质量可审计性和 AI 风险评估能力。**

### 分析过程

对两个项目进行了全源码级深度分析：

- gaobao-advisor：14 个 Python 模块 + 7 个 QC 模块 + 11 个知识模块 + 490 个测试
- AI-character-skill：9 个 persona 目录 + 3 份研究文件（456 行）+ 0 个可运行代码文件

**关键发现**：AI-character-skill 是一个**输出仓库**（只有 markdown 文件），不是代码仓库。所有工具脚本、prompt 模板、Web 界面均不在仓库内。

## 两个项目能力对照

| 能力维度 | gaobao-advisor | AI-character-skill | 整合价值 |
|---------|---------------|-------------------|---------|
| 人格定义 | system_prompt.md（v2.8，530 行虚构人格） | 7 层认知架构（张雪峰 546 行 SKILL.md） | ⚠️ 结构可借鉴，但不做重写 |
| 表达引擎 | 8 种开场白 + 节奏公式 + 禁词 | 完整表达 DNA（口音/语速/语调/句式/癖好） | ✅ **高**——结构化方法论可提取 |
| 决策框架 | 8 条启发式 + 9 条快速规则（我们增强后） | Layer 4 决策启发式 + 条件化推理 | ✅ **高**——条件推理逻辑可提取 |
| 专业推荐 | G2 红黑名单（通用列表） | work.md 精确到专业的条件化推荐 | ✅ **高**——条件列可补充 |
| 研究方法论 | 无（知识模块无来源追踪） | 6 维度结构化研究 + 矛盾/推断/模式追踪 | ✅ **高**——可创建审计框架 |
| AI 风险评估 | ai_era_risk.py（代码存在但数据文件缺失） | 无 | ✅ **中**——需补数据文件 |
| 知识库规模 | 11 个模块 + 105 条语录 + 3016 校 | 无代码、无数据 | ❌ 不适用 |
| 可运行代码 | 完整（FastAPI + LangGraph + 490 测试） | 0 行代码 | ❌ 不适用 |

## 3 个整合方向的决策

| 方向 | 决策 | 理由 |
|------|------|------|
| **方向一：借鉴表达DNA结构** | ✅ **做** | 借鉴张雪峰 Layer 2 的结构化方法（量化参数 + 功能化句式 + 声音示例），增强 gaobao-advisor 现有表达引擎，不复制人格 |
| **方向二：增强决策启发式** | ✅ **做** | 借鉴张雪峰 Layer 4 的条件化推理逻辑，为专业红黑名单增加条件列 + 决策树 |
| **方向三：创建知识审计框架** | ✅ **做** | 借鉴张雪峰研究文件的 6 维度结构化方法论，创建 gaobao-advisor 自身的知识模块审计框架 |
| 方向四：引入张雪峰 persona 作为"第二专家" | ❌ 不做 | gaobao-advisor 的 7 个 QC 模块已覆盖对抗性审查功能，叠角色会增加不确定性 |
| 方向五：用 7 层架构重写 system_prompt | ❌ 不做 | 现有人格 v2.8 已稳定运行，重写风险 > 收益 |
| 方向六：引入 dot-skill 引擎 | ❌ 不做 | 引擎不在仓库内，是外部依赖，无法控制 |

## 实施结果

### 新增文件（4 个）

| 文件 | 说明 |
|------|------|
| `skills/gaokao/expression_samples.md` | 4 个场景→完整回复示范（极端判断/观点挑战/争议回应/诚实边界） |
| `knowledge/knowledge_quality_audit.md` | 知识模块质量审计框架（6 维度 + 审计报告模板 + 首次审计结果） |
| `quality/ai_era_risk_data.json` | AI 风险评估数据文件（24 个主要专业，含风险级别/冲击描述/幸存岗位/建议） |
| `tests/test_ai_era_risk.py` | ai_era_risk 模块测试（7 个测试用例，含边界测试） |

### 修改文件（4 个）

| 文件 | 改动 |
|------|------|
| `skills/gaokao/expression_engine.md` | +表达参数表（6 维量化）+ 功能化句式库（6 类×3-5 句） |
| `skills/gaokao/heuristics.md` | +9 条 If-Then 快速规则 + 审慎度分级（低审慎/高审慎） |
| `system_prompt.md` | +优化目标声明（最大化确定性生存 + 优先级排序），版本升级至 v2.10 |
| `knowledge/groups/G2_major_school.md` | 红名单增加"推荐条件"列 + 黑名单增加"例外条件"列 + 新增条件化决策树 |
| `quality/ai_era_risk.py` | 添加空字符串/None 输入防御性检查 |

### 测试结果

```
490 passed, 0 failed, 1 warning
```

### Git Commit 历史

```
c39ea0b fix: 验收修复 — ai_era_risk防御性检查 + 审计状态更新 + 边界测试
f74597d feat: 创建AI风险评估数据文件，激活ai_era_risk模块
c664ada feat: 知识模块质量审计框架（借鉴AI-character-skill研究方法论）
cdcfb29 feat: 增强专业红黑名单条件化推理 + 决策树
1ce149f feat: 表达引擎增强 — 声音示例 + 功能化句式 + 快速规则
```

## 引用资产清单

以下内容从 AI-character-skill 张雪峰 persona 中提取并整合：

| # | 来源 | 目标 | 整合方式 |
|---|------|------|---------|
| 1 | Layer 2 表达DNA 量化参数（句长/反问频率/确定性程度） | `expression_engine.md` 表达参数表 | 结构借鉴，内容独立定义 |
| 2 | Layer 2 功能化句式分类（确认/判断/锚定/比喻/免责/反问） | `expression_engine.md` 功能化句式库 | 分类方法借鉴，句式为 gaobao 独有 |
| 3 | Layer 2 声音示例（场景→完整回复） | `expression_samples.md` 4 个示范 | 结构借鉴，内容为 gaobao 独有 |
| 4 | Layer 4 决策启发式条件化推理 | `G2_major_school.md` 条件列 + 决策树 | 逻辑借鉴，数据为 gaobao 独有 |
| 5 | Layer 4 快速决策/谨慎决策分类 | `heuristics.md` 审慎度分级 | 分类方法借鉴 |
| 6 | Layer 0 优化目标声明 | `system_prompt.md` 优化目标段落 | 理念借鉴，措辞为 gaobao 独有 |
| 7 | 研究方法论 6 维度（来源追踪/矛盾检测/推断标注/差距发现/覆盖率/一致性） | `knowledge_quality_audit.md` | 方法论完整借鉴 |
| 8 | 张雪峰 work.md 专业红黑名单推理 | `G2_major_school.md` 条件列 | 条件逻辑部分借鉴 |
| 9 | 00_ai_era_correction.md AI冲击评估数据 | `ai_era_risk_data.json` | 数据结构化转换 |

### 引用原则

- **只借鉴结构和方法论**，不复制人格（gaobao-advisor 是独立的虚构顾问）
- **只借鉴条件化推理逻辑**，不复制具体推荐（gaobao 有自己的数据支撑）
- **所有内容最终为 gaobao-advisor 独有**，不依赖 AI-character-skill 运行

## 关键设计决策

1. **不重写 system_prompt** — 现有人格 v2.8 已稳定运行，借鉴结构但保持独立人格
2. **条件列补充而非替换** — G2 红黑名单保留原有列表，在旁边增加条件列
3. **审计框架为元工具** — 不直接影响用户体验，为后续知识模块迭代提供方法论
4. **AI 风险数据独立维护** — 每年需根据最新就业数据更新，有明确的时效性声明
5. **零代码依赖** — 整合内容全部为 markdown + JSON，不引入新的 Python 依赖

## 后续扩展建议

1. **考研场景 skill 文件**：新建 `skills/kaoyan/` 目录，复用同一套 SkillService 架构
2. **职业规划 skill 文件**：新建 `skills/career/` 目录
3. **前端结构化卡片展示**：在 Streamlit 或 Vue3 前端中展示 StructuredPlanningCard 的 facts/suggestions/risks/next_actions
4. **语音通话**：待高考数据层做到极致后，可考虑引入 EduAgent 的语音实现
5. **多场景扩展**：先建设考研数据层（院校/专业/分数线），再扩展场景

---

# 第三轮整合 — zhangxuefeng-skill-merged 金句溯源 + 叙事知识 + 硬规则

## 日期

2026-06-14

## 背景

zhangxuefeng-skill-merged 项目（1184 行 Markdown / 8 文件）是一个张雪峰 persona 技能包。经过深度代码级分析发现：

- 其方法论内容（5 模型/8 启发/8 反模式/3 档情绪/9 故障自愈）**已被 gaobao-advisor 在 v2.6-v2.10 完全吸收**
- 真实缺口仅 3 块，本次方案据此重写为 3 Phase

## 整合内容

### Phase 1: 金句溯源

将 zhangxuefeng 50 句原版金句（带出处、年份、来源详情）写入 RAG：

- 文件：`knowledge/quotes/zhangxuefeng_originals.json`
- 代码层：扩展 `QuoteEntry` 增加 `source`/`year` 字段
- 检索：`_select_top_quotes` 增加 ZX 触发词额外 +0.5 召回提升
- 触发词：张雪峰/雪峰/演说家/综艺/直播里讲/主播说/讲座说过
- 测试：13 个，全部通过

### Phase 2: 叙事知识入 RAG

将 zhangxuefeng 的 5 个研究文件（5 本书/15 采访/11 决策/4 盲点/24 年时间线）整合为 G9 知识组：

- 文件：`knowledge/groups/G9_zhangxuefeng_methodology_origin.md`（7 节，精简整合，<100 行/节）
- 触发词：张雪峰/方法论溯源/为什么这么说/批评/盲点/演说家/决策/时空
- 测试：15 个，全部通过

### Phase 3: 数据来源标注硬规则

将 zhangxuefeng-skill-merged SKILL.md 的 6 条来源标注格式升级为代码层后处理：

- 新增 `server/graph/nodes/source_attribution.py`：`validate_source_attribution` 函数
- 集成到 `render.py`：两个路径（LLM 回复 + 系统组装回复）都过后处理
- Prompt 层：`system_prompt.md` 新增"数据来源标注硬规则"章节
- 安全数字豁免：年份/序号/月份/第 N/免责声明
- 测试：20 个，全部通过

## 总览

| 维度 | 数值 |
|------|------|
| 新增文件 | 6 个 |
| 修改文件 | 4 个 + CHANGELOG |
| 新增测试 | 48 个（3 文件） |
| 全量测试 | 538 通过，0 失败 |
| system_prompt | v2.7 → v2.11 |

## 核心决策

1. **不做张雪峰 persona 模式** — 只吸收方法论和调研资料，不引入角色切换
2. **金句走 RAG 检索** — 不注入 system_prompt，top-3-5 按场景召回
3. **硬规则做正则后处理** — 不依赖 LLM 自觉遵守规则

