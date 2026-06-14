# gaobao-advisor × zhangxuefeng-skill-merged 整合提升方案 v1.0

> **生成时间**: 2026-06-14
> **作者**: Claude Opus 4.8
> **状态**: 待用户审核
> **关联项目**:
> - [gaobao-advisor](/home/dev/projects/gaobao/gaobao-advisor) — 主项目
> - [zhangxuefeng-skill-merged](/home/dev/projects/gaobao/zhangxuefeng-skill-merged) — 调研资料源
> - [二次开发日志](./secondary-development-log.md) — 上一轮(2026-06-13)整合记录

---

## 0. TL;DR(用 30 秒看完)

| 维度 | 结论 |
|---|---|
| **方法论整合度** | **已 95% 完成** —— 3 档情绪、9 故障自愈、5 模型/8 启发/8 反模式、Step 0 省份识别,gaobao-advisor 都已实现 |
| **真正缺什么** | 3 块:① 张雪峰**原版金句溯源** + 出处时间(现有 505 句已"去个性化")② **叙事知识**(5 本书/15 采访/24 年时间线)③ **6 条数据来源标注硬规则**(现为软规则) |
| **总工作量** | 6-8 天(约原计划 1/3) |
| **风险等级** | 🟢 低(全部为内容扩充,不破坏现有架构) |
| **核心策略** | 不引入 zhangxuefeng 人物模式(用户已确认);只吸收**方法论 + 调研资料 + 硬规则** |

---

## 1. 摸底发现 —— 两个项目的真实状态

### 1.1 gaobao-advisor 现状(基于 `git log` + 代码深度阅读)

**已完成的方法论工程化**(2026-06-12 至 2026-06-13 共 3 个版本演进):

| 模块 | 实现位置 | 状态 |
|---|---|---|
| 3 档情绪(🔴🟡🟢) | `system_prompt.md:155-208` + `quality/emotion_detector.py` | ✅ 代码层 + Prompt 双层实现 |
| 🟢 共情 SOP 5 阶段 | `system_prompt.md:173-208` | ✅ Prompt 实现 |
| 9 条故障自愈 | `system_prompt.md:402-450` | ✅ Prompt 实现 |
| 5 大心智模型 | `skills/gaokao/mental_models.md`(67 行) | ✅ SkillService 注入 |
| 8 条决策启发 | `skills/gaokao/heuristics.md`(60 行) | ✅ SkillService 注入 |
| 8 条反模式 | `skills/gaokao/anti_patterns.md`(18 行) | ✅ SkillService 注入 |
| 表达引擎 | `skills/gaokao/expression_engine.md`(114 行) | ✅ SkillService 注入 |
| Step 0 省份识别 | `system_prompt.md:83-90` | ✅ Prompt 实现 |
| T1-T4 数据源分级 | `knowledge/groups/G5_data_format.md` + `kb_retriever.py:53-88` | ✅ RAG + 触发词 |
| 505 条金句库 | `knowledge/quotes/_by_major.json`(8550 行)+ `_index.json` | ✅ RAG 检索 |
| 8 个知识组 | `knowledge/groups/G1-G8.md`(共 996 行) | ✅ RAG 检索 |
| 14 节点 LangGraph | `server/graph/graph.py` | ✅ 流水线 |
| 质量 7 模块 | `quality/` + `server/services/quality.py` | ✅ 全栈 |
| 安全中间件 | `server/middleware/security.py` | ✅ 注入/SSRF/XSS |
| 限流 | `server/middleware/ratelimit.py` | ✅ 20/h 40/d |

**架构健康度**:
- 测试覆盖:35 个测试文件 / 430+ 测试函数
- 最新提交:`c39ea0b`(2026-06-13)— AI 风险防御性检查 + 审计状态更新
- 开发分支:`feature/expression-engine-and-pipeline-fix`
- CLAUDE.md 自动化:pre-commit 归档 system_prompt v2.7→v2.10

### 1.2 zhangxuefeng-skill-merged 现状(8 文件 / 1184 行 Markdown)

