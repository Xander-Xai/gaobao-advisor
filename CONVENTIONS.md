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
server/          → FastAPI 后端（routes/graph/services/middleware）
server/graph/    → LangGraph 工作流（state + 15 nodes + graph.py）
db/              → SQLAlchemy ORM 层（models/crud/database） — 13 张表
quality/         → 质量控制模块（emotion/risk/validator/decision/pattern/knowledge/model）
slots/           → 槽位提取（extractor/patterns）
skills/          → Gaokao 方法论技能框架（6 份方法论文档 + service）
config/          → 配置加载（loader + YAML + constants）
tests/           → 所有测试文件（48 个文件，538 个测试）
frontend/        → Vue 3 SPA（Pinia + Tailwind CSS）
prompts/         → 系统提示词版本管理（v1.0-v2.14，14 个模板）
knowledge/       → RAG 知识库（G1-G9 知识组 + 155+ 条语录）
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
- **LLM Mock**：所有涉及 LLM 调用的测试必须 mock
- **E2E**：核心对话流程至少 5 条 E2E 路径
- **运行**：`python -m pytest tests/ -v`

## 事实驱动的工程闭环

中等以上复杂度的 Bug、功能、RAG / Agent 优化和性能改动，不以“代码写完”作为完成标准。默认按以下顺序执行：

```text
事实 / 现象
→ 定义问题
→ 拆成可验证子问题
→ 建立 Baseline
→ 提出可证伪假设
→ 最小实现 / 实验
→ 测试与指标验证
→ 结果验收
→ 复盘并沉淀测试、文档或工具
```

必须区分：

- **事实**：日志、测试、Trace、评测集、数据库记录、真实运行结果；
- **未知**：当前没有证据支持的部分，明确写成 `UNKNOWN / NOT_MEASURED`；
- **假设**：能够被测试或数据推翻的解释；
- **决策**：基于当前证据选择的最小行动。

最低约束：

- `Code Complete != Problem Solved`：实现完成不等于问题解决；
- Bug 修复优先保留最小复现、根因和回归测试；
- RAG 优化至少区分数据/Query/Recall/Rerank/Context/Generation，并使用固定评测样本做同口径比较；
- Agent 优化至少区分 routing/tool/state/loop/fallback，不能用单次 Demo 代替稳定性证据；
- 性能优化先测 Baseline，再优化瓶颈；环境或数据口径不同则不得直接宣称提升百分比；
- CI PASS 只能证明自动化检查通过，不能代替真实用户路径、业务规则和生产运行验证；
- 学习新框架或方法至少留下一个可运行 Demo、实验、Benchmark、测试、决策记录或 SOP，不以“看完资料”为完成。

复杂任务的 Issue / PR 建议至少回答：

```text
Problem / Fact
Baseline
Hypothesis
Smallest Test
Change
Verification
Result
Risk / Rollback
Remaining UNKNOWN
Reusable Asset
```

## 安全红线

- ❌ 禁止硬编码密钥（使用环境变量）
- ❌ 禁止 `v-html` 直接渲染未净化内容（使用 DOMPurify）
- ✅ 所有用户输入经过 `sanitize_input()` 处理
- ✅ 所有 DB 查询使用 SQLAlchemy ORM（参数化）
- ✅ Profile 端点必须验证 session token
- ✅ SSRF 防御覆盖所有 URL 检查点

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
