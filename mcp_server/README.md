# Gaobao Advisor MCP Server

基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 的 MCP 服务器，为高考志愿 AI 顾问系统提供标准化工具接口，使 AI 代理能直接查询院校数据、录取分数线、招生计划、知识库和用户画像。

## 功能概览

| 工具类别 | 工具名称 | 说明 |
|---------|---------|------|
| **院校查询** | `gaobao_search_schools` | 按名称/省份/层次搜索院校 |
| | `gaobao_get_school_detail` | 获取院校详细信息 |
| **分数线** | `gaobao_query_scores` | 查询院校历年录取分数线 |
| **招生计划** | `gaobao_query_plans` | 查询院校招生计划 |
| **知识检索** | `gaobao_search_knowledge` | RAG 知识库语义检索 |
| | `gaobao_get_quotes` | 获取专家金句 |
| **用户画像** | `gaobao_get_profile` | 获取考生画像 |
| | `gaobao_update_profile` | 更新考生画像字段 |
| **系统** | `gaobao_health_check` | 服务健康检查 |

## 安装

### 作为 Claude Code / Claude Desktop 的 MCP 服务器

在 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "gaobao-advisor": {
      "command": "python3",
      "args": ["mcp_server/server.py"],
      "env": {
        "GAOBAO_API_BASE_URL": "http://localhost:8000",
        "GAOBAO_TIMEOUT": "30"
      }
    }
  }
}
```

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `GAOBAO_API_BASE_URL` | 是 | - | API 基础地址 |
| `GAOBAO_API_KEY` | 否 | - | API 鉴权密钥 |
| `GAOBAO_TIMEOUT` | 否 | 30 | 请求超时（秒） |

## 使用示例

在支持 MCP 的 AI 代理中，可以直接调用工具：

```
User: 展示一条合成院校记录

Agent: [调用 gaobao_search_schools → "星海理工学院"]
       [调用 gaobao_query_scores → 合成演示结果]

       这是合成演示数据，只用于展示 MCP 调用流程，不可用于真实志愿决策。
```

## 架构

```
mcp_server/
├── __init__.py         # 包声明
├── server.py           # MCP 服务器主入口（FastMCP）
├── client.py           # HTTP 客户端（与 gaobao-advisor API 通信）
├── schemas.py          # Pydantic 模型定义
├── README.md           # 本文档
├── requirements.txt    # 依赖声明
└── tools/
    ├── __init__.py     # 工具注册入口
    ├── schools.py      # 院校搜索/详情工具
    ├── scores.py       # 分数线/招生计划工具
    ├── knowledge.py    # 知识检索/金句工具
    ├── profile.py      # 用户画像管理工具
    └── system.py       # 健康检查工具
```

## 依赖

- `mcp >= 1.6.0` — MCP Python SDK (FastMCP)
- `httpx >= 0.27.0` — Async HTTP 客户端
- `pydantic >= 2.0.0` — 数据验证

## 开发

```bash
# 安装依赖
pip install -e '.[mcp]'

# 语法检查
python3 -m py_compile mcp_server/server.py

# 使用 MCP Inspector 测试
npx @modelcontextprotocol/inspector python3 mcp_server/server.py
```

## 与项目集成

MCP 服务器作为独立进程，通过 HTTP 与 gaobao-advisor API 通信：

```
┌──────────────┐    MCP Protocol     ┌──────────────────┐    HTTP    ┌──────────────────┐
│  AI Agent    │  ◄──────────────►   │  MCP Server      │  ◄──────►  │  Gaobao-API     │
│  (Claude等)  │    (stdio)          │  (Python-FastMCP) │           │  (FastAPI:8000) │
└──────────────┘                     └──────────────────┘           └──────────────────┘
```

## 协议版本

- **MCP Protocol**: 2025-03-26
- **Python SDK**: `mcp >= 1.6.0`
- **API Version**: v1
