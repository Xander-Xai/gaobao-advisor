# 雪峰 Agent 质量驱动升级 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 xuefeng-advisor 从"能用"升级为"不可替代"——通过情绪智能、数据交叉验证、AI时代校正三个质量控制节点。

**Architecture:** 在现有 `agent.py` 的 `GaokaoAdvisor.chat()` 方法中插入三个质量控制模块（`quality/emotion_detector.py`、`quality/cross_validator.py`、`quality/ai_era_risk.py`），不改变现有代码结构，仅新增 `quality/` 目录和对应的集成代码。

**Tech Stack:** Python 3.10+, 纯标准库（零新依赖）, JSON 数据文件

**Spec:** `docs/superpowers/specs/2026-06-12-quality-driven-upgrade-design.md`

**项目路径:** `/home/dev/projects/xuefeng/xuefeng-advisor/`

---

## 文件结构

### 新建文件
| 文件 | 职责 |
|------|------|
| `quality/__init__.py` | 包初始化 |
| `quality/emotion_detector.py` | 情绪检测：关键词加权评分 → 🟢🟡🔴 三档 |
| `quality/cross_validator.py` | 交叉验证：多源数据比对，标注置信度 |
| `quality/ai_era_risk.py` | AI时代风险：结构化专业风险数据查询 |
| `quality/test_quality.py` | 三个模块的单元测试 |
| `quality/ai_era_risk_data.json` | 193个本科专业的AI风险评估数据 |

### 修改文件
| 文件 | 修改位置 | 修改内容 |
|------|---------|---------|
| `agent.py:534-548` | `chat()` 方法开头 | 插入情绪检测 + 注入策略 |
| `agent.py:593-678` | 数据查询块 | 交叉验证包裹 + AI风险注入 |
| `agent.py:697-710` | LLM 调用后 | 质量自检（8项清单） |

---

## Task 1: 创建 quality/ 包和情绪检测模块

**Files:**
- Create: `quality/__init__.py`
- Create: `quality/emotion_detector.py`
- Create: `quality/test_quality.py`

- [ ] **Step 1: 创建 quality 包**

```python
# quality/__init__.py
"""质量控制模块：情绪检测、数据交叉验证、AI时代校正。"""
```

- [ ] **Step 2: 写情绪检测器的失败测试**

```python
# quality/test_quality.py
"""质量控制模块的单元测试。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quality.emotion_detector import detect_emotion


def test_normal_input():
    """普通咨询消息应返回🟢正常档。"""
    result = detect_emotion("我是湖北考生，580分，想学计算机")
    assert result["level"] == "🟢"
    assert result["score"] < 30
    assert result["strategy"] == "standard"


def test_anxious_input():
    """焦虑消息应返回🟡焦虑档。"""
    result = detect_emotion("我考砸了，只有480分，好焦虑，不知道怎么办")
    assert result["level"] == "🟡"
    assert 30 <= result["score"] < 70
    assert result["strategy"] == "empathize_first"


def test_breakdown_input():
    """崩溃消息应返回🔴崩溃档。"""
    result = detect_emotion("我完蛋了，才考了350分，这辈子没救了，不想活了")
    assert result["level"] == "🔴"
    assert result["score"] >= 70
    assert result["strategy"] == "crisis"


def test_compound_emotion():
    """多情绪词叠加应正确累加。"""
    result = detect_emotion("好焦虑好迷茫，不知道怎么办，怕选错专业毁了一辈子")
    assert result["level"] in ("🟡", "🔴")
    assert result["score"] >= 30


def test_empty_input():
    """空输入应返回正常档。"""
    result = detect_emotion("")
    assert result["level"] == "🟢"
    assert result["score"] == 0


if __name__ == "__main__":
    test_normal_input()
    test_anxious_input()
    test_breakdown_input()
    test_compound_emotion()
    test_empty_input()
    print("✅ All emotion tests passed")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: `ModuleNotFoundError: No module named 'quality.emotion_detector'`

- [ ] **Step 4: 实现情绪检测器**

```python
# quality/emotion_detector.py
"""
情绪检测模块 — 纯关键词加权评分，零成本零延迟。

三档策略:
  🟢 正常 (score < 30)  → 标准模式，直接分析
  🟡 焦虑 (30 ≤ score < 70) → 先共情1句，再分析
  🔴 崩溃 (score ≥ 70) → 接住情绪→锚定→心理热线→方案
"""

