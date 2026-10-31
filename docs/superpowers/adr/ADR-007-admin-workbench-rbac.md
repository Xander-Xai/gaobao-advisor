# ADR-007: 运营后台使用独立管理员令牌与 RBAC

- 状态：Accepted
- 日期：2026-10-30
- 关联：Phase 1 / `server/admin/*`、`frontend/src/views/AdminView.vue`

## 背景

原项目的 HMAC token 只证明「请求者拥有某个匿名聊天 session」，没有账号、
角色、过期时间。直接把它当管理员令牌会造成权限提升：任何拿到聊天 token 的
人都会获得后台写权限。另一方面，运营后台需要真实的列表、质检、审核与审计，
不能只做健康检查面板。

## 决策

1. **独立令牌域**：管理员 token 使用 `ADMIN_TOKEN_SECRET` 签名，载荷包含
   `aud=gaobao-admin`、`sub`、`role`、`iat`、`exp`、`jti`。聊天 token 的签名
   输入与 audience 都不同，二者不可互换。
2. **凭据外部注入**：`ADMIN_USERS_JSON`（或多个用户）或单用户
   `ADMIN_USERNAME + ADMIN_PASSWORD_HASH`。密码使用 PBKDF2-HMAC-SHA256
   （默认 600k 迭代），禁止在生产使用明文 `ADMIN_PASSWORD`。
3. **角色层级**：`viewer < operator < admin`。读接口 viewer+，创建任务
   operator+，审核/审计 admin。权限由 FastAPI 依赖执行，前端隐藏按钮只是
   UX，不是安全边界。
4. **fail-closed**：未配置管理员时后台返回 503；生产环境显式启用管理员却缺少
   `ADMIN_TOKEN_SECRET` 时启动失败。
5. **Bearer 而非 Cookie**：避免 CSRF 与跨站自动携带；前端把 token 放在
   `sessionStorage`（关闭标签页即失效）。代价是 XSS 可读，因此审计/错误消息
   统一脱敏，且未引入第三方脚本。
6. **审计与脱敏**：创建任务、任务完成/失败、审核写入 `operation_audit_logs`；
   审计详情递归脱敏姓名、手机号、身份证、邮箱、token。
7. **分布式限流（2026-10-31）**：`ADMIN_RATE_LIMIT_BACKEND=auto|memory|redis`。
   Redis 模式使用 Lua 原子滑动窗口（sorted set + Redis TIME + TTL）；登录同时限制
   IP 与用户名，任务创建同时限制管理员与 IP。生产不允许 memory；Redis 不可用时
   返回 503 `SECURITY_BACKEND_UNAVAILABLE`，不静默回退。
8. **Token 撤销（2026-10-31）**：新增 `admin_token_revocations` 持久化表，只存
   HMAC-SHA256(jti) 摘要。签名/audience/exp/当前用户/当前角色先校验，再查撤销；
   `POST /api/v1/admin/auth/logout` 幂等撤销当前 Token，其他 Token 不受影响。
   Redis 重启不会恢复已撤销 Token；数据库不可用时 admin 请求 fail-closed。
9. **可信代理（2026-10-31）**：默认忽略 `X-Forwarded-For`；只有直接 peer 在
   `ADMIN_TRUSTED_PROXIES` CIDR 内才从右向左解析，取第一个非可信 hop。限流与审计
   使用同一规范化 IP 哈希。
10. **退出语义（2026-10-31）**：前端先调用后端 logout；网络失败时清理本地状态并
    明确提示“服务端撤销未确认”，不谎称成功。

## 备选方案

| 方案 | 未采用原因 |
|---|---|
| 复用聊天 session token | 无法表达角色/过期，等价于权限提升 |
| 引入完整 OAuth/OIDC | 对本项目过重；无外部 IdP，演示价值低于维护成本 |
| HttpOnly Cookie + CSRF | 需要额外的 CSRF token 与 SameSite 策略；当前 SPA 用 Bearer 更直接 |
| 前端路由守卫作为权限 | 可被绕过；必须后端校验 |

## 后果

- 正面：权限边界清晰、可测试；生产配置错误会尽早失败；审计可追溯。
- 正面（2026-10-31）：支持多副本共享限流、服务端 Token 撤销、可信代理边界和
  Redis 故障 fail-closed；默认 SQLite/无 Redis 开发模式仍可用。
- 负面：`sessionStorage` 仍受 XSS 影响；撤销表按过期清理，无后台清理任务；
  Redis 限流单区域；无 MFA/OIDC/刷新令牌。
- 边界：这不是完整 IAM/MFA，不承诺多租户隔离或生产 SLA。

## 验收

- `tests/test_admin_auth.py`：401/403、聊天 token 拒绝、过期/篡改、生产
  fail-closed、登录限流。
- `tests/test_admin_quality_jobs.py`：角色校验、乐观锁审核、审计、回滚。
- `frontend/src/views/__tests__/AdminView.spec.ts`：登录、403、只读角色、logout。
- `tests/test_admin_security.py`：撤销/幂等/过期边界/可信代理/503。
- `tests/test_admin_limits_redis.py`：真实 Redis 原子并发、双客户端/双进程、
  TTL、Redis flush 后撤销仍有效。
- `docs/security/admin-auth-hardening.md`：威胁模型、配置和残余风险。
