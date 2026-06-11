# Session: 安全审计 — 攻击者视角
> 日期：2026-06-12
> 类型：安全审计 / 渗透测试
> 适用场景：项目上线前的安全检查

---

## 提示词

攻击者的角度来找这个项目 /home/dev/projects/xuefeng/xuefeng-advisor 的漏洞，把所有漏洞都列出来。

## 期望输出
- 按严重程度排序（致命/高/中/低）
- 每个漏洞包含：位置、复现方式、影响范围、修复建议
- 覆盖：注入攻击、XSS、敏感信息泄露、权限绕过、数据安全等维度

## 使用的 Skills
- security-review
- security-hardening
- security-best-practices
- security-threat-model
- code-review-and-quality

## 实际产出
- **执行日期**：2026-06-12
- **执行方式**：Agent 自动审计（攻击者视角，全文件白盒扫描）
- **结果**：15 个漏洞（2 致命 / 4 高危 / 5 中危 / 4 低危）
- **致命漏洞**：API Key 泄露（C1）、LLM 回复 XSS（C2）
- **高危**：侧边栏 XSS（H1）、SSRF DNS 重绑定（H2）、会话 ID 可猜测（H3）、密码时序攻击（H4）
- **防御亮点**：SSRF 防御、Prompt Injection 检测（16条正则）、输入长度限制、敏感信息检测等
- **完整报告**：见 `2026-06-12-综合审计报告.md` 第一章
