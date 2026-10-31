# Issue #58 历史敏感数据专项审计与沙盒演练

> 历史安全事件文档 / Historical security-incident document。本文只包含脱敏统计、
> 对象 SHA、路径和风险结论；不包含原始用户消息、手机号、邮箱、凭据或数据库内容。
> 当前仓库仅分发合成数据；本文描述的历史对象不代表当前数据。

- **日期**：2026-10-31（Asia/Shanghai）
- **仓库**：`Xander-Xai/gaobao-advisor`（public）
- **关联 Issue**：https://github.com/Xander-Xai/gaobao-advisor/issues/58
- **当前 master（审计起点）**：`9e7dc0307a0f1fe2dddd86324bbd4964d0d326fc`
- **防泄露控制合并后 master**：`0c7ff795c362d0ef648e622350e05ce14ac3a6ba`
- **远端重写授权**：**NO**
- **远端历史已重写**：**NO**
- **私有隔离区**：`/home/dev/gaobao-security-quarantine`（mode 700；未上传 GitHub）

---

## 0. 专项状态

| 状态项 | 结果 | 说明 |
|---|---|---|
| `SENSITIVE_DATA_CLASSIFIED` | **PASS** | 已按 PUBLIC/SYNTHETIC/INTERNAL/PERSONAL/SECRET/UNKNOWN 分类 |
| `EXPOSED_OBJECTS_INVENTORIED` | **PASS** | 17 个受影响 commit、21 个敏感 blob、14 个受影响 PR ref |
| `PRIVATE_BACKUP_VERIFIED` | **PASS** | `.git` 副本 + bundle，`fsck` 完整，bundle SHA-256 记录 |
| `LOCAL_UNIQUE_BRANCH_PRESERVED` | **PASS** | `release/unified-public-gaobao` 原样保留，未推送/删除 |
| `SANDBOX_REWRITE_VERIFIED` | **PASS（方法降级）** | `git filter-repo --sensitive-data-removal` 受 git 2.34 限制；使用 `git filter-branch --index-filter` 等价演练 |
| `OWNER_REMOTE_AUTHORIZATION` | **BLOCKED** | 尚未收到独立消息中的远端重写/支持工单授权 |
| `REMOTE_HISTORY_REWRITTEN` | **NO / BLOCKED** | 未 force-push、未改远端 ref |
| `GITHUB_PR_REFS_CLEANED` | **BLOCKED** | 需 GitHub Support；普通 Git Push 不能清理 `refs/pull/*` |
| `GITHUB_CACHE_PURGED` | **BLOCKED** | 需 GitHub Support |
| `SUPPORT_CASE_VERIFIED` | **BLOCKED** | 无 GitHub Support #4849701 的访问/可验证进展 |
| `FORK_RESIDUAL_RISK_REVIEWED` | **PASS** | 当前 forks=0；历史 clone/第三方副本无法保证清除 |
| `PREVENTION_CONTROLS_ENABLED` | **PASS（PR #77 已合并）** | 文件守卫、pre-commit、CI、`.gitignore`、文档 |
| `MASTER_CI_VERIFIED` | **PASS** | `0c7ff79` CI 13/13（run 41198100431）+ CodeQL（run 41198100449）success |
| `ISSUE_58_RESOLVED` | **BLOCKED** | 远端 PR refs/缓存/历史对象未清除 |
| `SECURITY_REVIEW` | **BLOCKED** | 历史暴露未闭环 |
| `REPOSITORY_READY` | **BLOCKED** | 同上 |

---

## 1. 实时仓库状态（Phase A）

