# Gaobao Advisor — 工程约束 (CONVENTIONS)

> 本文件是项目的工程规范。所有贡献者（包括 AI 工具）必须遵守。

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| Backend | Python / FastAPI / LangGraph | 3.10+ / 0.100+ / latest |
| ORM | SQLAlchemy | 2.x |
| Database | SQLite (WAL mode) | — |
| Frontend | Vue 3 / Vite / Tailwind CSS | 3.5+ / 8+ / 4+ |
| Testing | pytest / ruff | 7+ / 0.4+ |
| CI | GitHub Actions | — |
| Deploy | Docker / Nginx | — |

## 目录结构

```
server/          → FastAPI 后端（routes/graph/services/middleware，auth helpers centralized in server/auth.py）
server/graph/    → LangGraph 工作流（state + 17 nodes + graph.py）
db/              → SQLAlchemy ORM 层（models/crud/database） — 13 张表
quality/         → 质量控制模块（emotion/risk/validator/decision/pattern/knowledge/model）
slots/           → 槽位提取（extractor/patterns）
skills/          → Gaokao 方法论技能框架（6 份方法论文档 + service）
config/          → 配置加载（loader + YAML + constants）
tests/           → 所有测试文件（817 个已收集测试；当前 816 passed / 1 skipped）
frontend/        → Vue 3 SPA（Pinia + Tailwind CSS, composables/ + views/）
prompts/         → 系统提示词版本管理（v1.0-v2.14+，15 个模板）
knowledge/       → RAG 知识库（G1-G9 知识组 + 555+ 条语录）
scripts/         → 数据导入/工具脚本
legacy/          → 遗留代码（已弃用，安全迁移后保留）
```

## 编码标准

- **文件大小**：≤ 800 行（超限需拆分）
- **函数大小**：≤ 50 行
- **嵌套层级**：≤ 4 层（使用 early return）
- **类型标注**：所有函数签名必须有类型标注
- **格式化**：`ruff format .`（line-length=120）
- **Lint**：`ruff check .`（0 errors）

## 测试要求

- **覆盖率**：≥ 70%（`--cov-fail-under=70`）
- **测试模式**：AAA（Arrange-Act-Assert）
- **LLM Mock**：所有涉及 LLM/Voice/外部网络调用的测试必须 mock 或验证快速降级
- **E2E**：核心对话流程至少 5 条 E2E 路径
- **运行**：`python -m pytest tests/ -v`

## 安全红线

- ❌ 禁止硬编码密钥（使用环境变量）
- ❌ 禁止 `v-html` 直接渲染未净化内容（使用 DOMPurify）
- ✅ 所有用户输入经过 `sanitize_input()` 处理
- ✅ 所有 DB 查询使用 SQLAlchemy ORM（参数化）
- ✅ Profile 端点必须验证 session token
- ✅ Report 端点必须校验 session_id 与 token 的归属关系，禁止仅凭 report_id 读取
- ✅ SSRF 防御覆盖所有 URL 检查点
- ✅ Auth helpers centralized in server/auth.py（require_bearer_auth for Bearer token, require_token_auth for direct token）

## Git 规范

- Commit 格式：`<type>: <description>`
- 类型：feat / fix / refactor / docs / test / chore / perf / ci
- 分支：main（生产）、feature/*（开发）

## 禁止行为

- ❌ 不写 `except Exception: pass`（必须 logging）
- ❌ 不用 `global` 声明非单例变量
- ❌ 不在测试文件外放测试代码
- ❌ 不提交 `.env` / `secrets.toml`
- ❌ 不跳过 CI 流水线
