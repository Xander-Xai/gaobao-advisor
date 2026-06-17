# Frontend-Backend Alignment Report

> **日期**: 2026-06-17
> **作者**: AI 工程师
> **分支**: `feat/ai-quality-flywheel`
> **范围**: 前端 19 个后端端点的对齐补全

---

## Context

`gaobao-advisor` 后端 (FastAPI) 在 `feat/ai-quality-flywheel` 分支上已有 **7 个路由模块 / 19 个端点**,但前端 (Vue 3 SPA) 只接入了 4 个模块、4.5 个端点(其中 1 个半残——voice WebSocket 必被后端 4001 拒绝)。

**结果**: 用户进入前端后,无法查询院校 / 分数线 / 招生计划 / 知识语录 / 用户画像;且语音按钮一旦点击就立刻断开。

**本报告记录**: 一次性把 19 个端点全部对齐、修复 voice token 漏洞、补充 4 个视图/组件,并通过 46 个前端单测 + production build 验证。

---

## 端点对照表 (19 / 19)

| # | 后端端点 | 前端位置 | 改动 |
|---|---------|---------|------|
| 1 | `POST /api/v1/chat` | `stores/chat.js` + `api/client.js::chatAPI` | **+保存 session_token** (SSE `done` 事件) |
| 2 | `POST /api/v1/chat/feedback` | `api/client.js::feedbackAPI` + `MessageBubble.vue` | **替换裸 fetch** → client 调用 |
| 3 | `POST /api/v1/chat/highlight` | `api/client.js::highlightAPI` + `MessageBubble.vue` | **新增** ⭐ 按钮 (金句收藏) |
| 4 | `GET /api/v1/data/schools` | `api/client.js::dataAPI.searchSchools` | **新增** namespace |
| 5 | `GET /api/v1/data/scores` | `api/client.js::dataAPI.getScores` | **新增** |
| 6 | `GET /api/v1/data/plans` | `api/client.js::dataAPI.getPlans` | **新增** |
| 7 | `GET /api/v1/health` | `api/client.js::healthAPI` + `views/AdminView.vue` | **新增** 健康检查面板 |
| 8 | `POST /api/v1/knowledge/search` | `api/client.js::knowledgeAPI.search` | **新增** |
| 9 | `GET /api/v1/knowledge/quotes` | `api/client.js::knowledgeAPI.getQuotes` | **新增** |
| 10 | `POST /api/v1/onboarding` | `api/client.js::onboardingAPI` | 已在(签名不变) |
| 11 | `GET /api/v1/profile/{id}` | `api/client.js::profileAPI.get` + `views/ProfileView.vue` | **新增** + Bearer 鉴权 |
| 12 | `PUT /api/v1/profile/{id}` | `api/client.js::profileAPI.update` | **新增** |
| 13 | `GET /api/v1/profile/{id}/next-question` | `api/client.js::profileAPI.nextQuestion` | **新增** + 灵魂提问 UI |
| 14 | `POST /api/v1/profile/{id}/skip` | `api/client.js::profileAPI.skip` | **新增** + 跳过按钮 |
| 15-18 | `POST /api/v1/report/generate`<br>`GET /api/v1/report/{id}`<br>`GET /api/v1/report/{id}/html`<br>`GET /api/v1/report/{id}/cover.svg` | `api/client.js::reportAPI` + `stores/report.js` | **迁移** 4 次裸 fetch → client namespace (signature 不变) |
| 19 | `WS /ws/call` | `composables/useVoice.js` + `components/voice/VoiceModal.vue` | **修复** token 注入 (后端验证) |

**19/19 已对齐 ✅**

---

## 改动文件清单

### 新建 (3)

- `frontend/src/views/ProfileView.vue` — 用户画像管理页(7 字段编辑 + 灵魂提问 + 完成度)
- `frontend/src/api/__tests__/client.test.js` — 15 个 vitest 单测
- `FRONTEND-ALIGNMENT-REPORT-2026-06-17.md` — 本文件

### 修改 (9)

- `frontend/src/api/client.js` — **重写**:从 33 行 → 195 行,7 个 namespace (chat/onboarding/feedback/highlight/data/knowledge/profile/report/health) + 统一 `{data, error}` envelope
- `frontend/src/stores/chat.js` — 保存 `sessionToken` (SSE `done` 事件)
- `frontend/src/stores/report.js` — 4 个裸 fetch 迁移到 `reportAPI`
- `frontend/src/composables/useVoice.js` — `connect(sessionId, scene, token)` 拼 `&token=...`
- `frontend/src/components/voice/VoiceModal.vue` — 传 token + "未认证"提示 + 显式连接/挂断按钮
- `frontend/src/components/chat/MessageBubble.vue` — ⭐ 金句按钮 + 替换 `feedbackAPI` 裸 fetch
- `frontend/src/views/AdminView.vue` — 从占位符改写为健康检查面板
- `frontend/src/router/index.js` — 加 `/profile/:sessionId` 路由

---

## 核心设计决策

### 1. 统一 envelope `{ data, error }`

