# 部署指南 — 雪峰 Agent v2.0

> 两种部署方式：完整版（Streamlit Cloud）+ 免费轻量版（扣子 Bot）

---

## 方式一：Streamlit Cloud（完整版，推荐）

### 前置条件
- GitHub 账号
- DeepSeek API Key（[免费注册](https://platform.deepseek.com)，约 1 元/500 次咨询）

### 步骤

#### 1. 推送代码到 GitHub

```bash
cd xuefeng-advisor
git remote add origin https://github.com/你的用户名/xuefeng-advisor.git
git push -u origin master
```

#### 2. 部署到 Streamlit Cloud

1. 打开 [share.streamlit.io](https://share.streamlit.io)
2. 点击 **New app**
3. 选择你的仓库 `xuefeng-advisor`
4. Main file path: `app.py`
5. 点击 **Deploy!**

#### 3. 配置 API Key（零配置给用户）

在 Streamlit Cloud 的 **Settings → Secrets** 中粘贴：

```toml
LLM_API_KEY = "sk-你的DeepSeek-API-Key"
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
LLM_PROVIDER = "deepseek"
ENABLE_SEARCH = "true"
```

保存后应用自动重启。

#### 4. 分享给用户

用户打开链接即可直接使用，无需任何配置。

**费用估算**：DeepSeek 约 1 元/500 次咨询，1000 个家长每人咨询 3 次 = 约 6 元。

---

## 方式二：扣子 Bot（免费轻量版）

### 前置条件
- 扣子账号（[coze.cn](https://www.coze.cn)，手机号注册即可）

### 步骤

#### 1. 创建 Bot

1. 登录 [coze.cn](https://www.coze.cn)
2. 点击 **创建 Bot**
3. 名称：`雪峰高考志愿顾问`
4. 描述：`基于张雪峰方法论的 AI 高考志愿填报助手`

#### 2. 配置人设与提示词

在 **人设与回复逻辑** 中粘贴 `system_prompt.md` 的核心内容：

```
你是雪峰高考志愿顾问，一个在高考志愿规划这一行干了十几年的老炮。
说话直，不绕弯子，敢说真话。

核心原则：
1. 不跳步：信息不全不给结论
2. 不说瞎话：不确定的数据标注"建议查最新官方信息"
3. 敢说"不行"：不切实际的想法要指出
4. 看人下菜碟：根据家庭背景给不同建议
...
```

#### 3. 上传知识库

在 **知识库** 中上传以下文件：
- `knowledge_base.md`（主知识库）
- `knowledge/00_ai_era_correction.md`（AI时代校正）
- `knowledge/07_new_gaokao_subject_selection.md`（新高考选科）
- `knowledge/08_vocational_strategy.md`（专科策略）

#### 4. 配置工作流

扣子自带工作流编辑器，可配置：
1. **意图识别**：判断是否为志愿咨询
2. **信息采集**：提取省份、分数、选科等
3. **知识检索**：从知识库中检索相关内容
4. **LLM 生成**：用豆包模型生成回答

#### 5. 发布

点击 **发布**，选择：
- **扣子 Bot 商店**（可被搜索到）
- **Web 链接**（可直接分享）
- **微信小程序**（需要企业主体）

---

## 两种方式对比

| 维度 | Streamlit Cloud | 扣子 Bot |
|------|----------------|---------|
| 完整度 | 完整（含数据库、验证） | 轻量（知识库+对话） |
| 成本 | LLM API 费用（约 1 元/500 次） | 完全免费 |
| 分享 | 网页链接 | 微信二维码/小程序 |
| 适合 | 深度使用、数据查询 | 快速体验、引流 |
| 部署难度 | ⭐ 简单 | ⭐⭐ 中等 |
| 维护 | 需关注 API 余额 | 无需维护 |

---

## 常见问题

### Streamlit Cloud 部署失败
- 检查 `requirements.txt` 是否完整
- 检查 `app.py` 是否有语法错误
- 查看 Streamlit Cloud 的日志

### API Key 费用过高
- 使用 DeepSeek（最便宜）
- 设置 `max_tokens` 限制回复长度
- 考虑用扣子 Bot 分流轻度用户

### 扣子 Bot 回答不准确
- 上传更完整的知识库
- 优化人设与提示词
- 配置工作流增加信息采集环节
