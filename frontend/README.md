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
├── router/index.js              # 路由（/ /report/:id /admin）
├── stores/
│   ├── chat.js                  # 对话状态（会话/消息/流式/槽位）
│   ├── scene.js                 # 场景状态（gaokao/kaoyan/career）
│   └── voice.js                 # 语音模态框可见性
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
| `degraded` | LLM 降级时 | 降级原因 |
| `done` | 回复完整 | session_token（HMAC 签名）|

### 语音通话

VoiceModal 通过 `useVoice` composable 打开 WebSocket 连接至 `/ws/call`：
- PCM 音频帧上行 → ASR → LangGraph → TTS → PCM 音频帧下行
- `LiveSubtitle` 显示实时识别文本 + AI 回复
- `VoiceRipple` 动画表示说话状态

## 开发

```bash
npm install
npm run dev     # 开发服务器（默认端口 5173）
npm run build   # 生产构建
npm run test    # 运行单元测试
npm run lint    # ESLint 检查
```

## API 代理

开发模式下，Vite 配置代理将 `/api/` 和 `/ws/` 转发到 FastAPI 后端（默认 `localhost:8000`）。
