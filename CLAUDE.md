# gaobao — 高考志愿AI顾问 项目规则

## 提示词版本管理（自动）

当你修改 `system_prompt.md` 或任何 `prompts/` 下的文件时，**必须自动执行归档**：

1. 将修改后的 system_prompt.md 复制到 `prompts/system/v{版本号}.md`
2. 更新 `prompts/CHANGELOG.md`，记录日期、改动点、效果评估
3. 归档命令：`python3 prompts/extract_prompt.py --file system_prompt.md --version {版本号} --note "说明"`

**版本号规则**：
- 大版本（v2→v3）：人设/架构重构
- 小版本（v2.0→v2.1）：参数调优/新增场景

**会话归档**：当对话中产出了有价值的提示词迭代（实验、对比、调优），即使最终没有合入 system_prompt.md，也要归档到 `prompts/sessions/`：
```bash
python3 prompts/extract_prompt.py --session "主题名" --note "简要说明"
```

## 网络查询

内置的 `WebSearch` 和 `WebFetch` 工具不可用（API 代理不支持 web 端点）。
**不要使用这两个工具**，使用以下替代方案：

### 方案一：web-tool（轻量搜索）
```bash
# 搜索
web-tool search "关键词" [结果数量]

# 抓取网页
web-tool fetch "https://example.com" [extract_mode] [max_length]
```

搜索引擎优先级：Tavily API → Bing → DuckDuckGo（自动降级）

### 方案二：open-websearch MCP（多引擎搜索）
MCP 服务器已配置，支持 Bing / 百度 / CSDN / DuckDuckGo / Brave / 掘金等多引擎。
无需 API Key，MCP 工具名为 `mcp__open-websearch__search`。

### 方案三：联网 Skills
- **deep-research**：`/research 主题` 一键深度调研，全自动出报告
- **web-access**：三层联网通道（MCP + CLI + 浏览器 CDP）

## 多媒体生成

基于 Agnes AI（完全免费，无需额外配置）：

### 生图（agnes-image）
```bash
cd ~/.agents/skills/agnes-image
python3 scripts/generate_image.py "提示词" --size 1024x1024 -o ./output
python3 scripts/generate_image.py "风格转换" --image 参考图.png -o ./output
```

### 生视频（agnes-video）
```bash
cd ~/.agents/skills/agnes-video
python3 scripts/generate_video.py create "提示词" -o ./output
python3 scripts/generate_video.py status <task_id> -o ./output
```
视频为异步生成，提交后自动轮询（通常 2-4 分钟）。

### 图片理解（agnes-vision）
```bash
cd ~/.agents/skills/agnes-vision
python3 scripts/vision.py "描述这张图片" --image screenshot.png
python3 scripts/vision.py "这段代码有什么bug？" --image code.png
python3 scripts/vision.py "提取所有文字" --image doc.png -o result.txt
```
模型 `agnes-2.0-flash`，支持图片识别、OCR、代码排错、UI 分析、图表解读。
