# 审计验收回应 — 2026-06-15

> 对 `audit_report_20260615.md` 和 `audit_report_20260615_v2.md` 的逐条核实与应答。
> 基于代码库实际状态，区分"正确需要行动"、"正确但可商榷"、"不准确"三者，并按真实优先序重排。

---

## 前置：核实方法

所有项目均通过读文件、运行命令（ruff / npm audit / find / grep）进行了实体验证，非凭记忆应答。详见内联结果。

---

## 一、核实结果总表

| # | 审计项 | 审计定级 | 核实结论 | 我方定级 | 现状 |
|---|--------|---------|---------|---------|------|
| 1 | 前端 CVE + 无 lockfile | P0 | 审计自认 ✅ 已修复 | P0→已清除 | `npm audit` 0 vulns |
| 2 | ruff 22 errors | P0 | 23 errors，但 9 个在死代码，14 个在脚本 | **P2** | 无法到达的代码 + 脚本格式 |
| 3 | LLM 无超时 | P0 | ✅ 正确 | **P0** | 未修复 |
| 4 | SSE 脆弱性 | P0 | ✅ 正确 | **P0** | 未修复 |
| 5 | app.py 残留 | P1 | ✅ 正确，但 `sys.exit(1)` 使其运行时无害 | P2 | 文件仍在 |
| 6 | docker-compose streamlit | P1 | ✅ 正确，但 `profiles: ["legacy"]` 已隔离 | P3 | 已缓解 |
| 7 | SPEC.md / ADR 缺失 | P1 | ✅ 正确 | P2 | 完全缺失 |
| 8 | Sentry 缺失 | P1 | ✅ 正确 | P2 | 完全缺失 |
| 9 | voice.py 0% 覆盖 | P1 | ✅ 正确，但文件仅 20 行常量 | P2 | 等待业务逻辑完成 |
| 10 | CSP unsafe-inline | P1 | ✅ 正确 | P1 | 未修复 |
| 11 | auth.py 跨进程失配 | P1 | ✅ 正确，且比报告更严重（.env.example 也缺失） | **P1** | 未修复 |
| 12 | requirements.txt 宽泛 | P1 | 审计自认 ✅ 已修复（requirements.lock 已生成） | P1→已清除 | 已修复 |

---

## 二、逐项详细应答

### P0-1: 前端 CVE — 审计自认已修复

**审计原文：**「已修复（npm audit 通过），但需确认是否所有 CVE 都已清除」
**核实：** `npm audit --audit-level=high` → `found 0 vulnerabilities`。`package-lock.json` 存在。

**评价：** 审计在报告中标注了 ✅ 已修复，但结论表仍将其列为"未按质量完成"，前后矛盾。此条目应标记为"P0→已清除"，不应视为残留。

---

### P0-2: ruff 22 errors — 定级过重

**审计原文：**「app.py 仍有 9 个 E402 errors」「scripts/ 有 13 个 errors」

**核实数据：**

```
$ ruff check . --exclude scripts --exclude app.py  # 核心代码
→ 0 errors  ✔️

$ ruff check app.py
→ 9 errors, 全部 E402 (import not at top of file)
  原因：app.py 第 17 行 sys.exit(1) 之后的导入，代码静态不可达

$ ruff check scripts/
→ 14 errors (E401×2, I001×3, E701×8, W292×1)
  其中 6 个可自动修复，其余为 if/else 单行风格
```

**核心代码（server/ + db/ + tests/）ruff 检查通过，0 errors。**

**评价：** 9 个 E402 在 `sys.exit(1)` 之后——这是**死亡代码**中的虚假阳性。14 个脚本错误是**一次性诊断脚本**的格式问题。将此归类为 **P0（阻断性）** 意味着任何遗留文件都会阻塞发布，这是不可接受的。合理定级为 **P2（整洁性）**，与 `app.py` 删除绑定修复。

**修复方案：**
- 删除 `app.py` → 消除 9 个 E402
- `ruff check --fix scripts/` → 消除 6 个可自动修复错误
- 手动修复其余 8 个 E701（多语句单行拆分为 if/elif/else 块）
- 估计：30 分钟

