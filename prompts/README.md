# 提示词版本管理

## 目录结构

```
prompts/
├── README.md          # 本文件 — 使用说明
├── CHANGELOG.md       # 提示词变更日志（核心）
├── system/            # System Prompt 各版本
│   ├── v1.0.md        # 初始版本
│   ├── v2.0.md        # 当前版本（从 system_prompt.md 同步）
│   └── ...
├── templates/         # 可复用的提示词模板/模式
│   ├── persona.md     # 人设类模板
│   ├── tool-call.md   # 工具调用模板
│   ├── multi-perspective-audit.md  # 多角色审计框架
│   ├── multi-turn.md              # 多轮对话状态管理
│   │
│   │   # === 安全防护层（2026-06-12 新增）===
│   ├── guardrails-injection-defense.md  # Prompt Injection 三层防御
│   ├── guardrails-output-filter.md      # 输出安全四步过滤
│   ├── guardrails-rag-security.md       # RAG 知识库安全
│   │
│   │   # === 合规与隐私（2026-06-12 新增）===
│   ├── compliance-privacy-minors.md     # 数据隐私与未成年人保护
│   ├── compliance-china-ai-regulations.md # 中国 AI 法规合规清单
│   │
│   │   # === 测试体系（2026-06-12 新增）===
│   ├── testing-regression-suite.md      # 对话回归测试（黄金测试集）
│   ├── testing-multilingual-attacks.md  # 多语言对抗测试
│   ├── testing-ab-framework.md          # A/B 测试框架
│   │
│   │   # === 运维与降级（2026-06-12 新增）===
│   ├── observability-production.md      # 生产可观测性
│   └── sop-disaster-degradation.md      # 灾难降级 SOP
└── sessions/          # 对话中产出的关键提示词迭代
    ├── 2026-06-12-知识库接入优化.md
    └── ...
```

## 使用方式

### 1. 记录新版本
每次提示词有实质性改动，运行：
```bash
cd /home/dev/projects/xuefeng/xuefeng-advisor
python3 prompts/extract_prompt.py
```
或在对话中直接说：「归档当前提示词到 prompts/」

### 2. 查看变更历史
```bash
cat prompts/CHANGELOG.md
```

### 3. 回退到某个版本
所有版本都在 Git 中，直接 `git log --oneline prompts/` 查看。

### 4. 复用模板
`templates/` 中存放可组合的提示词片段，新项目直接引用。

## 版本命名规则

- **大版本**（v1.0 → v2.0）：人设/架构/核心逻辑重构
- **小版本**（v2.0 → v2.1）：参数调优/新增场景/修 bug
- **会话版本**（session/）：开发过程中一次对话的产物，可能是草稿