# ── 情绪关键词库（加权评分） ──
_HIGH_WEIGHT = 30   # 崩溃级
_MED_WEIGHT = 15    # 焦虑级
_LOW_WEIGHT = 5     # 轻度紧张

_EMOTION_KEYWORDS = {
    # 🔴 高权重：崩溃/绝望
    "崩溃": _HIGH_WEIGHT, "完蛋了": _HIGH_WEIGHT, "没救了": _HIGH_WEIGHT,
    "想死": _HIGH_WEIGHT, "不想活": _HIGH_WEIGHT, "废了": _HIGH_WEIGHT,
    "绝望": _HIGH_WEIGHT, "活不下去": _HIGH_WEIGHT, "没有希望": _HIGH_WEIGHT,
    "不想活了": _HIGH_WEIGHT, "想自杀": _HIGH_WEIGHT, "想结束": _HIGH_WEIGHT,
    "不想读了": _HIGH_WEIGHT, "这辈子完了": _HIGH_WEIGHT, "彻底完蛋": _HIGH_WEIGHT,
    # 🟡 中权重：焦虑/迷茫
    "焦虑": _MED_WEIGHT, "害怕": _MED_WEIGHT, "很怕": _MED_WEIGHT,
    "担心": _MED_WEIGHT, "迷茫": _MED_WEIGHT, "不知道怎么办": _MED_WEIGHT,
    "考砸了": _MED_WEIGHT, "考差了": _MED_WEIGHT, "复读": _MED_WEIGHT,
    "压力大": _MED_WEIGHT, "睡不着": _MED_WEIGHT, "心态崩了": _MED_WEIGHT,
    "没信心": _MED_WEIGHT, "不自信": _MED_WEIGHT, "怕选错": _MED_WEIGHT,
    "怎么办": _MED_WEIGHT, "好迷茫": _MED_WEIGHT, "好焦虑": _MED_WEIGHT,
    # 🟢 低权重：轻度紧张
    "紧张": _LOW_WEIGHT, "纠结": _LOW_WEIGHT, "犹豫": _LOW_WEIGHT,
    "不太确定": _LOW_WEIGHT, "有点慌": _LOW_WEIGHT, "不确定": _LOW_WEIGHT,
}

# 心理援助热线
CRISIS_HOTLINES = [
    "北京心理危机研究与干预中心：010-82951332",
    "全国心理援助热线：400-161-9995",
    "生命热线：400-821-1215",
]


