# Gaobao-Advisor Next Phase Design

> **Date**: 2026-06-13
> **Status**: Approved
> **Strategy**: Sprint 序列全量并行推进
> **Window**: 高考季 2026年6-7月（4周）
> **Execution**: 规划优先，Workflow 批量执行

---

## 1. Current State Summary

### What Works
- Core agent with 7-slot information gathering (2,154 lines)
- Streamlit Web + CLI + H5 mobile + FastAPI REST server
- SQLite database: 3,016 schools, 215 majors, 27,318 admission scores
- 30 provinces covered, years 2022-2024
- 7 quality modules: emotion detection, cross-validation, AI era risk, decision framework, anti-pattern, model selector, knowledge loader
- RAG hybrid retriever (implemented, disabled by default)
- Rate limiter, XSS sanitization, SSRF defense
- 15 test files, 273/274 passing
- Prompt engineering at v2.7 with 14 templates
- 55 Douyin content scripts prepared

### What's Missing
- 1 failing test (`test_import_schools_fills_missing_city`)
- No CI/CD pipeline
- RAG disabled by default (`ENABLE_RAG_KB=false`)
- Brand still references Zhang Xuefeng (张雪峰) throughout
- Empty DB tables: enrollment_plans (0), yi_fen_yi_duan (0), feedbacks (0)
- L2-L4 data import queued but not running
- No structured onboarding flow (6 hardcoded quick questions)
- No multi-stage loading indicators
- No conversation history UI
- No production deployment
- No `pyproject.toml`
- Session pool in api_server.py has no TTL cleanup

### Existing Plans Not Yet Executed
1. Data Pipeline Expansion (2026-06-12)
2. RAG Phase 1 (2026-06-13)
3. Quality-Driven Upgrade (2026-06-12)
4. Production Hardening (2026-06-12)
5. OPC Hooks (2026-06-12)
6. UX Development Plan Phase 0-3 (2026-06-12)

---

## 2. Sprint Overview

| Sprint | Name | Duration | Focus | Key Deliverable |
|--------|------|----------|-------|-----------------|
| S1 | 基础设施 | Day 1-3 | 先修路再跑车 | 274测试全绿 + CI + 品牌合规 + RAG开启 |
| S2 | 数据+可信 | Day 4-7 | 数据是核心竞争力 | 100K+录取分 + 一分一段 + 免责声明 |
| S3 | 产品+体验 | Day 8-10 | 用户感知提升 | 3步引导 + 多阶段加载 + 对话历史 + 导出 |
| S4 | 上线+商业化 | Day 11-14 | 高考季收割 | 生产部署 + OPC钩子 + 移动端 + 上线检查 |

### Dependency Graph

```
S1-T3 (品牌) ──→ S3 (所有前端改动使用新品牌)
S1-T4 (RAG)  ──→ S2-T4 (免责声明可借助RAG精准注入)
S2-T1 (导入) ──→ S2-T5 (验证需在导入完成后)
S4-T1 (加固) ──→ S4-T2 (部署需在加固后)
S4-T2 (部署) ──→ S4-T5 (上线检查需在部署后)
```

---

## 3. Sprint 1: 基础设施（Day 1-3）

### S1-T1: Bug 修复 + 全绿测试

**Problem**: `tests/test_import_pipeline.py::test_import_schools_fills_missing_city` 失败

**Approach**:
1. 运行失败测试，分析断言与实际行为差异
2. 修复测试或实现代码（取决于哪边是正确的）
3. 运行全量测试确认 274/274 通过

**Acceptance Criteria**:
- [ ] `pytest` 全量运行 0 failures
- [ ] 测试覆盖率不低于当前水平

**Effort**: 0.5 天
**Dependencies**: None

### S1-T2: CI/CD 建设

**Problem**: 无自动化测试/部署，全手动流程

**Approach**:
1. 创建 `pyproject.toml`（project metadata + dependencies + tool config）
2. 创建 `.github/workflows/ci.yml`:
   - Trigger: push / PR to main
   - Matrix: Python 3.10, 3.11
   - Steps: checkout → setup-python → pip install → flake8/ruff → pytest --cov
   - Coverage threshold: 80%
3. 添加 `Makefile` 作为本地开发快捷入口

**Acceptance Criteria**:
- [ ] `pyproject.toml` 包含完整项目元数据和依赖声明
- [ ] CI workflow 在 push 时自动运行
- [ ] `make test` / `make lint` 本地可用
- [ ] CI 在 GitHub Actions 上首次通过

