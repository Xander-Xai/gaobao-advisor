# Prompt A/B 测试框架模板

> 适用于：所有需要数据驱动优化 prompt 的 LLM 应用。解决"改了 prompt 不知道变好还是变差"的问题。

---

## 为什么需要 A/B 测试

你的 prompt 已经迭代了 4 个版本。但每次改动都依赖主观判断：
- "感觉 v2.1 的免责更规范了" — 但用户满意度有提升吗？
- "v2.2 去掉了名人引用" — 但回答的权威感是否下降了？

**A/B 测试让每次改动都有数据支撑。**

---

## 测试流程

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐
│ 定义假设  │ →  │ 设计实验   │ →  │ 分流执行   │ →  │ 统计分析   │ →  │ 决策部署  │
└─────────┘    └──────────┘    └──────────┘    └──────────┘    └─────────┘
```

### Step 1 — 定义假设

```yaml
hypothesis_template:
  # 每次 A/B 测试必须有明确的假设
  format: |
    H0（零假设）: {新版本} 在 {指标} 上与 {当前版本} 无显著差异
    H1（备择假设）: {新版本} 在 {指标} 上优于 {当前版本}，预期提升 {幅度}

  example:
    name: 'v2.2 金句引用方式优化'
    h0: 'v2.2（隐去名人引用）在用户满意度上与 v2.1 无显著差异'
    h1: 'v2.2 在用户满意度上不低于 v2.1（允许小幅下降 ≤5%），但在合规性上显著提升'
    rationale: '合规性提升的收益 > 满意度可能的轻微下降'
```

### Step 2 — 选择指标

```yaml
metrics:
  # 主要指标（只选 1 个，避免多重比较问题）
  primary_metric:
    options:
      - name: 'user_satisfaction'
        description: '用户主动评价（👍/👎）的正面比例'
        measurement: '每条响应后的 👍 率'
        why: '最直接反映用户感受'

      - name: 'recommendation_accuracy'
        description: '推荐院校的录取命中率'
        measurement: '事后验证：推荐的"稳"档院校是否真的录取了'
        why: '核心业务价值'
        caveat: '需要等到录取结果出来才能验证，周期长'

      - name: 'conversation_completion'
        description: '用户完成完整咨询流程的比例'
        measurement: '从开始到至少获得一轮推荐的会话占比'
        why: '反映整体体验流畅度'

      - name: 'hallucination_rate'
        description: '幻觉率（抽检）'
        measurement: '每周抽检 100 条对话，验证事实准确性'
        why: '质量和安全的综合指标'

    recommendation: '首选 user_satisfaction（即时反馈），辅以 hallucination_rate（质量保障）'

  # 次要指标（监控但不作为主要决策依据）
  secondary_metrics:
    - name: 'response_length'
      description: '平均响应字数'
      alert: '变化 > 30% 需要检查'

    - name: 'safety_trigger_rate'
      description: '安全过滤触发率'
      alert: '新版本触发率升高 > 2x → 可能过度保守'

    - name: 'cost_per_conversation'
      description: '每次对话的 API 成本'
      alert: '变化 > 50% 需要检查'

    - name: 'avg_turns'
      description: '平均对话轮数'
      alert: '显著增加可能意味着信息收集效率下降'
```

### Step 3 — 分流设计

```yaml
traffic_split:
  # 分流方式
  method: '用户 ID 哈希取模'
  implementation: |
    user_group = hash(user_id) % 100
    if user_group < traffic_percentage_new:
        prompt_version = "new"
    else:
        prompt_version = "current"

  # 分流比例（渐进式）
  phases:
    - phase: '小流量验证'
      new_percentage: 5
      duration: '3 天'
      trigger_to_next: '无 critical 安全事件'

    - phase: '扩大验证'
      new_percentage: 20
      duration: '7 天'
      trigger_to_next: '次要指标无显著退化'

    - phase: '大流量验证'
      new_percentage: 50
      duration: '7 天'
      trigger_to_next: '主要指标显著优于或不劣于'

    - phase: '全量发布'
      new_percentage: 100
      trigger: '统计显著性达成'

  # 最小样本量计算
  sample_size:
    method: '双样本比例检验 power analysis'
    parameters:
      baseline_rate: 0.70       # 当前满意度 70%
      minimum_detectable_effect: 0.05  # 最小可检测效应 5%
      significance_level: 0.05  # α = 0.05
      power: 0.80               # β = 0.20
    result: '每组约需 400 次完整会话'
    practical_implication: '5% 分流阶段约需 8000 次总访问，按日均 500 次需 16 天'

  # 一致性保证
  consistency:
    rule: '同一用户在整个实验期间始终在同一组'
    method: '哈希(user_id + 实验名称) → 确保不同实验互不干扰'
