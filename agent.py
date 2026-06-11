#!/usr/bin/env python3
"""
高考志愿顾问 Agent — 模型无关、支持实时搜索、结构化槽位采集。
Usage:
  python agent.py                    # 交互式对话
  python agent.py --model qwen-plus # 指定模型
  python agent.py --no-search        # 禁用搜索
"""

import os, sys, json, re, urllib.request, urllib.parse, urllib.error
from openai import OpenAI

# 高考数据模块（数据库优先 + 百度搜索兜底）
try:
    from gaokao_data import (
        query_admission, format_admission_info,
        query_school_info, query_major_info, query_match_schools,
        query_subject_ranking, search_policy, get_db_stats,
        query_yi_fen_yi_duan, query_match_schools_v2,
    )
    HAS_DATA_MODULE = True
except ImportError:
    HAS_DATA_MODULE = False

def read_clipboard():
    """读取 Windows 剪贴板文本。"""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT
            data = win32clipboard.GetClipboardData(13)
            win32clipboard.CloseClipboard()
            return data
        win32clipboard.CloseClipboard()
    except:
        pass
    return None

# ── 加载 .env 文件 ──────────────────────────────────
def load_dotenv(path):
    """简单的 .env 加载器，不依赖第三方库。"""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip()
                    if key not in os.environ:
                        os.environ[key] = val

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

