# Gaobao Advisor — 项目验收报告

> **验收日期**：2026-06-14
> **验收方法**：基于《网站开发实践》文档体系的多角色并行审计（05-多角色并行审计模板）
> **项目版本**：server v3.0.0 / pyproject v1.0.0
> **基线测试**：621 tests passed (51.67s)

---

## Phase 0 — 项目画像

| 维度 | 详情 |
|------|------|
| 项目类型 | Web App（AI 对话式顾问） |
| 技术栈 | FastAPI + LangGraph(14节点) + SQLAlchemy/SQLite + Vue 3 + Vite 8 + Docker |
| 用户群 | C端高考考生/家长，潜在 B端学校/机构 |
| 风险暴露 | **高** — 未成年人教育决策数据 + LLM 交互 + 无认证 |
| 成熟度 | Beta |
| 代码规模 | ~13K 行 Python + ~6.6K 行测试 + Vue 3 前端 |
| 前端双端 | H5（696行 vanilla JS）+ Vue SPA（Pinia + Tailwind CSS 4） |

---

## 审计概况

| 角色 | 审计维度 | P0 | P1 | P2 | P3 | 合计 |
|------|----------|:---:|:---:|:---:|:---:|:----:|
| 🔴 Attacker (A) | 安全漏洞、注入、认证绕过 | 3 | 4 | 6 | 4 | **17** |
| 🔵 Code Reviewer (C) | 代码质量、架构、技术债务 | 2 | 4 | 6 | 6 | **18** |
| 🟢 User/Consumer (U) | 用户体验、可用性、可访问性 | 2 | 5 | 11 | 5 | **23** |
| 🟡 Performance (P) | 性能瓶颈、资源管理、扩展性 | 4 | 5 | 9 | 4 | **22** |
| 🟣 Test Engineer (T) | 测试策略、覆盖率、测试质量 | 3 | 5 | 6 | 4 | **18** |
| **合计** | | **14** | **23** | **38** | **23** | **98** |

---

## 跨角色交叉分析矩阵

> 规则：2 角色命中 = 优先级 +1；3+ 角色命中 = 必须修复 / 阻塞上线

### 🔴 必须修复（跨 3+ 角色命中）

| # | 问题 | 命中角色 | 建议优先级 |
|---|------|----------|-----------|
| **X-1** | **完全无认证/授权** — 所有 API 端点开放，session_id 可枚举，任何人可读写他人 profile | A(P0) + U(P1) + C(P1) | **P0 阻塞** |
| **X-2** | **XSS via v-html** — AI 输出通过 `v-html` 渲染，未做 HTML 净化 | A(P1) + U(P0) + C(相关) | **P0 阻塞** |
| **X-3** | **速率限制器内存泄漏** — `_buckets` 无限增长，无驱逐机制 | A(P2) + C(P2) + P(P0) | **P1 高优** |
| **X-4** | **SSRF/注入模式三重重复** — security.py / agent.py / utils.py 各自维护独立副本 | C(P1) + A(P1) | **P1 高优** |
| **X-5** | **无前端测试** — Vue SPA 零 Vitest/Playwright 测试 | T(P2) + U(相关) | **P1 高优** |
| **X-6** | **双重 LLM 调用** — 每个请求调用两次 LLM API，延迟和成本翻倍 | P(P0) + C(相关) | **P0 阻塞** |

---

## 22 项上线前自查表（来自 00-启动清单与工具箱）

### P0 — 阻塞项（必须修复后才能上线）

