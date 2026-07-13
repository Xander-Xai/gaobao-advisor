# API 契约文档

> **版本**: 3.1.0
> **生成日期**: 2026-06-28
> **格式**: OpenAPI 3.0 (JSON + YAML)

---

## 📄 文件位置

- **JSON 格式**: [`openapi.json`](../openapi.json) (39.7 KB)
- **YAML 格式**: [`openapi.yaml`](../openapi.yaml) (25.2 KB)
- **在线文档**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🔄 重新生成

```bash
# 导出 OpenAPI 规范
python scripts/export_openapi.py

# 输出:
# ✓ Exported OpenAPI JSON: openapi.json (39.7 KB)
# ✓ Exported OpenAPI YAML: openapi.yaml (25.2 KB)
```

---

## 📊 API 概览

### 基本信息
- **标题**: 高考志愿AI顾问
- **版本**: 3.1.0
- **HTTP 端点数量**: 18（OpenAPI 统计，不含 WebSocket）
- **数据模型**: 13

### 可用端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | API 根信息 |
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/onboarding` | 用户引导流程 |
| POST | `/api/v1/chat` | SSE 流式聊天 |
| POST | `/api/v1/chat/feedback` | 提交用户反馈（需要 Bearer token） |
| POST | `/api/v1/chat/highlight` | 提取金句（需要 Bearer token） |
| GET | `/api/v1/profile/{session_id}` | 获取用户档案 |
| PUT | `/api/v1/profile/{session_id}` | 更新用户档案 |
| GET | `/api/v1/profile/{session_id}/next-question` | 获取下一个灵魂提问 |
| POST | `/api/v1/profile/{session_id}/skip` | 跳过可选字段 |
| GET | `/api/v1/data/scores` | 查询录取分数线 |
| GET | `/api/v1/data/schools` | 查询院校列表 |
| GET | `/api/v1/data/plans` | 查询招生计划 |
| GET | `/api/v1/knowledge/quotes` | 获取金句 |
| POST | `/api/v1/knowledge/search` | 知识库搜索 |
| POST | `/api/v1/report/generate` | 生成分析报告（请求体 `session_id + token`） |
| GET | `/api/v1/report/{report_id}` | 获取报告 JSON（Query `session_id + token`） |
| GET | `/api/v1/report/{report_id}/html` | 获取报告 HTML（Query `session_id + token`） |
| GET | `/api/v1/report/{report_id}/cover.svg` | 获取 SVG 封面（Query `session_id + token`） |
| WS | `/api/v1/ws/call` | 实时语音通话 |

---

## 🔑 认证方式

认证辅助函数统一集中在 `server/auth.py`，包括 token 签发、校验、HMAC-SHA256 签名等逻辑。

### Session Token 认证

需要访问用户画像、反馈、金句、语音和报告资源的端点使用 HMAC-SHA256 session token 认证。聊天接口本身不需要认证，会在 SSE `done` 事件中签发 `session_token`。

**获取 Token**：
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_001",
    "scene": "gaokao",
    "message": "我是山东考生，考了 580 分"
  }'
```

响应中包含 `session_token`：
```json
{
  "type": "done",
  "session_token": "abc123..."
}
```

**使用 Token**：
```bash
curl -X GET http://localhost:8000/api/v1/profile/test_001 \
  -H "Authorization: Bearer abc123..."
```

**报告读取/导出 Token**：
```bash
curl "http://localhost:8000/api/v1/report/REPORT_ID?session_id=test_001&token=abc123..."
```

---

## 📝 端点详解

### 1. 健康检查

**GET** `/api/v1/health`

无需认证。

**响应**：
```json
{
  "status": "ok",
  "version": "3.1.0",
  "database": "connected"
}
```

---

### 2. 用户引导

**POST** `/api/v1/onboarding`

提交前端采集到的表单片段，后端会做轻量槽位抽取并返回缺失项。

> **注意**：当前尚无前端 UI 对接此端点，仅后端 API 可用。

**请求体**：
```json
{
  "step": 1,
  "data": {
    "province": "山东",
    "score": "580分"
  }
}
```