# ── 常见模型预设 ────────────────────────────────────
# 用户只需设置 LLM_PROVIDER，系统自动填充 base_url 和 model
PRESETS = {
    "deepseek":  {"base_url": "https://api.deepseek.com",    "model": "deepseek-chat"},
    "qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm":       {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
    "moonshot":  {"base_url": "https://api.moonshot.cn/v1",   "model": "moonshot-v1-8k"},
    "openai":    {"base_url": "https://api.openai.com/v1",    "model": "gpt-4o"},
    "ollama":    {"base_url": "http://localhost:11434/v1",    "model": "qwen2.5:7b"},
}

def resolve_config():
    """解析配置：支持 LLM_PROVIDER 快捷切换 或 手工指定三项。"""
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider in PRESETS:
        preset = PRESETS[provider]
        return {
            "base_url": os.getenv("LLM_BASE_URL", preset["base_url"]),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", preset["model"]),
            "max_tokens": None,  # 不限制回复长度，让模型自由发挥
            "temperature": 0.7,
            "enable_search": True,
        }
    return {
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "max_tokens": None,  # 不限制回复长度，让模型自由发挥
        "temperature": 0.7,
        "enable_search": True,
    }

CONFIG = resolve_config()
SEARCH_ENGINE = "https://www.baidu.com/s?wd="

# ── 加载知识库 ──────────────────────────────────────
KNOWLEDGE_BASE_PATH = os.path.join(HERE, "knowledge_base.md")
SYSTEM_PROMPT_PATH = os.path.join(HERE, "system_prompt.md")
QUOTES_INDEX_PATH = os.path.join(HERE, "knowledge", "quotes", "_by_major.json")

# 加载语录索引（用于按专业查询张雪峰语录）
def load_quotes_index():
    """加载语录的反向索引（专业→语录列表）"""
    if os.path.exists(QUOTES_INDEX_PATH):
        with open(QUOTES_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

QUOTES_INDEX = load_quotes_index()

def load_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# ── 槽位管理器 ───────────────────────────────────────
SLOTS = {
    "province":     {"label": "省份", "filled": False, "value": ""},
    "score_rank":   {"label": "分数/位次", "filled": False, "value": ""},
    "subject":      {"label": "选科", "filled": False, "value": ""},
    "interest":     {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
    "region":       {"label": "地域偏好", "filled": False, "value": ""},
    "family":       {"label": "家庭资源", "filled": False, "value": ""},
    "goal":         {"label": "核心诉求", "filled": False, "value": ""},
}

def filled_slots(slots=None):
    s = slots if slots is not None else SLOTS
    return {k: v for k, v in s.items() if v["filled"]}

def missing_slots(slots=None):
    s = slots if slots is not None else SLOTS
    return [k for k, v in s.items() if not v["filled"]]

def slots_summary(slots=None):
    s = slots if slots is not None else SLOTS
    lines = []
    for k, v in s.items():
        status = "[OK]" if v["filled"] else "[ ]"
        lines.append(f"  {status} {v['label']}: {v['value'] if v['filled'] else '(未填)'}")
    return "\n".join(lines)

def extract_slots_from_message(msg, slots=None):
    """从用户消息中自动提取槽位信息。"""
    s = slots if slots is not None else SLOTS
    updated = []
    msg_lower = msg.lower()

    # 省份检测
    provinces = [
        "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
        "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
        "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
        "甘肃", "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆",
    ]
    for p in provinces:
        if p in msg and not s["province"]["filled"]:
            s["province"]["value"] = p
            s["province"]["filled"] = True
            updated.append(f"省份→{p}")

    # 分数/位次检测（增强版）
    score_match = re.search(r'(\d{3})\s*分', msg)
    # 多种位次格式：15000位次、位次15000、1.5万位次、省排15000、排名15000
    rank_patterns = [
        r'(\d{4,7})\s*(?:位次|名次|排名|名)',
        r'位次[是为：:]\s*(\d{4,7})',
        r'省排[名]?\s*(\d{4,7})',
        r'(\d+(?:\.\d+)?)\s*万\s*(?:位次|名|名次)',
    ]
    rank_value = None
    for rp in rank_patterns:
        m = re.search(rp, msg)
        if m:
            raw = m.group(1)
            if '万' in rp and '.' in raw:
                rank_value = str(int(float(raw) * 10000))
            elif '万' in rp:
                rank_value = str(int(raw) * 10000)
            else:
                rank_value = raw
            break

    if score_match and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = score_match.group(1) + "分"
        s["score_rank"]["filled"] = True
        updated.append(f"分数→{score_match.group(1)}分")
    if rank_value and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = "位次" + rank_value
        s["score_rank"]["filled"] = True
        updated.append(f"位次→{rank_value}")
    if rank_value and s["score_rank"]["filled"] and "位次" not in s["score_rank"]["value"]:
        s["score_rank"]["value"] += " / 位次" + rank_value

    # 选科检测（增加 3+1+2、3+3 模式识别）
    for subj in ["物理", "历史", "物化生", "物化地", "物化政", "物生政",
                  "史政地", "史政生", "史地生", "理科", "文科"]:
        if subj in msg and not s["subject"]["filled"]:
            s["subject"]["value"] = subj
            s["subject"]["filled"] = True
            updated.append(f"选科→{subj}")
            break

    # 地域检测（扩展城市列表）
    for r in ["省内", "本省", "离家近", "北上广", "江浙沪", "北京", "上海",
               "深圳", "广州", "杭州", "成都", "武汉", "南京", "西安",
               "天津", "重庆", "长沙", "合肥", "济南", "郑州", "昆明",
               "厦门", "苏州", "无锡", "佛山", "东莞"]:
        if r in msg and not s["region"]["filled"]:
            s["region"]["value"] = r
            s["region"]["filled"] = True
            updated.append(f"地域→{r}")
            break

    # 家庭资源检测（增加经济条件、家庭状况）
    for fw in ["电力", "电网", "铁路", "医生", "教师", "老师", "做生意",
                "公务员", "烟草", "石油", "普通家庭", "没资源",
                "经济一般", "经济压力大", "条件一般", "家里没钱", "没钱",
                "能负担", "能接受高学费", "私立", "中外合作"]:
        if fw in msg and not s["family"]["filled"]:
            s["family"]["value"] = fw
            s["family"]["filled"] = True
            updated.append(f"家庭→{fw}")
            break

    # 诉求检测
    for g in ["就业", "考公", "考研", "稳定", "高薪", "赚钱", "深造", "出国"]:
        if g in msg and not s["goal"]["filled"]:
            s["goal"]["value"] = g
            s["goal"]["filled"] = True
            updated.append(f"诉求→{g}")
            break

    # 兴趣/厌恶检测（专业方向）
    interest_keywords = [
        "计算机", "软件", "人工智能", "AI", "电气", "电子信息", "通信",
        "临床医学", "口腔", "金融", "会计", "法学", "土木", "机械",
        "新闻", "汉语言", "数学", "物理", "化学", "生物", "材料",
        "环境", "自动化", "集成电路", "大数据", "信息安全", "车辆",
        "建筑学", "统计学", "药学", "师范", "英语", "历史学", "哲学",
        "想学", "喜欢", "想读", "感兴趣", "讨厌", "不想学", "不喜欢",
        "绝对不", "绝不",
    ]
    if not s["interest"]["filled"]:
        matched_interests = [kw for kw in interest_keywords if kw in msg]
        if matched_interests:
            s["interest"]["value"] = " ".join(matched_interests[:3])
            s["interest"]["filled"] = True
            updated.append(f"兴趣→{'、'.join(matched_interests[:3])}")

    return updated

def is_consultation_intent(msg):
    """判断用户是否有志愿咨询意图。"""
    keywords = [
        "高考", "志愿", "选专业", "报学校", "报志愿", "填志愿", "选科",
        "分科", "考研", "选学校", "大学", "专业", "就业", "考公",
        "能报", "能上", "推荐", "建议", "帮忙看", "帮我选",
    ]
    return any(kw in msg for kw in keywords)

# ── 搜索功能 ─────────────────────────────────────────
def web_search(query, max_results=3):
    """搜索并获取网页内容。先用百度搜索找URL，再抓取页面文字。"""
    results = []
    try:
        # Step 1: 百度搜索获取结果链接
        url = SEARCH_ENGINE + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Step 2: 提取搜索结果URL（尝试多种匹配模式）
        urls = re.findall(r'href="(https?://[^"]+)"', html)
        # 过滤掉百度自己的链接，保留真实网站
        valid_urls = [u for u in urls if 'baidu.com' not in u and len(u) > 30][:max_results]

        # Step 3: 抓取每个结果页面的文字内容
        for target_url in valid_urls:
            try:
                page_req = urllib.request.Request(target_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                with urllib.request.urlopen(page_req, timeout=8) as page_resp:
                    page_html = page_resp.read().decode("utf-8", errors="ignore")
                # 去掉所有标签，提取可见文字
                clean = re.sub(r'<script[^>]*>.*?</script>', '', page_html, flags=re.DOTALL)
                clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
                clean = re.sub(r'<[^>]+>', ' ', clean)
                clean = re.sub(r'\s+', ' ', clean).strip()
                # 取有效内容（100-500字）
                if len(clean) > 100:
                    results.append(clean[:500] + "...")
            except:
                continue

        if not results:
            # Step 4: 降级——只取百度摘要
            snippets = re.findall(r'<span class="content-right_[^"]*">(.*?)</span>', html)
            for s in snippets[:max_results]:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                if len(clean) > 20:
                    results.append(clean)

        return results if results else ["(搜索无结果，建议手动查询官方渠道)"]
    except Exception as e:
        return [f"(搜索暂时不可用: {e})"]

def should_search(msg):
    """判断是否需要联网搜索——更积极触发。"""
    triggers = [
        "今年", "最新", "2026", "2025", "最近", "现在",
        "分数线", "录取分", "投档线", "招生计划", "录取",
        "政策", "变化", "改革", "新规",
        "就业率", "就业前景", "薪资", "月薪", "年薪",
        "排名", "第几名", "怎么样", "好不好",
        "能上", "能报", "能进", "稳不稳", "冲不冲",
        "多少分", "什么专业", "一本", "二本", "985", "211",
        "王牌专业", "优势", "缺点", "劣势", "值得", "推荐吗",
    ]
    return any(t in msg for t in triggers)

# ── LLM 对话 ─────────────────────────────────────────
def cleanup_format(text):
    """去掉 AI 模型可能会漏的 Markdown 格式，确保输出像真人聊天。"""
    if not text:
        return text
    # 去掉 **粗体**
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 去掉 ### 标题
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # 去掉行首 - 列表标记
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    # 去掉行首数字编号 1. 2. 等
    text = re.sub(r'^\s*\d+[\.\、]\s*', '', text, flags=re.MULTILINE)
    return text.strip()

class GaokaoAdvisor:
    def __init__(self, api_key=None, base_url=None, model=None, slots=None):
        # 支持外部传入 API 配置（多用户场景各自用自己的 key）
        _api_key = api_key or CONFIG["api_key"]
        _base_url = base_url or CONFIG["base_url"]
        _model = model or CONFIG["model"]
        self.model = _model
        self.client = OpenAI(base_url=_base_url, api_key=_api_key)
        self.knowledge_base = load_file(KNOWLEDGE_BASE_PATH)
        self.system_prompt = load_file(SYSTEM_PROMPT_PATH)
        self.conversation = []
        # 支持外部传入独立的 slots（多用户场景各自有自己的槽位）
        self.slots = slots if slots is not None else {k: dict(v) for k, v in SLOTS.items()}

    def _build_system_message(self):
        """构建系统消息，包含 system prompt + 知识库 + 数据库状态 + 数据治理规则 + 槽位状态。"""
        kb = self.knowledge_base if self.knowledge_base else ""
        slots_status = slots_summary(self.slots)
        search_note = ""
        if CONFIG["enable_search"]:
            search_note = "\n\n【联网搜索已启用。遇到最新政策/分数线/就业数据等问题时，优先查询本地数据库，数据不足时再搜索。】"

        # 数据库状态
        db_info = ""
        if HAS_DATA_MODULE:
            try:
                stats = get_db_stats()
                if isinstance(stats, dict) and "schools" in stats:
                    db_info = f"""
【本地数据库已就绪】
- 院校: {stats['schools']} 条（985/211/双一流/普通）
- 专业: {stats['majors']} 条（含就业率、薪资、就业方向）
- 录取分数线: {stats['admission_scores']} 条（多省份多年份）
- 学科排名: {stats['subject_rankings']} 条（教育部评估）
- 招生政策: {stats['policies']} 条

数据来源分级：T1-官方数据（教育部/省考试院）> T2-权威平台（掌上高考/麦可思）> T4-百度搜索（仅供参考）
引用录取分数/就业数据时必须标注数据来源和年份。"""
            except Exception:
                db_info = "\n【本地数据库加载中...】"

        full_system = f"""{self.system_prompt}
{db_info}
{search_note}

【知识库参考】
{kb}

【当前用户信息采集状态】
{slots_status}

【数据查询规则】
当用户问到具体学校/专业/分数时，按以下优先级获取数据：
1. 本地数据库（有结构化的录取分数、院校信息、专业就业数据）→ 直接引用并标注来源
2. 百度实时搜索（数据库没有时的兜底方案）→ 标注"百度搜索，仅供参考，请核实官方数据"
3. 用户自行查询（数据完全缺失时）→ 建议去省考试院官网/阳光高考平台查询

严禁编造具体的录取分数和位次。不确定的数据必须标注"请核实"。

请在回答时：
1. 如果用户信息不全，追问缺失的槽位（用自然的方式，不要像填表）。
2. 如果信息已经足够（至少省份+分数/位次+核心诉求），查询数据库获取匹配院校后给出冲稳保推荐。
3. 引用数据时标注来源（如"根据教育部2023年学科评估..."或"数据库显示该校2024年录取线..."）。
4. 保持直爽、接地气的风格。"""
        return full_system

    def chat(self, user_msg):
        """处理一轮对话。返回 assistant 的回复。"""
        # 检查意图
        if is_consultation_intent(user_msg):
            # 提取槽位（使用实例自己的 slots）
            updates = extract_slots_from_message(user_msg, self.slots)
        else:
            updates = []

        # 构建消息
        system_msg = self._build_system_message()
        messages = [{"role": "system", "content": system_msg}]
        # 添加历史（最近10轮=20条消息）
        for h in self.conversation[-20:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_msg})

        # 如果有槽位更新，追加提示
        if updates:
            hint = f"(系统自动识别到: {', '.join(updates)}。请在回复中确认并追问缺失信息。)"
            messages.append({"role": "system", "content": hint})

        # 语录库注入：根据用户提到的专业，注入相关语录作为参考
        if QUOTES_INDEX:
            quote_keywords = []
            for major_key in QUOTES_INDEX:
                if major_key in user_msg:
                    quote_keywords.append(major_key)
            if quote_keywords:
                quotes_to_inject = []
                for mk in quote_keywords[:2]:  # 最多注入 2 个专业的语录
                    for q in QUOTES_INDEX[mk][:2]:  # 每专业最多 2 条
                        quotes_to_inject.append(q["text"])
                if quotes_to_inject:
                    quote_text = "\n".join([f"· {q}" for q in quotes_to_inject[:3]])
                    messages.append({
                        "role": "system",
                        "content": f"【相关语录参考】\n{quote_text}\n（以上语录可化用到回复中，不要一字不差照搬）"
                    })

        # 搜索（数据库优先 + 百度兜底）
        search_results = None
        if CONFIG["enable_search"] and should_search(user_msg):
            data_hints = []

            # 提取学校名和省份
            school_match = re.findall(r'[一-鿿]{2,10}(?:大学|学院|学校)', user_msg)
            prov_match = re.findall(
                r'(北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|西藏|宁夏|新疆)',
                user_msg
            )

            if HAS_DATA_MODULE:
                # 1. 查录取分数线（学校+省份）
                if school_match and prov_match:
                    try:
                        raw = query_admission(school_match[0], prov_match[0])
                        admission_text = format_admission_info(raw)
                        if admission_text and "暂无" not in admission_text:
                            data_hints.append(f"【录取数据查询结果】\n{admission_text}")
                    except Exception:
                        pass

                # 2. 查院校基本信息
                if school_match:
                    try:
                        info = query_school_info(school_match[0])
                        if info:
                            level_parts = []
                            if info.get("is_985"): level_parts.append("985")
                            if info.get("is_211"): level_parts.append("211")
                            if info.get("is_double_first_class"): level_parts.append("双一流")
                            level_str = "/".join(level_parts) if level_parts else info.get("level", "")
                            data_hints.append(
                                f"【院校信息】{info['name']} | {info['province']}{info['city']} | "
                                f"{level_str} {info.get('school_type','')} | 软科排名{info.get('ranking','未知')} | "
                                f"来源：{info['data_source']}"
                            )
                    except Exception:
                        pass

                # 3. 提取专业关键词，查就业数据
                major_match = re.findall(
                    r'(计算机|软件|人工智能|电气|电子信息|通信|临床医学|口腔|金融|法学|会计|土木|机械|新闻|汉语言|数学|物理|化学|生物|材料|环境|自动化|集成电路|大数据|物联网|信息安全|车辆工程|建筑学|统计学|药学|师范|英语|历史学|哲学)',
                    user_msg
                )
                if major_match:
                    try:
                        major_info = query_major_info(major_match[0])
                        if major_info:
                            emp_rate = f"{major_info['employment_rate']*100:.0f}%" if major_info.get('employment_rate') else "未知"
                            salary = f"{major_info['avg_salary']:.0f}元/月" if major_info.get('avg_salary') else "未知"
                            data_hints.append(
                                f"【就业数据】{major_info['name']} | {major_info.get('category','')} | "
                                f"就业率{emp_rate} | 毕业5年均薪{salary} | "
                                f"来源：{major_info['data_source']}"
                            )
                    except Exception:
                        pass

                # 4. 如果有分数+省份+选科信息，做位次法匹配推荐
                score_match = re.search(r'(\d{3})\s*分', user_msg)
                if score_match and prov_match and not school_match:
                    try:
                        score = int(score_match.group(1))
                        subject = "物理类" if "物理" in user_msg else ("历史类" if "历史" in user_msg else "综合")
                        # 先查位次
                        rank_info = query_yi_fen_yi_duan(prov_match[0], score, subject, 2024)
                        if rank_info and rank_info.get("rank"):
                            data_hints.append(
                                f"【分数→位次】{prov_match[0]} {score}分 {subject} → 位次约 {rank_info['rank']:,}\n"
                                f"来源：{rank_info['source']}\n"
                                f"置信度：{rank_info['confidence']}"
                            )

                        # 冲/稳/保三档推荐
                        for strategy in ["冲", "稳", "保"]:
                            matches = query_match_schools_v2(
                                score, prov_match[0], subject, strategy, year=2024
                            )
                            if matches:
                                match_lines = []
                                for m in matches[:5]:
                                    badge = ""
                                    if m.get("is_985"): badge = "985/"
                                    elif m.get("is_211"): badge = "211/"
                                    match_lines.append(
                                        f"  {m.get('school_name','')[:15]:15}({badge}{m.get('school_level','')}) "
                                        f"{m.get('batch','')[:8]:8} "
                                        f"最低分{m.get('min_score','')} 位次{m.get('min_rank','')}"
                                    )
                                data_hints.append(
                                    f"【{strategy}档位次法推荐】{prov_match[0]} {score}分 {subject}：\n" +
                                    "\n".join(match_lines)
                                )
                    except Exception as e:
                        pass

            # 汇总数据库结果
            if data_hints:
                messages.append({"role": "system", "content": "\n\n".join(data_hints)})
                search_results = "db_used"

            # 降级：数据库没有足够数据 → 百度搜索
            if not search_results:
                search_query = user_msg[:100]
                try:
                    baidu_results = web_search(search_query)
                except Exception:
                    baidu_results = []
                if baidu_results:
                    search_hint = "【百度搜索结果（T4级，仅供参考，请核实官方数据）】\n" + "\n".join(
                        f"· {r}" for r in baidu_results[:3]
                    )
                    messages.append({"role": "system", "content": search_hint})

        # 调用 LLM
        try:
            kwargs = dict(
                model=CONFIG["model"],
                messages=messages,
                temperature=CONFIG["temperature"],
            )
            if CONFIG["max_tokens"] is not None:
                kwargs["max_tokens"] = CONFIG["max_tokens"]
            resp = self.client.chat.completions.create(**kwargs)
            reply = resp.choices[0].message.content
        except Exception as e:
            reply = f"出错了：{e}\n请检查 API 配置（base_url, api_key, model 是否正确）。"

        # 清理格式：去掉模型不听 prompt 时残留的 markdown
        reply = cleanup_format(reply)

        # 保存对话历史
        self.conversation.append({"role": "user", "content": user_msg})
        self.conversation.append({"role": "assistant", "content": reply})

        return reply

    def reset(self):
        """重置对话和槽位。"""
        self.conversation = []
        for k in self.slots:
            self.slots[k]["filled"] = False
            self.slots[k]["value"] = ""

# ── CLI 界面 ─────────────────────────────────────────
def test_connection():
    """测试 API 连接是否正常。"""
    try:
        client = OpenAI(base_url=CONFIG["base_url"], api_key=CONFIG["api_key"])
        resp = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return True, resp.choices[0].message.content
    except Exception as e:
        return False, str(e)

def main():
    import textwrap

    print("=" * 60)
    print("  高考志愿顾问 Agent")
    print(f"  模型: {CONFIG['model']}")
    print(f"  搜索: {'开' if CONFIG['enable_search'] else '关'}")
    print("=" * 60)

    if not CONFIG["api_key"]:
        print("\n❌ 未检测到 API Key！")
        print("   请复制 .env.example 为 .env 并填入你的 API Key。")
        print("   或者设置环境变量 LLM_API_KEY=你的key")
        print()
        print("   快速开始（任选一种）：")
        print("   · DeepSeek:  set LLM_PROVIDER=deepseek && set LLM_API_KEY=sk-xxx")
        print("   · 通义千问:  set LLM_PROVIDER=qwen && set LLM_API_KEY=sk-xxx")
        print("   · 智谱GLM:   set LLM_PROVIDER=glm && set LLM_API_KEY=xxx")
        input("\n   按回车退出...")
        return

    # 测试连接
    print("  正在测试 API 连接...", end=" ", flush=True)
    ok, msg = test_connection()
    if ok:
        print("[OK] 连接成功")
    else:
        print(f"[X] 连接失败: {msg[:200]}")
        print()
        # 智能诊断
        if "401" in msg or "Authentication" in msg:
            print("   → Key 无效或格式错误。检查：")
            print("   1. Key 是不是 sk- 完整开头？前后有没有空格？")
            print("   2. 去 API 平台确认 Key 状态是'有效'")
            print("   3. 试试只留两行：LLM_PROVIDER=deepseek + LLM_API_KEY=你的key")
        elif "402" in msg or "Insufficient" in msg or "Balance" in msg:
            print("   → 账户余额不足！去 API 平台充值，或换通义千问（有免费额度）")
        elif "403" in msg or "Forbidden" in msg:
            print("   → Key 没有权限。检查 Key 是否开通了 chat/completions 接口")
        elif "404" in msg or "Not Found" in msg:
            print("   → 接口地址不对。试试 BASE_URL 末尾加 /v1")
        elif "timeout" in msg.lower() or "connect" in msg.lower():
            print("   → 网络连不上 API 服务器。检查网络/代理")
        else:
            print("   检查 .env 中 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
        input("\n   按回车退出...")
        return

    print("=" * 60)
    print("  命令: /paste 粘贴 | /slots 信息 | /reset 重置 | /quit 退出")
    print("  直接描述你的情况，我会帮你分析。")
    print("=" * 60)
    print()

    advisor = GaokaoAdvisor()

    while True:
        try:
            user_input = input("\n[You] 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见！")
            break
        elif user_input == "/reset":
            advisor.reset()
            print("[OK] 已重置对话和信息采集")
            continue
        elif user_input == "/slots":
            print(slots_summary())
            continue
        elif user_input == "/paste":
            cb = read_clipboard()
            if cb and cb.strip():
                user_input = " ".join(cb.strip().split("\n"))
                print(f"📋 剪贴板已读取 ({len(user_input)}字)")
                print(f"📋 内容: {user_input[:100]}...")
            else:
                print("📋 剪贴板为空或无法读取")
                continue

        print("\n🤖 顾问: ", end="", flush=True)
        reply = advisor.chat(user_input)
        print(reply)

if __name__ == "__main__":
    main()
