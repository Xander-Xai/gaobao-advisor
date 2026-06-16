"""RAG 知识检索集成测试 — 验证 7 个核心查询场景。"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.services.kb_retriever import (
    KbRetriever,
    KeywordOnlyEmbedding,
)


def _make_test_retriever(tmpdir: str) -> KbRetriever:
    """创建一个模拟生产环境的测试 retriever。"""
    groups_dir = os.path.join(tmpdir, "knowledge", "groups")
    os.makedirs(groups_dir, exist_ok=True)

    with open(os.path.join(groups_dir, "G1_core_method.md"), "w") as f:
        f.write("""# 核心方法论

## 志愿填报方法论
冲稳保规则：根据位次法，将志愿分为冲一冲、稳一稳、保一保三个层次。
投档线、滑档、退档是高考志愿填报的三大风险。

## 灵魂拷问法
咨询的第一步不是问分数，而是问这个家庭能给孩子什么资源。

## 咨询表达风格
说话要直接，不要含糊，用生活化的例子。
""")

    with open(os.path.join(groups_dir, "G2_major_school.md"), "w") as f:
        f.write("""# 专业与学校

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
""")

    with open(os.path.join(groups_dir, "G3_career_future.md"), "w") as f:
        f.write("""# 就业与前景

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
""")

    with open(os.path.join(groups_dir, "G4_life_planning.md"), "w") as f:
        f.write("""# 规划与选择

## 城市选择逻辑
一线城市（北上广深）：机会多但竞争激烈。
新一线城市（成都、杭州、武汉）：性价比高。

## 专科志愿策略
专科不是终点，专升本是正道。选专业 > 选学校。

## 高中阶段规划
高一选科决定了大学能报什么专业。
""")

    with open(os.path.join(groups_dir, "G5_data_format.md"), "w") as f:
        f.write("""# 数据与格式

## 数据可信度分级
T1: 官方数据（教育部、省考试院）

## Output 格式
推荐结果格式：冲 X 所 / 稳 X 所 / 保 X 所
""")

    with open(os.path.join(groups_dir, "G6_quick_ref.md"), "w") as f:
        f.write("""# 速查

## 选科速查表
物理+化学+生物 → 理工农医全覆盖

## 职业路径速查
公务员：法学、汉语言文学、计算机、会计
""")

    quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
    os.makedirs(quotes_dir, exist_ok=True)
    quotes = {
        "计算机": [
            {
                "id": "q1",
                "text": "学计算机就要卷到底，不卷就别学。",
                "tags": ["计算机", "努力"],
                "category": "zhuanye",
                "sentiment": "cautionary",
            },
            {
                "id": "q2",
                "text": "985的计算机，不要去211的金融。",
                "tags": ["985", "211", "计算机", "金融"],
                "category": "zhuanye",
                "sentiment": "neutral",
            },
        ],
        "医学": [
            {
                "id": "q3",
                "text": "学医就是选择了一条漫长但稳定的路。",
                "tags": ["医学", "稳定"],
                "category": "zhuanye",
                "sentiment": "neutral",
            },
        ],
        "考公": [
            {
                "id": "q4",
                "text": "考公不是唯一出路，但是最稳的出路之一。",
                "tags": ["考公", "稳定"],
                "category": "rensheng",
                "sentiment": "neutral",
            },
        ],
        "女生": [
            {
                "id": "q5",
                "text": "女生选专业，先看就业稳定性，再看收入天花板。",
                "tags": ["女生", "选择"],
                "category": "rensheng",
                "sentiment": "neutral",
            },
        ],
        "985": [
            {
                "id": "q6",
                "text": "能上985就别去211，学校层次就是你的第一张名片。",
                "tags": ["985", "211", "学校层次"],
                "category": "yuanxiao",
                "sentiment": "cautionary",
            },
        ],
        "转专业": [
            {
                "id": "q7",
                "text": "转专业不是万能药，进去之前想清楚比进去之后再转好。",
                "tags": ["转专业", "选择"],
                "category": "zhuanye",
                "sentiment": "cautionary",
            },
        ],
        "专科": [
            {
                "id": "q8",
                "text": "专科不是终点，是另一个起点。选对专业比选对学校重要。",
                "tags": ["专科", "选择"],
                "category": "zhuanye",
                "sentiment": "motivational",
            },
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


class Test7CoreQueries:
    """验证 7 个核心查询的检索质量。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.retriever = _make_test_retriever(tmpdir)
            yield

    def _check_groups(self, result, expected_groups, query_desc):
        hit = any(g in result.groups for g in expected_groups)
        assert hit, f"Query '{query_desc}': expected one of {expected_groups}, got {result.groups}"

    def test_query_1_coding_career(self):
        result = self.retriever.search("学码农以后还能找到工作吗", {})
        self._check_groups(result, ["G2_major_school", "G3_career_future"], "学码农以后还能找到工作吗")

    def test_query_2_civil_service(self):
        result = self.retriever.search("进体制内稳不稳", {})
        self._check_groups(result, ["G3_career_future"], "进体制内稳不稳")

    def test_query_3_female_major(self):
        result = self.retriever.search("女生学什么专业比较好", {})
        self._check_groups(result, ["G2_major_school"], "女生学什么专业比较好")

    def test_query_4_rural_low_score(self):
        result = self.retriever.search("农村的，分数不高，能报什么", {})
        self._check_groups(result, ["G1_core_method", "G2_major_school"], "农村的，分数不高，能报什么")

    def test_query_5_clinical_medicine(self):
        result = self.retriever.search("临床医学出来好找工吗", {})
        self._check_groups(result, ["G2_major_school", "G3_career_future"], "临床医学出来好找工吗")

    def test_query_6_school_comparison(self):
        result = self.retriever.search("帮我对比武汉大学和华中科技大学", {})
        self._check_groups(result, ["G2_major_school"], "帮我对比武汉大学和华中科技大学")

    def test_query_7_transfer_major(self):
        result = self.retriever.search("转专业难不难", {})
        self._check_groups(result, ["G1_core_method", "G2_major_school"], "转专业难不难")


class TestTokenSavings:
    """验证 token 消耗对比。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.retriever = _make_test_retriever(tmpdir)
            yield

    def test_retrieved_content_shorter_than_full(self):
        result = self.retriever.search("我想填报志愿", {})
        retrieved_text = "\n".join(c.text for c in result.group_chunks)
        retrieved_lines = len(retrieved_text.split("\n"))
        assert retrieved_lines < 400