| 项 | 实测 |
|---|---|
| 默认分支 | `master` |
| master HEAD | `9e7dc0307a0f1fe2dddd86324bbd4964d0d326fc` |
| Open PR / Issue | 0 / 1（#58） |
| 远端分支 | `master` |
| 本地分支 | `master`、`release/unified-public-gaobao`（保留） |
| Tags | `archive/vue3-ts-readonly-20261030`（annotated） |
| Releases | 0 |
| GitHub Pages | disabled（404） |
| Forks | 0 |
| Collaborators | 1（`Xander-Xai`） |
| Actions artifacts | 7；均为 SARIF/compose 日志；扫描无敏感路径/凭据/个人信息模式 |
| Actions secrets | 0 |
| Deployments / Environments | 0 / 0 |
| LFS | 无 `.gitattributes` LFS filter；不适用 |
| Branch protection | 13 required checks，strict，admins enforced，no force/delete，conversation resolution |
| Secret scanning / push protection | enabled |
| CodeQL open alerts | 0（8 条 clear-text 已逐条 dismissed） |
| PR refs | 64 个 `refs/pull/*/head`；14 个受影响 |

> GitHub 的 `refs/pull/*` 和按 SHA 访问的旧 commit 不会出现在 `git branch -a`。
> 本次通过 `git ls-remote 'refs/pull/*'`、PR ref 镜像、GitHub commit API 分别核查。

---

## 2. 暴露对象清单（Phase A2）

### 2.1 敏感 blob

| 路径 | blob 数 | 最大字节 | 分类 |
|---|---:|---:|---|
| `data/gaokao.db` | 13 | 75,018,240 | `UNKNOWN` / `INTERNAL`（真实院校名与 2022–2025 分数；无合成标记；授权未核实） |
| `data/gaokao.db.corrupted` | 1 | 86,499,328 | 同上 |
| `backups/gaokao_db_20260617_013418.sql.gz` | 1 | 16,910,890 | 同上（gzip 后为 SQLite DB；400,194 条分数行） |
| `backups/gaokao_db_20260617_025354.sql.gz` | 1 | 16,977,063 | 同上（383,363 条分数行） |
| `data/gaokao.db-wal` / `-shm` | 4 | 4,194,192 | 可能含未 checkpoint 数据；`UNKNOWN` |
| `.env.production` | 1 | 482 | `SECRET` 占位符；无长凭据/有效 Token |

- 唯一敏感 blob：**21 个**，合计 **404,879,187 bytes（约 386.12 MiB）**。
- 最大单文件：**86,499,328 bytes**（`data/gaokao.db.corrupted`）。
- 用户消息统计（脱敏）：`Conversation` 43 个、消息 3,014 对；**31 条唯一用户文本**，
  均为测试模板（如“我是某省考生…”“忽略之前的所有指令”等）；邮箱/身份证匹配 0；
  2 条“手机号形状”匹配位于系统错误文本，不是已确认的用户手机号。
  → 分类为 `UNKNOWN`（很可能为测试 fixture，但未验证为合成，不能按 PUBLIC 处理）。

### 2.2 受影响 commit

共 **17 个** commit 触及上述路径，全部可通过 GitHub commit 页面/API 访问：

| SHA | 日期 | 摘要 |
|---|---|---|
| `308ba5a828da` | 2026-06-11 | feat: v2.0 数据库架构 + 知识库扩展 + 爬虫系统 |
| `59b6ca7931ab` | 2026-06-12 | docs: add data pipeline expansion design doc… |
| `64ef0a0e9023` | 2026-06-12 | feat: 全面升级 — Docker 部署 + H5 前端… |
| `227d789bdfaf` | 2026-06-13 | fix: repair 2 failing import pipeline tests… |
| `2b9491aa7eb5` | 2026-06-13 | feat: populate yi_fen_yi_duan… |
| `2e21ba8f71f9` | 2026-06-13 | feat: production Docker config and database backup script |
| `3ddf974340c5` | 2026-06-13 | feat: add FastAPI server scaffold with health endpoint |
| `66f105134d99` | 2026-06-13 | feat: add StructuredPlanningCard Pydantic schema |
| `99d1dbb21751` | 2026-06-13 | docs: update all project docs… |
| `5519ed868d78` | 2026-06-13 | feat: Phase 7+8 deliverables — WeChat optimization… |
| `4d49aaa32506` | 2026-06-14 | chore: ruff check --fix + ruff format… |
| `e715a05b5d5c` | 2026-06-14 | chore: stash pre-Phase0 work… |
| `151729191c02` | 2026-06-15 | chore: remove deprecated app.py |
| `5278ae1b9e3d` | 2026-06-16 | fix: deduplicate admission_scores…（72 MiB DB） |
| `b222bde2fc98` | 2026-06-16 | refactor: … remove root shims…（删除 DB/`.env.production`） |
| `6059d9fb4c22` | 2026-06-17 | fix: clean subject_type… |
| `18c358848922` | 2026-06-17 | fix: sensitive info allowlist… |

