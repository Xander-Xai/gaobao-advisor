# Todo: 审计修复执行列表

## Phase 1: 架构清理
- [ ] 1.1 删除 `api_server.py`
- [ ] 1.2 重定向 `app.py` 为纯 legacy 入口
- [ ] 1.3 更新 Dockerfile 为 FastAPI 模式
- [ ] 1.4 删除 `requirements-api.txt`（已合并到主依赖）

## Phase 2: 文档修复
- [ ] 2.1 重写 README 快速开始
- [ ] 2.2 更新项目结构树

## Phase 3: 依赖锁定
- [ ] 3.1 生成 `requirements.lock`
- [ ] 3.2 更新 Dockerfile 使用锁定文件

## Phase 4: Docker 安全
- [ ] 4.1 Dockerfile 添加非 root 用户

## Phase 5: 最终验证
- [ ] 5.1 全量测试验证
- [ ] 5.2 最终检查清单