# Todo: 审计修复执行列表

## Phase 1: 架构清理（已部分完成）
- [x] 1.1 删除 `api_server.py`（已移除）
- [x] 1.2 `app.py` 已不再作为主入口（FastAPI 替代）
- [x] 1.3 Dockerfile 已更新为 FastAPI 模式
- [x] 1.4 `requirements-api.txt` 已合并到主依赖

## Phase 2: 文档修复
- [x] 2.1 README 已重写（2026-06-28）
- [x] 2.2 项目结构树已更新

## Phase 3: 依赖锁定
- [x] 3.1 `requirements.lock` 已生成
- [x] 3.2 Dockerfile 使用锁定文件

## Phase 4: Docker 安全
- [ ] 4.1 Dockerfile 添加非 root 用户（待办）

## Phase 5: 最终验证
- [ ] 5.1 全量测试验证
- [ ] 5.2 最终检查清单

## 已知剩余问题
- [ ] Dockerfile 未配置非 root 用户运行
- [ ] nginx 反向代理默认端口 80 无 HTTPS（可配合 Caddy/Certbot）
- [ ] Report 文件存储无自动清理策略
- [ ] `db.database.py` 中 SQLite scheme 白名单仅支持 `sqlite://`
