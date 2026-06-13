# Skill Methodology System + Structured Planning Output Design

## Context

gaobao-advisor 的 `system_prompt.md` 有 653 行，混合了人设、心智模型、启发式、表达引擎、安全规则等内容。所有方法论硬编码在一个文件中，无法按场景独立加载，维护时需要反复编辑整个文件。

同时，LangGraph 的 `structure_output_node` 只组装了数据查询结果（matched_schools/rank_info），缺少 `title/summary/facts/suggestions/risks/next_actions` 等规划级别的结构化输出，API 也无法向前端返回有组织的规划卡片。

EduAgent 的 `skill/service.py` 和 `StructuredPlanningCard` 提供了可复用的架构设计。

## Goal

1. **Skill 体系**：将 system_prompt.md 中的方法论拆成可独立加载的 skill 文件，由 `skills/service.py` 按场景拼接注入，不改变 LLM 输出质量。
2. **结构化输出**：每次推荐都生成 `StructuredPlanningCard`（title/summary/facts/suggestions/risks/next_actions），通过 SSE 发送给前端。

## Architecture

```
用户输入
  → quality_orchestrate_node
      └─ SkillService.build_strategy(scene)  ← 方向五
  → data_query → rag_retrieve
  → reason_node
      └─ SkillService.build_context(scene)  ← 方向五
      └─ 提取 facts/suggestions/risks       ← 方向四基础
  → structure_output_node
      └─ 组装 StructuredPlanningCard         ← 方向四
  → render_reply (纯文本，不变)
  → SSE 响应 (文本 + structured_card)
```

## File Changes

### Direction 5: Skill 体系

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `skills/__init__.py` | Package marker |
| Create | `skills/service.py` | SkillService: 加载 skill md 文件，构建 strategy/context/question |
| Create | `skills/bootstrap.py` | 预热加载 |
| Create | `skills/gaokao/mental_models.md` | 5 大心智模型 |
| Create | `skills/gaokao/heuristics.md` | 8 条决策启发式 |
| Create | `skills/gaokao/anti_patterns.md` | 8 条决策反模式 |
| Create | `skills/gaokao/expression_engine.md` | 表达引擎 |
| Create | `skills/gaokao/safety_rules.md` | 安全边界 |
| Modify | `system_prompt.md` | 精简：移除已拆出内容，保留人设+流程骨架 |
| Modify | `server/graph/nodes/quality_nodes.py` | quality_orchestrate_node 调用 SkillService |
| Modify | `server/graph/nodes/reason.py` | reason_node 注入 skill context |
| Modify | `server/services/quality.py` | QualityOrchestrator 增加 skill 层 |

### Direction 4: 结构化输出

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `server/domain/schemas.py` | StructuredPlanningCard Pydantic schema |
| Modify | `server/graph/nodes/structure.py` | 重写：从 reasoning 提取 facts/suggestions/risks/next_actions |
| Modify | `server/graph/nodes/reason.py` | 增加结构化字段提取 |
| Modify | `server/routes/chat.py` | SSE 中发送完整 structured_card |

## Constraints

- system_prompt.md 精简后，skill context 通过 quality_orchestrate_node 注入 system message，等价于原来的内容
- skill 文件加载失败时降级回读 system_prompt.md 全文（向后兼容）
- structure_output_node 失败时返回默认空卡片（不影响纯文本回复）
- 不改任何已有节点的接口签名
