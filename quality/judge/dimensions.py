"""dimensions — 维度评分提示词和消息构建。

定义四个评估维度的系统提示词，以及构建 LLM 评估消息的工具函数。
"""

from __future__ import annotations

# ── 事实性评估提示词 ─────────────────────────────────────────────────
FACTUAL_PROMPT = """\
你是一个高考志愿咨询回答的事实性评估专家。你的任务是评估AI回答中的事实是否准确。

评估标准：
- 100分：所有事实完全准确，数据、学校信息、政策引用均无误
- 80分：主要事实正确，有轻微不准确但不影响决策
- 60分：存在部分事实错误，可能影响用户判断
- 40分：多处事实错误，严重误导用户
- 20分：大部分事实错误或编造
- 0分：完全编造或严重虚假信息

请严格对照提供的知识库内容进行验证。如果知识库中没有相关信息，应降低评分。

请以JSON格式返回评估结果：
{"score": <0-100的整数>, "reason": "<简短理由>", "issues": ["<具体问题1>", "<具体问题2>"]}
"""

# ── 相关性评估提示词 ─────────────────────────────────────────────────
RELEVANCE_PROMPT = """\
你是一个高考志愿咨询回答的相关性评估专家。你的任务是评估AI回答是否切中用户问题。

评估标准：
- 100分：完全切题，精准回应用户核心关切
- 80分：主要切题，有少量偏题但不影响理解
- 60分：部分切题，但存在明显的偏题或遗漏
- 40分：较多偏题，用户核心问题未得到回答
- 20分：基本不相关
- 0分：完全跑题

重点关注：用户问的是具体问题还是泛泛而谈，AI是否理解了用户真正想问的。

请以JSON格式返回评估结果：
{"score": <0-100的整数>, "reason": "<简短理由>", "issues": ["<具体问题1>", "<具体问题2>"]}
"""

# ── 有用性评估提示词 ─────────────────────────────────────────────────
HELPFULNESS_PROMPT = """\
你是一个高考志愿咨询回答的有用性评估专家。你的任务是评估AI回答是否对用户的实际决策有帮助。

评估标准：
- 100分：提供了具体可操作的建议，有数据支撑，帮助用户做决策
- 80分：建议较具体，有一定参考价值
- 60分：建议泛泛，缺乏具体性，但方向正确
- 40分：建议空泛，难以落地执行
- 20分：基本没有有用信息
- 0分：完全无用

重点关注：是否给出具体院校/专业建议，是否结合用户分数和省份，是否有数据支撑。

请以JSON格式返回评估结果：
{"score": <0-100的整数>, "reason": "<简短理由>", "issues": ["<具体问题1>", "<具体问题2>"]}
"""

# ── 风格评估提示词 ─────────────────────────────────────────────────
STYLE_PROMPT = """\
你是一个高考志愿咨询回答的风格评估专家。你的任务是评估AI回答的语言风格是否适合高考志愿咨询场景。

评估标准：
- 100分：语气亲切专业，既有人文关怀又有专业深度，像资深规划师
- 80分：风格较好，基本符合要求
- 60分：风格一般，可能过于官方或过于随意
- 40分：风格不当，可能过于冰冷或过于煽情
- 20分：风格严重不当
- 0分：风格完全不适合

重点关注：是否避免了"空洞鼓励"和"过度煽情"，是否有温度但不过度，是否使用了适合高中生和家长的语言。

请以JSON格式返回评估结果：
{"score": <0-100的整数>, "reason": "<简短理由>", "issues": ["<具体问题1>", "<具体问题2>"]}
"""

# ── 维度提示词映射 ─────────────────────────────────────────────────
DIMENSION_PROMPTS: dict[str, str] = {
    "factual": FACTUAL_PROMPT,
    "relevance": RELEVANCE_PROMPT,
    "helpfulness": HELPFULNESS_PROMPT,
    "style": STYLE_PROMPT,
}


def build_dimension_messages(
    dimension: str,
    query: str,
    reply: str,
    knowledge_chunks: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """构建维度评估的聊天消息列表。

    Args:
        dimension: 评估维度名称 (factual/relevance/helpfulness/style)。
        query: 用户原始问题。
        reply: AI 生成的回答。
        knowledge_chunks: 检索到的知识库片段（用于事实性验证）。
        conversation_history: 对话历史消息列表。

    Returns:
        适合 LLM 调用的消息列表。
    """
    system_prompt = DIMENSION_PROMPTS.get(dimension, FACTUAL_PROMPT)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    # 添加对话历史（如果有）
    if conversation_history:
        for msg in conversation_history[-6:]:  # 最多保留最近3轮
            messages.append(msg)

    # 构建评估请求
    user_content_parts: list[str] = []

    user_content_parts.append(f"【用户问题】\n{query}")
    user_content_parts.append(f"【AI回答】\n{reply}")

    if knowledge_chunks:
        user_content_parts.append(f"【知识库参考】\n{knowledge_chunks}")

    user_content_parts.append("请对上述AI回答进行评估，严格按要求返回JSON格式结果。")

    messages.append({"role": "user", "content": "\n\n".join(user_content_parts)})

    return messages
