"""
掌上高考 API 采集器 — 从 zhiyuan.com 公开接口获取数据
数据源等级: T2（可靠，需交叉验证）

API 端点（公开、无需认证）：
- 院校列表: https://api.zhiyuan.com/api/v1/school/list
- 院校详情: https://api.zhiyuan.com/api/v1/school/info
- 专业列表: https://api.zhiyuan.com/api/v1/major/list
- 录取分数: https://api.zhiyuan.com/api/v1/admission/score
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.zhiyuan.com/",
}

# API 基础地址
BASE_URL = "https://api.zhiyuan.com"


def _fetch_json(url, params=None, retries=2):
    """通用 JSON 请求，带重试"""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                return json.loads(data)
        except Exception as e:
            if attempt < retries:
                time.sleep(1 * (attempt + 1))
            else:
                return {"error": str(e)}
    return {"error": "max retries"}


def fetch_school_list(province=None, level=None, page=1, page_size=50):
    """获取院校列表
    Args:
        province: 省份过滤（如"湖北"）
        level: 层次过滤（如"985","211"）
    Returns:
        list of school dicts
    """
    params = {"page": page, "page_size": page_size}
    if province:
        params["province"] = province
    if level:
        params["level"] = level

    data = _fetch_json(f"{BASE_URL}/api/v1/school/list", params)
    if "error" in data:
        return []
    return data.get("data", data.get("result", []))


def fetch_school_info(school_id):
    """获取院校详情"""
    data = _fetch_json(f"{BASE_URL}/api/v1/school/info", {"school_id": school_id})
    if "error" in data:
        return None
    return data.get("data", data.get("result"))


def fetch_major_list(school_id=None, category=None, page=1, page_size=100):
    """获取专业列表"""
    params = {"page": page, "page_size": page_size}
    if school_id:
        params["school_id"] = school_id
    if category:
        params["category"] = category
    data = _fetch_json(f"{BASE_URL}/api/v1/major/list", params)
    if "error" in data:
        return []
    return data.get("data", data.get("result", []))


def fetch_admission_scores(school_id, province=None, year=None, page=1, page_size=100):
    """获取录取分数线"""
    params = {"school_id": school_id, "page": page, "page_size": page_size}
    if province:
        params["province"] = province
    if year:
        params["year"] = year
    data = _fetch_json(f"{BASE_URL}/api/v1/admission/score", params)
    if "error" in data:
        return []
    return data.get("data", data.get("result", []))


# ── 备选数据源：中国教育在线 ──

EOL_BASE = "https://gkcx.eol.cn"


def fetch_eol_school_list(province=None, page=1):
    """从中国教育在线获取院校列表"""
    params = {"provinceid": "", "page": page, "size": 50}
    if province:
        # 省份名转 ID（简化映射）
        province_map = {
            "北京": "11",
            "天津": "12",
            "河北": "13",
            "山西": "14",
            "内蒙古": "15",
            "辽宁": "21",
            "吉林": "22",
            "黑龙江": "23",
            "上海": "31",
            "江苏": "32",
            "浙江": "33",
            "安徽": "34",
            "福建": "35",
            "江西": "36",
            "山东": "37",
            "河南": "41",
            "湖北": "42",
            "湖南": "43",
            "广东": "44",
            "广西": "45",
            "海南": "46",
            "重庆": "50",
            "四川": "51",
            "贵州": "52",
            "云南": "53",
            "西藏": "54",
            "陕西": "61",
            "甘肃": "62",
            "青海": "63",
            "宁夏": "64",
            "新疆": "65",
        }
        pid = province_map.get(province, "")
        if pid:
            params["provinceid"] = pid

    data = _fetch_json(f"{EOL_BASE}/api/school/lists", params)
    if "error" in data:
        return []
    return data.get("data", {}).get("item", [])


def fetch_eol_admission(school_id, province_id=None, year=None):
    """从中国教育在线获取录取分数线"""
    params = {"school_id": school_id, "page": 1, "size": 50}
    if province_id:
        params["province_id"] = province_id
    if year:
        params["year"] = year
    data = _fetch_json(f"{EOL_BASE}/api/admission/score", params)
    if "error" in data:
        return []
    return data.get("data", {}).get("item", [])


if __name__ == "__main__":
    # 快速测试
    print("测试掌上高考 API...")
    schools = fetch_school_list(level="985", page_size=5)
    print(f"  院校列表: {len(schools)} 条")
    if schools:
        print(f"  示例: {schools[0]}")

    print("\n测试中国教育在线 API...")
    eol_schools = fetch_eol_school_list(page=1)
    print(f"  EOL 院校列表: {len(eol_schools)} 条")