---

### P0-3: LLM 无超时 — 正确，必须修复

**审计原文：**「OpenAI 客户端调用缺少 timeout 参数」

**核实：** `llm_node.py:64-67`
```python
_client = OpenAI(
    api_key=api_key,
    base_url=cfg["base_url"],
)
# ← timeout 缺失
```
OpenAI Python SDK 默认 `timeout=600.0s`（10 分钟），但这是隐式默认，不是显式设置。当 LLM API 挂起或 DNS 解析缓慢时，此请求会阻塞线程池线程长达 10 分钟。

此外，`_sync_retry` 函数（第 83 行）只重试 HTTP 状态码 `{429, 500, 502, 503}`，不处理连接超时或 DNS 故障。

**修复方案：**
```python
_client = OpenAI(
    api_key=api_key,
    base_url=cfg["base_url"],
    timeout=cfg.get("timeout", 120.0),  # 显式 2 分钟超时
    max_retries=2,
)
```
- 从配置读取 `timeout`，以支持不同 LLM 提供者
- 同时更新 `config/llm_providers.yaml` 模式
- 估计：5 分钟

---

### P0-4: SSE 脆弱性 — 正确，必须修复

**审计原文：**「Phase 1（`graph.invoke`）失败时无 try-except 保护」

**核实：** `chat.py:55-56`
```python
# Phase 1: Run graph (synchronous, offloaded to thread)
result = await asyncio.to_thread(graph.invoke, initial_state)
```
这行代码在 `_sse_generator` 中，**没有** try/except 包裹。如果 `graph.invoke` 抛出异常（例如 LLM 重试耗尽、数据库连接失败、RAG 超时），生成器会传播异常到 FastAPI 的 `StreamingResponse`。客户端会收到 200 OK + 被截断的 SSE 流，而不是格式良好的错误事件。

Phase 2（`llm_node_stream`，第 81 行）自带异常处理并返回 fallback 回复，但 Phase 1 没有。

**修复方案：**
```python
try:
    result = await asyncio.to_thread(graph.invoke, initial_state)
except Exception as e:
    logger.exception("Graph invocation failed for session %s", session_id)
    yield f"data: {json.dumps({'type': 'error', 'code': 'GRAPH_FAILED', 'message': '服务暂时不可用，请稍后重试'})}\n\n"
    return
```
- 使用 `return`（而非 `raise`）来优雅终止生成器
- 记录完整异常栈以便调试
- 估计：10 分钟

---

### P1-5: app.py 残留 — 正确但已缓解

**审计原文：**「文件仍在（95KB），虽加了 sys.exit(1)」

**核实：** `app.py` 存在，第 1-17 行打印弃用警告并调用 `sys.exit(1)`。第 19 行之后的代码（90KB 的 Streamlit 入口）静态不可达。

**评价：** 运行时完全无害。但存在两个实际问题：
1. 造成 ruff 9 个 E402 虚假阳性
2. 给新开发者造成认知负担

**修复方案：**
- **推荐：** 直接删除 `app.py`（git 历史可回溯）
- **备选：** 移至 `legacy/app.py` 并在 `.gitignore` 中排除 ruff 扫描
- 与 P0-2（ruff 清理）绑定
- 估计：2 分钟

---

### P1-6: docker-compose streamlit 挂载 — 正确但已缓解

**审计原文：**「streamlit 服务仍在 `profiles: ["legacy"]` 下，且挂载了 `./data`」

**核实：** `docker-compose.yml:39-51`
```yaml
streamlit:
  profiles: ["legacy"]       # ← 仅显式 --profile legacy 启动
  volumes:
    - ./data:/app/data
```

`profiles: ["legacy"]` 确保 `docker compose up` **不会**启动此服务。它只会在 `docker compose --profile legacy up streamlit` 时运行。