（完整 17 行及精确时间保存在私有 `affected-commits.tsv`；所有 17 个 SHA 均已逐个
通过 GitHub commit API 验证可访问。）

### 2.3 受影响 refs / PR / Tag

| 类型 | 结果 |
|---|---|
| `refs/heads/master` | **干净**：`rev-list --objects` 无敏感路径 |
| `refs/tags/archive/vue3-ts-readonly-20261030` | **干净**（414 files，无敏感路径） |
| 本地 `release/unified-public-gaobao` | **受影响**（历史含 21 个敏感 blob）；保留 |
| PR refs | **14 个受影响**：PR **#1–#9、#11–#15**；PR #10 无 ref |
| Releases / Pages / Artifacts / LFS / Tags | 无敏感对象 |

- 受影响的普通 Git refs：release 分支 + 14 个 PR refs。
- `refs/pull/*/merge`：0 个。
- 公开 Release：0；Pages：disabled；Artifacts：7 个，扫描无敏感内容。
- Fork：0（当前）；但历史 clone/第三方副本不可控。

---

## 3. 数据分类与风险（Phase A3）

| 数据 | 分类 | 依据 |
|---|---|---|
| 当前 `master` 合成院校/分数/语料 | `SYNTHETIC` / `PUBLIC` | `SYNTHETIC_DEMO_DATA` 标记、8 校/128 分数、manifest 校验 |
| 历史 DB 中的院校与录取分数 | `UNKNOWN`（倾向 `INTERNAL`） | 真实院校名、2022–2025 分数；无合成标记；来源/授权未记录 |
| 历史 DB 中的用户消息 | `UNKNOWN`（可能测试 fixture） | 31 条唯一模板；无邮箱/身份证；手机号形状仅出现在错误文本；未证实为真实个人 |
| `.env.production` | `SECRET`（占位符） | 仅 placeholder-like LLM 值；无有效长凭据 |
| 历史 SQLite 备份 | `UNKNOWN` / `INTERNAL` | 仅 `admission_scores` 表，383k/400k 行 |
| GitHub artifacts | `PUBLIC`（无敏感模式） | SARIF 0 results；compose 日志无敏感路径/凭据 |
| 当前仓库代码/合成数据 | `PUBLIC` | MIT + CC0 + SYNTHETIC_DEMO |

> UNKNOWN 一律按风险未解除处理。不得仅因“看起来像测试数据”就将历史对象标为安全。

---

## 4. 私有备份（Phase B）

| 项 | 值 |
|---|---|
| 隔离区 | `/home/dev/gaobao-security-quarantine`（700） |
| Git 副本 | `original-backup/repo.git`（86 MiB，含本地 branch/tag/unreachable objects） |
| 便携 bundle | `original-backup/gaobao-all-refs-plus-5278.bundle`（75 MiB） |
| bundle SHA-256 | `4c36ec0007f5e418f352f77699497a48ad47ac33941fea9c2b59df18b5d920c2` |
| 捕获时间 | `2026-10-31T10:51:43Z` |
| 校验 | `git fsck --full --unreachable` 完成；bundle `verify` 记录 complete history；`6bec50…` blob 存在且大小 75,018,240 |
| 访问控制 | 目录 700；bundle/敏感快照 600；未上传任何公开位置 |