**Effort**: 0.5 天
**Dependencies**: S1-T1（需先确保测试全绿）

### S1-T3: 品牌去张雪峰化

**Problem**: 产品仍大量引用张雪峰，存在法律/伦理风险。张雪峰已于2026年3月去世。

**Approach**: 统一改造为通用高考顾问人设

**改造范围**:

| 文件 | 改动 |
|------|------|
| `system_prompt.md` | v2.8: 移除张雪峰人格定义，改为"资深高考志愿规划师"通用人设 |
| `app.py` | 页面标题、侧边栏、页脚的品牌名替换 |
| `h5/index.html` | 移动端标题和品牌引用 |
| `agent.py` | Agent 类名和注释中的引用 |
| `admin.py` | 运营面板标题 |
| `api_server.py` | API 文档描述 |
| `knowledge_base.md` | 张雪峰语录保留为"行业专家观点"分类，不作为核心人设 |
| `knowledge/quotes/` | 语录归属标注调整 |
| `prompts/templates/` | 涉及人设的模板（persona.md 等）更新 |
| `README.md` | 案例和品牌名替换 |
| `Dockerfile` / `docker-compose.yml` | 服务名/标签调整 |

**新品牌**: "gaobao"（高报）
**人设**: "资深高考志愿规划师，10年志愿填报辅导经验"

**Acceptance Criteria**:
- [ ] `grep -r "张雪峰\|xuefeng\|雪峰" --include="*.py" --include="*.md"` 无核心功能引用
- [ ] system_prompt.md 升级到 v2.8
- [ ] 所有前端页面显示新品牌名
- [ ] 知识库语录保留但归属标注为"行业专家"
- [ ] 所有 15 个 prompt 模板检查并更新
- [ ] 所有测试通过（品牌改动不破坏逻辑）

**Effort**: 1 天
**Dependencies**: None

### S1-T4: RAG 启用

**Problem**: RAG 混合检索已实现但默认关闭，导致每次对话注入完整知识库（>800行），浪费 token 且可能超出上下文窗口

**Approach**:
1. `.env.example` 中设置 `ENABLE_RAG_KB=true`
2. 验证 kb_retriever.py 在无向量嵌入时的关键词回退路径
3. 如果有 DashScope/OpenAI key，验证向量检索质量
4. 添加 RAG 检索日志（检索了哪些文件、耗时）
5. 确保 agent.py 的知识加载逻辑正确切换到 RAG 路径

**Acceptance Criteria**:
- [ ] 默认启用 RAG（新用户无需额外配置）
- [ ] 无 embedding key 时关键词检索正常工作
- [ ] 有 embedding key 时向量+关键词混合检索正常工作
- [ ] RAG 检索结果包含来源文件标注
- [ ] token 消耗减少约 40%（通过日志对比）

**Effort**: 0.5 天
**Dependencies**: None

### Sprint 1 交付清单
- [ ] 274/274 测试全绿
- [ ] CI/CD pipeline 运行正常
- [ ] 品牌统一为新名称
- [ ] RAG 默认开启

---

## 4. Sprint 2: 数据+可信度（Day 4-7）

### S2-T1: L2-L4 数据全量导入

**Problem**: 当前仅 L1（双一流）82% 完成，省重点/普通本科/高职数据为空

**Approach**:
1. 检查 L1 导入进度，如未完成则先完成
2. 依次启动 L2 → L3 → L4 导入
3. 使用 `--resume` 断点续传
4. 后台运行（预估 ~20 小时总计）
5. 每个层级完成后运行验证脚本

**Import commands**:
```bash
python scripts/import_baidu_gaokao.py --resume --provinces ALL --layer L2
python scripts/import_baidu_gaokao.py --resume --provinces ALL --layer L3
python scripts/import_baidu_gaokao.py --resume --provinces ALL --layer L4
```

**Target**: 100,000+ admission score records

**Acceptance Criteria**:
- [ ] L1 完成率 100%
- [ ] L2 导入完成（省重点大学 30省×3年）
- [ ] L3 导入启动并持续运行
- [ ] `validate_data.py` 通过
- [ ] 总记录数 > 50,000（阶段性目标）

**Effort**: 代码 0.5 天，数据采集后台运行
**Dependencies**: None（可在后台与 S2 其他任务并行）

### S2-T2: 一分一段表导入

**Problem**: `yi_fen_yi_duan` 表 0 行，用户无法查询"我这个分排名多少"

**Approach**:
1. 检查现有导入脚本是否支持一分一段表
2. 如不支持，编写导入脚本
3. 导入 30 省 × 2022-2024 年数据
4. 验证数据完整性

