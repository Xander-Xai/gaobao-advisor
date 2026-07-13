# 开发计划：gaobao-advisor 用户体验升级

> 制定日期：2026-06-12 | 更新日期：2026-06-28
> **当前状态：Phase 0-3 已全部实现，Phase 5-8 执行计划已制定**
> 项目已从 Streamlit 迁移至 FastAPI + Vue 3 架构。

---

## 总体策略

```
Phase 0 (零门槛)  →  Phase 1 (数据可信)  →  Phase 2 (结果好用)  →  Phase 3 (产品闭环)
   去掉技术障碍          让数据说话             可视化+工具           持久化+分享
   ──── ✅ 完成 ───    ──── ✅ 完成 ───     ──── ✅ 完成 ───    ──── ✅ 完成 ───
```

---

## Phase 0：零门槛体验（已完成）

> 目标：用户打开前端，3 秒内能开始对话，不需要任何技术知识

**实现方式**（FastAPI + Vue 3）：
- 后端预配置 API Key（通过 `.env` 环境变量），用户无需输入
- Vue 3 前端直接显示欢迎消息和输入框
- MessageInput 组件支持回车快捷发送
- 对话流式返回（SSE），显示"正在思考..."动画

---

## Phase 1：数据可信（已完成）

> 目标：用户查询任何省份的院校，都有数据可查

**实现方式**：
- 30 省份 × 近 3 年录取数据已导入
- 数据库中 3,016+ 所院校、215+ 个专业、35 万+ 条分数线
- 位次法推荐（YiFenYiDuan 表：11,524+ 条记录）
- 选科约束查询（subject_requirement 过滤）
- 数据来源标注：6 条硬规则（`system_prompt.md` + 后处理校验）
- RAG 知识库：9 个知识组（G1-G9）+ 555+ 条专家金句

---

## Phase 2：结果好用（已完成）

> 目标：推荐结果结构化展示，可浏览、可比较

**实现方式**：
- LangGraph 10+ 节点工作流，按冲/稳/保策略推荐
- StructuredPlanningCard 结构化输出（建议、风险、行动项）
- SSE 事件分阶段推送（slots→emotion→structured→token→quality→done）
- 质量模块 7 项（AI 风险检测、反模式检查、交叉验证、情绪检测等）
- 用户画像持久化（SQLite），7 字段 + 灵魂提问引擎

---

## Phase 3：产品闭环（已完成）

> 目标：会话持久化、结果可分享

**实现方式**：
- Conversation + ConversationMessage 表持久化对话
- 报告生成：一键生成 HTML / SVG 封面志愿分析报告
- HMAC session_token 鉴权（Bearer token）
- 历史对话列表（侧边栏）
- 反馈/金句表（用户可评价回复质量）

---

## Phase 4：上线准备（已完成）

> 目标：前后端联调通过，生产环境安全配置就绪

**实现方式**：
- 前后端联调：ProfileView/ReportView 与后端 Profile/Report API 完整对齐
- 安全中间件：注入检测覆盖 `/api/v1/report/generate` 端点
- CSP 策略：SVG 报告 `img-src 'self' data:`、`font-src 'self' data:`
- API 路由统一：WebSocket `/ws/call` → `/api/v1/ws/call`
- 版本对齐：pyproject.toml 3.1.0 与 server/__init__.py 一致
- 文档同步：API 契约、部署清单、规格文档与代码对齐
- Voice 路由：`token` 查询参数鉴权 + injection 检测
- ReportStorage：report_id 字符校验 + 路径遍历防护
- SSE 错误/降级事件：前端已处理 error 与 degraded 事件类型
- Voice WebSocket 错误消息：前端已处理 WebSocket 错误提示
- 报告标题动态化：根据场景（scene）生成不同标题
- 报告生成 UI 触发：ChatView 中新增一键生成报告入口
- Auth 集中化：鉴权辅助函数统一至 server/auth.py，消除重复代码
- needs_rewrite 条件边：LangGraph 流水线新增 needs_rewrite 条件路由
- 消息与会话 token 持久化：Messages 和 session tokens 写入 localStorage

---

## Phase 5-8：商业闭环（待执行）

详见 [OPC 赋能策略](2026-06-12-opc-empowerment-strategy.md) 和社区运营手册 [community-ops-handbook.md](community-ops-handbook.md)。

---

## 技术架构变更记录

| 时间 | 变更 | 说明 |
|------|------|------|
| 2026-06 前 | Streamlit → FastAPI | ADR-001：分离前后端，支持 SSE 流式 |
| 2026-06 | LangGraph 引入 | 17 节点状态机工作流（含质量判断、反馈路由） |
| 2026-06 | SQLite + WAL | 零依赖嵌入式数据库 |
| 2026-06 | Hybrid RAG | 向量 + 关键词混合检索 |
| 2026-06-14 | 张雪峰方法论整合 | G9 知识组 + 50 条原版金句 + 来源硬规则 |
| 2026-06-28 | WebSocket 路由统一 | `/ws/call` → `/api/v1/ws/call` 统一 API 前缀 |
| 2026-06-28 | 前后端对齐 | SSE 错误处理、Auth 集中化、报告 UI 触发、消息持久化、needs_rewrite 条件边 |

---

## 验收标准（当前版本 v3.0）

| 标准 | 状态 | 衡量方式 |
|------|------|----------|
| 测试通过率 | ✅ 816 passed / 817 collected（1 skipped） | `pytest tests/ -q --timeout=60 --timeout-method=thread` |
| 测试覆盖率 | ✅ 77.78%（≥70%） | `pytest-cov` |
| 关键 API 鉴权 | ✅ Bearer / body token / query token | profile、feedback、highlight、report、voice |
| 安全中间件 | ✅ 注入检测 + SSRF + XSS + CSP | 自动测试 |
| 外部服务降级 | ✅ LLM Judge / Voice 缺配置快速回退 | 自动测试 |
| 限流 | ✅ 20 req/s, burst 40 | Token Bucket |