备份包含：`master`、`release/unified-public-gaobao`、archive tag、`5278ae1` 及历史对象。
本地 `release/unified-public-gaobao` **未推送、未合并、未删除**。

---

## 5. 沙盒历史重写（Phase C）

### 5.1 工具评估

- 首选 `git-filter-repo --sensitive-data-removal`。
- 系统 git = **2.34.1**；上游 main 分支的 filter-repo 要求 **git >= 2.36.0**；
  PyPI 最新 **2.47.0** 不包含该参数。
- 结论：`--sensitive-data-removal` 在当前环境不可用（记录为方法降级）。
- 回退：`git filter-branch --index-filter 'git rm --cached …' --tag-name-filter cat -- --all`
  对隔离副本执行，显式列出 7 个路径，不使用通配符误删。
- 未对原始工作仓库执行 `git-filter-repo`；所有重写在隔离副本完成。

### 5.2 清理路径

```text
data/gaokao.db
data/gaokao.db-shm
data/gaokao.db-wal
data/gaokao.db.corrupted
backups/gaokao_db_20260617_013418.sql.gz
backups/gaokao_db_20260617_025354.sql.gz
.env.production
```

### 5.3 沙盒结果

| 项 | 原始 | 沙盒重写后 |
|---|---|---|
| master commit | `9e7dc0307a0f1fe2dddd86324bbd4964d0d326fc` | `40989b73fbe10c1eea723c9856fc6a40f01e1bdb` |
| master tree | `eefcc168d8bbfe55e69742a38c92ee805b7df523` | **完全相同** `eefcc168…` |
| master commits | 318 | 318 |
| release/unified-public-gaobao | `858df3799fa1658bfb6a92839a76e4ee3021aa09` | `d060e9a3ece1024c2488e3c9df6cf9f614886c38` |
| release commits | 245 | 245 |
| archive tag（annotated object） | `dd937f0119ace6fe5d90759a5096576dfbe509cb` | `c41d4c98d378f5bb4e32830fd42bf4cf738ee2bc` |
| archive tag commit | `8fe4f614781bc82b2ce1e37a2c59ee0fa9d70701` | `7d7a2d49c4ec11dc3d1b428952ebb65abb381cd2` |
| 变更 refs | — | 67 个 ref 中 66 个 SHA 改变（tree 内容仅在敏感路径处变化） |
| 敏感 blob | 21 | **0**（全部 `cat-file` 不存在） |
| 敏感路径 | 21 | **0**（所有 refs 遍历无命中） |

- master/tag 文件树与原始 **完全一致**（523 / 414 files，0 added/removed/changed）。
- release 文件树仅少 3 个文件：2 个 `backups/*.sql.gz` + `data/gaokao.db.corrupted`；
  无其他非敏感文件丢失。
- `git fsck --full` 无 missing/corrupt object。
- PR refs 64 个全部无敏感路径；`refs/pull/*` 不在普通 push 可更新范围。

### 5.4 沙盒验收

| 检查 | 结果 |
|---|---|
| Python 全量测试（沙盒 master） | **1162 passed / 34 skipped**，coverage 81.73% |
| 前端 `vue-tsc` + vitest | **15 files / 92 tests passed** |
| 前端 build | 通过 |
| MySQL 8 + Redis 7 集成 | **33 passed** |
| 合成 Demo seed | 8 schools / 128 scores / 48 plans / 40 rankings |
| Ruff check/format | 通过 |
| 旧/新 master tree | 完全相同 |
| 敏感 blob 残留 | 0 |

> 沙盒中 `make test-integration` 需显式 `PYTHON=<venv>/bin/python`（系统 3.10
> 缺 pymysql）；使用项目 venv 后 33 passed。该差异是测试环境配置，不是重写回归。

---

## 6. REMOTE_REWRITE_APPROVAL_PACKET

### 6.1 基本信息