| 文件 | 行数 | 关键内容 |
|---|---|---|
| `SKILL.md` | 745 | 角色规则 + 7 表达规则 + Step 0-5 工作流 + 9 fallback + 3 档情绪 + 5 模型(详)+ 8 启发(详)+ 8 反模式(简)+ 来源标注 6 规则 |
| `examples/demo-conversation.md` | 271 | 10 个 demo 场景 |
| `references/research/02-conversations.md` | 284 | 15+ 采访 |
| `references/research/03-expression-dna.md` | 264 | 50+ 原版金句(带出处时间) |
| `references/research/05-decisions.md` | 172 | 11 关键决策 + 5 行为模式 |
| `examples/demo-conversation.md` | 271 | 10 场景 |
| `references/research/01-writings.md` | 60 | 5 本书分析 |
| `references/research/04-external-views.md` | 70 | 批评/局限 |
| `references/research/06-timeline.md` | 63 | 1984-2026 时间线 |

### 1.3 **关键事实修正** —— 上一轮评估的偏差

> 上一轮(2026-06-13) 整合时,`secondary-development-log.md` 第 24 行记录 zhangxuefeng "**105 语录**" —— 实际目前 505 条,**已实现 5 倍增长**;`v2.6` 版本注释写"三档语气 + 9 条故障自愈" —— **这些都已落地**。
>
> 因此本方案**不再重复**已实现部分,只针对**真实缺口**。

---

## 2. 三块真实缺口(对症下药)

### 缺口 1:张雪峰原版金句溯源

**现状**(`knowledge/quotes/expansion_v3.json`):
```json
{
  "text": "计算机不是不能学,是你得会用AI,光写代码的码农时代结束了。",
  "tags": ["计算机", "AI"],
  "id": "q_500",
  "category": "zhuanye",
  "source": "项目内部语料整理"   ← 缺出处时间和原文
}
```

**应有状态**(对比 zhangxuefeng `references/research/03-expression-dna.md`):
| 原话 | 出处 | 时间 |
|---|---|---|
| 中国几乎所有500强企业都说学历不重要,但他们会去齐齐哈尔大学招聘吗?不会! | 《演说家》节目 | 2017年 |
| 如果我是家长,孩子非要报新闻学,我一定会把他打晕 | 直播回答家长提问(理科590分想报川大新闻) | 2023年6月 |
| 学习,是你这辈子遇到过最简单的事情,没有之一。 | 2019年吉林财经大学演讲 | 2019年 |

**为什么重要**:
- 金句**溯源到具体场合**(节目/讲座/直播) → 增强权威感
- **时间戳**可判断时效性(2017 年言论 vs 2023 年言论,权重不同)
- 当用户问"张雪峰怎么看",可精确回答"他在 2017 年《演说家》说过..."
- 现版本"项目内部语料整理"使 LLM 无法引用具体场合,**降低人设真实感**

**提升目标**:
- 沉淀 50 句张雪峰**原版金句**到 `knowledge/quotes/zhangxuefeng_originals.json`
- 与现有 505 条**并存**(原版金句用于"溯源"诉求,内部金句用于"日常"建议)
- 不破坏现有 RAG pipeline,只增加新数据源

### 缺口 2:叙事层调研资料(WHY,不只是 WHAT)

**现状**:现有 `knowledge/groups/G1-G8` 都是**方法论 + 数据**(WHAT to do)
- G1:核心方法论
- G2:专业/学校数据
- G3:就业趋势数据
- G4:城市生活
- G5:数据格式
- G6:速查
- G7:就业路径
- G8:考研/专科

**应有状态**(zhangxuefeng 项目独有):
- `01-writings.md` — 5 本书核心论点(**方法论溯源**)
- `02-conversations.md` — 15+ 采访 + 4 节目 + 6 争议事件(**观点演变**)
- `04-external-views.md` — 2.5 页批评 + 4 盲点(**反向校验**)
- `05-decisions.md` — 11 决策 + 5 行为模式(**决策模式案例**)
- `06-timeline.md` — 24 年时间线(**价值观形成**)

**为什么重要**:
- 让 AI 回答"为什么这么建议"时有**真实案例支撑**
- `04-external-views.md` 的 4 个盲点 = 4 个"反向校验"思路,防止 LLM 偏听偏信
- `05-decisions.md` 的 11 决策 = 11 个**真实决策案例**,可被 RAG 命中作为类比
- 现有 G1-G8 是"知识",**这是"故事"** —— LLM 在叙事上更擅长讲故事知识

**提升目标**:
- 把 5 个 references 文件**直接作为 RAG 数据源**挂入(无需重写,Markdown 即可)
- 不破坏现有 8 个 groups,**新增 1 个 group: G9 张雪峰方法论溯源**

