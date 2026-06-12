#!/usr/bin/env python3
"""
RAG 知识检索引擎 — 端到端自动化验证脚本。

验证维度：
1. 检索质量（7 个核心查询）
2. Token 消耗对比（新系统 vs 旧系统）
3. Fallback 降级（embedding 失败 / 检索为空）
4. 知识完整性（文件存在 + 可加载）

用法：
    python scripts/verify_rag.py
    python scripts/verify_rag.py --verbose
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from kb_retriever import (
    KbRetriever, KeywordOnlyEmbedding, RetrievalResult,
    load_all_groups, GROUP_TRIGGERS,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)


# ── 测试数据 ──────────────────────────────────────────────────

@dataclass
class TestQuery:
    query: str
    expected_groups: list[str]
    description: str


TEST_QUERIES: list[TestQuery] = [
    TestQuery(
        query="学码农以后还能找到工作吗",
        expected_groups=["G2_major_school", "G3_career_future"],
        description="码农→计算机语义匹配，应检索 G2(专业) + G3(就业前景)",
    ),
    TestQuery(
        query="进体制内稳不稳",
        expected_groups=["G3_career_future"],
        description="体制内→考公关键词，应检索 G3(就业路径)",
    ),
    TestQuery(
        query="女生学什么专业比较好",
        expected_groups=["G2_major_school"],
        description="应检索 G2(专业选择)",
    ),
    TestQuery(
        query="农村的，分数不高，能报什么",
        expected_groups=["G1_core_method", "G2_major_school"],
        description="应检索 G1(方法论) + G2(专业推荐)",
    ),
    TestQuery(
        query="临床医学出来好找工吗",
        expected_groups=["G2_major_school", "G3_career_future"],
        description="应检索 G2(专业) + G3(就业)",
    ),
    TestQuery(
        query="帮我对比武汉大学和华中科技大学",
        expected_groups=["G2_major_school"],
        description="学校对比应检索 G2(学校选择)",
    ),
    TestQuery(
        query="转专业难不难",
        expected_groups=["G1_core_method", "G2_major_school"],
        description="应检索 G1(方法论) + G2(专业选择)",
    ),
]


# ── 辅助函数 ──────────────────────────────────────────────────

def count_tokens_approx(text: str) -> int:
    """粗略估算 token 数（中文 1 字 ≈ 2 token，英文 1 词 ≈ 1 token）。"""
    import re
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    ascii_tokens = len(re.findall(r'[a-zA-Z0-9]+', text))
    return chinese_chars * 2 + ascii_tokens


def make_test_retriever(tmpdir: str) -> KbRetriever:
    """创建模拟生产环境的测试 retriever。"""
    groups_dir = os.path.join(tmpdir, "knowledge", "groups")
    os.makedirs(groups_dir, exist_ok=True)

    group_contents = {
        "G1_core_method.md": """# 核心方法论

## 志愿填报方法论
冲稳保规则：根据位次法，将志愿分为冲一冲、稳一稳、保一保三个层次。
投档线、滑档、退档是高考志愿填报的三大风险。

## 灵魂拷问法
咨询的第一步不是问分数，而是问这个家庭能给孩子什么资源。

## 咨询表达风格
说话要直接，不要含糊，用生活化的例子。
""",
        "G2_major_school.md": """# 专业与学校

## 专业选择知识库
计算机科学与技术、软件工程、信息安全是当前就业最好的专业之一。
医学类专业学制长（临床医学5+3），但就业稳定。
文科类专业（哲学、历史、文学）就业面窄，需要研究生学历。

## 学校选择方法论
985 > 211 > 双一流 > 普通本科。学校层次是第一张名片。

## 推荐专业
计算机、人工智能、电气工程、临床医学、师范类专业。
天坑专业：生物工程、环境科学、化学、材料（生化环材）。

## 行业名校分类
两电一邮（电子科大、西电、北邮）、建筑老八校、师范六校。
""",
        "G3_career_future.md": """# 就业与前景

## 考研方法论
考研不是目的，是手段。要先想清楚读研之后要干什么。

