# 生产可观测性模板

> 适用于：所有已部署的 LLM 应用。从"出了问题才知道"升级为"问题发生前就能感知"。

---

## 监控 vs 可观测性

| | 监控（Monitoring） | 可观测性（Observability） |
|:--|:--|:--|
| 关注点 | "系统是否正常？" | "为什么系统不正常？" |
| 方法 | 阈值告警（CPU > 80%） | 多维度关联分析 |
| 工具 | Prometheus + Grafana | Langfuse + 日志 + 追踪 |
| 例子 | "API 错误率 > 1%" | "这批错误集中在广东省用户的'计算机专业推荐'场景，原因是知识库中该校的选科要求数据过期" |

**两者都需要，不可替代。**

---

## 指标体系（四层）

### 第一层 — 基础设施指标（秒级）

```yaml
infrastructure_metrics:
  # LLM API 健康度
  api_health:
    - name: 'llm_api_latency_p50'
      description: 'LLM API 响应时间 P50'
      unit: 'ms'
      normal: '< 1500ms'
      warning: '> 2000ms'
      critical: '> 5000ms'
      action_on_critical: '自动切换备用模型'

    - name: 'llm_api_latency_p95'
      description: 'LLM API 响应时间 P95'
      unit: 'ms'
      normal: '< 3000ms'
      warning: '> 5000ms'
      critical: '> 10000ms'

    - name: 'llm_api_error_rate'
      description: 'LLM API 错误率（429/500/503）'
      unit: '%'
      normal: '< 0.5%'
      warning: '> 1%'
      critical: '> 5%'
      action_on_critical: '切换备用模型 + 通知运维'

    - name: 'llm_api_timeout_rate'
      description: 'LLM API 超时率（>30秒）'
      unit: '%'
      normal: '< 0.1%'
      warning: '> 0.5%'
      critical: '> 2%'

  # 应用服务健康度
  app_health:
    - name: 'request_queue_depth'
      description: '等待处理的请求数'
      normal: '< 10'
      warning: '> 50'
      critical: '> 200'

    - name: 'memory_usage'
      description: '服务内存使用率'
      normal: '< 70%'
      warning: '> 85%'
      critical: '> 95%'
```

### 第二层 — 业务流程指标（分钟级）

```yaml
business_metrics:
  # 对话质量
  conversation_quality:
    - name: 'conversation_completion_rate'
      description: '用户完成完整咨询流程的比例'
      measurement: '从首次提问到至少获得一轮推荐的会话占比'
      target: '> 60%'
      alert: '< 40%'

    - name: 'avg_conversation_turns'
      description: '平均对话轮数'
      target: '5-8 轮'
      alert: '< 3轮（可能体验差）或 > 15轮（可能信息收集效率低）'

    - name: 'user_satisfaction_rate'
      description: '用户主动评价的正面比例'
      measurement: '👍 / (👍 + 👎)'
      target: '> 70%'
      alert: '< 60%'

    - name: 'early_abandon_rate'
      description: '用户在前 2 轮就离开的比例'
      target: '< 30%'
      alert: '> 50%'

  # 安全指标
  safety:
    - name: 'injection_block_rate'
      description: '注入攻击拦截率'
      measurement: '被 Layer 1/2/3 拦截的请求占比'
      normal: '0.1%-1%'
      alert: '> 5%（可能正在被攻击）或 < 0.01%（检测可能失效）'

    - name: 'crisis_intervention_rate'
      description: '危机干预触发率'
      measurement: '触发 Level 2+ 危机响应的对话占比'
      normal: '< 0.1%'
      alert: '> 0.5%（可能有异常用户群体）'

    - name: 'output_filter_hit_rate'
      description: '输出过滤触发率'
      measurement: '被 Step 2 重写的响应占比'
      normal: '< 1%'
      alert: '> 3%（system prompt 可能需要优化）'
```

### 第三层 — 成本指标（小时级）

```yaml
cost_metrics:
  - name: 'cost_per_conversation'
    description: '每次完整对话的 API 成本'
    unit: 'RMB'
    target: '< ¥0.10'
    alert: '> ¥0.50'

  - name: 'daily_total_cost'
    description: '每日 API 总成本'
    unit: 'RMB'
    budget: '{根据你的预算设定}'
    alert_when: '日消耗超过月预算的 5%'

  - name: 'tokens_per_conversation'
    description: '每次对话的平均 token 消耗'
    target: '< 3000 tokens'
    alert: '> 8000 tokens（可能有冗长对话或 prompt 需要优化）'

  - name: 'cache_hit_rate'
    description: '语义缓存命中率（如果启用了缓存）'
    target: '> 15%'
    note: '高考咨询个性化程度高，缓存命中率天然低于通用 Q&A'
```

### 第四层 — 数据质量指标（日级）

