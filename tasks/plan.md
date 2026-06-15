# 审计修复计划（2026-06-15）

> 基于 `audit_report_20260615.md` 多角色审计结果，按优先级依次修复。

## 优先级排序

| 优先级 | 编号 | 问题 | 严重程度 | 依赖 |
|--------|------|------|---------|------|
| P0 | C-1 | 新旧架构并存（精神分裂） | 🔴 致命 | — |
| P0 | U-1 | README 与代码脱节 | 🔴 致命 | C-1 |
| P1 | C-2 | 有状态的 API 设计 (api_server.py) | 🟠 高危 | C-1 |
| P1 | S-1 | 依赖版本范围过宽 | 🟠 高危 | — |
| P2 | F-1 | 多容器并发写 SQLite | 🟠 高危 | C-1 |
| P3 | A-1 | Docker 容器以 root 运行 | 🟡 中危 | — |

---

## Phase 1: 架构清理 — 消除"精神分裂"

### 1.1 删除废弃入口 `api_server.py`

- **目标**：移除旧的 `api_server.py`（其功能已被 `server/main.py` 替代）
- **操作**：删除 `api_server.py` 文件
- **验证**：确认 `server/main.py` 已提供相同的 API 功能（/api/chat, /api/health 等）
- **验收标准**：`api_server.py` 不复存在；`grep -r "api_server"` 无残留引用（除 git 历史外）

### 1.2 重定向 `app.py` 为纯遗留入口

- **目标**：明确 `app.py` 的 legacy 地位，防止新用户误用
- **操作**：在 `app.py` 文件头部注释中强化遗留标记，运行时打印重定向提示
- **验收标准**：运行 `app.py` 时打印 "⚠️ LEGACY: Use `uvicorn server.main:app` instead" 后退出

### 1.3 更新 Dockerfile 为 FastAPI 模式

- **目标**：`docker build` 默认启动 FastAPI（`server.main:app`）而非 Streamlit
- **操作**：
  - 修改 CMD 从 `streamlit run app.py` → `uvicorn server.main:app --host 0.0.0.0 --port 8000`
  - 更新 HEALTHCHECK 指向 FastAPI 健康端点 `/api/v1/health`
  - 更新 EXPOSE 从 8501 → 8000
- **验收标准**：`docker build . && docker run` 启动 FastAPI 服务，`curl localhost:8000/api/v1/health` 返回 200

### 1.4 清理 `requirements-api.txt` 并合并到主依赖

- **目标**：`api_server.py` 已删除，对应的依赖文件应合并或清理
- **操作**：`requirements-api.txt` 内容已完全被 `server/` 模块覆盖，可删除；其依赖已包含在 `requirements.txt` 中（fastapi, uvicorn）
- **验收标准**：`requirements-api.txt` 删除，`grep -rn "requirements-api" .` 无引用

---

## Phase 2: 文档修复 — README 重写

### 2.1 重写 README 快速开始

- **目标**：README "快速开始" 反映当前主力架构（FastAPI + Frontend）
- **操作**：
  1. 顶部 Quick Start 改为 `docker-compose up -d`（一键拉起 FastAPI + Frontend + Nginx）
  2. Streamlit/CLI 模式移入附录作为替代方案
  3. API 接口文档指向新的 `server/main.py` 路由而非 `api_server.py`
  4. 更新 Docker 部署说明反映新的默认入口
- **验收标准**：按新 README 操作可正确启动 FastAPI 服务；无 `api_server.py` 引用

### 2.2 更新项目结构树

- **目标**：项目结构图移除已删除的 `api_server.py`
- **操作**：README 中项目结构树移除 `api_server.py` 行
- **验收标准**：README 项目结构图与实际代码匹配

---

## Phase 3: 依赖锁定

### 3.1 生成锁定的 requirements.lock

- **目标**：锁定所有依赖版本，保证构建可重复性
- **操作**：
  1. 使用 `uv pip compile requirements.txt -o requirements.lock` 或 `pip-tools`
  2. 使用 `uv pip compile requirements-dev.txt -o requirements-dev.lock`（可选）
  3. 确保哈希验证可用
- **验收标准**：`requirements.lock` 生成，所有依赖有精确版本号

### 3.2 更新 Dockerfile 使用锁定文件

- **目标**：Docker 构建使用锁定依赖
- **操作**：将 `COPY requirements.txt .` + `pip install -r requirements.txt` 改为 `COPY requirements.lock .` + `pip install -r requirements.lock`
- **验收标准**：`docker build .` 成功，安装的版本与 lock 文件一致

---

## Phase 4: Docker 安全加固

### 4.1 Dockerfile 添加非 root 用户

- **目标**：容器进程以非 root 用户运行
- **操作**：在 `Dockerfile` 尾部添加 `RUN adduser -D appuser && chown -R appuser /app` + `USER appuser`
- **验收标准**：`docker run` 后 `whoami` 返回 `appuser`；`1000` 端口无需 root 权限

---

## Phase 5: 最终验证

### 5.1 全量测试验证

- **目标**：所有修复不改坏已有功能
- **操作**：运行 `pytest tests/` 确认全部通过
- **验收标准**：333 个测试全部通过

### 5.2 最终检查清单

- [ ] `api_server.py` 已删除
- [ ] `app.py` 有清晰 legacy 标记
- [ ] Dockerfile CMD 指向 FastAPI
- [ ] README 与实际架构一致
- [ ] `requirements.lock` 已生成，Dockerfile 使用它
- [ ] Dockerfile 使用非 root 用户
- [ ] 333 个测试全部通过

---

## 不被采纳说明

以下审计发现项在本次修复中**不处理**：

| 编号 | 原因 |
|------|------|
| C-2 | `api_server.py` 直接删除，不单独修复其有状态设计 |
| F-1 | Streamlit 已标记为 `profiles: [legacy]` 不默认启动；SQLite 在单容器单进程场景下正常工作。如需多实例部署，建议后续迁移到 PostgreSQL |