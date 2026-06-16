# 高考季 MVP — 报告系统 + API Key 增强 + 15天部署

> **日期:** 2026-06-17
> **作者:** gaobao-advisor 设计团队
> **状态:** 已确认 — 等待实施

---

## 1. 设计目标

在高考出分前（约2-3周），利用免费资源（2x Agnes Flash + 1x GLM 4.0 + JD Cloud 15天试用），为考生提供一个可生成结构化志愿报告并导出为精美封面的服务。15天后根据数据决定是否续费。

**核心价值主张：**
- 考生：从对话到可保存、可分享的志愿报告
- OPC：收集真实使用数据 + 技术信任背书 + 内容素材

---

## 2. 范围界定

### 做（In Scope）

| 模块 | 功能 | 优先级 |
|------|------|--------|
| **报告系统 L1-L3** | 对话→结构化报告→金榜题名封面→PNG导出 | P0 |
| **API Key 精简增强** | 2x Agnes Flash 轮询 + GLM 4.0 复杂任务 + 降级链 | P1 |
| **JD Cloud 15天部署** | 极简架构 + 域名 + 监控 | P1 |
| **前端报告页** | ReportView.vue 从空壳→完整报告页 | P0 |

### 不做（Out of Scope）

| 功能 | 原因 |
|------|------|
| 用户注册/登录 | Session token 够用，不增加注册阻力 |
| B端班主任工具 | 无销售团队，没人会用 |
| 内容引擎自动化 | 手动发社交媒体即可 |
| 移动端原生 App | Vue 3 响应式已够用 |
| 完整 API Key 池管理 | 3个Key不需要加权轮询、配额面板 |

---

## 3. 报告系统设计

### 3.1 数据流

```
用户对话 → LangGraph 13节点 → structure_output_node
                                    │
                                    ▼
                            StructuredPlanningCard
                            (title, summary, facts,
                             suggestions, risks,
                             next_actions, confidence)
                                    │
                                    ▼
                            ReportGenerator
                            (映射为 Report 数据模型)
                                    │
                                    ▼
                            ┌──────────────┐
                            │  ReportCover │  SVG 金榜题名封面
                            │  (服务端生成) │
                            └──────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  ReportExporter│
                            │  HTML / PNG  │
                            └──────────────┘
```

### 3.2 Report 数据模型

```python
@dataclass
class Report:
    """志愿分析报告数据模型。"""

    id: str                    # UUID v4
    session_id: str            # 关联对话 session
    created_at: datetime       # 生成时间
    student_name: str | None   # 考生姓名（可选）
    province: str              # 省份
    score: int                 # 分数
    subject: str               # 选科
    interest: str              # 专业意向

    # 结构化内容（来自 StructuredPlanningCard）
    summary: str               # 一句话摘要
    facts: list[str]           # 事实列表
    suggestions: list[str]     # 建议列表（冲稳保院校）
    risks: list[str]          # 风险提示
    next_actions: list[str]    # 下一步行动
    confidence: float           # 置信度 0-1

    # 元数据
    match_schools: list[dict]  # 匹配院校详情
    scene: str                 # gaokao/kaoyan/career
```

### 3.3 存储方案

**不做数据库表**，用文件系统存储：

```
data/reports/
├── {session_id}/
│   ├── report.json          # Report 对象 JSON
│   ├── cover.svg            # 金榜题名封面 SVG
│   └── cover.png            # 封面 PNG 导出（可选）
```

理由：
- 报告数据是只读的，生成后不再修改
- 文件系统足够简单，不需要新增数据库表
- 便于直接通过 nginx 静态文件服务访问

### 3.4 金榜题名封面设计

基于 `docs/superpowers/docs/html-report-design.md` 的设计理念，但改为**服务端 SVG 生成**（不依赖浏览器）：

