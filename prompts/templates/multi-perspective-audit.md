# 多角色审计模板 — 可复用模式

## 模式：多维度项目审计

### 核心公式
```
以 {角色A} 的角度来审视这个项目 {项目路径}，找出 {关注维度} 的不足。

期望输出：
- 按严重程度排序
- 每个问题包含：位置、影响、修复建议
- 覆盖：{维度1}、{维度2}、{维度3}...

使用的 Skills：{列出相关 skills}
```

### gaobao 实例（5 角色审计）

| 角色 | 关注维度 | 核心 Skills |
|------|---------|-------------|
| 攻击者 | 安全漏洞、注入、泄露 | security-review, security-threat-model |
| 调研员 | 竞品、开源方案、可借鉴点 | deep-research, web-access |
| 规划师 | 加固方向、优先级、任务拆分 | brainstorming, planning-and-task-breakdown |
| 用户 | 体验痛点、困惑、流失风险 | webapp-testing, best-practices |
| 验收员 | 全维度评分、上线结论 | code-review, verification-before-completion |

### 关键设计点
1. **角色定义明确**：不是泛泛的「审查」，而是具体到「焦虑型家长」这种角色
2. **输出格式统一**：所有角色都输出「问题 + 严重程度 + 修复建议」
3. **Skills 匹配角色**：每个角色配不同的 skills，不是一股脑全用
4. **有前置依赖**：调研 → 规划 → 实现 → 验收，形成闭环

### 扩展到其他项目
```
# 替换项目路径和角色即可
攻击者角度来审计 /path/to/project 的安全漏洞
产品经理角度来审视 /path/to/project 的用户体验
运维工程师角度来检查 /path/to/project 的部署可靠性
```