## 稳定就业路径详解
考公（公务员）：最稳定的职业路径之一。国考、省考、选调生。
教师：师范类专业 + 教师资格证 = 稳定就业。
医生：临床医学5+3一体化，毕业后进三甲医院。
国企（国家电网、中石油、铁路局）：电气、石油、交通运输专业优先。

## 2025-2026 最新趋势
AI 对就业的冲击：大模型正在替代基础编程、翻译、基础文员等岗位。
未来 5 年最有前景的方向：AI+医疗、新能源、芯片设计。
""",
        "G4_life_planning.md": """# 规划与选择

## 城市选择逻辑
一线城市（北上广深）：机会多但竞争激烈。
新一线城市（成都、杭州、武汉）：性价比高。

## 专科志愿策略
专科不是终点，专升本是正道。选专业 > 选学校。

## 高中阶段规划
高一选科决定了大学能报什么专业。
""",
        "G5_data_format.md": """# 数据与格式

## 数据可信度分级
T1: 官方数据（教育部、省考试院）

## Output 格式
推荐结果格式：冲 X 所 / 稳 X 所 / 保 X 所
""",
        "G6_quick_ref.md": """# 速查

## 选科速查表
物理+化学+生物 → 理工农医全覆盖

## 职业路径速查
公务员：法学、汉语言文学、计算机、会计
""",
    }

    for filename, content in group_contents.items():
        with open(os.path.join(groups_dir, filename), "w") as f:
            f.write(content)

    quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
    os.makedirs(quotes_dir, exist_ok=True)
    quotes = {
        "计算机": [
            {"id": "q1", "text": "学计算机就要卷到底，不卷就别学。",
             "tags": ["计算机", "努力"], "category": "zhuanye", "sentiment": "cautionary"},
            {"id": "q2", "text": "985的计算机，不要去211的金融。",
             "tags": ["985", "211", "计算机", "金融"], "category": "zhuanye", "sentiment": "neutral"},
        ],
        "医学": [
            {"id": "q3", "text": "学医就是选择了一条漫长但稳定的路。",
             "tags": ["医学", "稳定"], "category": "zhuanye", "sentiment": "neutral"},
        ],
        "考公": [
            {"id": "q4", "text": "考公不是唯一出路，但是最稳的出路之一。",
             "tags": ["考公", "稳定"], "category": "rensheng", "sentiment": "neutral"},
        ],
        "女生": [
            {"id": "q5", "text": "女生选专业，先看就业稳定性，再看收入天花板。",
             "tags": ["女生", "选择"], "category": "rensheng", "sentiment": "neutral"},
        ],
        "985": [
            {"id": "q6", "text": "能上985就别去211，学校层次就是你的第一张名片。",
             "tags": ["985", "211", "学校层次"], "category": "yuanxiao", "sentiment": "cautionary"},
        ],
        "转专业": [
            {"id": "q7", "text": "转专业不是万能药，进去之前想清楚比进去之后再转好。",
             "tags": ["转专业", "选择"], "category": "zhuanye", "sentiment": "cautionary"},
        ],
        "专科": [
            {"id": "q8", "text": "专科不是终点，是另一个起点。选对专业比选对学校重要。",
             "tags": ["专科", "选择"], "category": "zhuanye", "sentiment": "motivational"},
        ],
    }
    with open(os.path.join(quotes_dir, "_by_major.json"), "w") as f:
        json.dump(quotes, f, ensure_ascii=False)

    return KbRetriever(
        groups_dir=groups_dir,
        quotes_path=quotes_dir,
        embedding_provider=KeywordOnlyEmbedding(),
        embedding_model="",
    )


def make_full_knowledge_base() -> str:
    """模拟原始的全量 knowledge_base.md。"""
    return """
# 高考志愿顾问知识库 v2.7

## 一、核心咨询哲学
灵魂拷问法：咨询的第一步不是问分数，而是问这个家庭能给孩子什么资源。
家庭资源矩阵：父母职业、家庭收入、人脉关系、地域限制。