```

### Step 4 — 统计分析

```yaml
analysis:
  # 统计检验方法
  methods:
    proportion_test:
      use_when: '指标是比例（如满意度 👍 率）'
      method: '双样本 z 检验（proportions）'

    continuous_test:
      use_when: '指标是连续值（如响应长度、成本）'
      method: 'Mann-Whitney U 检验（不假设正态分布）'

  # 显著性标准
  significance:
    p_value_threshold: 0.05
    effect_size_threshold: 0.02  # Cohen's h > 0.2 视为有实际意义

  # 分层分析
  stratification:
    dimensions:
      - '省份组（3+3 / 3+1+2 / 传统）'
      - '分数段（高分/中分/低分）'
      - '对话轮数（短对话/长对话）'
    purpose: '检测整体无差异但某个子群体有差异的情况'
```

### Step 5 — 决策规则

```yaml
decision_rules:
  # 推进到全量
  ship:
    conditions:
      - '主要指标 p < 0.05 且效应量 > 最小阈值'
      - '次要指标无显著退化'
      - '安全指标无恶化'
    action: '全量部署新版本'

  # 保持现状
  keep_current:
    conditions:
      - '主要指标无显著差异'
      - '新版本无明显优势'
    action: '保留当前版本，分析为什么没有提升'

  # 回滚
  rollback:
    conditions:
      - '新版本主要指标显著劣于当前版本'
      - '或安全指标显著恶化'
      - '或出现 critical 安全事件'
    action: '立即回滚 + 复盘分析'

  # 灰度观察
  hold:
    conditions:
      - '样本量不足'
      - '结果方向一致但未达显著性'
    action: '延长实验至达到最小样本量'
```

---

## 实验记录模板

```yaml
experiment_log:
  id: 'exp-{YYYYMMDD}-{序号}'
  name: '{简短描述}'
  hypothesis: '{H0 和 H1}'

  versions:
    control:
      version: 'v2.2'
      description: '{当前版本关键特征}'
    treatment:
      version: 'v2.3-rc1'
      description: '{改动点}'

  primary_metric: '{指标名}'
  traffic_split: '{比例}'

  timeline:
    start: '{开始日期}'
    end: '{结束日期}'
    duration: '{天数}'

  results:
    sample_size:
      control: '{N}'
      treatment: '{N}'
    primary_metric:
      control: '{值}'
      treatment: '{值}'
      p_value: '{p}'
      effect_size: '{d}'
      significant: true/false
    secondary_metrics:
      - metric: '{名称}'
        control: '{值}'
        treatment: '{值}'
        significant: true/false

  decision: 'ship / keep_current / rollback / hold'
  rationale: '{决策理由}'

  learnings:
    - '{发现 1}'
    - '{发现 2}'
```

---

## 与现有项目的集成

1. **版本管理已有基础**：你的 `extract_prompt.py` + CHANGELOG 已经支持版本管理
2. **需要新增**：分流逻辑（在调用 LLM 前决定用哪个版本的 prompt）
3. **需要新增**：评价收集（在对话中嵌入 👍/👎 按钮）
4. **需要新增**：统计分析脚本（每日汇总对比数据）
5. **建议首次实验**：v2.1 vs v2.2（已有两个版本，可以直接对比）