```svg
<!-- 金榜题名封面 SVG -->
<svg viewBox="0 0 800 500" xmlns="http://www.w3.org/2000/svg">
  <!-- 金色渐变背景 -->
  <defs>
    <linearGradient id="gold-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFD700"/>
      <stop offset="50%" stop-color="#FFA500"/>
      <stop offset="100%" stop-color="#FF8C00"/>
    </linearGradient>
  </defs>

  <!-- 背景矩形 -->
  <rect width="800" height="500" rx="20" fill="url(#gold-bg)"/>

  <!-- 深红边框 -->
  <rect x="8" y="8" width="784" height="484" rx="15"
        fill="none" stroke="#8B0000" stroke-width="8"/>

  <!-- 装饰内框 -->
  <rect x="30" y="30" width="740" height="440" rx="10"
        fill="none" stroke="rgba(139,0,0,0.3)" stroke-width="3"/>

  <!-- 标题：金榜题名 -->
  <text x="400" y="200" text-anchor="middle"
        font-family="KaiTi, STKaiti, serif"
        font-size="72" font-weight="bold" fill="#DC143C"
        letter-spacing="20">
    金榜题名
  </text>

  <!-- 副标题 -->
  <text x="400" y="260" text-anchor="middle"
        font-family="Microsoft YaHei, sans-serif"
        font-size="24" fill="#8B0000" letter-spacing="5">
    高考志愿填报分析报告
  </text>

  <!-- 年份标签 -->
  <rect x="300" y="300" width="200" height="50" rx="10"
        fill="rgba(139,0,0,0.8)"/>
  <text x="400" y="335" text-anchor="middle"
        font-family="Microsoft YaHei, sans-serif"
        font-size="28" font-weight="bold" fill="#FFD700">
    2026 年度
  </text>

  <!-- 考生信息 -->
  <text x="400" y="390" text-anchor="middle"
        font-family="Microsoft YaHei, sans-serif"
        font-size="18" fill="#8B0000">
    {student_name} · {province} · {score}分
  </text>

  <!-- 底部信息 -->
  <text x="400" y="460" text-anchor="middle"
        font-family="Microsoft YaHei, sans-serif"
        font-size="14" fill="rgba(139,0,0,0.6)">
    © 高考志愿AI顾问 · 助力每一个梦想
  </text>
</svg>
```

**SVG → PNG 转换**：使用 `cairosvg`（纯 Python，依赖 cairo 库，可通过 `apt-get install libcairo2` 安装）。

### 3.5 API 接口设计

```python
# POST /api/v1/report/generate
# 从当前对话生成报告
# Request: {"session_id": "xxx", "student_name": "张三"}
# Response: {"report_id": "uuid", "status": "generating"}

# GET /api/v1/report/{report_id}
# 获取报告详情
# Response: Report 对象 JSON

# GET /api/v1/report/{report_id}/cover.svg
# 获取封面 SVG

# GET /api/v1/report/{report_id}/cover.png
# 获取封面 PNG

# GET /api/v1/report/{report_id}/html
# 获取完整 HTML 报告（含封面+内容）
```

---

## 4. API Key 增强设计

### 4.1 当前问题

现有 `config/llm_providers.yaml` 只支持单 Provider 切换（通过 `LLM_PROVIDER` 环境变量），没有多 Key 轮换能力。

### 4.2 增强方案（精简版）

**目标**：3个免费 Key 的自动轮换 + 降级，不做完整池管理。

```yaml
# config/llm_providers.yaml (增强后)
providers:
  # Agnes Flash 1 — 简单任务（FAQ、数据查询、RAG）
  agnes-flash-1:
    base_url: "https://api.agnes.ai/v1"
    model: "agnes-2.0-flash"
    api_key: "${AGNES_API_KEY_1}"
    priority: "fast"
    task_types: ["faq", "data_query", "rag", "summary", "report_format"]

  # Agnes Flash 2 — 简单任务备用
  agnes-flash-2:
    base_url: "https://api.agnes.ai/v1"
    model: "agnes-2.0-flash"
    api_key: "${AGNES_API_KEY_2}"
    priority: "fast"
    task_types: ["faq", "data_query", "rag", "summary", "report_format"]

  # GLM 4.0 — 复杂任务（推理、结构化输出、质量检测）
  glm-4:
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4"
    api_key: "${GLM_API_KEY}"
    priority: "smart"
    task_types: ["recommend", "strategy", "quality_check", "structured_output"]

defaults:
  provider: "agnes-flash-1"
```

### 4.3 路由规则

```python
# 规则路由（不调用 LLM 判断）
def route_task(task_type: str) -> str:
    """根据任务类型路由到合适的 Provider。"""
    fast_tasks = {"faq", "data_query", "rag", "summary", "report_format"}
    smart_tasks = {"recommend", "strategy", "quality_check", "structured_output"}

    if task_type in fast_tasks:
        # Agnes 轮询: 1 → 2 → 1 → 2
        return _round_robin_agnes()
    elif task_type in smart_tasks:
        return "glm-4"
    else:
        # 默认走 Agnes
        return _round_robin_agnes()
```

### 4.4 降级链

