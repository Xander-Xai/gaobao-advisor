# Web 版部署指南

> gaobao-advisor Web版 — 三种部署方式，从免费到专业

---

## 🚀 Streamlit Cloud 一键部署（推荐，免费）

### 部署步骤

**1. 准备 GitHub 仓库**
```bash
cd gaobao-advisor
git init  # 如果尚未初始化
git add .
git commit -m "ready for deploy"
gh repo create gaobao-advisor --public --source=. --push
```

**2. 关联 Streamlit Cloud**
- 访问 https://share.streamlit.io
- 用 GitHub 账号登录
- 点击 "New app" → 选择 `gaobao-advisor` 仓库
- Main file: `app.py`

**3. 配置 Secrets（在 Advanced settings → Secrets）**
```toml
LLM_API_KEY = "sk-你的真实key"
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
```

**4. 点击 Deploy，等待 2-3 分钟即可访问**

### 限流配置（已在代码内置）

- 单 IP 每小时最多 20 次对话
- 每天最多 40 次对话
- 超出后展示友好提示

### 监控日志

Streamlit Cloud 的 "Logs" 标签页可实时查看 `[INFO]`/`[ERROR]` 日志。

---

## 方式一：本地运行（最快，5分钟）

### 前置条件
- Python 3.10+
- 已配置 .env 文件（API Key）

### 步骤
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（如果还没有 .env）
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key

# 3. 启动
streamlit run app.py
# 浏览器自动打开 http://localhost:8501
```

### Windows 用户
双击 `启动Web版.bat` 即可。

---

## 方式二：Streamlit Cloud 部署（免费，推荐）

> 零成本、公网可访问、微信可直接打开

### 步骤

#### 第1步：推送到 GitHub
```bash
cd gaobao-advisor
git add .
git commit -m "Add Streamlit web frontend"
git push origin master
```

#### 第2步：部署到 Streamlit Cloud
1. 打开 https://share.streamlit.io
2. 用 GitHub 账号登录
3. 点击 "New app"
4. 选择你的仓库：`你的用户名/gaobao-advisor`
5. Main file path: `app.py`
6. 点击 "Deploy!"

#### 第3步：配置 API Key（Secrets）
在 Streamlit Cloud 的 app 设置页面，点击 "Secrets"，添加：

```toml
[deepseek]
LLM_API_KEY = "sk-your-api-key-here"
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
```

#### 第4步：获取分享链接
部署成功后会得到一个链接，格式如：
`https://your-app-name.streamlit.app`

**这个链接可以直接在微信中打开！**

### 注意事项
- Streamlit Cloud 免费版有一定访问限制
- 如果流量大，考虑升级或迁移到自己的服务器
- 每次 GitHub 推送会自动重新部署

---

## 方式三：云服务器部署（¥50-100/月）

> 适合有稳定流量后，需要更高性能和自定义域名

### 推荐配置
- 阿里云/腾讯云轻量应用服务器：2核4G，¥50-100/月
- 操作系统：Ubuntu 22.04

### 部署步骤
```bash
# 1. SSH 登录服务器
ssh root@your-server-ip

# 2. 安装 Python 和依赖
apt update && apt install -y python3 python3-pip git
git clone https://github.com/你的用户名/gaobao-advisor.git
cd gaobao-advisor
pip3 install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
nano .env  # 填入 API Key

# 4. 后台运行
nohup streamlit run app.py --server.port 8501 --server.headless true &

# 5. 配置 Nginx 反向代理（可选，用于自定义域名）
apt install -y nginx
# 配置 /etc/nginx/sites-available/gaobao-advisor
```

### Nginx 配置示例
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 微信中打开的注意事项

Streamlit Web版可以在微信中直接打开，但需要注意：

1. **微信内置浏览器兼容性**：Streamlit 在微信中基本可用，但某些高级交互可能受限
2. **分享方式**：
   - 直接发送链接
   - 生成二维码（用草料二维码生成器）
   - 放在抖音/小红书简介中
3. **加载速度**：首次加载可能较慢（需要冷启动），后续会快很多

---

## 配置 API Key 的几种方式

### 方式A：DeepSeek（推荐，最便宜）
```
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```
- 价格：约 ¥1/百万 tokens
- 注册：https://platform.deepseek.com

### 方式B：通义千问（阿里，国内快）
```
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

### 方式C：智谱 GLM
```
LLM_API_KEY=your-key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4
```

---

## 后续升级路线

| 阶段 | 触发条件 | 升级内容 |
|------|---------|---------|
| MVP | 现在 | Streamlit Cloud 免费版 |
| 增长期 | 日活 100+ | 迁移到云服务器 |
| 爆发期 | 高考季日活 1000+ | 加 CDN + 数据库 + 用户系统 |
| 规模化 | 月收入 ¥10k+ | 考虑微信小程序版本 |

---

*gaobao-advisor · Web版部署指南 V1.0*

## 💰 运营成本估算

| 指标 | 数值 |
|------|------|
| 单次对话成本 | ~¥0.002 (DeepSeek) |
| 单用户单日上限 | 40 次 |
| 单用户单日成本 | ~¥0.08 |
| 1000 用户/日成本 | ~¥80 |

限流器是成本控制的核心，请勿关闭。