**评价：** 风险完全缓解。保留 `./data` 挂载对 legacy 模式是必要的（streamlit 也需要读数据库）。不存在"误启动风险"。

**修复方案：**
- 添加内联注释说明此挂载仅用于 legacy 模式
- 或者：在 SQLite 迁移完成（WAL 模式就位）后彻底删除此服务
- 估计：1 分钟注释 | P3 计划删除

---

### P1-7: SPEC.md / ADR 缺失 — 正确，需要弥补

**审计原文：**「项目中无 SPEC.md，也无 docs/adr/ 目录」

**核实：** 完全缺失。项目从 EduAgent fork 后经过大量重构（FastAPI 迁移、LangGraph 流程、RAG 架构），但无架构决策记录。

**评价：** 这是真实的文档债。但修复需要 1-2 小时的专注思考，不能仓促完成。

**修复方案：**
1. 创建 `docs/adr/` 目录
2. 为关键架构决策编写 ADR：
   - ADR-001: 从 Streamlit 迁移到 FastAPI
   - ADR-002: LangGraph 流程架构
   - ADR-003: SQLite + WAL 模式 + joinedload
   - ADR-004: 混合 RAG（向量 + 关键词）
   - ADR-005: Voice/TTS 集成
3. 编写 `SPEC.md` 项目规格概览
- 估计：2 小时

---

### P1-8: Sentry 缺失 — 正确，但 P1 定级取决于项目阶段

**审计原文：**「无 Sentry、无 timeout、无告警」

**核实：** `grep -r "sentry" .` → 零结果。

**评价：** Sentry 集成是 30 分钟的工作（`pip install sentry-sdk` + 几行初始化代码）。真正的问题是「为什么还没做」，答案是该项目处于活跃开发阶段，尚未投入生产。我同意在 1 周路线图中加入 Sentry，但如果项目尚未上线，说它是 P1 可能过高。

**修复方案：**
```python
# server/monitoring.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def init_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            environment=os.getenv("APP_ENV", "development"),
        )
```
在 `server/main.py` 启动时调用 `init_sentry()`。
- 估计：30 分钟

---

### P1-9: voice.py 0% 测试覆盖 — 正确但范围需要上下文化

**审计原文：**「server/services/voice.py 覆盖率 0%」

**核实：** `tests/` 下没有 `test_voice*.py` 文件。但 `voice.py` 内容如下：
- 14 行的 `VOICE_RENDER_SYSTEM_PROMPT` 常量
- 6 行的 `SCENE_VOICE_STYLES` 字典
- 实际编排逻辑（TTS 调用、ASR）**尚未完全实现**

**评价：** 为一个 20 行的"提示常量 + 字典"模块编写测试意义有限。建议在 voice 服务的实际业务逻辑完成后，再为**视图层**编写集成测试。

**修复方案：**
- 等待 voice 服务的 TTS/ASR 编排逻辑完成
- 在 `tests/server/services/` 下创建 `test_voice.py`
- 使用 pytest + httpx 测试 ASR → Graph → TTS 流程
- 估计：1 小时（在逻辑完成后）

---

### P1-10: CSP unsafe-inline — 正确，需要修复

**审计原文：**「nginx.conf:20 仍有 unsafe-inline」

**核实：** `nginx.conf:20`
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:;" always;
```

`script-src` 上的 `'unsafe-inline'` 是最关键的风险点——它允许任意内联脚本执行，即使是 XSS 注入的。

**修复方案：**
- 立即修复（周一）：从 `script-src` 删除 `'unsafe-inline'`
  - React CRA 构建生成脚本哈希，不需要 unsafe-inline 也能工作
- 长期修复（本月）：实现 nonce 生成管道
  ```nginx
  # 构建后生成 nonce 或使用 Strict CSP
  add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:;" always;
  ```
- 估计：15 分钟（立即修复）

---

### P1-11: auth.py 跨进程失配 — 正确，且比报告更严重

**审计原文：**「未设置会导致多 worker 失配」「.env.example 中该值被注释掉」

**核实：**
```python
# auth.py:15
_SECRET = os.getenv("SESSION_SECRET", "")  # 空字符串 = 未设置