### 缺口 3:6 条数据来源标注硬规则(从软到硬)

**现状**(`system_prompt.md` 中"8 条基础原则"第 3 条):
> "3. **不说瞎话**:不确定的数据要标注'建议查最新官方信息',不要编。"

**问题**:这是**自然语言**软规则,LLM 可能不执行(尤其在 token 紧张时)。

**应有状态**(zhangxuefeng `SKILL.md:196-207`):

> **以下标注规则在任何情况下不可跳过、不可简化、不可"批量处理后再标注":**
> 1. **录取分数线/位次**:`XX大学 XX专业 XXX分/位次XXXXX(来源:XX省教育考试院 20XX年投档数据)`
> 2. **薪资数据**:`年薪XX-XX万(来源:XX大学20XX年就业质量报告 / 猎聘20XX年度报告 / Boss直聘20XX行业薪资报告)`
> 3. **就业率**:`就业率XX%(来源:XX大学20XX年就业质量报告 / 教育部20XX年高校就业统计)`
> 4. **行业数据**:`(来源:XX研究院20XX年行业报告 / XX部门发布)`
> 5. **未交叉验证的数据**:必须标注 `⚠️ 此数据来自单一来源(XX网站),建议到省考试院官网二次确认`
> 6. **训练语料推断的数据**:`⚠️ 此为往年趋势推断,非实时数据,请以最新官方公布为准`

**为什么重要**:
- "在任何情况下不可跳过"=**绝对硬规则**措辞
- 6 条**明确格式模板** LLM 可直接套用
- "不可批量处理后再标注" 解决 LLM 常见的"最后统一加来源"漏标问题
- 现有实现只有"标注来源"这个**原则**,无**格式模板**

**提升目标**:
- 把 6 条规则**字面照搬**到 `system_prompt.md`(替换"8 条基础原则"第 3 条)
- 在 `server/graph/nodes/structure.py` 加一个**正则后处理**:检测 LLM 输出,如果提到具体数字未带 `来源:` 标记,自动注入 ⚠️ 提示

---

## 3. 实施方案(3 个 Phase / 6-8 天)

### Phase 1:金句溯源(2 天,纯内容)

**目标**:把 zhangxuefeng 50 句原版金句**带出处时间**沉淀到 RAG

**1.1 创建数据文件** `knowledge/quotes/zhangxuefeng_originals.json`

```json
[
  {
    "id": "zx_001",
    "text": "中国几乎所有500强企业都说学历不重要,但他们会去齐齐哈尔大学招聘吗?不会!",
    "tags": ["学历", "500强", "招聘", "齐齐哈尔大学"],
    "context": "《演说家》反驳老板马丁",
    "source": "节目",
    "source_detail": "《演说家》2017年",
    "year": 2017,
    "category": "xuexi",
    "tone": "犀利"
  },
  {
    "id": "zx_002",
    "text": "如果我是家长,孩子非要报新闻学,我一定会把他打晕,然后给他报个别的。",
    "tags": ["新闻学", "专业选择", "家长"],
    "context": "直播回答家长提问(理科590分想报川大新闻)",
    "source": "直播",
    "source_detail": "2023年6月直播",
    "year": 2023,
    "category": "zhuanye",
    "tone": "犀利"
  },
  // ... 共 50 句
]
```

**1.2 改造 `kb_retriever.py`** — 让 RAG 加载这个文件

修改 `_load_quotes` 方法(行 282-299):
```python
def _load_quotes(self, quotes_path: str) -> list[QuoteEntry]:
    quotes: list[QuoteEntry] = []
    # 现有 _by_major.json 加载
    index_path = os.path.join(quotes_path, "_by_major.json")
    if os.path.exists(index_path):
        quotes.extend(self._load_major_index(index_path))
    # 新增:加载 zhangxuefeng 原版金句
    zx_path = os.path.join(quotes_path, "zhangxuefeng_originals.json")
    if os.path.exists(zx_path):
        quotes.extend(self._load_zhangxuefeng_originals(zx_path))
    return quotes
```

**1.3 改造 LLM prompt 注入逻辑** — 让 LLM 知道有"溯源型"金句可用

在 `server/graph/nodes/quality_nodes.py` `quality_orchestrate_node`(行 34-78)中:
- 当用户问题含"张雪峰说过""直播里讲""《演说家》"等触发词
- RAG 优先召回 `zhangxuefeng_originals.json`
- Prompt 注入格式:`(2017年《演说家》节目) "..." ——张雪峰`

