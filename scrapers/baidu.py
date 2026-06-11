"""
百度搜索采集器 — 兜底方案（T4 级数据源）
当 API 不可用时，用百度搜索获取基本信息
"""
import re
import time
import urllib.request
import urllib.parse


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def search_baidu_snippets(query, max_results=5):
    """百度搜索，提取摘要片段"""
    try:
        url = "https://www.baidu.com/s?wd=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 提取摘要
        snippets = re.findall(
            r'<span class="content-right_[^"]*">(.*?)</span>', html
        )
        results = []
        for s in snippets[:max_results]:
            clean = re.sub(r'<[^>]+>', '', s).strip()
            if len(clean) > 20:
                results.append(clean)

        # 降级：提取任意包含数字的段落
        if not results:
            text = re.sub(r'<[^>]+>', ' ', html)
            paras = [p.strip() for p in text.split('。') if any(c.isdigit() for c in p) and len(p) > 20]
            results = paras[:max_results]

        return results if results else []
    except Exception as e:
        return [f"(搜索出错: {e})"]


def search_admission_snippets(school, province, year=2024):
    """搜索录取分数线摘要"""
    queries = [
        f"{school} {province} {year} 录取分数线 最低分 最低位次",
        f"{school} {year} 各省录取分数线",
    ]
    all_snippets = []
    for q in queries:
        snippets = search_baidu_snippets(q, max_results=3)
        all_snippets.extend(snippets)
        if len(all_snippets) >= 3:
            break
        time.sleep(0.5)
    return all_snippets[:5]


def search_employment_snippets(major):
    """搜索就业数据摘要"""
    queries = [
        f"{major} 就业率 薪资 2024 2025",
        f"{major} 专业 毕业生 就业前景",
    ]
    all_snippets = []
    for q in queries:
        snippets = search_baidu_snippets(q, max_results=3)
        all_snippets.extend(snippets)
        if len(all_snippets) >= 3:
            break
        time.sleep(0.5)
    return all_snippets[:5]