**Acceptance Criteria**:
- [ ] yi_fen_yi_duan 表有数据（30省 × 3年）
- [ ] 用户输入分数可查到对应排名
- [ ] 测试覆盖导入和查询

**Effort**: 0.5 天
**Dependencies**: None

### S2-T3: 招生计划数据导入

**Problem**: `enrollment_plans` 表 0 行

**Approach**:
1. 评估数据源可用性（百度高考 API 是否提供招生计划）
2. 如有数据源：编写导入脚本
3. 如无数据源：在 UI 中标记"招生计划数据暂不可用"而非显示空白
4. 为后续数据源预留接口

**Acceptance Criteria**:
- [ ] 有数据则导入，无数据则优雅降级
- [ ] UI 不显示空白/错误
- [ ] 后续添加数据源时无需修改 UI 代码

**Effort**: 1 天
**Dependencies**: None

### S2-T4: 数据年份标注 + 免责声明

**Problem**: 推荐结果中缺少数据年份说明和风险提示

**Approach**:
1. **后处理层**: 在 agent.py 的输出后处理中，检查推荐回复是否包含：
   - 数据年份引用（如"2024年录取数据"）
   - 免责声明（如"以上数据仅供参考"）
2. **自动注入**: 如未包含，自动追加
3. **系统提示词强化**: 在 v2.8 中明确要求标注数据年份
4. **UI 层**: 在推荐卡片中添加数据来源标签（已有部分实现）

**Acceptance Criteria**:
- [ ] 每次推荐回复包含数据年份
- [ ] 每次推荐回复包含免责声明
- [ ] 用户可在界面看到数据来源标签
- [ ] 后处理层确保即使 LLM 忘记标注也会自动补上

**Effort**: 1 天
**Dependencies**: S1-T4（RAG 启用后知识注入更精准）

### S2-T5: 数据质量验证

**Problem**: 全量导入后需确认数据质量

**Approach**:
1. 运行 `scripts/validate_data.py`
2. 修复发现的数据质量问题
3. 确认海南标准分（最高 900）不被标记为异常
4. 检查 description 字段覆盖率（当前 ~15%）
5. 检查 ranking 字段覆盖率（当前 ~30%）

**Acceptance Criteria**:
- [ ] validate_data.py 全部通过
- [ ] 无异常数据标记
- [ ] 覆盖率报告输出

**Effort**: 0.5 天
**Dependencies**: S2-T1（需在导入完成后验证）

### Sprint 2 交付清单
- [ ] 50,000+ 录取分数记录（阶段性）
- [ ] 一分一段表数据导入
- [ ] 招生计划数据或优雅降级
- [ ] 所有推荐包含数据年份和免责声明
- [ ] 数据质量验证通过

---

## 5. Sprint 3: 产品+体验（Day 8-10）

### S3-T1: 3 步引导卡片

**Problem**: 新用户面对空白聊天界面不知从何开始，当前 6 个硬编码快速问题不直觉

**Approach**:
在 app.py 中实现 3 步结构化引导流程（首次访问时展示）：

**Step 1 — 选择省份**:
- 30 省份卡片网格（2列布局）
- 每个卡片显示省名 + 高考模式标签（如"新高考3+1+2"）
- 点击选择后自动进入下一步

**Step 2 — 输入分数**:
- 数字输入框 + 科类选择（物理类/历史类）
- 分数范围验证（0-750，海南 0-900）
- 快速分数段按钮（高分段/中分段/低分段）

**Step 3 — 选择方向**:
- 选科组合（新高考省份显示）
- 兴趣方向标签（理工/医学/财经/师范/法学/文学/艺术/其他）
- 家庭资源（可选，跳过）

完成后自动将信息填入 session state，对话直接从个性化推荐开始。

**Implementation location**: `app.py` 新增 `render_onboarding()` 函数

**Acceptance Criteria**:
- [ ] 首次访问显示 3 步引导
- [ ] 已填写过引导的用户不再显示（session 级）
- [ ] 引导信息正确传入 agent slot 系统
- [ ] 引导完成后直接进入个性化对话
- [ ] 移动端（h5）适配相同流程

**Effort**: 1.5 天
**Dependencies**: S1-T3（新品牌名）

### S3-T2: 多阶段加载指示器

**Problem**: 当前只有单阶段脉冲动画，用户不知道 AI 在做什么

**Approach**:
使用 Streamlit 的 `st.empty()` + `time.sleep()` 实现阶段性文本：