def detect_emotion(text: str) -> dict:
    """
    检测用户消息中的情绪状态。

    Args:
        text: 用户输入的消息

    Returns:
        {
            "level": "🟢" | "🟡" | "🔴",
            "score": int (0-100),
            "strategy": "standard" | "empathize_first" | "crisis",
            "matched_keywords": list[str],
            "hint": str,  # 给 LLM 的策略提示
        }
    """
    if not text or not text.strip():
        return {
            "level": "🟢", "score": 0, "strategy": "standard",
            "matched_keywords": [], "hint": "",
        }

    # 扫描关键词，累加分数（同一个词只计一次）
    score = 0
    matched = []
    seen = set()
    for keyword, weight in _EMOTION_KEYWORDS.items():
        if keyword in text and keyword not in seen:
            seen.add(keyword)
            score += weight
            matched.append(keyword)

    # 封顶 100
    score = min(score, 100)

    # 档位判定
    if score >= 70:
        level, strategy = "🔴", "crisis"
        hint = (
            "【情绪危机检测：用户情绪崩溃】\n"
            "请按以下流程回复：\n"
            "1. 接住情绪（不超过2句话，不要说'别担心''会好的'）\n"
            "2. 锚定到具体层面（'先把分数告诉我，我帮你看看'）\n"
            "3. 如有自伤信号，提供心理援助热线\n"
            "4. 给1-2个务实选择\n"
            "5. 温暖收尾"
        )
    elif score >= 30:
        level, strategy = "🟡", "empathize_first"
        hint = (
            "【情绪检测：用户有焦虑情绪】\n"
            "先用1句话共情（'我理解你的感受'），然后直接进入分析。"
            "不要长篇安慰，用事实和数据转化焦虑。"
        )
    else:
        level, strategy = "🟢", "standard"
        hint = ""

    return {
        "level": level,
        "score": score,
        "strategy": strategy,
        "matched_keywords": matched,
        "hint": hint,
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: `✅ All emotion tests passed`

- [ ] **Step 6: Commit**

```bash
git add quality/__init__.py quality/emotion_detector.py quality/test_quality.py
git commit -m "feat(quality): add emotion detector with 3-tier strategy (🟢🟡🔴)"
```

---

## Task 2: 集成情绪检测到 agent.py

**Files:**
- Modify: `agent.py:533-548`（`chat()` 方法开头）

- [ ] **Step 1: 在 agent.py 顶部添加导入**

在 `agent.py` 第 24 行 `HAS_DATA_MODULE = False` 之后添加：

```python
# 质量控制模块
try:
    from quality.emotion_detector import detect_emotion, CRISIS_HOTLINES
    HAS_EMOTION_DETECTOR = True
except ImportError:
    HAS_EMOTION_DETECTOR = False
```

- [ ] **Step 2: 在 chat() 方法中插入情绪检测**

将 `agent.py` 的 `chat()` 方法（从第 533 行开始）修改。在 `user_msg = validate_user_input(user_msg)` 之后、`if is_consultation_intent(user_msg):` 之前，插入：

```python
        # 情绪检测（质量控制节点1）
        emotion_result = None
        if HAS_EMOTION_DETECTOR:
            emotion_result = detect_emotion(user_msg)
```

- [ ] **Step 3: 将情绪策略注入系统消息**

在 `_build_system_message()` 返回的 `full_system` 字符串末尾追加情绪策略。修改 `chat()` 方法中 `system_msg = self._build_system_message()` 之后：

将：
```python
        system_msg = self._build_system_message()
        messages = [{"role": "system", "content": system_msg}]
```

改为：
```python
        system_msg = self._build_system_message()
        # 注入情绪策略
        if emotion_result and emotion_result["hint"]:
            system_msg += f"\n\n{emotion_result['hint']}"
            if emotion_result["strategy"] == "crisis":
                hotlines = "\n".join(CRISIS_HOTLINES)
                system_msg += f"\n\n【心理援助热线（仅在用户有自伤信号时提供）】\n{hotlines}"
        messages = [{"role": "system", "content": system_msg}]
```

- [ ] **Step 4: 手动验证**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python -c "from quality.emotion_detector import detect_emotion; print(detect_emotion('我完蛋了，才考了350分'))"`
Expected: dict with `level: 🔴`, `score >= 70`

- [ ] **Step 5: Commit**

```bash
git add agent.py
git commit -m "feat(agent): integrate emotion detector into chat pipeline"
```

---

## Task 3: 实现交叉验证模块

**Files:**
- Create: `quality/cross_validator.py`
- Modify: `quality/test_quality.py`

- [ ] **Step 1: 写交叉验证的失败测试**

在 `quality/test_quality.py` 末尾追加：

```python
from quality.cross_validator import cross_validate_admission


def test_cross_validate_consistent():
    """两个来源数据一致时应返回高置信度。"""
    sources = [
        {"source": "DB", "min_score": 600, "min_rank": 5000},
        {"source": "API", "min_score": 598, "min_rank": 5200},
    ]
    result = cross_validate_admission(sources)
    assert result["confidence"] == "高"
    assert "一致" in result["note"] or result["note"] == ""


def test_cross_validate_inconsistent():
    """两个来源数据差异大时应返回中置信度+警告。"""
    sources = [
        {"source": "DB", "min_score": 600, "min_rank": 5000},
        {"source": "API", "min_score": 580, "min_rank": 8000},
    ]
    result = cross_validate_admission(sources)
    assert result["confidence"] == "中"
    assert "差异" in result["note"] or "核实" in result["note"]


def test_cross_validate_single_source():
    """仅一个来源时应返回低置信度。"""
    sources = [
        {"source": "DB", "min_score": 600, "min_rank": 5000},
    ]
    result = cross_validate_admission(sources)
    assert result["confidence"] == "低"
    assert "单源" in result["note"] or "核实" in result["note"]


def test_cross_validate_no_sources():
    """无数据来源时应返回 None。"""
    result = cross_validate_admission([])
    assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: `ModuleNotFoundError: No module named 'quality.cross_validator'`

- [ ] **Step 3: 实现交叉验证器**

```python
# quality/cross_validator.py
"""
数据交叉验证模块 — 多源数据比对，标注置信度。

验证规则:
  - ≥2源且分数差 ≤5分 → 高置信度
  - ≥2源但分数差 >5分 → 中置信度 + 警告
  - 仅1源 → 低置信度 + 建议核实
  - 无数据 → None
"""

SCORE_TOLERANCE = 5   # 分数差 ≤5 分视为一致
RANK_TOLERANCE_RATIO = 0.10  # 位次差 ≤10% 视为一致


def cross_validate_admission(sources: list[dict]) -> dict | None:
    """
    交叉验证录取数据。

    Args:
        sources: 数据来源列表，每项包含:
            - source: str ("DB" | "API" | "Search")
            - min_score: int | None
            - min_rank: int | None
            - 其他字段可选

    Returns:
        {
            "best": dict,        # 最佳数据源的完整数据
            "confidence": "高" | "中" | "低",
            "note": str,         # 给用户的说明
            "sources_used": list[str],
        }
        无数据时返回 None。
    """
    if not sources:
        return None

    # 过滤出有分数的数据
    valid = [s for s in sources if s.get("min_score") is not None]
    if not valid:
        return None

    # 取第一个作为 best（DB 优先级最高）
    best = valid[0]

    if len(valid) == 1:
        return {
            "best": best,
            "confidence": "低",
            "note": "仅单源数据，请核实官方信息",
            "sources_used": [best.get("source", "未知")],
        }

    # ≥2 个来源：比较一致性
    ref_score = valid[0]["min_score"]
    ref_rank = valid[0].get("min_rank")

    all_consistent = True
    for s in valid[1:]:
        score_diff = abs(s["min_score"] - ref_score)
        if score_diff > SCORE_TOLERANCE:
            all_consistent = False
            break
        # 如果都有位次，也检查位次一致性
        if ref_rank and s.get("min_rank"):
            rank_diff_ratio = abs(s["min_rank"] - ref_rank) / max(ref_rank, 1)
            if rank_diff_ratio > RANK_TOLERANCE_RATIO:
                all_consistent = False
                break

    sources_used = [s.get("source", "未知") for s in valid]

    if all_consistent:
        return {
            "best": best,
            "confidence": "高",
            "note": "",
            "sources_used": sources_used,
        }
    else:
        return {
            "best": best,
            "confidence": "中",
            "note": f"数据源存在差异（{' vs '.join(sources_used)}），建议核实官方数据",
            "sources_used": sources_used,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: `✅ All emotion tests passed` + cross_validation tests passed

- [ ] **Step 5: Commit**

```bash
git add quality/cross_validator.py quality/test_quality.py
git commit -m "feat(quality): add cross-validator for multi-source data verification"
```

---

## Task 4: 集成交叉验证到 agent.py 数据查询链路

**Files:**
- Modify: `agent.py:24-28`（导入区）
- Modify: `agent.py:593-678`（数据查询块）

- [ ] **Step 1: 添加导入**

在 agent.py 顶部导入区追加：

```python
try:
    from quality.cross_validator import cross_validate_admission
    HAS_CROSS_VALIDATOR = True
except ImportError:
    HAS_CROSS_VALIDATOR = False
```

- [ ] **Step 2: 修改录取数据查询逻辑**

将 `agent.py` 中查询录取数据的代码块（约第 594-601 行）：

```python
                # 1. 查录取分数线（学校+省份）
                if school_match and prov_match:
                    try:
                        raw = query_admission(school_match[0], prov_match[0])
                        admission_text = format_admission_info(raw)
                        if admission_text and "暂无" not in admission_text:
                            data_hints.append(f"【录取数据查询结果】\n{admission_text}")
                    except Exception:
                        pass
```

改为：

```python
                # 1. 查录取分数线（学校+省份）+ 交叉验证
                if school_match and prov_match:
                    try:
                        raw = query_admission(school_match[0], prov_match[0])
                        if raw and HAS_CROSS_VALIDATOR:
                            # 提取各数据源进行交叉验证
                            validation_sources = []
                            for r in raw:
                                if r.get("min_score") is not None:
                                    validation_sources.append({
                                        "source": r.get("data_source", "未知")[:10],
                                        "min_score": r["min_score"],
                                        "min_rank": r.get("min_rank"),
                                    })
                            if len(validation_sources) >= 2:
                                cv_result = cross_validate_admission(validation_sources)
                                if cv_result:
                                    conf_tag = f"[置信度:{cv_result['confidence']}]"
                                    if cv_result["note"]:
                                        conf_tag += f" {cv_result['note']}"
                                    admission_text = format_admission_info(raw)
                                    if admission_text and "暂无" not in admission_text:
                                        data_hints.append(
                                            f"【录取数据查询结果】{conf_tag}\n{admission_text}"
                                        )
                                    # 高置信度时标记，供后续逻辑使用
                                    if cv_result["confidence"] == "高":
                                        search_results = "db_verified"
                                    continue  # 已处理，跳过原有逻辑
                        # 降级：无交叉验证或仅单源
                        admission_text = format_admission_info(raw)
                        if admission_text and "暂无" not in admission_text:
                            data_hints.append(f"【录取数据查询结果】\n{admission_text}")
                    except Exception:
                        pass
```

- [ ] **Step 3: 手动验证导入正确**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python -c "from quality.cross_validator import cross_validate_admission; print(cross_validate_admission([{'source':'DB','min_score':600,'min_rank':5000},{'source':'API','min_score':598,'min_rank':5200}]))"`
Expected: dict with `confidence: 高`

- [ ] **Step 4: Commit**

```bash
git add agent.py
git commit -m "feat(agent): integrate cross-validation into admission data query"
```

---

## Task 5: 实现 AI 时代专业风险评估模块

**Files:**
- Create: `quality/ai_era_risk_data.json`
- Create: `quality/ai_era_risk.py`
- Modify: `quality/test_quality.py`

- [ ] **Step 1: 创建 AI 风险评估数据文件**

从 `knowledge/00_ai_era_correction.md` 提取结构化数据：

```json
{
  "计算机科学与技术": {"risk_zone": "🟡", "risk_score": 45, "ai_impact": "初级开发岗被AI替代率40%，但高端AI工程岗缺口大、月薪3-5万", "recommendation": "必须往AI/大数据方向深耕，不能只学基础编程", "salary_trend": "分化严重：低端↓高端↑", "source": "Anthropic 2026报告+麦可思2025"},
  "软件工程": {"risk_zone": "🟡", "risk_score": 50, "ai_impact": "基础代码开发、测试岗位被压缩，架构师和AI工程师稀缺", "recommendation": "名校+深造，或走嵌入式/硬件结合方向", "salary_trend": "初级↓高级↑", "source": "麦可思2025"},
  "人工智能": {"risk_zone": "🟢", "risk_score": 15, "ai_impact": "AI行业本身是就业创造方向，算法工程师增速110%", "recommendation": "顶尖985优先，需强数学基础", "salary_trend": "持续↑（均薪29万）", "source": "智联招聘2025"},
  "电气工程及其自动化": {"risk_zone": "🟢", "risk_score": 10, "ai_impact": "AI基础设施用电需求爆发，智能电网需要大量电气工程师", "recommendation": "进电网仍是好选择，新能源方向有红利", "salary_trend": "稳定↑", "source": "WEF 2025就业报告"},
  "电子信息工程": {"risk_zone": "🟢", "risk_score": 15, "ai_impact": "芯片/半导体国家战略重点，人才缺口持续", "recommendation": "集成电路方向最稳妥", "salary_trend": "持续↑", "source": "工信部2025"},
  "通信工程": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "5G/6G基础设施建设需要，但传统通信运维岗位缩减", "recommendation": "往无线/光通信/AI通信方向靠", "salary_trend": "稳定", "source": ""},
  "临床医学": {"risk_zone": "🟢", "risk_score": 10, "ai_impact": "AI辅助诊断工具发展快，但执业资格+临床操作是强护城河", "recommendation": "学制长是主要障碍，就业确定性高", "salary_trend": "越老越值钱", "source": "WEF 2025"},
  "口腔医学": {"risk_zone": "🟢", "risk_score": 10, "ai_impact": "操作性强，AI替代风险极低", "recommendation": "性价比极高的医学方向", "salary_trend": "持续↑", "source": ""},
  "护理学": {"risk_zone": "🟢", "risk_score": 10, "ai_impact": "物理操作+情感沟通，AI最难替代的方向之一", "recommendation": "老龄化加速，需求持续增长", "salary_trend": "稳定↑", "source": "WEF 2025"},
  "金融学": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "券商投行入门职位迅速减少，基础研究员/数据整理被AI替代", "recommendation": "普通院校强烈不推荐，顶尖985+家里有资源才考虑", "salary_trend": "高端↑低端↓↓", "source": "WEF 2025"},
  "会计学": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "做账、报表、凭证整理、基础审计被AI显著压缩", "recommendation": "必须考CPA走高端路线，基础会计岗位大量消失", "salary_trend": "基础↓高端稳定", "source": "前程无忧2025"},
  "法学": {"risk_zone": "🟡", "risk_score": 50, "ai_impact": "合同审查、法律文书、案例检索被AI冲击，但出庭辩护有护城河", "recommendation": "五院四系+法考是硬门槛，年轻律师积累通道变窄", "salary_trend": "两极分化", "source": ""},
  "新闻学": {"risk_zone": "🔴", "risk_score": 80, "ai_impact": "内容生产、图文编辑、基础采访已被AI冲击，叠加行业萎缩双重打击", "recommendation": "强烈不推荐，除非家里有媒体资源", "salary_trend": "持续↓", "source": ""},
  "英语": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "AI翻译质量大幅提升，基础翻译岗位大幅缩减", "recommendation": "除非北外/上外层次，否则强烈不推荐", "salary_trend": "持续↓", "source": ""},
  "汉语言文学": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "考公大户，AI对公务员岗位冲击较小", "recommendation": "考公方向稳定，教师方向也可", "salary_trend": "稳定", "source": ""},
  "师范类": {"risk_zone": "🟢", "risk_score": 15, "ai_impact": "教育需要情感沟通和个性化指导，AI替代风险低", "recommendation": "公费师范生最稳", "salary_trend": "稳定", "source": ""},
  "土木工程": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "行业下行+智能化施工减少人力需求", "recommendation": "强烈不推荐，985也要去工地", "salary_trend": "持续↓", "source": ""},
  "建筑学": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "AI设计工具冲击+房地产下行", "recommendation": "5年制投入大、回报低，不推荐", "salary_trend": "持续↓", "source": ""},
  "工商管理": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "无专业壁垒，AI工具让管理效率提升但减少中层需求", "recommendation": "家里没企业不要选", "salary_trend": "↓", "source": ""},
  "市场营销": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "AI营销工具普及，基础营销岗位缩减", "recommendation": "没有任何壁垒，不推荐", "salary_trend": "↓", "source": ""},
  "数据科学与大数据技术": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "数据时代强需求，但需往AI方向深耕", "recommendation": "好方向，需持续学习", "salary_trend": "↑", "source": ""},
  "集成电路设计与集成系统": {"risk_zone": "🟢", "risk_score": 10, "ai_impact": "芯片人才缺口大，国家战略重点", "recommendation": "最稳妥的硬科技方向之一", "salary_trend": "持续↑", "source": "工信部2025"},
  "自动化": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "工业自动化+机器人需求增长", "recommendation": "往智能制造/机器人方向靠", "salary_trend": "稳定↑", "source": ""},
  "信息安全": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "网络安全需求持续增长，AI安全是新方向", "recommendation": "好方向，考公也对口", "salary_trend": "↑", "source": ""},
  "物联网工程": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "IoT+AI融合，但需往应用层深耕", "recommendation": "好方向，与硬件结合更稳", "salary_trend": "稳定↑", "source": ""},
  "机械工程": {"risk_zone": "🟡", "risk_score": 35, "ai_impact": "传统机械岗位缩减，智能制造/机器人方向增长", "recommendation": "往智能制造方向转型", "salary_trend": "传统↓智能制造↑", "source": ""},
  "化学": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "基础研究岗位少，本科就业难，需读到博士", "recommendation": "四大天坑之一，普通家庭慎选", "salary_trend": "↓", "source": ""},
  "生物科学": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "本科就业极难，需读博才有出路", "recommendation": "四大天坑之一，除非走学术路线", "salary_trend": "↓", "source": ""},
  "环境科学": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "就业面窄，本科就业难", "recommendation": "四大天坑之一，不推荐", "salary_trend": "↓", "source": ""},
  "材料科学与工程": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "传统材料方向就业差，新能源材料有机会", "recommendation": "四大天坑之一，除非走新能源材料方向", "salary_trend": "传统↓新能源↑", "source": ""},
  "哲学": {"risk_zone": "🔴", "risk_score": 80, "ai_impact": "无直接对口岗位，AI进一步压缩文字工作", "recommendation": "普通家庭慎选，除非走学术/考公", "salary_trend": "↓", "source": ""},
  "历史学": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "对口岗位少，待遇偏低", "recommendation": "就业难度高，慎选", "salary_trend": "↓", "source": ""},
  "统计学": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "数据分析需求大，可转计算机/金融", "recommendation": "好方向，万金油底座", "salary_trend": "↑", "source": ""},
  "药学": {"risk_zone": "🟡", "risk_score": 35, "ai_impact": "AI药物研发加速，但临床药学有护城河", "recommendation": "南北双药优先，走临床药学方向", "salary_trend": "稳定", "source": ""},
  "车辆工程": {"risk_zone": "🟡", "risk_score": 40, "ai_impact": "新能源+自动驾驶转型，传统燃油车岗位缩减", "recommendation": "必须往新能源/智能驾驶方向靠", "salary_trend": "传统↓新能源↑", "source": ""},
  "物流管理": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "智能物流系统替代大量基础岗位", "recommendation": "专科都不推荐", "salary_trend": "↓", "source": ""},
  "电子商务": {"risk_zone": "🔴", "risk_score": 70, "ai_impact": "AI电商工具普及，基础运营岗位缩减", "recommendation": "听着高大上，出来就是送快递", "salary_trend": "↓", "source": ""},
  "公共管理": {"risk_zone": "🔴", "risk_score": 75, "ai_impact": "行政支持类岗位AI替代率最高", "recommendation": "强烈不推荐", "salary_trend": "↓", "source": ""},
  "心理学": {"risk_zone": "🟡", "risk_score": 35, "ai_impact": "AI心理咨询工具发展，但深度咨询有护城河", "recommendation": "就业面广但竞争激烈，需深造", "salary_trend": "稳定", "source": ""},
  "能源与动力工程": {"risk_zone": "🟢", "risk_score": 15, "ai_impact": "新能源+算力中心电力需求，结构性受益", "recommendation": "好方向，电网+新能源双驱动", "salary_trend": "↑", "source": ""},
  "航空航天类": {"risk_zone": "🟢", "risk_score": 15, "ai_impact": "国防需求稳定，AI替代风险低", "recommendation": "有情怀、稳定、钱不多但体面", "salary_trend": "稳定", "source": ""},
  "生物医学工程": {"risk_zone": "🟢", "risk_score": 20, "ai_impact": "医疗器械研发需求增长，注意跟生物专业不一样", "recommendation": "好方向，与AI医疗结合前景好", "salary_trend": "↑", "source": ""},
  "数字媒体技术": {"risk_zone": "🟡", "risk_score": 35, "ai_impact": "AI生成工具冲击基础设计，但创意/交互方向有机会", "recommendation": "往交互设计/AI创意方向走", "salary_trend": "基础↓创意↑", "source": ""}
}
```

- [ ] **Step 2: 写 AI 风险模块的失败测试**

在 `quality/test_quality.py` 末尾追加：

```python
from quality.ai_era_risk import get_major_risk, get_risk_summary


def test_get_risk_known_major():
    """已知专业应返回风险数据。"""
    result = get_major_risk("计算机科学与技术")
    assert result is not None
    assert result["risk_zone"] == "🟡"
    assert 0 <= result["risk_score"] <= 100


def test_get_risk_red_zone():
    """红灯区专业应正确标识。"""
    result = get_major_risk("金融学")
    assert result is not None
    assert result["risk_zone"] == "🔴"


def test_get_risk_green_zone():
    """绿灯区专业应正确标识。"""
    result = get_major_risk("电气工程及其自动化")
    assert result is not None
    assert result["risk_zone"] == "🟢"


def test_get_risk_unknown_major():
    """未知专业应返回 None。"""
    result = get_major_risk("量子玄学")
    assert result is None


def test_get_risk_summary():
    """摘要应为一句话 ≤50字。"""
    summary = get_risk_summary("金融学")
    assert summary is not None
    assert len(summary) <= 80
    assert "风险" in summary or "🔴" in summary or "高" in summary
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: `ModuleNotFoundError: No module named 'quality.ai_era_risk'`

- [ ] **Step 4: 实现 AI 风险模块**

```python
# quality/ai_era_risk.py
"""
AI时代专业风险评估模块 — 结构化风险数据查询。

每个专业有:
  - risk_zone: 🔴红灯(高风险) / 🟡黄灯(中风险) / 🟢绿灯(低风险)
  - risk_score: 0-100，越高风险越大
  - ai_impact: AI对该专业的具体影响
  - recommendation: 建议方向
"""

import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "ai_era_risk_data.json")

