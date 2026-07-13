# 贡献指南

感谢你考虑为 gaobao-advisor 贡献！

## 行为准则
参与即表示同意遵守 [社区行为准则](CODE_OF_CONDUCT.md)。安全问题请按
[安全政策](SECURITY.md) 私密报告。

## 如何贡献

### 报告 Bug
1. 使用 Bug Report 模板创建 Issue
2. 提供可复现步骤和环境信息
3. 只使用合成数据；日志和截图必须移除密钥、Token、对话和考生资料

### 提交 PR
1. Fork 本仓库
2. 创建特性分支：`git checkout -b feat/your-feature`
3. 遵循代码规范
4. 确保测试通过
5. 提交 PR

## 开发规范

### 代码风格
- Python: 遵循 PEP 8，使用 Black + Ruff 格式化
- 前端: Vue 3 Composition API + Pinia
- 所有模块从 `config` 读取配置，不硬编码

### 测试要求
- 新功能必须有测试覆盖
- 后端测试使用 pytest，前端使用 vitest
- 覆盖率不低于 70%
- 前端必须通过生产构建
- 提交前运行开源仓库审计

### 数据与内容贡献
- 阅读 [数据许可](DATA_LICENSE.md) 和 [数据来源要求](DATA_SOURCES.md)
- PR 必须说明来源、权利人、许可、采集日期、处理步骤和隐私评估
- 可公开访问不等于允许重新分发；权利不明确的资产不会合并
- 禁止提交生产数据库、备份、报告、日志、会话或真实用户资料

### 提交信息格式
```
<type>: <简要描述>
```

类型: feat / fix / refactor / docs / test / chore

## 项目架构速览
```
config/          → 配置系统（环境变量 + YAML）
server/          → FastAPI 后端
  routes/        → API 路由
  graph/         → LangGraph 工作流
  services/      → 业务服务层
  report/        → 报告生成
  auth.py        → Centralized auth helpers
frontend/        → Vue 3 前端
  src/composables/ → Vue composables (voice, etc.)
  src/views/       → Page views (ChatView, ReportView, ProfileView, AdminView)
db/              → 数据库层（SQLite）
quality/         → 质量评估模块
```

## 本地开发
```bash
make install     # 安装依赖
make run-api     # 启动后端
ruff check .
ruff format --check .
pytest tests/ -q --timeout=60 --timeout-method=thread
cd frontend && npm ci && npm test -- --run && npm run build && npm audit --audit-level=moderate
cd .. && bash scripts/audit_open_source.sh
```

完整历史秘密扫描是发布门禁：

```bash
bash scripts/audit_open_source.sh --history --require-gitleaks
```