```python
# 调用失败时的降级链
def call_with_fallback(task_type: str, messages: list[dict]) -> str:
    """调用 LLM，失败时自动降级。"""
    primary = route_task(task_type)
    providers = [primary]

    # 构建降级链
    if primary.startswith("agnes"):
        # Agnes 失败 → 另一个 Agnes → GLM → 降级提示
        other_agnes = "agnes-flash-2" if primary == "agnes-flash-1" else "agnes-flash-1"
        providers = [primary, other_agnes, "glm-4"]
    elif primary == "glm-4":
        # GLM 失败 → Agnes 1 → Agnes 2 → 降级提示
        providers = ["agnes-flash-1", "agnes-flash-2"]

    last_error = None
    for provider in providers:
        try:
            return _call_provider(provider, messages)
        except Exception as e:
            last_error = e
            logger.warning("Provider %s failed: %s, trying next...", provider, e)
            continue

    # 全部失败，返回降级回复
    logger.error("All providers failed: %s", last_error)
    return _FALLBACK_REPLY
```

### 4.5 健康检查

```python
# 每 5 分钟 ping 一次每个 Provider
# 连续 3 次失败标记为不可用
# 每小时尝试恢复标记为不可用的 Provider
```

---

## 5. JD Cloud 15天部署设计

### 5.1 架构

```
用户访问
    ↓
域名 (免备案二级域名，如 gaobao.example.com)
    ↓
JD Cloud 轻量服务器 (2核4G, 15天免费)
    ├── Nginx (反向代理, 80端口)
    │   ├── /api/* → FastAPI (Docker, 8000端口)
    │   ├── /ws/*  → FastAPI WebSocket
    │   └── /      → Vue 3 静态文件
    ├── FastAPI (Docker Compose)
    │   ├── 后端服务
    │   ├── SQLite (./data/ 持久化)
    │   └── 报告文件 (./data/reports/)
    └── 监控脚本 (简单 cron)
```

### 5.2 部署清单

| 组件 | 方案 | 原因 |
|------|------|------|
| 域名 | 免备案二级域名 | 15天内来不及 ICP 备案 |
| 数据库 | SQLite (现有) | 零运维，迁移成本低 |
| 缓存 | 无 Redis | 2核4G 够用，省资源 |
| 日志 | 文件日志 + 简单脚本 | 不需要 ELK |
| 监控 | UptimeRobot 免费版 | 够用 |
| 备份 | 每天 rsync 到本地 | 15天数据量小 |

### 5.3 部署脚本

```bash
# deploy/jdcloud/setup.sh
# 一键部署脚本

#!/bin/bash
set -e

echo "=== Gaobao Advisor JD Cloud 部署 ==="

# 1. 安装 Docker & Docker Compose
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# 2. 克隆项目
git clone https://github.com/yourname/gaobao-advisor.git
cd gaobao-advisor

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 4. 启动服务
docker-compose up -d

# 5. 健康检查
curl -f http://localhost/api/v1/health || exit 1

echo "=== 部署完成 ==="
echo "访问: http://$(curl -s ifconfig.me)"
```

---

## 6. 前端设计

### 6.1 ReportView.vue 结构

```vue
<template>
  <div class="report-container">
    <!-- 封面区域 -->
    <div class="cover-section">
      <img :src="coverUrl" alt="金榜题名封面" class="cover-image"/>
      <button @click="downloadCover">下载封面</button>
    </div>

    <!-- 报告内容 -->
    <div class="report-content">
      <!-- 考生信息 -->
      <section class="student-info">
        <h2>考生信息</h2>
        <p>{{ report.province }} · {{ report.score }}分 · {{ report.subject }}</p>
      </section>

      <!-- 事实摘要 -->
      <section class="facts">
        <h2>分析摘要</h2>
        <ul>
          <li v-for="fact in report.facts" :key="fact">{{ fact }}</li>
        </ul>
      </section>

      <!-- 冲稳保建议 -->
      <section class="suggestions">
        <h2>院校推荐</h2>
        <div class="school-cards">
          <div v-for="s in report.suggestions" :key="s" class="school-card">
            {{ s }}
          </div>
        </div>
      </section>

      <!-- 风险提示 -->
      <section class="risks">
        <h2>风险提示</h2>
        <ul>
          <li v-for="risk in report.risks" :key="risk">{{ risk }}</li>
        </ul>
      </section>

      <!-- 下一步 -->
      <section class="next-actions">
        <h2>建议行动</h2>
        <ol>
          <li v-for="action in report.next_actions" :key="action">{{ action }}</li>
        </ol>
      </section>
    </div>

    <!-- 导出按钮 -->
    <div class="export-actions">
      <button @click="exportHTML">导出 HTML</button>
      <button @click="exportPNG">导出 PNG</button>
    </div>
  </div>
</template>
```

### 6.2 从 Chat 页面触发报告生成

