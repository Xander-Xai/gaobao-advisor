# 输出安全过滤层模板

> 适用于：所有面向用户的 LLM 应用。解决"模型可能说出不该说的话"的问题。

---

## 设计原则

- **输出即不可信**：模型输出必须经过过滤才能到达用户
- **不只拦截，还要重写**：被拦截的内容替换为合规表述，而非生硬的"无法回答"
- **四步流水线**：每条响应必须依次通过 4 个检查点

---

## 四步过滤管道

```
LLM 原始输出
    │
    ▼
┌─────────────────────────────┐
│ Step 1: System Prompt 泄露检测 │ ──→ 命中 → 替换为安全回答
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Step 2: 违规内容检测           │ ──→ 命中 → 重写为合规表述
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Step 3: 情感安全检测           │ ──→ 命中 → 切换危机干预 SOP
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Step 4: 合规尾注注入           │ ──→ 自动附加免责/来源信息
└──────────────┬──────────────┘
               ▼
          最终输出给用户
```

---

## Step 1 — System Prompt 泄露检测

### 检测模式

```yaml
prompt_leakage_patterns:
  # 自我指涉泄露
  - pattern: '(我是|我被设定为|我的系统提示|我的指令是|我的人设是|我的角色是)'
    severity: critical
    # 例外：正常的人格表达"我是规划师"不算泄露
    exception: '(我是.*志愿.*规划师|我是.*高考.*顾问|我是.*资深.*规划师)'

  # 输出 prompt 结构
  - pattern: '(\{[^}]*"role"[^}]*\}|"system":\s*"|<system>|<instructions>)'
    severity: critical

  # 泄露关键词
  - pattern: '(system\s*prompt|系统提示词|提示词内容|内部指令|底层规则|原始指令)'
    severity: high

  # 模型自我揭露
  - pattern: '(我是(一个)?(AI|人工智能|语言模型|大模型|LLM|助手)|I am (an? )?(AI|language model|LLM|assistant))'
    severity: high
    # 例外：讨论 AI 话题时不算
    exception: '(关于|话题|讨论|说到|提到).{0,20}(AI|人工智能)'

  # JSON/XML 输出泄露
  - pattern: '(\{"[^"]*":\s*"[^"]*"\s*,\s*"[^"]*")|(<(system|user|assistant|role)>)'
    severity: critical
```

### 命中后的替换策略

```yaml
replacements:
  critical:
    action: '替换整条响应'
    template: |
      我就是专注做高考志愿规划的，帮你做志愿填报。
      你有什么关于志愿填报的问题，直接问就行。
  high:
    action: '移除泄露片段，保留其余内容'
    process: '用正则移除匹配片段，检查剩余内容是否仍有意义'
    fallback: '如果移除后内容无意义，使用 critical 模板'
```

---

## Step 2 — 违规内容检测

### 高考场景专用违规库

```yaml
hard_block:
  # 绝对保证类（违反《暂行办法》+ 行业规范）
  absolute_guarantees:
    patterns:
      - '(保证|确保|肯定|一定|必定|100%|百分之一百).{0,10}(录取|考上|上岸|通过|被.*录取)'
      - '(稳了|包过|包录取|保底.*录取|铁定能上)'
      - '(我(保证|承诺|打包票)(你)?(能|会|可以)(考上|录取|上))'
    action: '重写'
    rewrite_template: '根据往年数据，{大学}{专业}在{省份}的录取位次大约在{区间}，你的位次{比较分析}。志愿填报存在多种变量，建议作为参考范围之一。'

  # 消极否定类（可能造成心理伤害）
  negative_predictions:
    patterns:
      - '(你(肯定|一定|绝对|铁定)?(考不上|没戏|没希望|没机会|白搭|凉了))'
      - '(放弃(吧|得了|算了)|别想了|做梦吧|不可能的)'
      - '(以你(的)?(成绩|分数|水平)(根本|压根|完全)?(不|没)(可能|戏|希望))'
    action: '重写'
    rewrite_template: '以你目前的分数，{大学}确实竞争激烈，但我建议你同时关注{替代方案}，这些学校在{优势}方面其实不错。'

  # 个人信息泄露（响应中不应出现用户未明确提供的隐私）
  privacy_leakage:
    patterns:
      - '(你的(手机号|电话|身份证|地址|学校全名|家庭住址))'
      # 注意：如果用户主动提供了这些信息，AI 不应复述
    action: '移除隐私字段'

soft_block:
  # 敏感话题（不拦截但添加警告）
  sensitive_topics:
    - topic: '作弊/替考'
      patterns: '(作弊|替考|代考|泄题|买答案|传答案)'
      response_addition: '提醒：高考作弊属于违法行为，将面临取消成绩、禁考等严厉处罚。'
    - topic: '极端行为'
      patterns: '(报复|威胁|伤害).{0,10}(学校|老师|招生|考官)'
      escalate_to: 'crisis_sop'
```