- Repository: `https://github.com/Xander-Xai/gaobao-advisor`
- Issue: `#58`
- 原始 master HEAD: `9e7dc0307a0f1fe2dddd86324bbd4964d0d326fc`
- 沙盒 master HEAD: `40989b73fbe10c1eea723c9856fc6a40f01e1bdb`
- 沙盒 master tree: `eefcc168d8bbfe55e69742a38c92ee805b7df523`（与原始相同）
- 沙盒 release HEAD: `d060e9a3ece1024c2488e3c9df6cf9f614886c38`
- 沙盒 tag: object `c41d4c98…` → commit `7d7a2d49…`
- 敏感 blob：21 个，约 386.12 MiB；最大 86.5 MiB
- 受影响 commit：17（全部 GitHub API 可访问）
- 受影响 PR refs：14（#1–#9、#11–#15）
- 受影响普通 branch：本地 `release/unified-public-gaobao`（未推送）
- 受影响 tags：0（archive tag tree 干净）
- 受影响 Releases/Pages/Artifacts/LFS：0 / 0 / 0 / N/A

### 6.2 方案与建议

**方案 A（推荐，无需改写 master）**：

1. 保持 `master@9e7dc03` 不变（其历史已干净）。
2. 由 owner 授权后向 GitHub Support 提交清理请求，要求处理
   `refs/pull/1..9,11..15`、旧 commit SHA 缓存、unreachable objects 和缓存视图。
3. 验证 `refs/pull/*`、commit 页面/API、缓存视图不再返回敏感对象。
4. 不删除本地 `release` 分支，除非后续独立授权并完成取证备份。

优点：不破坏现有 13 项 CI/PR/Issue 链接；master 工程成果完全保留。
限制：历史 PR diff 和旧 commit SHA 可能仍被 GitHub 缓存，必须由 Support 处理；
第三方 fork/clone 无法保证清除。

**方案 B（仅在 Support 明确要求时）**：

1. 临时调整 branch protection（需单独授权），force-push sandbox master
   `40989b7` 和 tag 新对象。
2. 更新所有协作者 clone；旧 PR refs 仍需 Support 清理。
3. 重新运行 CI/CodeQL/Compose。

风险：master tree 与原始相同，force-push 不会增加安全性，却会使
PR/commit/CI 链接失效；`refs/pull/*` 仍保留旧对象。因此**不推荐**。

### 6.3 影响与风险

- **签名**：历史 commit 未做签名验证；重写会改变所有 commit SHA。
- **PR diff**：14 个历史 PR 的 head SHA 将失效；GitHub 仍可能显示旧 diff。
- **Branch Protection**：master 禁止 force-push；方案 B 需临时授权关闭/绕过，
  完成后再恢复；不得降低 Required Checks。
- **独有代码**：沙盒 master/tag tree 完全一致；release 仅少 3 个敏感文件，
  无非敏感代码丢失。
- **协作者/克隆**：当前 collaborator=1、fork=0；未知本地 clone 仍可能保留旧对象。
- **回滚**：隔离区 `.git` + bundle 可完整恢复；回滚不得使用公开仓库。
- **未授权状态**：`OWNER_REMOTE_AUTHORIZATION=NO`、`REMOTE_HISTORY_REWRITTEN=NO`。

### 6.4 需要 owner 独立批准的事项

1. 是否授权向 GitHub Support 提交/更新清理请求（方案 A）。
2. 是否在 Support 要求时授权 force-push sandbox master/tag（方案 B），以及
   临时调整 branch protection 的范围与时限。
3. 确认历史院校/分数数据的来源授权，以及 31 条唯一测试模板是否确为测试 fixture。
4. 是否需要向数据主体通知/法律评估（当前未确认真实个人信息）。

> 在收到独立授权前，不执行任何远端历史重写、force-push、删除远端引用或修改
> Branch Protection。

---

## 7. GitHub Support 信息草稿（未提交）