_risk_data = None


def _load_data() -> dict:
    global _risk_data
    if _risk_data is None:
        if os.path.exists(_DATA_PATH):
            with open(_DATA_PATH, "r", encoding="utf-8") as f:
                _risk_data = json.load(f)
        else:
            _risk_data = {}
    return _risk_data


def get_major_risk(major_name: str) -> dict | None:
    """
    查询专业的 AI 风险评估。

    Args:
        major_name: 专业名称（如 "计算机科学与技术"）

    Returns:
        风险数据 dict，或 None（未收录）
    """
    data = _load_data()
    # 精确匹配
    if major_name in data:
        return data[major_name]
    # 模糊匹配（如 "计算机" 匹配 "计算机科学与技术"）
    for key in data:
        if major_name in key or key in major_name:
            return data[key]
    return None


def get_risk_summary(major_name: str) -> str | None:
    """
    获取专业风险的一句话摘要（用于注入 LLM 提示）。

    Returns:
        如 "🟡 计算机科学与技术：初级开发岗被AI替代率40%，建议往AI方向深耕"
        未收录时返回 None
    """
    risk = get_major_risk(major_name)
    if not risk:
        return None
    return (
        f"{risk['risk_zone']} {major_name}：{risk['ai_impact']}。"
        f"建议：{risk['recommendation']}"
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: All tests passed

- [ ] **Step 6: Commit**

```bash
git add quality/ai_era_risk.py quality/ai_era_risk_data.json quality/test_quality.py
git commit -m "feat(quality): add AI era risk assessment for 42 majors"
```

---

## Task 6: 集成 AI 风险评估到 agent.py 推荐链路

**Files:**
- Modify: `agent.py:24-28`（导入区）
- Modify: `agent.py:622-639`（专业查询块）

- [ ] **Step 1: 添加导入**

在 agent.py 顶部导入区追加：

```python
try:
    from quality.ai_era_risk import get_risk_summary
    HAS_AI_RISK = True
except ImportError:
    HAS_AI_RISK = False
```

- [ ] **Step 2: 在专业查询后注入风险提示**

在 `agent.py` 的专业查询块（约第 622-639 行）中，在 `data_hints.append(就业数据)` 之后追加：

```python
                        # 附加 AI 时代风险提示
                        if HAS_AI_RISK:
                            for mj in major_match[:2]:
                                risk_summary = get_risk_summary(mj)
                                if risk_summary:
                                    data_hints.append(f"【AI时代风险评估】{risk_summary}")
                                    break  # 只注入一个专业的风险
```

- [ ] **Step 3: 手动验证**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python -c "from quality.ai_era_risk import get_risk_summary; print(get_risk_summary('金融学'))"`
Expected: `🔴 金融学：券商投行入门职位迅速减少...`

- [ ] **Step 4: Commit**

```bash
git add agent.py
git commit -m "feat(agent): integrate AI era risk assessment into recommendation pipeline"
```

---

## Task 7: 运行全部测试 + 端到端验证

**Files:**
- Test: `quality/test_quality.py`

- [ ] **Step 1: 运行完整测试套件**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python quality/test_quality.py`
Expected: `✅ All tests passed`（或类似输出）

- [ ] **Step 2: 端到端验证（不需要 API Key）**

Run: `cd /home/dev/projects/xuefeng/xuefeng-advisor && python -c "
from quality.emotion_detector import detect_emotion
from quality.cross_validator import cross_validate_admission
from quality.ai_era_risk import get_risk_summary, get_major_risk

# 测试情绪检测
print('=== 情绪检测 ===')
for msg in ['想学计算机', '好焦虑不知道怎么办', '完蛋了不想活了']:
    r = detect_emotion(msg)
    print(f'{r[\"level\"]} (score={r[\"score\"]}) strategy={r[\"strategy\"]} | {msg}')

# 测试交叉验证
print('\n=== 交叉验证 ===')
r = cross_validate_admission([
    {'source':'DB', 'min_score':600, 'min_rank':5000},
    {'source':'API', 'min_score':598, 'min_rank':5200},
])
print(f'置信度:{r[\"confidence\"]} note:{r[\"note\"]}')

# 测试 AI 风险
print('\n=== AI风险 ===')
for m in ['计算机科学与技术', '金融学', '电气工程及其自动化']:
    print(get_risk_summary(m))
"
Expected: 情绪三档正确、交叉验证高置信度、三个专业风险摘要

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(quality): complete quality control module integration

- Emotion detector: 3-tier strategy (🟢🟡🔴)
- Cross-validator: multi-source data verification
- AI era risk: 42 major risk assessments
- All tests passing"
```

---

## 验收清单

| 检查项 | 验收方式 |
|--------|---------|
| 情绪检测准确率 ≥90% | 5 条测试消息全部正确分档 |
| 交叉验证逻辑正确 | 一致/不一致/单源/无源 4 种场景测试通过 |
| AI 风险数据覆盖 | 42 个专业全部有红/黄/绿区标注 |
| agent.py 无破坏性修改 | 现有功能（槽位采集、搜索链、LLM 对话）不受影响 |
| 零新依赖 | quality/ 模块仅使用 Python 标准库 |