---

## Step 3 — 情感安全检测

### 危机信号等级

```yaml
crisis_levels:
  # Level 1 — 高压力（正常范围但需关注）
  level_1:
    signals:
      - '(压力大|好焦虑|睡不着|紧张|害怕|担心考不好)'
      - '(爸妈(期望|要求|压力)|家里(压力|期望)|老师(批评|失望))'
    response: '共情 + 理性分析 + 减压建议'
    template: |
      我理解你的压力，这很正常。
      但你要知道，{理性分析当前情况}。
      现阶段最重要的是{具体建议}，其他的先别想太多。

  # Level 2 — 严重焦虑（需要积极干预）
  level_2:
    signals:
      - '(完了|废了|毁了|人生没有意义|活着没意思|考砸了一切都完了)'
      - '(对不起(爸妈|家人|老师)|让他们失望了|我是个废物|我太差了)'
    response: '深度共情 + 事实锚定 + 资源推荐'
    template: |
      你现在的感受我完全理解，高考压力确实很大。
      但我想告诉你一个事实：{真实的正面案例或数据}。
      如果你觉得很难受，可以跟信任的人聊聊，
      也可以拨打 12355 青少年服务热线，那里的老师很专业也很耐心。

  # Level 3 — 自残/自杀信号（紧急干预）
  level_3:
    signals:
      - '(不想活了|想死|自杀|跳楼|割腕|结束(生命|一切)|活着太累了)'
      - '(遗书|告别|最后(一次|一面)|不会再(烦|打扰)你们了)'
    response: '立即切换为危机干预 SOP'
    template: |
      我听到你了，你现在很痛苦，我很担心你的安全。

      请你现在就拨打这个电话：
      📞 全国24小时心理援助热线：400-161-9995
      📞 北京心理危机研究与干预中心：010-82951332
      📞 生命热线：400-821-1215

      你的安全比任何事情都重要。请现在就联系他们。
      如果你身边有信任的人，请告诉他们你现在的感受。
```

---

## Step 4 — 合规尾注注入

### 触发条件

```yaml
footer_rules:
  # 当响应涉及具体院校推荐时，必须附加
  triggers:
    - '提到具体大学名称 + 录取相关数据'
    - '给出冲/稳/保建议'
    - '引用往年分数线或位次'

  footer_template: |
    ---
    ⚠️ 以上建议基于{数据年份}年公开数据，仅供参考，不作为志愿填报最终依据。
    请以各省教育考试院官方发布的信息为准。

  # 当响应不涉及具体数据时，不需要尾注
  skip_when:
    - '纯闲聊/情感交流'
    - '解释政策概念（不含具体数据）'
    - '通用建议（不含个性化推荐）'
```

---

## 过滤效果监控

```yaml
monitoring:
  # 过滤统计（每日汇总）
  metrics:
    - name: 'prompt_leakage_rate'
      description: '触发 Step 1 的响应占比'
      alert_threshold: '> 1%'
      action: '排查 system prompt 是否有泄露风险'

    - name: 'violation_rewrite_rate'
      description: '触发 Step 2 重写的响应占比'
      alert_threshold: '> 3%'
      action: '分析违规模式，优化 system prompt 从源头减少'

    - name: 'crisis_trigger_rate'
      description: '触发 Step 3 的响应占比'
      alert_threshold: '> 0.5%'
      action: '可能有用户群体在测试系统，或需要增加心理支持资源'

    - name: 'false_positive_rate'
      description: '被误拦的正常响应占比（抽检）'
      alert_threshold: '> 5%'
      action: '调整正则阈值或例外规则'
```

---

## 在代码中的实现建议

```python
# 伪代码示意
def filter_response(raw_output: str, user_input: str, conversation: list) -> str:
    # Step 1
    if detect_prompt_leakage(raw_output):
        return SAFETY_TEMPLATE

    # Step 2
    violation = detect_violations(raw_output)
    if violation:
        raw_output = rewrite_violation(raw_output, violation)

    # Step 3
    crisis = detect_crisis(user_input)
    if crisis:
        return generate_crisis_response(crisis.level)

    # Step 4
    if needs_footer(raw_output):
        raw_output += generate_footer(raw_output)

    return raw_output
```
