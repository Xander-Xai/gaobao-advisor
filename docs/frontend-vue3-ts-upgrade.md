# Vue 3 + TypeScript 能力补齐：真实代码证据与 AI Coding 提示词

## 基线与边界（2026-10-30）

- 仓库：`Xander-Xai/gaobao-advisor`，原前端入口 `frontend/src/main.js`，Vue 3 + Pinia + Vue Router + Vite。
- 原 `AdminView.vue` 只有健康查询与模块描述。不存在已经验证的管理后台登录、权限管理、写入 API。
- 后端：`GET /api/v1/health` 提供数据库 / RAG 健康状态、`data_profile`；`GET /api/v1/data/schools` 支持按 `province` / `level` 游标查询，传 `school_name` 时改为 `{count,results}` 单校检索。
- 当前公开演示数据为 `SYNTHETIC_DEMO`。严禁声称提供真实招生数据库或实际志愿填报建议。
- MCP Evidence Gate 的独立 TypeScript CLI 不能冒充本仓库 Vue TypeScript 经历。

## 本 PR 实现范围

1. `src/api/admin.ts`：TypeScript 后端契约、只读 API、运行时解析与失败时关闭、AbortSignal 透传。
2. `src/views/AdminView.vue`：`<script setup lang="ts">`、健康服务与 RAG 状态、只读院校列表、省份/层次筛选、名称查询、游标分页、加载/空/错误/重试状态、卸载取消请求。
3. Vitest：API 契约及异常测试、组件交互测试。
4. `frontend/tsconfig.json`：严格检查的新 TS 垂直切片，历史 JS 尚未迁移；生产构建依然由 Vite 处理。

### 未实现，不允许在简历或面试中声称已实现

- 管理员登录 / RBAC / 审计日志 / 院校 CRUD / 运营统计：后端未提供相应契约。
- 整个前端全面 TS 迁移：`main.js`、router、Pinia stores、其余 Vue 文件仍为 JS。
- 端到端生产部署验证 / 浏览器真实联调：以实际 CI、运行演示与观测记录为准。

## 后续阶段工程要求

**P1：补齐 TypeScript toolchain**
- 使用经校验的 Node 版本安装 `typescript` / `vue-tsc` 作为 devDependencies，连同 `package-lock.json` 更新、`npm ci` 验证。
- 为新增 TS 切片运行 `vue-tsc --noEmit -p tsconfig.json`，CI 将其设为必过门禁。
- 实施后逐模块迁移 `main.js`、Router、Pinia、Chat/Report 视图与 API；保持后端合同一致。

**P2：企业后台标准**
- 新增管理员 AuthN/RBAC 必须先定义服务端认证、角色、资源与权限映射，鉴权与审计在服务端完成；前端按钮隐藏不算权限控制。
- 为院校 / 数据版本管理设计受保护的后端 CRUD，校验、分页、并发冲突、审计日志；先通过后端集成测试再开放前端操作。
- 再补上真实数据脱敏、访问安全、监控和部署压测；绝不使用 SYNTHETIC_DEMO 证明真实业务数据准确性。

## 可直接交给 AI Coding Agent 的开发提示词

```text
你是资深 Vue 3 + TypeScript + FastAPI 全栈工程师。目标仓库 Xander-Xai/gaobao-advisor。
目标是形成“企业级全栈工程能力的可验证证据”，而不是产生一个无法连通后端的 UI Demo。

执行规则：
1. 先读取仓库 README、SPEC、frontend/package.json 与 package-lock、src/api/client.js、src/views/AdminView.vue、server/routes/health.py、server/routes/data.py、.github/workflows/ci.yml。
2. 新建 feat 分支，不直接改 master；检查已有 PR，避免与未合并工作冲突。
3. 以现有真实 API 契约为单一事实来源；保护 SSE/Chat、Voice、Report 原链路。
4. 首先完成只读工作台：健康指标、RAG 降级展示、院校筛选与游标分页、loading/empty/error/retry/abort。名称搜索与游标分页是互斥模式，不得伪造页码或总数。
5. 使用 Vue 3 script setup + TypeScript。拆分 API 类型、接口状态与展示组件。API 返回值实施运行时校验，对后端错误 fail-closed，禁止 mock 成功返回。
6. 添加 Vitest 契约测试与组件交互测试，覆盖筛选重置、next/previous cursor、401/403/5xx、网络异常、并发请求覆盖、组件卸载取消请求、非法 API 响应。
7. 安装并锁定 TypeScript/vue-tsc，更新 package-lock，npm ci + vue-tsc --noEmit + vitest --run + vite build 必须全部通过。把命令放入 CI。
8. 若无后端 AuthN/RBAC/CRUD 合约，不实现假管理员写入操作；要实施这些能力，先提出 API 和数据库迁移方案、服务端权限测试，再开发前端。
9. 交付 PR、运行截图/可复现命令、CI 链接、变更对照、待办/风险、明确真实完成与未完成项；不得虚构通过状态或企业上线经历。
10. 禁止修改非相关文档、删除历史功能、把演示数据包装成真实招生数据。优先小范围、可回退、可验收的 PR。
```

## 面试表述（仅在 CI 和实际运行通过后使用）

“我原来的前端是 Vue 3 JavaScript，后面针对院校查询做了一次渐进式 TypeScript 改造。我把院校与健康接口加上类型契约，处理了两种后端返回结构、游标分页、错误空态和请求取消，并配套 Vitest 测试。这是有实际前后端接口对接的只读工作台；管理员认证和 CRUD 还没有完成，所以我不会将其说成完整权限后台。”