| # | 检查项 | 状态 | 发现 |
|---|--------|:----:|------|
| 1 | CONVENTIONS.md 工程约束文件 | ❌ | 项目中不存在该文件，无统一工程约束 |
| 2 | API 契约文档（OpenAPI/Swagger） | ❌ | 无 API 文档，FastAPI 自带的 /docs 未验证 |
| 3 | Spec/PRD 需求规格文档 | ❌ | 无 SPEC.md 或 PRD.md |
| 4 | 安全基线 — 认证授权 | ❌ | **所有端点无认证**，session_id 可枚举 |
| 5 | 安全基线 — XSS 防护 | ❌ | `v-html` 未净化，stored XSS 向量存在 |
| 6 | 安全基线 — 安全响应头 | ❌ | Nginx 缺少 CSP/HSTS/X-Frame-Options |
| 7 | HTTPS 强制 | ❌ | 仅监听 80 端口，无 TLS 配置 |
| 8 | 测试覆盖率 ≥ 80% | ❌ | **未配置覆盖率测量**，pytest-cov 已安装但未启用 |

### P1 — 高优项（上线前应修复）

| # | 检查项 | 状态 | 发现 |
|---|--------|:----:|------|
| 9 | CI/CD 流水线 | ✅ | GitHub Actions 配置完整（lint + test matrix） |
| 10 | Docker 部署就绪 | ✅ | docker-compose 多服务编排 + healthcheck |
| 11 | 代码质量（ruff lint） | ⚠️ | 156 个 lint 错误（78 可自动修复） |
| 12 | 代码格式化 | ⚠️ | 128 个文件需要重新格式化 |
| 13 | 前端零测试 | ❌ | Vue SPA 无 Vitest/Playwright |
| 14 | 遗留代码引用 | ⚠️ | agent.py(1816行)/app.py(2151行) 仍被测试引用 |
| 15 | N+1 查询 | ❌ | 两处循环内逐条查 Major，225K 行全表扫描 |
| 16 | SQLite WAL 模式 | ❌ | 未开启，并发下读写锁竞争 |
| 17 | 数据库备份 | ✅ | 7天轮转 gzip 备份脚本就绪 |

### P2 — 建议项（上线后迭代）

| # | 检查项 | 状态 | 发现 |
|---|--------|:----:|------|
| 18 | Feature Flags | ⚠️ | .env 中定义但代码未引用（死配置） |
| 19 | 监控告警（Sentry等） | ❌ | 无 Sentry/uptime 监控 |
| 20 | 404/错误页 | ❌ | 无 catch-all 路由，404 显示白屏 |
| 21 | 响应式设计 | ⚠️ | Vue SPA 桌面端侧边栏无响应式断点 |
| 22 | SEO/Meta 标签 | ❌ | title 为 "frontend"，lang="en"（应为 zh-CN） |

---

## 各维度评分

| 维度 | 评分 | 说明 |
|------|:----:|------|
| 🔒 安全性 | **3/10** | 无认证、XSS、无安全头、无 HTTPS |
| 🏗️ 架构 | **7/10** | Graph 管道清晰，但遗留代码和重复逻辑拖分 |
| 💻 代码质量 | **6/10** | 类型标注一致，但 lint 报错多、静默异常、全局变量 |
| 🎨 用户体验 | **5/10** | H5 版良好，Vue SPA 流式输出缺失、无反馈机制 |
| ⚡ 性能 | **5/10** | 双重 LLM 调用、N+1 查询、无缓存 |
| 🧪 测试 | **6/10** | 621 测试通过，但覆盖率未测量、前端零测试、图节点覆盖差 |
| 🚀 部署运维 | **7/10** | Docker + CI + 备份就绪，但无监控告警 |
| 📄 文档 | **4/10** | README 详尽，但无 CONVENTIONS/SPEC/API 文档 |

**综合评分：5.5/10**

---

## 验收结论

### 🚦 建议：**有条件通过（需完成 P0 阻塞项后方可上线）**

项目在**功能完整度**和**核心架构**上表现良好：
- ✅ 14 节点 LangGraph 管道设计清晰
- ✅ 621 测试全部通过
- ✅ 安全中间件全面（注入检测 + SSRF 防御 + 限流）
- ✅ 多 LLM Provider 支持（6家预设）
- ✅ 知识库丰富（3016院校 + 70K+ 分数记录 + 105+ 专家金句）
- ✅ Docker 多服务编排 + CI 流水线