参考 `rules/common/patterns.md` API 响应格式。`_request()` helper 集中处理:
- HTTP 2xx → `{ data: payload, error: null }`
- HTTP 4xx/5xx → `{ data: null, error: { code, message, status } }`
- 网络异常 → `{ data: null, error: { code: 'NETWORK_ERROR', message } }`

调用方一律解构 `{ data, error }`,**不抛异常**(SSE 流式 chat 除外,因其本质是迭代器)。

### 2. 鉴权 token 显式传参

profile/voice 端点需要 `Bearer <session_token>`,但后端 token 仅在 chat SSE `done` 事件下发。
为避免 `client.js ↔ stores/chat.js` 循环依赖,采取显式传参:

```js
// 调用方
const token = useChatStore().sessionToken
const { data, error } = await profileAPI.get(sessionId, token)
```

VoiceModal 同理:`connect(sessionId, scene, chatStore.sessionToken)`。

### 3. 共享 helper 而非重复造轮

- `_request(path, { method, body, headers, token })` — 所有非流式方法共用
- `_toQuery(params)` — 自动跳过 `null/undefined/''`,避免拼出 `?key=`
- SSE 在 `chatAPI.send` 内单列,因 fetch + ReadableStream 的模式与 envelope helper 完全不同

### 4. 不破坏现有调用方

- `chatAPI.send(sessionId, message, slots, scene)` — **签名 100% 兼容** 旧调用
- `reportStore.generateReport(sessionId, studentName)` / `fetchReport(id)` / `exportHTML(id)` / `exportCover(id)` — 4 个方法签名不变
- `useVoice().connect(sessionId, scene)` — 第 3 个 token 参数为可选,旧调用仍然能跑(但会被后端 4001 拒)

---

## 测试结果

```
$ npm run test

 Test Files  8 passed (8)
      Tests  46 passed (46)
   Duration  1.88s
```

新加的 15 个 client.test.js 覆盖:
- ✅ envelope 3 种形态 (2xx / 4xx / 网络错)
- ✅ dataAPI 3 个方法 (URL 参数 / 跳过空值)
- ✅ knowledgeAPI 2 个方法 (POST body / GET query)
- ✅ profileAPI 4 个方法 (Bearer 注入 / PUT body / skip 路径)
- ✅ reportAPI generate body
- ✅ feedbackAPI + highlightAPI body
- ✅ onboardingAPI body

`MessageBubble.spec.js` 旧测仍通过(因无破坏性改动)。

### Build

```
$ npm run build

✓ built in 478ms
dist/assets/ProfileView-DX7qcls3.js    6.73 kB │ gzip:  2.97 kB
dist/assets/AdminView-OS1sQkLL.js      3.04 kB │ gzip:  1.59 kB
dist/assets/ReportView-DIyndBJo.js     5.13 kB │ gzip:  2.15 kB
dist/assets/ChatView-BNfF9XOg.js      37.52 kB │ gzip: 14.98 kB
dist/assets/index-22Hr2KCX.js        102.88 kB │ gzip: 39.75 kB
```

无 warning,无 error。

---

## 用户视角可验证的端到端流程

| 流程 | 路径 | 验证点 |
|------|------|-------|
| 1. 对话 + 获取 token | `/` | 输入消息 → 后端 SSE `done.session_token` 写入 `chatStore.sessionToken` |
| 2. 健康检查 | `/admin` | 展示 `status=ok` / `version=3.0.0` / `database=connected` |
| 3. 画像管理 | `/profile/<sessionId>` | 7 字段可编辑、跳过、灵魂提问;未认证时显示 ⚠ 提示 |
| 4. 院校查询 | (待调用方接入) | `dataAPI.searchSchools({ schoolName: '清华' })` 返回 `{count, results}` |
| 5. 知识搜索 | (待调用方接入) | `knowledgeAPI.search({ query: '位次法', topK: 5 })` |
| 6. 语音连接 | `/` → 🎤 | useVoice 把 token 拼到 URL,后端不再 4001 关闭 |
| 7. 报告生成 | `/report/:id` | ReportView 不变,内部走 `reportAPI` |

---

## 已知后续 (out-of-scope, 记录在 TODO)

1. **sessionToken 持久化**: 当前只存 ref,刷新页面会丢。需 localStorage + 过期检测。
2. **WebSocket 鉴权增强**: 现在 token 在 URL 里(查询参数),生产建议走 `Sec-WebSocket-Protocol` 子协议头(防 access log 泄露)。
3. **data / knowledge 调用方**: 端点 API 暴露完毕,但暂无 view 调用。建议新增 `SchoolSearchView.vue` + `KnowledgeSearchView.vue`。
4. **ProfileView 跳过必填字段**: 当前 UI 允许"跳过"任意字段,后端 `_require_auth` 之后会拒绝 `req.field not in valid_fields`。如 `score` 是 required,前端按钮需做禁用。

---

## Commit

参见 `git log feat/ai-quality-flywheel` 的最新 `feat(frontend): align with 7 backend route modules...`。