**响应**：
```json
{
  "step": 1,
  "extracted": {
    "province": "山东",
    "score": "580分"
  },
  "missing": [],
  "next_step": 2,
  "message": "信息已记录"
}
```

---

### 3. 聊天接口（SSE 流式）

**POST** `/api/v1/chat`

核心聊天接口，支持 Server-Sent Events 流式响应。

**请求体**：
```json
{
  "session_id": "user_123",
  "scene": "gaokao",
  "message": "我是山东考生，考了 580 分，物理类"
}
```

**SSE 事件流**：
```
data: {"type": "slots", "data": {"province": "山东", "score": 580}}

data: {"type": "emotion", "state": "焦虑"}

data: {"type": "structured", "result": {...}}

data: {"type": "token", "content": "根"}
data: {"type": "token", "content": "据"}
data: {"type": "token", "content": "2024"}
data: {"type": "token", "content": "年"}

data: {"type": "quality", "grade": "pass", "rewritten": false}

data: {"type": "done", "session_token": "abc123..."}
```

**事件类型**：
- `slots`: 提取的槽位信息
- `emotion`: 情绪状态
- `structured`: 结构化结果
- `token`: 流式文本片段
- `degraded`: LLM 降级通知
- `quality`: 质量评分结果
- `error`: 图管线失败通知，格式 `{"type": "error", "code": "GRAPH_FAILED", "message": "错误描述"}`
- `done`: 完成信号（含 session_token）

---

### 4. 用户档案

#### 获取档案

**GET** `/api/v1/profile/{session_id}`

需要认证。

**响应**：
```json
{
  "session_id": "user_123",
  "profile": {
    "province": "山东",
    "score": 580,
    "subject": "物理类",
    "interest": "计算机",
    "region": null,
    "family": null,
    "goal": null
  },
  "is_complete": false,
  "missing_fields": ["region", "family", "goal"]
}
```

#### 更新档案

**PUT** `/api/v1/profile/{session_id}`

需要认证。

**请求体**：
```json
{
  "field": "province",
  "value": "山东"
}
```

---

### 5. 数据查询

#### 录取分数线

**GET** `/api/v1/data/scores?school_name=清华大学&province=山东&year=2024`

**响应**（游标分页）：
```json
{
  "items": [
    {
      "id": 1,
      "school_name": "清华大学",
      "province": "山东",
      "year": 2024,
      "batch": "本科一批",
      "subject_type": "物理类",
      "min_score": 680,
      "avg_score": 685,
      "max_score": 700,
      "min_rank": 100,
      "major": "计算机科学与技术"
    }
  ],
  "next_cursor": "2",
  "has_more": true
}
```

#### 院校列表

**GET** `/api/v1/data/schools?province=山东&level=985`

**响应**（游标分页）：
```json
{
  "items": [
    {
      "id": 1,
      "name": "山东大学",
      "province": "山东",
      "level": "985",
      "city": "济南",
      "type": "综合"
    }
  ],
  "next_cursor": "2",
  "has_more": true
}
```

`school_name` 参数使用全文搜索（FTS），返回 `{count, results}` 格式：
```json
{
  "count": 1,
  "results": [{
    "id": 1,
    "name": "清华大学",
    "province": "北京",
    "level": "985",
    "city": "北京",
    "type": "综合"
  }]
}
```

#### 招生计划

**GET** `/api/v1/data/plans?school_name=清华大学&province=山东`

**响应**（游标分页）：
```json
{
  "items": [
    {
      "id": 1,
      "school_name": "清华大学",
      "province": "山东",
      "year": 2024,
      "plan_count": 5,
      "batch": "本科一批",
      "major": "计算机科学与技术",
      "subject_requirement": "物理+化学",
      "duration": 4,
      "tuition": 5000
    }
  ],
  "next_cursor": "2",
  "has_more": true
}
```

---

### 6. 报告生成与导出

报告相关端点使用 `require_token_auth` 校验（通过请求体或 Query 参数传递 `session_id` + `token`，**不使用** `Authorization: Bearer` 头）。

#### 生成报告

**POST** `/api/v1/report/generate`