但存在 **6 个跨角色交叉命中问题** 和 **8 个 P0 自查项未通过**，主要集中在：
1. **零认证** — 任何人均可访问所有端点和用户数据
2. **XSS 漏洞** — AI 输出未净化直接渲染 HTML
3. **双重 LLM 调用** — 每个请求成本和延迟翻倍
4. **工程规范缺失** — 无 CONVENTIONS/SPEC/API 文档/覆盖率测量

---

## 修复路线图

### 🔴 Phase A — 阻塞项修复（预计 2-3 天）

| 优先级 | 任务 | 工作量 | 验收标准 |
|--------|------|--------|----------|
| A1 | 添加 Session 认证（HMAC token） | 4h | 所有 profile/chat 端点要求 token |
| A2 | 消除双重 LLM 调用 | 3h | 每个请求仅调用一次 LLM API |
| A3 | 前端 v-html → DOMPurify 净化 | 2h | XSS payload 无法在浏览器执行 |
| A4 | 添加安全响应头（Nginx） | 1h | CSP/HSTS/X-Frame-Options/CSP 全部配置 |
| A5 | 配置 pytest-cov + CI 覆盖率门禁 | 1h | 覆盖率 ≥ 70% 在 CI 中强制执行 |
| A6 | 创建 CONVENTIONS.md | 1h | 工程约束文件就位 |

### 🟡 Phase B — 高优项修复（预计 3-5 天）

| 优先级 | 任务 | 工作量 | 验收标准 |
|--------|------|--------|----------|
| B1 | 修复 N+1 查询（joinedload） | 2h | admission/enrollment 查询仅 1 次 DB 调用 |
| B2 | 速率限制器 TTL 驱逐 | 2h | 空闲 IP 条目 1 小时后自动清除 |
| B3 | 合并重复安全逻辑 | 2h | SSRF/injection 检测仅在一处维护 |
| B4 | SQLite WAL 模式 | 1h | `PRAGMA journal_mode=WAL` 在启动时执行 |
| B5 | 前端 Vitest 基础测试 | 4h | 核心组件有单元测试 |
| B6 | 修复 silent exception swallowing | 1h | 4 处 `except Exception: pass` 添加日志 |
| B7 | ruff check/format 全量修复 | 1h | 0 lint 错误，0 格式化问题 |
| B8 | 移动错位测试文件 | 0.5h | 328 行测试被 pytest 发现并运行 |

### 🟢 Phase C — 上线后迭代

| 任务 | 说明 |
|------|------|
| H5 与 Vue SPA 合并 | 统一前端，消除维护双倍工作 |
| 监控告警接入（Sentry） | 生产环境可观测性 |
| HTTPS + Let's Encrypt | 全站加密 |
| LLM 响应缓存 | 重复查询减少 API 调用 |
| WebSocket 限流 | 语音端点防滥用 |
| 前端流式输出 | Vue SPA 改用 SSE 流式渲染 |
| CONVENTIONS/SPEC 补全 | 工程规范文档化 |

---

## 防御亮点（做得好的地方）

| # | 亮点 | 来源 |
|---|------|------|
| 1 | 14 节点 Graph 管道架构清晰，每个节点职责单一 | Code Review |
| 2 | 17+7 中英文 Prompt Injection 检测模式 | Attacker |
| 3 | SQLAlchemy ORM 参数化查询 + LIKE 通配符转义 | Attacker |
| 4 | DB 文件权限 0600 锁定 + URL 白名单 | Attacker |
| 5 | 621 测试全通过，安全测试 35+ 参数化用例 | Test |
| 6 | AAA 模式一致，LLM Mock 模式正确 | Test |
| 7 | H5 版安全区域适配、流式输出、进度条 | User |
| 8 | 备份脚本 7天轮转 + Docker healthcheck | Performance |
| 9 | 可观测性 Trace 内建于每个 Graph 节点 | Code Review |
| 10 | 多 LLM Provider 支持（6家）+ 优雅降级 | Performance |
| 11 | 情绪检测含危机热线，5阶段危机处理 | Code Review |
| 12 | Source Attribution 后处理防幻觉 | Attacker |