```python
# 伪代码
loading = st.empty()
loading.info("🔍 正在理解你的需求...")
time.sleep(1)
loading.info("📊 正在查询录取数据...")
time.sleep(2)
loading.info("💡 正在生成个性化建议...")
# LLM 响应完成后
loading.empty()
```

**注意**: Streamlit 的 `time.sleep()` 会阻塞线程，需评估是否使用 `st.spinner` + callback 模式

**Acceptance Criteria**:
- [ ] 加载时显示至少 3 个阶段的提示文本
- [ ] 提示文本随时间推进更新
- [ ] 响应完成后提示消失
- [ ] 不影响正常响应流程

**Effort**: 0.5 天
**Dependencies**: None

### S3-T3: API Key 维护页面

**Problem**: 当 `LLM_API_KEY` 未配置时，暴露 API Key 输入框给终端用户

**Approach**:
1. 检查环境变量 `LLM_API_KEY`
2. 如未设置，显示维护页面：
   - 服务暂时维护中
   - 预计恢复时间
   - 联系方式/微信群二维码
3. 仅管理员可通过 URL 参数 `?admin=true` 看到 API Key 输入

**Acceptance Criteria**:
- [ ] 无 API Key 时终端用户看到维护页面
- [ ] 管理员可绕过维护页面
- [ ] 维护页面品牌一致

**Effort**: 0.5 天
**Dependencies**: S1-T3（新品牌名）

### S3-T4: 对话历史 UI + 结果导出

**Problem**: 数据库已有 conversation/conversation_message 表，但无 UI 展示

**Approach**:
1. **侧边栏对话列表**: 显示历史对话，按时间倒序
2. **对话恢复**: 点击历史对话恢复上下文
3. **结果导出**:
   - PDF 导出（已有 reportlab 基础）
   - Markdown 导出（轻量替代）
4. **分享链接**: 生成加密 token 链接（可选，复杂度高可推迟）

**Acceptance Criteria**:
- [ ] 侧边栏显示历史对话列表
- [ ] 点击可恢复对话上下文
- [ ] 可导出当前对话为 PDF
- [ ] 可导出当前对话为 Markdown
- [ ] 新对话和历史对话正确区分

**Effort**: 1.5 天
**Dependencies**: None

### Sprint 3 交付清单
- [ ] 3 步引导卡片可用
- [ ] 多阶段加载指示器工作
- [ ] 未配置 Key 时显示维护页面
- [ ] 对话历史可浏览和恢复
- [ ] 结果可导出 PDF/Markdown

---

## 6. Sprint 4: 上线+商业化（Day 11-14）

### S4-T1: 生产加固

**Problem**: 安全和稳定性未达生产标准

**Approach**:

| 项目 | 行动 |
|------|------|
| API 限流 | ratelimit.py 已实现，在 api_server.py 的每个端点集成 token bucket |
| XSS 全面扫描 | utils.py 的 sanitize 已实现，扫描所有前端输出点 |
| 结构化日志 | logger.py 已实现，在 agent.py/app.py/api_server.py 统一接入 |
| SQLite WAL 权限 | 确保 .db-wal 和 .db-shm 文件权限与 .db 一致 |
| Session 清理 | api_server.py 添加 TTL 清理（30 分钟无活动自动过期） |
| 依赖安全审计 | `pip-audit` 或 `safety check` |

**Acceptance Criteria**:
- [ ] API 端点全部有速率限制
- [ ] 无 XSS 漏洞（grep 检查 + 手动验证）
- [ ] 日志输出为 JSON 格式
- [ ] Session 30 分钟无活动自动清理
- [ ] 依赖无已知高危漏洞

**Effort**: 1 天
**Dependencies**: None

### S4-T2: 部署上线

**Problem**: 产品未部署到生产环境

**Approach**:
1. **Docker Compose 生产化**:
   - 添加 `docker-compose.prod.yml`
   - 环境变量通过 `.env.production` 管理
   - 健康检查端点 `/health`
   - 自动重启策略
2. **Streamlit Cloud**（免费备选）:
   - 连接 GitHub repo
   - 自动部署
3. **域名 + HTTPS**（如可用）:
   - Nginx 反向代理 + Let's Encrypt
4. **数据库备份策略**:
   - 每日自动备份 gaokao.db
   - 保留最近 7 天

**Acceptance Criteria**:
- [ ] `docker compose -f docker-compose.prod.yml up` 可启动
- [ ] 健康检查端点返回 200
- [ ] Streamlit Cloud 部署成功（如选择此方案）
- [ ] 数据库自动备份脚本就绪