```text
Repository: https://github.com/Xander-Xai/gaobao-advisor
Issue: https://github.com/Xander-Xai/gaobao-advisor/issues/58
Request: purge historical sensitive data from internal PR refs/caches/unreachable objects.

Sensitive data:
- Removed SQLite databases/backups and one placeholder .env.production.
- 21 blobs, ~386 MiB; largest ~86.5 MiB.
- Real-looking admissions data (2022-2025) and test-like conversation rows.
- No valid credentials confirmed.

Affected public refs:
- refs/pull/1/head .. refs/pull/9/head, refs/pull/11/head .. refs/pull/15/head (14 PR refs).
- refs/heads/master is clean; no release assets; no forks currently.

First changed commits (UTC dates):
- 2026-06-11 308ba5a828da (first DB)
- 2026-06-13 2e21ba8f71f9 (.env.production)
- 2026-06-16 5278ae1b9e3d (72 MiB DB revision)
- 2026-06-17 6059d9f/18c3588 (backups/corrupted DB)

Please purge/expire the affected PR refs, cached commit views, and unreachable Git objects
where policy permits, and advise on remaining limitations. The current master tree is clean;
we are not requesting repository deletion.
```

- 现有 Support 工单 **#4849701**：本环境无 Support 门户访问权限，无法验证其状态或更新；
  不将其视为已解决。
- 未提交新工单，避免重复；待 owner 授权后优先更新已有工单。

---

## 8. 防再次泄露（Phase G）

已准备并通过独立 PR（#77）：

- `.gitignore` 扩展：`*.db`、`*.sqlite`、`*.sql`、`*.sql.gz`、`*.dump`、`*.bak`、
  `*.log`、备份/隔离目录。
- `scripts/check_sensitive_files.py`：依赖为零，检查 tracked/staged 路径与 >10 MiB 文件；
  只打印路径，不打印内容。
- `.pre-commit-config.yaml`：本地 hook。
- CI `Secret Scan` 在 gitleaks 前运行同一守卫。
- `docs/security/sensitive-data-handling.md`：生成合成库、事件响应、历史重写边界。
- 测试：15 项 guard 测试；CI 全量测试/CodeQL 继续运行。

当前仓库仍使用 `scripts/seed_demo_data.py` 生成合成数据；无真实用户 fixture、
CI artifact 不含真实数据、MySQL/Redis 集成测试能力保留。

---

## 9. 残余风险与未完成事项

| 项 | 状态 | 责任/下一步 |
|---|---|---|
| GitHub `refs/pull/*` 旧对象 | **未清除** | Owner 授权后 GitHub Support |
| 旧 commit SHA 缓存/不可达对象 | **未清除** | GitHub Support |
| 历史 PR diff/缓存视图 | **未清除** | GitHub Support |
| 第三方 fork/clone | 不可控 | 记录残余风险；无法承诺互联网范围删除 |
| 真实个人信息确认/通知 | 未确认 | Owner/法律/数据保护负责人 |
| 本地 release 分支 | 保留 | 禁止推送/删除，待独立取证授权 |
| Support #4849701 | 无法验证 | Owner 通过 Support 门户更新 |

**Issue #58 保持 OPEN。** 在 GitHub 端对象/缓存/PR refs 清理并有可验证证据前，
不得关闭；不得用 PR #77 或本报告替代远端清理。

---

## 10. 结论

- Phase A–D 的只读取证、分类、隔离备份、沙盒重写与独立验证已完成。
- 沙盒证明：显式移除 7 个路径后，21 个敏感 blob 全部消失，master/tag tree 不变，
  release 仅少 3 个敏感文件，测试/前端/集成全部通过。
- **未执行**远端历史重写、force-push、删除远端引用或修改 Branch Protection。
- 远端清理必须由 owner 独立授权，并通过 GitHub Support 处理 PR refs/缓存/不可达对象。
- 当前 `SECURITY_REVIEW` / `REPOSITORY_READY` 仍为 **BLOCKED**，`ISSUE_58_RESOLVED`
  仍为 **BLOCKED**。
