# Session: 质量安全验收 — 全面审计
> 日期：2026-06-12
> 类型：综合验收 / 多维度审计
> 适用场景：项目上线前的最终验收

---

## 提示词

质量安全专家和验收员的角度来看这个项目 /home/dev/projects/xuefeng/xuefeng-advisor，可以调用全局技能库中的能用上的所有 skills，找出这个项目的不足，然后把它告诉我。

## 期望输出
- 覆盖维度：安全性、代码质量、性能、可维护性、文档完整性、测试覆盖、部署可靠性
- 每个维度独立评分（1-10）
- 列出不达标项 + 修复建议
- 最终给出「是否可以上线」的结论

## 使用的 Skills（全部）
- security-review / security-hardening / security-best-practices / security-threat-model
- code-review-and-quality / code-simplification
- best-practices / performance / performance-optimization
- debugging-and-error-recovery
- documentation-and-adrs
- web-quality-audit
- webapp-testing
- verification-before-completion

## 实际产出
- **执行日期**：2026-06-12
- **执行方式**：Agent 逐文件全面审计（7 维度）
- **结果**：总体评分 **6.3/10**，有条件可上线

| 维度 | 评分 | 状态 |
|------|------|------|
| 安全性 | 7/10 | ✅ 达标（API Key 需轮换） |
| 代码质量 | 7/10 | ✅ 达标 |
| 性能 | 6/10 | ⚠️ 刚达标 |
| 可维护性 | 6/10 | ⚠️ 刚达标 |
| 提示词质量 | 8/10 | ✅ 良好 |
| 测试覆盖 | 6/10 | ⚠️ 刚达标 |
| 部署可靠性 | 4/10 | ❌ 不达标 |

- **上线条件**：轮换 API Key + 清除 Git 历史 + 修复限流竞态 + XSS 清理
- **完整报告**：见 `2026-06-12-综合审计报告.md` 第四章