```yaml
data_quality_metrics:
  - name: 'hallucination_rate_sampled'
    description: '幻觉率（每日抽检）'
    measurement: '每日随机抽 50 条对话，人工/LLM-judge 验证事实准确性'
    target: '< 5%'
    alert: '> 10%'

  - name: 'data_coverage'
    description: '知识库覆盖度'
    measurement: '用户提问涉及的院校/专业中，知识库有数据的比例'
    target: '> 90%'
    alert: '< 80%'

  - name: 'data_staleness'
    description: '数据时效性'
    measurement: '使用当年数据的推荐占比'
    target: '> 80%'
    alert: '< 60%（需要更新知识库）'
```

---

## 告警与响应

### 告警通道

```yaml
alert_channels:
  # 即时告警（5分钟内响应）
  immediate:
    channel: '企业微信/钉钉机器人 + 短信'
    triggers:
      - 'API 错误率 > 5%'
      - 'Critical 安全事件'
      - '服务完全不可用'

  # 快速告警（1小时内响应）
  quick:
    channel: '企业微信/钉钉机器人'
    triggers:
      - 'API 延迟 P95 > 5秒'
      - '注入攻击率异常飙升'
      - '用户满意度突然下降 > 10%'

  # 日常告警（24小时内处理）
  daily:
    channel: '邮件 + 工单系统'
    triggers:
      - '日成本超预算'
      - '幻觉率上升'
      - '知识库覆盖度下降'
```

### 响应手册

```yaml
incident_playbook:
  api_outage:
    symptom: 'LLM API 错误率 > 5% 或完全不可用'
    response:
      step_1: '确认是上游 API 问题还是自身网络问题'
      step_2: '切换备用模型（DeepSeek → Qwen → 通义千问）'
      step_3: '如果所有模型都不可用，启用缓存模式 + 降级回答'
      step_4: '通知用户"系统繁忙，请稍后再试"'
      step_5: '恢复后切换回主模型，通知用户'

  cost_spike:
    symptom: '日成本突增 > 200%'
    response:
      step_1: '检查是否有异常长对话或循环调用'
      step_2: '检查是否有注入攻击导致的大量请求'
      step_3: '如果确认是攻击 → 启用严格限流'
      step_4: '如果是正常增长 → 调整预算或优化 prompt'

  quality_degradation:
    symptom: '幻觉率 > 10% 或满意度下降 > 15%'
    response:
      step_1: '检查是否最近有 prompt/model 变更'
      step_2: '检查知识库是否有异常数据'
      step_3: '对比变更前后的回归测试结果'
      step_4: '如有变更 → 回滚；如无变更 → 排查模型/API 变化'
```

---

## 技术栈推荐

```yaml
recommended_stack:
  # 开源方案（推荐，可自部署满足国内合规）
  open_source:
    tracing:
      tool: 'Langfuse'
      url: 'https://langfuse.com'
      features: '请求追踪、prompt 版本管理、成本统计、评估集成'
      deployment: 'Docker 自部署'

    metrics:
      tool: 'Prometheus + Grafana'
      features: '基础设施指标、自定义业务指标、告警规则'

    logging:
      tool: 'Loki（日志） + Grafana（可视化）'
      features: '结构化日志存储、查询、关联分析'

  # 商业方案（功能更全，但需考虑数据出境）
  commercial:
    - 'LangSmith（LangChain 生态）'
    - 'Helicone（代理模式，最小侵入）'
    - 'Datadog LLM Observability（企业级）'

  # 最小可行方案（快速起步）
  mvp:
    - '结构化日志输出到文件（JSON 格式）'
    - 'Python 脚本每日汇总分析'
    - '企业微信机器人发送日报'
    - '成本：接近零（只需开发时间）'
```

---

## 日报/周报模板

```yaml
report_templates:
  daily_report: |
    # 高考志愿助手日报 - {date}

    ## 运行概况
    - 今日会话数: {N} ({vs_yesterday})
    - 今日 API 成本: ¥{cost} ({vs_yesterday})
    - P95 延迟: {latency}ms
    - 错误率: {error_rate}%

    ## 质量概况
    - 用户满意度: {satisfaction}% ({vs_yesterday})
    - 危机干预: {crisis_count} 次
    - 安全拦截: {block_count} 次

    ## 告警
    - {告警列表，无则显示"无告警"}

    ## 需要关注
    - {异常点说明}

  weekly_report: |
    # 高考志愿助手周报 - Week {week_number}

    ## 本周趋势
    - 会话数: {weekly_total} (日均 {daily_avg})
    - 成本: ¥{weekly_cost} (日均 ¥{daily_cost})
    - 满意度: {satisfaction}% ({vs_last_week})

    ## Top 10 热门咨询
    - {院校/专业排行}

    ## 省份分布
    - {省份会话占比}

    ## 质量事件
    - 幻觉率: {hallucination}% ({trend})
    - 安全事件: {count} 次

    ## 下周行动项
    - {action_items}
```