在 ChatView.vue 的对话界面中，添加一个"生成报告"按钮：

```vue
<!-- 在 ChatArea 组件中 -->
<div class="report-trigger">
  <button v-if="canGenerateReport" @click="generateReport">
    📝 生成志愿分析报告
  </button>
</div>
```

触发条件：`profile.is_complete && conversation_rounds >= 3`

---

## 7. 测试策略

### 7.1 单元测试

```python
# tests/server/report/test_generator.py
def test_report_from_structured_card():
    """从 StructuredPlanningCard 生成 Report 对象。"""
    card = StructuredPlanningCard(
        title="高考志愿规划建议",
        summary="山东，600分，意向计算机，规划分析中。",
        scene="gaokao",
        facts=["省份：山东", "分数：600"],
        suggestions=["推荐：山东大学"],
        risks=["数据有限"],
        next_actions=["对比推荐院校"],
        confidence=0.85,
    )
    report = ReportGenerator.from_card(card, session_id="test-123")
    assert report.province == "山东"
    assert report.score == 600

# tests/server/report/test_cover.py
def test_cover_svg_generation():
    """生成金榜题名封面 SVG。"""
    report = Report(...)
    svg = CoverGenerator.generate(report)
    assert "金榜题名" in svg
    assert "山东" in svg
    assert "600" in svg
```

### 7.2 集成测试

```python
# tests/test_report_api.py
def test_report_generation_endpoint(client):
    """测试报告生成 API。"""
    response = client.post("/api/v1/report/generate", json={
        "session_id": "test-session",
        "student_name": "张三"
    })
    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data

# tests/test_report_export.py
def test_report_cover_png(client, report_id):
    """测试封面 PNG 导出。"""
    response = client.get(f"/api/v1/report/{report_id}/cover.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
```

---

## 8. 价值验证指标（15天后评估）

| 指标 | 目标 | 来源 |
|------|------|------|
| 独立用户数 | 100+ | 日志统计 |
| 生成报告数 | 50+ | data/reports/ 目录 |
| GitHub Stars | 10+ | GitHub API |
| 社交媒体曝光 | 1000+ | 小红书/抖音/朋友圈 |
| 用户反馈数 | 10+ | 问卷/评论 |
| 咨询意向 | 1-2 | 私信/邮件 |

**决策标准：**
- ≥3 个指标达标 → 续费/迁移长期运行
- 1-2 个指标达标 → 归档数据，继续 GitHub 开源维护
- 0 个指标达标 → 复盘原因，调整方向

---

## 9. 风险与应对

| 风险 | 可能性 | 影响 | 应对 |
|------|--------|------|------|
| Agnes API 免费额度用完 | 中 | 高 | 降级到 GLM，或暂停服务 |
| JD Cloud 15天后无法续费 | 中 | 中 | 提前准备 Oracle Cloud 免费迁移方案 |
| 报告生成性能差 | 低 | 中 | SVG 生成是同步的，但很快；PNG 转换异步 |
| 用户数据丢失 | 低 | 高 | 每天 rsync 备份到本地 |
| 高考政策变化 | 低 | 中 | 依赖 RAG 知识库，更新 knowledge/ 目录 |

---

## 10. 附录

### A. 文件清单

```
gaobao-advisor/
├── server/
│   ├── report/
│   │   ├── __init__.py          # Report 模块初始化
│   │   ├── models.py            # Report 数据模型
│   │   ├── generator.py         # 对话→Report 生成器
│   │   ├── cover.py             # 金榜题名封面 SVG 生成
│   │   ├── exporter.py          # HTML/PNG 导出
│   │   └── routes.py            # 报告 API 路由
│   └── services/
│       └── llm_router.py        # API Key 路由 + 降级链
├── frontend/src/
│   ├── views/
│   │   └── ReportView.vue       # 报告页面（重写）
│   └── components/
│       └── report/
│           ├── ReportCover.vue   # 封面展示
│           ├── SchoolTable.vue   # 院校推荐表
│           └── ExportButton.vue  # 导出按钮
├── deploy/
│   └── jdcloud/
│       ├── setup.sh             # 一键部署脚本
│       └── nginx.conf           # Nginx 配置
└── tests/
    └── server/report/           # 报告模块测试
```

### B. 依赖清单

```
# 新增 Python 依赖
cairosvg>=2.7.0          # SVG → PNG 转换
Pillow>=10.0.0           # 图像处理（备用）

# 新增系统依赖
# Ubuntu/Debian: sudo apt-get install libcairo2
```

---

*设计文档完成。下一步：编写实施计划。*