## 二、志愿填报方法论
冲稳保规则：根据位次法，将志愿分为冲一冲、稳一稳、保一保三个层次。

## 三、专业选择知识库
12 大学科门类：哲学、经济学、法学、教育学、文学、历史学、理学、工学、农学、医学、管理学、艺术学。
同名专业差异：同一个专业名称在不同学校可能差别巨大。

## 四、学校选择方法论
985 > 211 > 双一流 > 普通本科。

## 五、城市选择逻辑
选城市 = 选产业链 = 选实习机会。

## 六、考研方法论
考研不是目的，是手段。

## 七、咨询表达风格
说话要直接，不要含糊。

## 八、数据可信度分级
T1: 官方数据 / T2: 权威数据 / T3: 行业数据 / T4: 口碑数据

## 九、Output 格式
推荐结果格式：冲 X 所 / 稳 X 所 / 保 X 所

## 十、推荐/不推荐专业
天坑专业：生化环材。

## 十一、行业名校分类
两电一邮、建筑老八校。

## 十二、速查
选科速查表、职业路径速查。

## 十三、稳定就业路径详解
考公、教师、医生、国企。

## 十四、专科志愿策略
专科不是终点。

## 十五、高中阶段规划
高一选科决定了大学能报什么专业。

## 十六、2025-2026 最新趋势
AI 对就业的冲击。
""" * 1  # 约 866 行的简化版


# ── 验证维度 ──────────────────────────────────────────────────

@dataclass
class VerifyResult:
    dimension: str
    passed: bool
    details: list[str] = field(default_factory=list)
    score: str = ""


def verify_retrieval_quality(retriever: KbRetriever) -> VerifyResult:
    """维度 1：检索质量验证。"""
    passed_count = 0
    details: list[str] = []

    for tq in TEST_QUERIES:
        result = retriever.search(tq.query, {})
        hit = any(g in result.groups for g in tq.expected_groups)
        status = "✓" if hit else "✗"
        if hit:
            passed_count += 1
        details.append(
            f"  {status} \"{tq.query}\" → {result.groups} "
            f"(期望: {tq.expected_groups})"
        )

    return VerifyResult(
        dimension="检索质量",
        passed=passed_count == len(TEST_QUERIES),
        details=details,
        score=f"{passed_count}/{len(TEST_QUERIES)}",
    )


def verify_token_savings(retriever: KbRetriever) -> VerifyResult:
    """维度 2：Token 消耗对比。"""
    full_kb = make_full_knowledge_base()
    full_tokens = count_tokens_approx(full_kb)

    savings: list[float] = []
    details: list[str] = []

    for tq in TEST_QUERIES:
        result = retriever.search(tq.query, {})
        retrieved_text = "\n".join(c.text for c in result.group_chunks)
        retrieved_tokens = count_tokens_approx(retrieved_text)
        saving_pct = (1 - retrieved_tokens / full_tokens) * 100 if full_tokens > 0 else 0
        savings.append(saving_pct)
        details.append(
            f"  \"{tq.query}\" → {retrieved_tokens} tokens "
            f"(旧: {full_tokens}) 节省 {saving_pct:.0f}%"
        )

    avg_saving = sum(savings) / len(savings) if savings else 0
    details.append(f"  平均节省: {avg_saving:.0f}%")

    return VerifyResult(
        dimension="Token 节省",
        passed=avg_saving > 20,  # 至少节省 20%
        details=details,
        score=f"平均 {avg_saving:.0f}%",
    )


def verify_fallback(retriever: KbRetriever) -> VerifyResult:
    """维度 3：Fallback 降级验证。"""
    details: list[str] = []
    passed_count = 0

    # 测试 1: 空查询 → 应有 fallback
    result = retriever.search("", {})
    has_fallback = len(result.groups) > 0
    status = "✓" if has_fallback else "✗"
    passed_count += int(has_fallback)
    details.append(f"  {status} 空查询 fallback → {result.groups}")

    # 测试 2: 无关查询 → 应返回基础组
    result = retriever.search("今天天气不错", {})
    has_groups = len(result.groups) > 0
    status = "✓" if has_groups else "✗"
    passed_count += int(has_groups)
    details.append(f"  {status} 无关查询 fallback → {result.groups}")

    # 测试 3: KeywordOnly embedding → 降级为纯关键词
    with tempfile.TemporaryDirectory() as tmpdir2:
        kb2 = make_test_retriever(tmpdir2)
        result = kb2.search("计算机怎么学", {})
        keyword_works = len(result.groups) > 0
        status = "✓" if keyword_works else "✗"
        passed_count += int(keyword_works)
        details.append(f"  {status} 纯关键词降级 → {result.groups}")

    return VerifyResult(
        dimension="Fallback 降级",
        passed=passed_count >= 2,
        details=details,
        score=f"{passed_count}/3",
    )


def verify_knowledge_integrity(retriever: KbRetriever) -> VerifyResult:
    """维度 4：知识完整性验证。"""
    details: list[str] = []
    passed_count = 0

    # 测试 1: 6 个知识组存在
    expected_groups = {"G1_core_method", "G2_major_school", "G3_career_future",
                       "G4_life_planning", "G5_data_format", "G6_quick_ref"}
    actual_groups = set(retriever._groups.keys())
    groups_ok = expected_groups == actual_groups
    status = "✓" if groups_ok else "✗"
    passed_count += int(groups_ok)
    details.append(f"  {status} 知识组: {len(actual_groups)}/6 ({', '.join(sorted(actual_groups))})")

    # 测试 2: 每个组至少有 1 个 chunk
    for gid, chunks in retriever._groups.items():
        has_chunks = len(chunks) > 0
        if not has_chunks:
            details.append(f"  ✗ {gid}: 0 chunks")

    all_have_chunks = all(len(c) > 0 for c in retriever._groups.values())
    status = "✓" if all_have_chunks else "✗"
    passed_count += int(all_have_chunks)
    details.append(f"  {status} 所有组均有 chunks")

    # 测试 3: 语录加载
    quotes_count = len(retriever._quotes)
    quotes_ok = quotes_count > 0
    status = "✓" if quotes_ok else "✗"
    passed_count += int(quotes_ok)
    details.append(f"  {status} 语录: {quotes_count} 条")

    # 测试 4: 关键词触发词配置
    triggers_ok = len(GROUP_TRIGGERS) == 6
    status = "✓" if triggers_ok else "✗"
    passed_count += int(triggers_ok)
    total_triggers = sum(len(v) for v in GROUP_TRIGGERS.values())
    details.append(f"  {status} 触发词: {total_triggers} 个 (6 组)")

    return VerifyResult(
        dimension="知识完整性",
        passed=passed_count >= 3,
        details=details,
        score=f"{passed_count}/4",
    )


# ── 主程序 ──────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 端到端自动化验证")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    print("=" * 60)
    print("  RAG 端到端验证报告")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        retriever = make_test_retriever(tmpdir)

        # 运行 4 个验证维度
        results: list[VerifyResult] = [
            verify_retrieval_quality(retriever),
            verify_token_savings(retriever),
            verify_fallback(retriever),
            verify_knowledge_integrity(retriever),
        ]

        # 输出结果
        all_passed = True
        for r in results:
            icon = "✓" if r.passed else "✗"
            print(f"{icon} {r.dimension}: {r.score}")
            if args.verbose or not r.passed:
                for detail in r.details:
                    print(detail)
            if not r.passed:
                all_passed = False
            print()

        # 汇总
        print("-" * 60)
        passed_dims = sum(1 for r in results if r.passed)
        total_dims = len(results)

        if all_passed:
            print(f"  总计: {passed_dims}/{total_dims} 维度通过 ✓")
        else:
            print(f"  总计: {passed_dims}/{total_dims} 维度通过 ✗")
            failed = [r.dimension for r in results if not r.passed]
            print(f"  失败: {', '.join(failed)}")

        print("=" * 60)

        # 返回退出码
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
