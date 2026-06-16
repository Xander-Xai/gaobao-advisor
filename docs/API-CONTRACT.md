# API 契约文档

> **版本**: 3.0.0  
> **生成日期**: 2026-06-16  
> **格式**: OpenAPI 3.0 (JSON + YAML)

---

## 📄 文件位置

- **JSON 格式**: [`openapi.json`](../openapi.json) (24.1 KB)
- **YAML 格式**: [`openapi.yaml`](../openapi.yaml) (15.3 KB)
- **在线文档**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🔄 重新生成

```bash
# 导出 OpenAPI 规范
python scripts/export_openapi.py

# 输出:
# ✓ Exported OpenAPI JSON: openapi.json (24.1 KB)
# ✓ Exported OpenAPI YAML: openapi.yaml (15.3 KB)
```

---

## 📊 API 概览

### 基本信息
- **标题**: gaobao-advisor
- **版本**: 3.0.0
- **端点数量**: 12
- **数据模型**: 9

### 可用端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | API 根信息 |
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/onboarding` | 用户引导流程 |
| POST | `/api/v1/chat` | 聊天接口（SSE 流式） |
| GET | `/api/v1/profile/{session_id}` | 获取用户档案 |
| PUT | `/api/v1/profile/{session_id}` | 更新用户档案 |
| GET | `/api/v1/profile/{session_id}/next-question` | 获取下一个问题 |
| POST | `/api/v1/profile/{session_id}/skip` | 跳过问题 |
| GET | `/api/v1/data/scores` | 查询录取分数线 |
| GET | `/api/v1/data/schools` | 查询院校列表 |
| GET | `/api/v1/data/plans` | 查询招生计划 |
| GET | `/api/v1/knowledge/quotes` | 获取语录推荐 |
| POST | `/api/v1/knowledge/search` | 知识库搜索 |

---

## 🔑 认证方式

### Session Token 认证

大部分端点需要 HMAC-SHA256 session token 认证。

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

---

## 📝 端点详解

### 1. 健康检查

**GET** `/api/v1/health`

无需认证。

**响应**：
```json
{
  "status": "ok",
  "version": "3.0.0",
  "database": "connected"
}
```

---

### 2. 用户引导

**POST** `/api/v1/onboarding`

开始新用户引导流程。

**请求体**：
```json
{
  "session_id": "user_123",
  "scene": "gaokao"
}
```

**响应**：
```json
{
  "question": "请问你是哪个省份的考生？",
  "field": "province",
  "options": ["山东", "江苏", "浙江", "..."]
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

data: {"type": "done", "session_token": "abc123..."}
```

**事件类型**：
- `slots`: 提取的槽位信息
- `emotion`: 情绪状态
- `structured`: 结构化结果（卡片/建议）
- `token`: 流式文本片段
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
  "province": "山东",
  "score": 580,
  "subject": "物理类",
  "interest": "计算机",
  "filled_fields": ["province", "score", "subject"],
  "missing_fields": ["family", "goal"]
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

**GET** `/api/v1/data/scores?school=清华大学&province=山东&year=2024`

**响应**：
```json
[
  {
    "school": "清华大学",
    "level": "985",
    "province": "山东",
    "year": 2024,
    "min_score": 680,
    "min_rank": 100,
    "major": "计算机科学与技术"
  }
]
```

#### 院校列表

**GET** `/api/v1/data/schools?province=山东&level=985`

#### 招生计划

**GET** `/api/v1/data/plans?school=清华大学&province=山东`

---

### 6. 知识库

#### 获取语录

**GET** `/api/v1/knowledge/quotes?major=计算机&limit=5`

**响应**：
```json
[
  {
    "id": "zx_001",
    "text": "选择大于努力",
    "category": "专业选择",
    "source": "张雪峰直播",
    "year": 2023
  }
]
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

**最后更新**: 2026-06-16  
**维护者**: AI Assistant
