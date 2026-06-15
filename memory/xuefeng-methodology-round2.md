---
name: xuefeng-methodology-round2
description: 2026-06-14 第二轮整合 — zhangxuefeng-skill-merged 金句溯源+叙事知识+硬规则
metadata:
  type: project
---

第二轮 zhangxuefeng-skill-merged 整合完成。与第一轮区分（第一轮吸收方法论：5 模型/8 启发/8 反模式/3 档情绪/9 故障自愈），第二轮吸收：Phase 1 金句溯源（50 句带出处/年份的原版金句入 RAG）、Phase 2 叙事知识（G9 知识组：书籍溯源/行为模式/4 盲点/11 决策/24 年时间线）、Phase 3 数据来源标注硬规则（6 条强制标注格式 + validate_source_attribution 后处理）。

**关键决策**：不做张雪峰 persona 模式，只吸收调研资料和硬规则。金句走 RAG 检索不注入 prompt。

**全量测试**: 538 通过（+48 新增、0 失败）。system_prompt v2.7 → v2.11。归档 `prompts/system/v2.11.md`。

[[gaobao-data-pipeline]]
[[gaobao-二次开发记录]]

**Why**: 上一轮（2026-06-13）已吸收方法论，本轮填补剩下的调研资料和硬规则缺口。全部整合完成。

**How to apply**: 后续任何涉及"张雪峰"用户问题的回答，RAG 自动命中 `zhangxuefeng_originals.json`（金句）或 `G9_zhangxuefeng_methodology_origin.md`（叙事知识）。