**1.4 测试** `tests/test_quote_attribution.py`(新建)

```python
def test_zhangxuefeng_quote_loaded():
    retriever = KbRetriever(
        groups_dir="knowledge/groups",
        quotes_path="knowledge/quotes",
    )
    zx_quotes = [q for q in retriever._quotes if q.id.startswith("zx_")]
    assert len(zx_quotes) >= 50

def test_zx_quote_has_source_year():
    """每条原版金句必须有 source_detail 和 year 字段。"""
    for q in zx_quotes:
        assert q.source_detail, f"Missing source_detail: {q.id}"
        assert 2017 <= q.year <= 2026, f"Invalid year: {q.id}"
```

### Phase 2:叙事知识入 RAG(2 天,纯内容)

**目标**:把 5 个 references 文件作为 G9 group 挂入

**2.1 创建 `knowledge/groups/G9_zhangxuefeng_methodology_origin.md`**

直接整合 5 个 references 文件内容(精简后),按主题切片:
```markdown
# G9 张雪峰方法论溯源(WHY 张雪峰这样说)

## 9.1 核心论点的书籍溯源
[来自 01-writings.md 的 5 本书核心论点]

## 9.2 关键决策的"为什么"
[来自 05-decisions.md 的 11 决策]

## 9.3 观点演变
[来自 02-conversations.md 的观点变化时间线]

## 9.4 反向校验:4 个盲点
[来自 04-external-views.md 的批评]

## 9.5 24 年时间线
[来自 06-timeline.md 的关键事件]
```

**2.2 更新 `kb_retriever.py` GROUP_TRIGGERS**(行 53-88)

```python
GROUP_TRIGGERS["G9_zhangxuefeng_methodology_origin"] = [
    "张雪峰", "为什么这么说", "观点演变", "出处",
    "反例", "盲点", "批评", "局限",
    "《演说家》", "直播", "讲座", "决策",
]
```

**2.3 测试** `tests/test_g9_retrieval.py`(新建)

```python
def test_g9_triggers_match_zhangxuefeng_query():
    """含'张雪峰'/'为什么'/'出处'应触发 G9。"""
    retriever = KbRetriever(...)
    result = retriever.search("张雪峰为什么反对新闻学?")
    assert "G9_zhangxuefeng_methodology_origin" in result.groups
```

### Phase 3:6 条数据来源标注硬规则(2-3 天,半代码半内容)

**目标**:从"软规则"升级为"硬规则 + 自动校验"

**3.1 Prompt 层修改**(`system_prompt.md`)

替换"8 条基础原则"第 3 条,新增"硬规则"章节:

```markdown
## 数据来源标注硬规则(最高优先级,不可批量处理后再标注)

任何具体数据(分数/位次/薪资/就业率/行业)在回复中首次出现时,必须立即标注来源,
**不允许先输出全部数字最后统一加来源**。使用以下 6 条格式:

1. **录取分数线/位次**:`XX大学 XX专业 XXX分/位次XXXXX(来源:XX省教育考试院 20XX年投档数据)`
2. **薪资数据**:`年薪XX-XX万(来源:XX大学20XX年就业质量报告 / 猎聘20XX年度报告)`
3. **就业率**:`就业率XX%(来源:XX大学20XX年就业质量报告 / 教育部20XX年高校就业统计)`
4. **行业数据**:`(来源:XX研究院20XX年行业报告)`
5. **未交叉验证的数据**:必须标注 `⚠️ 此数据来自单一来源(XX网站),建议二次确认`
6. **训练语料推断的数据**:`⚠️ 此为往年趋势推断,非实时数据`

**❌ 严禁**:不标来源地引用具体数字(如"录取分数线是 XXX"但不说数据从哪来)
```

**3.2 代码层添加正则后处理**(`server/graph/nodes/structure.py`)

