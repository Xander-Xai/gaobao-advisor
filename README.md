# gaobao-advisor — 高考志愿 AI 顾问

[![CI](https://github.com/yandexuanxuan/gaobao-advisor/actions/workflows/ci.yml/badge.svg)](https://github.com/yandexuanxuan/gaobao-advisor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Node.js 20](https://img.shields.io/badge/node-20-339933.svg)](https://nodejs.org/)

一个基于 FastAPI、LangGraph 和 Vue 3 的高考志愿咨询软件框架。社区版默认以无需密钥、
不访问模型服务的合成数据演示模式启动，适合评估代码、参与开发和搭建自有合规数据管线。

当前版本：3.1.0（社区候选版；尚未创建远程 Release）。

> **重要说明：** 本项目与教育主管部门、考试院及高校无隶属或授权关系，不是官方志愿填报
> 工具。演示输出不能用于真实志愿决策；实际使用前必须依据省级考试院和高校的最新官方信息核验。

## 三分钟启动（无需 API Key）

需要 Docker 与 Docker Compose v2：

```bash
git clone https://github.com/yandexuanxuan/gaobao-advisor.git
cd gaobao-advisor
cp .env.example .env
docker compose up --build
```

打开 <http://localhost:3080>。API 健康检查位于
<http://localhost:8000/api/v1/health>，应显示 `mode: demo`，且 RAG/语音为 `disabled`。

首次启动会将 `data/sample/` 中的 CC0 合成数据写入独立 Docker volume。示例仅包含
3 所虚构院校、3 个虚构专业和 6 条虚构分数记录，不包含真实考生或真实录取结果。

停止并删除演示数据：

```bash
docker compose down --volumes
```

## 功能状态

| 状态 | 能力 | 社区版说明 |
|---|---|---|
| 稳定 | SSE 多轮对话、槽位提取、合成数据查询、健康检查 | 默认 demo provider，全程明确标注合成演示和非官方性质 |
| 稳定 | 用户画像、报告 API、HTML/SVG 报告 | 使用前需自行评估隐私、留存和真实数据授权 |
| 实验 | 自有 LLM / Ollama / OpenAI 兼容 Provider | 需要显式配置；费用、内容与数据传输由部署者负责 |
| 实验 | RAG、向量索引、知识检索 | 默认关闭；公开发行版不附带权利不明的知识库或行业语料 |
| 实验 | MCP 接入、质量评分与监控 | 接口可能变化，生产采用前需独立验证 |
| 不可直接用 | 实时语音端到端链路 | 默认关闭，需自备并验证 ASR/TTS 服务 |

公开仓库不内置真实院校、专业、录取分数、招生计划、专家语录或考生数据。“可公开访问”
不等于“允许再分发”。数据边界和导入要求见 [DATA_LICENSE.md](DATA_LICENSE.md) 与
[DATA_SOURCES.md](DATA_SOURCES.md)。

## 使用自有模型或数据

复制 `.env.example` 后，可显式切换兼容 Provider；默认值不会联网：

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=replace-with-your-secret
LLM_MODEL=replace-with-your-model
ENABLE_RAG_KB=false
VOICE_ENABLED=false
```

不要提交 `.env` 或密钥。生产环境还必须设置稳定的 `SESSION_SECRET` 和明确的
`CORS_ORIGINS`；启动时会拒绝缺少这些安全配置的 production 模式。详细步骤见
[开源部署与定制指南](docs/open-source-guide.md)。

自有数据必须先确认来源、权利人、许可、采集日期、允许用途和隐私状态，再通过导入脚本
写入运行时数据库。数据库、备份、报告、日志、对话和真实用户资料不得提交到仓库。

## 本地开发

支持 Python 3.10/3.11 与 Node.js 20。推荐使用独立虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn server.main:app --reload
```

另一个终端启动前端：

```bash
cd frontend
npm ci
npm run dev
```

提交前运行与 CI 相同的核心门禁：

```bash
ruff check .
ruff format --check .
pytest tests/ --cov-fail-under=70
python scripts/check_docs.py
python scripts/check_licenses.py
bash scripts/audit_open_source.sh
cd frontend && npm ci && npm test -- --run && npm run build && npm audit --audit-level=moderate
```

完整命令和贡献边界见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 架构

```text
config/       配置加载、品牌与调优参数
server/       FastAPI 路由、LangGraph、服务与报告
db/           SQLite 模型和查询层
quality/      回答质量与评估模块
frontend/     Vue 3 / Vite / Pinia 单页应用
data/sample/  CC0 合成演示数据
scripts/      初始化、导入与发布门禁脚本
```

## 文档与社区政策

- [交付状态与最终验收](docs/finalization/FINAL_CI_MATRIX.md)
  - [数据恢复与质量](docs/finalization/DATA_RECOVERY_AND_QUALITY.md)
  - [演示模式契约](docs/finalization/DEMO_MODE_CONTRACT.md)
  - [安全与许可阻塞项](docs/finalization/SECURITY_AND_LICENSE_BLOCKERS.md)
  - [部署指南](docs/finalization/DEPLOYMENT_GUIDE.md)
  - [面试指南](docs/finalization/INTERVIEW_GUIDE.md) · [简历可用陈述](docs/finalization/RESUME_CLAIMS.md)
- [开源部署与定制](docs/open-source-guide.md)
- [FAQ 与故障排除](docs/faq-troubleshooting.md)
- [API 契约](docs/API-CONTRACT.md)
- [贡献指南](CONTRIBUTING.md) 与 [行为准则](CODE_OF_CONDUCT.md)
- [安全政策](SECURITY.md)、[隐私政策](PRIVACY.md) 与 [支持范围](SUPPORT.md)
- [数据许可](DATA_LICENSE.md)、[数据来源](DATA_SOURCES.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)
- [商标政策](TRADEMARKS.md) 与 [变更日志](CHANGELOG.md)

## 许可证

有权许可的源代码和文档采用 [MIT License](LICENSE)。数据、第三方内容、图片、模型输出和
用户内容不因位于同一项目目录而自动获得 MIT 授权，详见 [DATA_LICENSE.md](DATA_LICENSE.md)。
