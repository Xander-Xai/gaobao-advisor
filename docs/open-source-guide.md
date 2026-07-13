# gaobao-advisor 开源部署与定制指南

## 社区演示模式

根目录 [README](../README.md) 的 Docker 命令是公开发行版的标准启动路径。复制
`.env.example` 后无需填写任何 API Key；默认 `LLM_PROVIDER=demo`，RAG、联网搜索和语音关闭。

```bash
cp .env.example .env
docker compose up --build
curl -fsS http://localhost:8000/api/v1/health
```

健康响应应显示 `mode` 为 `demo`，`rag` 和 `voice` 为 `disabled`。演示数据库来自
`data/sample/` 中的 CC0 合成数据，不应被解释为真实高校或录取信息。

## 接入自有 LLM

只有在明确需要联网模型时才修改 `.env`：

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=replace-with-your-secret
LLM_MODEL=replace-with-your-model
```

也可使用配置中已有的 OpenAI 兼容 Provider 或本地 Ollama。部署者负责供应商条款、费用、
数据跨境和内容安全。密钥只能通过环境变量或密钥管理服务注入，不得写入配置文件或提交 Git。

## RAG 与自有数据

公开发行版不包含权利不明的知识库、专家语录或真实招生数据。启用 RAG 前：

1. 阅读 [数据许可](../DATA_LICENSE.md) 和 [数据来源要求](../DATA_SOURCES.md)。
2. 记录来源、权利人、许可、采集日期、处理步骤和隐私评估。
3. 将数据导入运行时数据库或自有挂载卷，不提交数据库、备份、索引和生成报告。
4. 显式设置 `ENABLE_RAG_KB=true` 及 embedding Provider；先在合成数据上验证。

## 生产安全配置

设置 `APP_ENV=production` 时，至少需要：

```dotenv
APP_ENV=production
SESSION_SECRET=replace-with-a-random-64-character-secret
CORS_ORIGINS=https://advisor.your-domain.invalid
```

生产启动校验会拒绝空 `SESSION_SECRET` 或未明确配置的 CORS。不要直接暴露 API；使用 HTTPS、
可信反向代理、访问控制和最小日志留存。漏洞和私密信息按 [安全政策](../SECURITY.md) 报告。

## 品牌定制

编辑 `config/brand.yaml` 中的品牌名称、报告标题、年度和封面配色，然后重启服务。项目名称和
标识的使用仍受 [商标政策](../TRADEMARKS.md) 约束；不得暗示教育主管部门或高校背书。

## 裸机开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn server.main:app --reload
```

前端使用 Node.js 20：

```bash
cd frontend
npm ci
npm run dev
```

锁定的 `requirements.lock` 用于 Python 3.11 容器构建；Python 3.10/3.11 开发与 CI 使用
`pyproject.toml` 的受支持范围解析依赖。

## 停止与清理

```bash
docker compose down --volumes --remove-orphans
```

这会删除命名的合成演示数据卷。自有生产数据应有独立、加密且经过恢复演练的备份策略。
