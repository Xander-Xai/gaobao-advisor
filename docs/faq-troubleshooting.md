# FAQ 与故障排除

## 没有 API Key 能否启动

可以。公开发行版默认 `LLM_PROVIDER=demo`，不会访问远程或本地模型服务。复制 `.env.example`
后直接启动即可。返回内容会标注“社区演示模式”“合成示例”和“非官方工具”。

## 配置联网模型后 API Key 无效

**现象**：启动后 API 调用返回 401 或认证错误。

**排查步骤**：
1. 检查 `.env` 文件是否存在且 `LLM_API_KEY` 已正确填入（不要把值贴到 Issue）
2. 验证 API Key 在对应平台是否有效且有余额
3. 检查 `LLM_PROVIDER` 是否与 API Key 来源一致

**常见原因**：
- `.env` 文件不存在：复制 `.env.example` 为 `.env`，演示模式无需密钥
- API Key 过期：重新生成并更新
- Provider 不匹配：更换 `LLM_PROVIDER` 或使用对应平台的 Key

## 数据库位置与迁移

Docker 演示使用命名卷中的 `/app/data/demo.db`；本地路径由 `GAOBAO__DB_PATH` 决定。
仓库不分发真实 `gaokao.db`，数据库、备份和 WAL 文件也不能提交。

**迁移数据**：
1. 停止服务
2. 按部署策略备份自有数据库（不要放回仓库目录）
3. 启动新版本服务（框架会自动建表）

> 注意：当前版本仅支持 SQLite。如需 MySQL/PostgreSQL，需要修改 `db/database.py` 中的连接配置并添加对应的 SQLAlchemy driver。

## 如何更换 LLM Provider

### 方法一：环境变量（推荐）
```bash
export LLM_PROVIDER=deepseek
export LLM_API_KEY=sk-your-key
```

### 方法二：配置文件
编辑 `config/llm_providers.yaml`，添加或修改 Provider 配置。

**支持的 Provider**：Agnes Flash / DeepSeek / Qwen / GLM / OpenAI / Ollama / Moonshot

## 多 Worker 下 SESSION_SECRET 问题

**症状**：用户在使用过程中 Session Token 频繁失效，需要重新获取。

**原因**：多个 Worker 进程使用了不同的 `SESSION_SECRET`，导致 Token 签名不匹配。

**解决方案**：
```bash
# 在所有 Worker 中使用相同的 SESSION_SECRET
export SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

Docker Compose 部署时，确保在 `environment` 中统一设置：
```yaml
environment:
  - SESSION_SECRET=${SESSION_SECRET}
```

## 前端页面白屏/无法加载

**原因**：
1. API 地址未正确配置
2. 前端构建产物缺失
3. nginx 反向代理配置错误

**排查方案**：
```bash
# 1. 检查前端构建
cd frontend && npm run build && ls dist/

# 2. 检查 VITE_API_BASE_URL
grep VITE_API_BASE_URL frontend/.env  # 应指向后端地址

# 3. 检查 health 端点
curl -f http://localhost:8000/api/v1/health
```

## SSE 流式对话中断

**症状**：消息发出后只看到"正在思考..."但无回复。

**原因**：
1. LLM API 调用超时
2. nginx 代理缓冲区设置不当
3. 后端异常导致 stream 中断

**排查方案**：
```bash
# 1. 检查 nginx 配置中的 proxy_buffering 设置
# 应设置为 off
proxy_buffering off;
proxy_cache off;

# 2. 检查 API 日志
docker compose logs api

# 3. 直接测试
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-demo","message":"你好"}'
```

## 报告生成失败

**症状**：点击"生成报告"后报错或无响应。

**原因**：
1. 缺少 session token（必须先发一条消息）
2. 用户画像数据不足（缺少省份/分数等必需字段）
3. 会话没有 AI 回复记录

**解决**：
- 先在对话页发送一条消息，获得 session_token
- 确保已填写省份、分数等基本信息
- 等待 AI 完成回答后再生成报告

## RAG 知识搜索为空

**症状**：`/api/v1/knowledge/search` 返回空结果。

**原因**：
1. 公开发行版默认不附带知识库内容且 `ENABLE_RAG_KB=false`
2. `RAG_EMBEDDING_PROVIDER` 未正确配置
3. 搜索关键词不匹配

**排查方案**：
```bash
# 1. 检查 RAG 配置
echo $ENABLE_RAG_KB
echo $RAG_EMBEDDING_PROVIDER

# 2. 查看启动日志（分享前清除密钥、会话和考生信息）
docker compose logs api | grep "RAG"
```

启用前请先阅读 [数据许可](../DATA_LICENSE.md) 和 [数据来源要求](../DATA_SOURCES.md)，只导入
你有权处理的内容。