**Effort**: 1 天
**Dependencies**: S4-T1

### S4-T3: OPC 商业化钩子

**Problem**: 无商业化入口，高考季无法变现

**Approach**:

**P0 — 微信社群钩子**（最高优先）:
- 侧边栏添加微信群二维码图片
- 公众号关注引导
- 免费 PDF《高考志愿填报指南》下载入口

**P1 — 事件追踪增强**:
- 复用已有 analytics 模块
- 新增事件：session_start, emotion_detected, slot_filled, major_query, school_query, export_clicked
- 隐私合规：不存储原始用户文本

**P2 — 内容引擎**:
- 对话中自动收集"金句"（用户表达的有价值观点）
- 3 轮对话后弹出微信社群引导
- 55 个抖音脚本的分发渠道对接（预留接口）

**Acceptance Criteria**:
- [ ] 侧边栏显示微信社群二维码
- [ ] 事件追踪覆盖核心用户行为
- [ ] 3 轮对话后显示社群引导
- [ ] 金句收集功能可用

**Effort**: 1.5 天
**Dependencies**: S1-T3（新品牌名）

### S4-T4: 移动端优化

**Problem**: h5/index.html 基础可用但交互体验不足

**Approach**:
1. 按钮尺寸增大（最小 44px 触摸目标）
2. 输入框全宽适配
3. 加载动画适配移动端
4. 长文本自动折叠
5. FastAPI 路由集成测试

**Acceptance Criteria**:
- [ ] 移动端触摸友好（按钮 >= 44px）
- [ ] 输入/输出在小屏幕正常显示
- [ ] 与 FastAPI 集成正常

**Effort**: 0.5 天
**Dependencies**: None

### S4-T5: 上线检查清单

**Problem**: 上线前需系统性检查

**Approach**:

**安全检查**:
- [ ] 无硬编码密钥
- [ ] 用户输入全部验证
- [ ] SQL 参数化查询
- [ ] XSS 防护
- [ ] CSRF 防护（如适用）
- [ ] 认证/授权（如适用）
- [ ] 速率限制
- [ ] 错误信息不泄漏敏感数据

**功能检查**:
- [ ] 核心流程走通（省份→分数→推荐→导出）
- [ ] 所有前端页面无报错
- [ ] API 端点全部可访问
- [ ] 数据库连接正常

**性能检查**:
- [ ] 并发 10 用户无报错
- [ ] 响应时间 < 30 秒（含 LLM 调用）
- [ ] 内存使用稳定

**监控检查**:
- [ ] 日志正常输出
- [ ] 健康检查端点正常
- [ ] 错误可追踪

**回滚方案**:
- [ ] Docker 镜像版本标记
- [ ] 数据库备份可恢复
- [ ] 回滚步骤文档化

**Effort**: 0.5 天
**Dependencies**: S4-T2

### Sprint 4 交付清单
- [ ] 生产环境安全加固完成
- [ ] Docker/Streamlit Cloud 部署成功
- [ ] 微信社群钩子上线
- [ ] 事件追踪覆盖核心行为
- [ ] 移动端体验达标
- [ ] 上线检查清单全部通过

---

## 7. Cross-Cutting Concerns

### Testing Strategy
- 每个 Sprint 完成后运行全量测试
- Sprint 3-4 的 UI 改动添加手动验证步骤
- Sprint 4 的部署需进行冒烟测试

### Risk Mitigation
| Risk | Impact | Mitigation |
|------|--------|------------|
| L2-L4 数据导入失败 | 数据不完整 | 使用断点续传，分省导入 |
| 品牌改造遗漏 | 法律风险 | grep 全量扫描确认 |
| RAG 启用后检索质量差 | 推荐质量下降 | 关键词回退保障 |
| Streamlit 性能瓶颈 | 用户体验差 | H5 移动端分流 |
| 高考季前未完成 | 收入损失 | S1-S2 优先保证核心可用 |

### Not in Scope (Deferred)
- EduAgent 子项目独立推进
- 多语言支持
- 微信小程序原生版本
- AI 图片/视频生成集成
- 一分一段表的可视化图表

---

## 8. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| 测试通过率 | 273/274 (99.6%) | 274/274 (100%) |
| 录取分数记录 | 27,318 | 100,000+ |
| 省份覆盖 | 30/30 | 30/30 (maintained) |
| CI/CD | None | GitHub Actions |
| RAG 启用 | false | true |
| 品牌合规 | 张雪峰引用 | 通用人设 |
| 部署状态 | 本地 | Production |
| 商业化入口 | None | 微信社群+事件追踪 |