# auth.py:21-23
if not _SECRET:
    _SECRET = secrets.token_hex(32)  # 随机生成，每进程不同
```

更严重的问题是：`.env.example` 中**完全没有** `SESSION_SECRET` 条目。一个新的部署者复制 `.env.example` → 所有 worker 使用不同的随机 secret → 令牌验证间歇性失败。这是一个**静默部署陷阱**。

**修复方案：**
1. 添加 `SESSION_SECRET=` 到 `.env.example`
   ```env
   # ── Session 签名密钥（生产环境必填）──
   # 生成：python3 -c "import secrets; print(secrets.token_hex(32))"
   # 不填则每次重启随机生成，多 worker 下会导致 session 失效
   SESSION_SECRET=
   ```
2. 在启动时添加验证日志
   ```python
   if not _SECRET:
       logger.warning("SESSION_SECRET not set — using ephemeral random secret. "
                       "Session tokens will be invalidated on restart. "
                       "Set SESSION_SECRET in .env for production.")
   ```
3. 可选：启动时如果 secret 是自动生成的且 `APP_ENV=production`，则硬性失败
- 估计：10 分钟

---

### P1-12: requirements.txt 版本宽泛 — 审计自认已修复

**审计原文：**「requirements.lock 已存在」「已修复」

**核实：** `requirements.txt` 仍使用 `>=`，但 `requirements.lock`（uv 编译）已存在，Dockerfile 也使用了 `.lock` 文件。

**评价：** 已修复。`requirements.txt` 保持宽泛范围是标准做法——它定义**允许的范围**，`requirements.lock` 锁定**实际使用的版本**。这是正确的做法。

---

## 三、真实优先级与分阶段修复计划

### Phase 0：阻断性修复（今天，~15 分钟）

| 顺序 | 文件 | 修复内容 |
|------|------|---------|
| 1 | `server/graph/nodes/llm_node.py` | 添加 timeout 参数到 OpenAI() |
| 2 | `server/routes/chat.py` | Phase 1 graph.invoke 添加 try-except |
| 3 | `server/auth.py` + `.env.example` | 添加 SESSION_SECRET 验证和文档 |

### Phase 1：高优先级（本周，~1 小时）

| 顺序 | 文件 | 修复内容 |
|------|------|---------|
| 4 | `nginx.conf` | 删除 script-src 的 'unsafe-inline' |
| 5 | `app.py` | 删除或移入 legacy/ |
| 6 | `scripts/*.py` | ruff 修复（`--fix` + 手动修复 8 个 E701） |
| 7 | 新建 `server/monitoring.py` | Sentry 集成 |

### Phase 2：中等优先级（本月，~3 小时）

| 顺序 | 文件 | 修复内容 |
|------|------|---------|
| 8 | 新建 `docs/adr/*.md` | 架构决策记录 |
| 9 | `docker-compose.yml` | 清理 streamlit 服务或添加警告注释 |
| 10 | `tests/server/services/test_voice.py` | 在 voice 逻辑完成后添加测试 |

---

## 四、审计质量反思

### 审计做得好的地方
- **时序正确**：审计在修复后编写，但识别出了多个被忽略的问题
- **SSE / LLM timeout** 抓住了真正的生产质量缺口
- **auth.py 跨进程风险** 识别出了 .env.example 缺失的问题——这是真正的运维陷阱

### 审计可以改进的地方
- **P0 标签膨胀**：三个 P0 中只有两个是真正的阻断性。将 ruff 脚本格式问题标记为 P0 削弱了优先级体系的价值
- **数字不精确**：声称 22 个 ruff 错误，实际是 23 个，且 9 个在死亡代码中
- **前后矛盾**：前端 CVE 标注"已修复"但结论表仍列为"未按质量完成"
- **分类偏差**：`cli.py` 的回退值（非阻塞/有界/非搜索）被标记为 P1 → 实际上与 LLM timeout（P0）权重相同是误导性的