新增方法 `validate_source_attribution`:
```python
import re

# 匹配"具体数字 + 单位"且未带"来源"的句子
NUMBER_PATTERN = re.compile(
    r'(\d+[\d,\.]*)\s*'
    r'(分|位次|%|万|元/月|元/年|人|所|个|倍)',
)

def validate_source_attribution(reply: str) -> str:
    """检测回复中无来源标注的具体数字,自动追加警告。"""
    # 按句子切分
    sentences = re.split(r'([。！？\n])', reply)
    annotated: list[str] = []
    for sent in sentences:
        if not sent.strip():
            annotated.append(sent)
            continue
        # 如果含数字 + 单位,无"来源",加 ⚠️
        if NUMBER_PATTERN.search(sent) and '来源' not in sent and '⚠️' not in sent:
            sent = sent + " (来源:数据待补全)"
        annotated.append(sent)
    return ''.join(annotated)
```

**3.3 测试** `tests/test_source_attribution.py`(新建)

```python
def test_score_must_have_source():
    """含具体分数的句子必须有来源。"""
    reply = "你的分数是 580 分,可以去武汉理工大学。"
    result = validate_source_attribution(reply)
    assert "来源" in result

def test_vague_numbers_skipped():
    """模糊数字(如'很多''一些')不强制要求来源。"""
    reply = "很多学生都选了计算机。"
    result = validate_source_attribution(reply)
    # 不应追加来源(因为是模糊描述)
    assert result == reply

def test_attribution_passes():
    """已带来源的不重复添加。"""
    reply = "580 分(来源:湖北省考试院 2024)"
    result = validate_source_attribution(reply)
    assert result.count("来源") == 1
```

**3.4 集成到 render_reply 节点**

修改 `server/graph/nodes/render.py` 的最后一步,让 `validate_source_attribution` 作为后处理:
```python
def render_reply_node(state):
    raw_reply = state.get("reply", "")
    validated = validate_source_attribution(raw_reply)
    return {"reply": validated, ...}
```

---

## 4. 不做的事(避坑清单)

| ❌ 不要做 | 原因 |
|---|---|
| 把 zhangxuefeng-skill-merged 整个 `SKILL.md` 塞进 `system_prompt.md` | SKILL.md 是"以张雪峰身份说话"的人设,与现有"老炮规划师"人设冲突 |
| 引入"张雪峰 persona 切换"功能 | 用户已确认不需要,会污染默认人设 |
| 删 505 条现有金句 | 现有金句用于日常建议,zhangxuefeng 原版用于"溯源"诉求,场景不同 |
| 把 5 个 references 文件**原样**复制到 G9 | 原文件长(284 行/篇),LLM 上下文压力大,需精简 |
| 50 句金句**全量**塞进 system_prompt | 应走 RAG 检索,只回灌 top-3-5 |
| 在 emotion_detector.py 加"档位选择"逻辑 | emotion_detector 现有 3 级(高危/中危/低危),与 3 档表达(🔴🟡🟢)概念不同,不应耦合 |
| 修改现有 5 模型/8 启发/8 反模式内容 | 现有内容已与 zhangxuefeng 几乎一一对应,修改风险>收益 |
| 改 system_prompt.md 的版本号 | 应由 CLAUDE.md 自动化 pre-commit 触发,不要手动改 |

---

## 5. 风险评估

| 风险点 | 等级 | 缓解 |
|---|---|---|
| 50 句金句的质量参差 | 🟡 中 | 人工筛选,优先选 5-10 句最经典的入 RAG,其他备选 |
| G9 引入后 RAG 误召回(其他问题命中 G9) | 🟡 中 | GROUP_TRIGGERS 用具体触发词,不只用"张雪峰" |
| 后处理函数破坏 LLM 输出格式 | 🟡 中 | 单元测试覆盖 + 与现有 disclaimer 检测兼容 |
| Phase 3 硬规则与现有"8 条原则"措辞冲突 | 🟢 低 | 硬规则为新增段落,8 条原则保留 |
| 现有 333+ tests 在新增 3 个测试文件后通过率下降 | 🟢 低 | 单元测试不依赖外部 API |

---

## 6. 实施检查清单(Checklist)

### Phase 1(2 天)
- [ ] 创建 `knowledge/quotes/zhangxuefeng_originals.json`(50 条)
- [ ] 改造 `kb_retriever.py:282-299` `_load_quotes` 方法
- [ ] 改造 `quality_nodes.py:34-78` 注入溯源金句
- [ ] 新建 `tests/test_quote_attribution.py`(3+ 测试)
- [ ] 跑通 `pytest tests/test_quote_attribution.py -v`
- [ ] 跑通全量 `pytest --tb=short` 无回归
- [ ] 更新 `docs/2026-06-14-xuefeng-integration-v1.md`(本方案执行记录)

