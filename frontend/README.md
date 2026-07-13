# gaobao-advisor Frontend

Vue 3 SPA 前端 — 高考志愿 AI 顾问的对话界面。

## 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 | 组件框架 |
| Vite | 构建工具 |
| Pinia | 状态管理 |
| Vue Router | 路由管理 |
| Tailwind CSS | 样式框架 |
| DOMPurify | XSS 消毒 |
| Vitest | 单元测试 |

## 目录结构

```
src/
├── main.js                      # 应用入口
├── App.vue                      # 根组件
├── router/index.js              # 路由（/ /report/:id /profile/:sessionId /admin）
├── stores/
│   ├── chat.js                  # 对话状态（会话/消息/流式/槽位）
│   ├── scene.js                 # 场景状态（gaokao/kaoyan/career）
│   ├── voice.js                 # 语音模态框可见性
│   └── report.js                # 报告生成状态
├── components/
│   ├── chat/                    # 对话组件（ChatArea, MessageBubble, MessageInput）
│   ├── layout/                  # 布局组件（AppHeader, AppSidebar, AppRightPanel）
│   └── voice/                   # 语音组件（VoiceModal, VoiceRipple, LiveSubtitle）
├── views/
│   ├── ChatView.vue             # 主界面（三栏布局 + 语音浮窗）
│   ├── AdminView.vue            # 管理面板（占位）
│   └── ReportView.vue           # 报告页面（占位）
├── api/client.js                # API 客户端（SSE 流式 + 引导）
├── composables/useVoice.js      # WebSocket 语音通话
└── utils/sanitize.js            # HTML 消毒 + Markdown 渲染
```

## 关键架构

### 数据流

```
用户输入 → MessageInput
  → chatStore.sendMessage()
    → chatAPI.send() POST /api/v1/chat
      → SSE 流式解析（token / slots / emotion / structured 事件）
    → messages[] 增量更新
  → ChatArea 自动滚动
```

### SSE 流式事件

| 事件 | 触发时机 | 数据 |
|------|---------|------|
| `slots` | 槽位提取后 | 用户画像字段 |
| `emotion` | 情绪检测后 | 情绪状态/策略 |
| `structured` | 结构化卡片生成后 | StructuredPlanningCard |
| `token` | LLM 推理中 | token 文本块 |
| `error` | 知识图谱查询失败 | 错误信息 |
| `degraded` | LLM 降级回退时 | 降级原因 |
| `done` | 回复完整 | session_token（HMAC 签名）|

### 语音通话

VoiceModal 通过 `useVoice` composable 打开 WebSocket 连接至 `/ws/call`：
- PCM 音频帧上行 → ASR → LangGraph → TTS → PCM 音频帧下行
- `LiveSubtitle` 显示实时识别文本 + AI 回复
- `VoiceRipple` 动画表示说话状态
- WebSocket 错误消息已处理，异常时自动关闭连接并提示用户

### 消息持久化

对话消息自动持久化到 `localStorage`，页面刷新后会话历史不丢失。每个会话以 `chat_messages_{sessionId}` 为 key 存储。

### 报告生成

报告生成由 ChatView 触发：当对话中产出结构化规划卡片后，用户可点击生成报告，`reportStore` 调用后端 API 生成并跳转至 `/report/:id` 查看结果。

## 开发与门禁

```bash
npm ci
npm run dev     # 开发服务器（默认端口 3080）
npm run build   # 生产构建
npm test -- --run
npm audit --audit-level=moderate
npm run lint    # ESLint 检查
```

Node.js 基线为 20。不要使用 `npm install` 随意改写锁文件；依赖变更应同时提交
`package.json` 与 `package-lock.json`，并通过测试、生产构建和依赖审计。

## API 代理

开发模式下，Vite 配置代理将 `/api/` 和 `/ws/` 转发到 FastAPI 后端（默认 `localhost:8000`）。

默认后端运行在无需密钥的社区演示模式。界面和 API 返回的演示内容均为合成示例，项目不是
官方志愿填报工具。RAG 和语音默认关闭，启用前请阅读根目录的
[数据许可](../DATA_LICENSE.md)、[隐私政策](../PRIVACY.md) 和 [支持范围](../SUPPORT.md)。
