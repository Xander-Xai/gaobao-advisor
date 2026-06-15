# 验收回退修复计划

> 根因分类见 ACCEPTANCE-REPORT-2026-06-15.md → 第四章

## A 组 — E2E 401 认证副作用（6 tests）
- `test_integration_e2e.py` (5个): 添加 `create_session_token` + `Authorization` header
- `test_routes.py::test_chat_returns_sse` (1个): 同上

## B 组 — 旧 unittest 期望未更新（4 tests）
- `test_quality_legacy.py::TestAiEraRisk` (4个): 更新 risk_zone 字符串 + summary 长度

## C 组 — SSE 认证（1 test）
- `test_chat_sse.py` (1个): 添加 auth token

## D 组 — 假图测试 auth（1 test）
- `test_auth_endpoints.py::TestChatTokenIssuance` (1个): 添加 auth token 到 fake graph 测试

## E 组 — ImportError（1 collection error）
- `test_agent_core.py`: 更新 import 路径（slots/extractor.py 替代 agent.py）

## 总览
| 组 | 文件 | 影响 | 修复方式 |
|----|------|------|---------|
| A | tests/test_integration_e2e.py | 5 fail | 添加 `from server.auth import create_session_token` + `headers={"Authorization": f"Bearer {token}"}` |
| A | tests/test_routes.py | 1 fail | 同上 |
| B | tests/test_quality_legacy.py | 4 fail | 更新 assertEqual 期望值 |
| C | tests/test_chat_sse.py | 1 fail | 添加 auth token |
| D | tests/test_auth_endpoints.py | 1 fail | 添加 auth token 到 fake graph |
| E | tests/test_agent_core.py | 1 error | 更新 import 路径 |