请求体必须包含当前会话的 `session_id` 和 `token`。`token` 与聊天 `done` 事件签发的 `session_token` 一致。

```json
{
  "session_id": "test_001",
  "token": "abc123...",
  "student_name": "测试考生"
}
```

#### 读取与导出

以下端点都必须携带 Query 参数 `session_id` 和 `token`：

- **GET** `/api/v1/report/{report_id}?session_id=test_001&token=abc123...`
- **GET** `/api/v1/report/{report_id}/html?session_id=test_001&token=abc123...`
- **GET** `/api/v1/report/{report_id}/cover.svg?session_id=test_001&token=abc123...`

报告读取会同时校验 token 和报告所属 session，不能只凭 `report_id` 访问。

---

### 7. 知识库

#### 获取语录

**GET** `/api/v1/knowledge/quotes?major=计算机&top_k=5`

**响应**：
```json
{
  "count": 1,
  "quotes": [
    {
      "id": "zx_001",
      "text": "选择大于努力",
      "category": "专业选择",
      "source": "张雪峰直播",
      "year": 2023
    }
  ]
}
```

#### 知识库搜索

**POST** `/api/v1/knowledge/search`

**请求体**：
```json
{
  "query": "计算机专业就业前景",
  "top_k": 5
}
```

**响应**：
```json
{
  "count": 3,
  "groups": ["G1", "G2"],
  "chunks": [
    {
      "text": "计算机专业在山东招生情况...",
      "score": 0.92,
      "source": "knowledge/groups/G1"
    }
  ],
  "quotes": []
}
```

---

## 🔧 集成示例

### Python (requests)

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# 1. 健康检查
response = requests.get(f"{BASE_URL}/api/v1/health")
print(response.json())

# 2. 聊天（SSE 流式）
import sseclient

response = requests.post(
    f"{BASE_URL}/api/v1/chat",
    json={
        "session_id": "test_001",
        "scene": "gaokao",
        "message": "我是山东考生，考了 580 分"
    },
    stream=True
)

for event in sseclient.SSEClient(response):
    data = json.loads(event.data)
    if data["type"] == "token":
        print(data["content"], end="", flush=True)
    elif data["type"] == "done":
        print("\nToken:", data["session_token"])
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000';

// 健康检查
const health = await fetch(`${BASE_URL}/api/v1/health`);
console.log(await health.json());

// 聊天（SSE 流式）
const response = await fetch(`${BASE_URL}/api/v1/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: 'test_001',
    scene: 'gaokao',
    message: '我是山东考生，考了 580 分'
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      if (data.type === 'token') {
        process.stdout.write(data.content);
      }
    }
  }
}
```

### cURL

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 聊天
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_001",
    "scene": "gaokao",
    "message": "我是山东考生，考了 580 分"
  }'

# 带认证的档案查询
curl http://localhost:8000/api/v1/profile/test_001 \
  -H "Authorization: Bearer YOUR_TOKEN"

# 带认证的报告读取
curl "http://localhost:8000/api/v1/report/REPORT_ID?session_id=test_001&token=YOUR_TOKEN"
```

---

## 📦 第三方集成

### Swagger Codegen

```bash
# 生成 Python 客户端
swagger-codegen generate \
  -i openapi.yaml \
  -l python \
  -o ./clients/python

# 生成 JavaScript 客户端
swagger-codegen generate \
  -i openapi.yaml \
  -l javascript \
  -o ./clients/javascript
```

### OpenAPI Generator

```bash
# 生成 Go 客户端
openapi-generator generate \
  -i openapi.yaml \
  -g go \
  -o ./clients/go
```

---

## 🔍 验证规范

```bash
# 使用 swagger-cli 验证
npm install -g @apidevtools/swagger-cli
swagger-cli validate openapi.yaml

# 预期输出: openapi.yaml is valid
```

---

## 📚 相关文档

- **在线 Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **FastAPI 文档**: https://fastapi.tiangolo.com/
- **OpenAPI 规范**: https://swagger.io/specification/

---

**最后更新**: 2026-06-28
**维护者**: AI Assistant