### Phase 2(2 天)
- [ ] 创建 `knowledge/groups/G9_zhangxuefeng_methodology_origin.md`(精简整合 5 个 references)
- [ ] 改造 `kb_retriever.py:53-88` `GROUP_TRIGGERS` 新增 G9
- [ ] 新建 `tests/test_g9_retrieval.py`(2+ 测试)
- [ ] 跑通测试
- [ ] 手动验证:用"张雪峰为什么反对新闻学"等 query 触发 G9

### Phase 3(2-3 天)
- [ ] 修改 `system_prompt.md` 新增"数据来源标注硬规则"章节
- [ ] 触发 `extract_prompt.py` 自动归档为 v2.11
- [ ] 创建 `server/graph/nodes/structure.py` `validate_source_attribution` 方法
- [ ] 改造 `server/graph/nodes/render.py` 调用后处理
- [ ] 新建 `tests/test_source_attribution.py`(5+ 测试)
- [ ] 跑通全量测试无回归
- [ ] 手动验证:故意构造一个无来源回复,看是否被自动标注

---

## 7. 后续可考虑(本方案不实施,留作 v2)

| 想法 | 优先级 | 备注 |
|---|---|---|
| 引入"张雪峰 persona 切换"作为可选项 | 🟢 P2 | 用户已确认默认不做 |
| 把 5 个 references 文件做向量化(语义检索) | 🟡 P1 | 当前 keyword+vector 混合已够,延后 |
| 引入"多角色审计"(`multi-perspective-audit.md`) | 🟡 P1 | 已在 `prompts/templates/`,可实施 |
| 把 50 句金句做情绪分类(犀利/温和/共情) | 🟢 P2 | Phase 1 已记录 tone 字段,后续可作 RAG 过滤 |

---

## 8. 与既有文档的关系

| 文档 | 关系 |
|---|---|
| [docs/secondary-development-log.md](./secondary-development-log.md) | 上一轮(2026-06-13)整合日志,记录了"105 语录/三档语气"等**已完成**部分,本方案是**新一轮补全** |
| [docs/implementation-plan-phase0-2.md](./implementation-plan-phase0-2.md) | P0/P1/P2 21 任务全部完成的记录,本方案在其后 |
| [prompts/CHANGELOG.md](../prompts/CHANGELOG.md) | 本方案 Phase 3 完成后,会新增 v2.11 归档条目 |
| [CLAUDE.md](../CLAUDE.md) | 已规定 system_prompt 改动的自动归档流程,本方案 Phase 3 触发 |

---

## 9. 实施完成后建议的同步动作

1. **更新 README.md**:把"知识库"部分从 8 个 groups 改为 9 个,加注 G9 用途
2. **更新 system_prompt.md 头部 v 号注释**:v2.7 → v2.11(自动)
3. **更新 gaobao-advisor-improvement-plan.md**(记忆中的 49 天方案):标记 3 块已实施
4. **在 MEMORY.md 中新增**:本次整合的工作量、关键决策、未实施项
5. **创建本方案执行记录** `docs/2026-06-14-xuefeng-integration-execution.md`

---

## 10. 核心 KPI(成功度量)

| 指标 | 现状 | 目标 | 衡量方式 |
|---|---|---|---|
| 语录总数 | 505 | 555(50 句原版) | `len(retriever._quotes)` |
| 知识组数 | 8 | 9 | `len(retriever._groups)` |
| 数据来源标注覆盖率 | 0%(无自动检测) | ≥80% | 后处理日志 + 人工抽检 100 条 |
| 文档-实现一致 | v2.7 注释 vs v2.10 归档 | 一致 | 跑 `extract_prompt.py --validate` |
| 测试通过率 | 100%(430+) | 100%(+ 15 新增) | `pytest --tb=short` |
| 测试覆盖率 | ≥80% | ≥80% | `pytest --cov` |

---

**方案结束。请审核以下 3 个决策点:**

1. ✅ **Phase 1 金句数**:50 句 vs 100 句 vs 全部 264 句?
2. ✅ **Phase 2 整合深度**:精简整合(每篇 <100 行) vs 全文照搬(每篇 60-280 行)?
3. ✅ **Phase 3 触发后处理的阈值**:仅检测"具体数字+单位"vs 检测所有名词性数据(年份/学校名/位次)?

任一项有疑问,或希望我直接进入实施,告诉我即可。
