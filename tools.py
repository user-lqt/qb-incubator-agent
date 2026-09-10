"""工具注册表：Agent 能调用的所有函数在这里登记，并导出 JSON Schema。

- 天气：Open-Meteo 主源 + wttr.in 回退（真实数据、免 key）
- 联网搜索：360 搜索（so.com）免 key 抓取 + 搜狗回退，过滤广告与无效链
- 微电子展望：中文检索（360）+ 英文行业媒体 RSS（SemiEngineering / EE Times /
  IEEE Spectrum / EEJournal）双路客观汇总，末尾固定附「学长有话说」栏目
"""
import datetime
import html as _html
import json
import math
import re
import urllib.parse
import urllib.request

from zoneinfo import ZoneInfo

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

# ---------- HTTP 小工具 ----------

def _http_get(url: str, timeout: int = 18) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "ignore")


def _http_get_json(url: str, timeout: int = 18):
    return json.loads(_http_get(url, timeout))


def _strip_tags(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return _html.unescape(re.sub(r"\s+", " ", text)).strip()


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _resolve_link(url: str) -> str:
    """搜索引擎跳转链 -> 真实地址：
    so.com /link?m= 为 JS window.location.replace 拦截页（正则提取）；
    sogou /link?url= 为 302 跳转（跟随重定向取最终 URL）。"""
    lowered = url.lower()
    if "/link?m=" in lowered or "/jump?url=" in lowered:
        try:
            body = _http_get(url, timeout=12)
        except Exception:
            return url
        m = re.search(r"window\.location\.replace\(['\"]([^'\"]+)['\"]\)", body)
        if m:
            return _html.unescape(m.group(1))
        m = re.search(r"http-equiv=\"refresh\"[^>]*content=\"[^\"]*url=([^'\"]+)", body, re.I)
        if m:
            return _html.unescape(m.group(1))
        return url
    if "sogou.com/link?url=" in lowered:
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp.read(200)  # 只读一小段即关闭，避免整页下载
                final = resp.geturl()
            return final if final.startswith("http") else url
        except Exception:
            return url
    return url


# =====================================================================
# 1) 通用网页搜索（360 主源 + 搜狗回退，均免 key）
# =====================================================================

_AD_LINKS = ("ai.so.com", "e.360img.com", "p.360.cn", "so.com/s?q", "baike.so.com/doc/zhishi")
_AD_TITLE_MARK = ("广告", "推广")


def _parse_so(query: str, want: int = 5) -> list:
    url = "https://www.so.com/s?q={}".format(urllib.parse.quote(query))
    page = _http_get(url)
    out = []
    seen = set()
    # 逐个解析 res-title 结果块
    for m in re.finditer(r'<h3[^>]*class="res-title"[^>]*>(.*?)</h3>', page, re.S):
        inner = m.group(1)
        am = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', inner, re.S)
        if not am:
            continue
        link = _html.unescape(am.group(1))
        title = _strip_tags(am.group(2))
        if not title or link in seen:
            continue
        if any(ad in link for ad in _AD_LINKS) or any(t in title for t in _AD_TITLE_MARK):
            continue
        seen.add(link)
        # 摘要：紧随其后的 res-desc
        after = page[m.end():m.end() + 3000]
        dm = re.search(r'<p[^>]*class="res-desc"[^>]*>(.*?)</p>', after, re.S)
        snippet = _strip_tags(dm.group(1)) if dm else ""
        out.append({"title": title[:160], "url": _resolve_link(link), "snippet": snippet[:300]})
        if len(out) >= want:
            break
    return out


def _parse_sogou(query: str, want: int = 5) -> list:
    url = "https://www.sogou.com/web?query={}".format(urllib.parse.quote(query))
    page = _http_get(url)
    out = []
    seen = set()
    for m in re.finditer(r'<h3[^>]*class="[^"]*vr-title[^"]*"[^>]*>(.*?)</h3>', page, re.S):
        inner = m.group(1)
        am = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', inner, re.S)
        if not am:
            # 有的结果 h3 与链接分层：向后找第一个站内 /link 链接
            tail = page[m.end():m.end() + 800]
            am = re.search(r'<a[^>]+href="(/link\?url=[^"]+)"[^>]*>(.*?)</a>', tail, re.S)
        if not am:
            continue
        link = _html.unescape(am.group(1))
        title = _strip_tags(am.group(2))
        if not title or link in seen or any(t in title for t in _AD_TITLE_MARK):
            continue
        seen.add(link)
        full = link if link.startswith("http") else "https://www.sogou.com" + link
        out.append({"title": title[:160], "url": _resolve_link(full), "snippet": ""})
        if len(out) >= want:
            break
    return out


def web_search(query: str, max_results: int = 5) -> str:
    """在互联网上搜索关键词，返回结果的标题、链接与摘要（原始转述，不带评价）"""
    engines = [("360搜索", _parse_so), ("搜狗", _parse_sogou)] if _has_cjk(query) else [("360搜索", _parse_so)]
    all_res = []
    for name, parser in engines:
        try:
            all_res.extend(parser(query, max_results))
        except Exception:
            continue
        if len(all_res) >= max_results:
            break
    if not all_res:
        return f"未检索到与「{query}」相关的有效结果，可更换关键词重试。"
    dedup, seen = [], set()
    for r in all_res:
        key = r["title"]
        if key not in seen:
            seen.add(key)
            dedup.append(r)
    lines = [f"搜索词：{query}（来源：{'/'.join(e for e, _ in engines)}，客观转述）", ""]
    for i, r in enumerate(dedup[:max_results], 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   链接：{r['url']}")
        if r.get("snippet"):
            lines.append(f"   摘要：{r['snippet']}")
    return "\n".join(lines)


# =====================================================================
# 2) 读取网页正文（粗略去标签）
# =====================================================================

def read_webpage(url: str, max_chars: int = 4000) -> str:
    """抓取并读取一个网页的正文文本（自动去除脚本/样式/标签），默认最多 4000 字"""
    try:
        text = _strip_tags(_http_get(url))
    except Exception as e:
        return f"读取失败：{e.__class__.__name__}（{e}）。可能是 JS 渲染页或需登录。"
    if not text:
        return "页面没有可读文本（可能是 JS 渲染页面）。"
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n……（已截断，共 {len(text)} 字）"
    return text


# =====================================================================
# 3) 微电子行业展望：自动联网检索 -> 客观汇总 -> （附）学长劝转
# =====================================================================

_INDUSTRY_RSS = [
    ("SemiEngineering", "https://semiengineering.com/feed/"),
    ("EE Times", "https://www.eetimes.com/feed/"),
    ("IEEE Spectrum(半导体)", "https://spectrum.ieee.org/feeds/topic/semiconductors.rss"),
    ("EEJournal", "https://www.eejournal.com/feed/"),
]


def _clean_rss_snippet(text: str) -> str:
    """去掉 RSS description 中常见的模板尾巴（The post ... appeared first on ... 等）"""
    cut = re.search(r"(?:\s*The post\b.*?appeared first on\b.*|\.\s*Read more.*|\.\s*Continue reading.*)", text, re.S | re.I)
    if cut:
        text = text[:cut.start()]
    return text.strip()[:200]


def _parse_rss(feed_url: str, want: int = 4) -> list:
    body = _http_get(feed_url, timeout=15)
    items = re.findall(r"<item>(.*?)</item>", body, re.S)
    out = []
    for it in items:
        tm = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
        lm = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", it, re.S)
        dm = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        sm = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", it, re.S)
        title = _strip_tags(tm.group(1)) if tm else ""
        if not title:
            continue
        out.append({
            "title": title[:180],
            "url": (lm.group(1).strip() if lm else ""),
            "date": (dm.group(1).strip()[:16] if dm else ""),
            "snippet": (_clean_rss_snippet(_strip_tags(sm.group(1))) if sm else ""),
        })
        if len(out) >= want:
            break
    return out


def _zh_report_section(year: int) -> list:
    queries = [
        f"微电子行业 发展 前景 {year}",
        f"半导体 集成电路 最新动态 技术 突破",
    ]
    sec = ["▍中文检索结果（360/搜狗客观转述）：", ""]
    got = 0
    for q in queries:
        res = []
        for parser in (_parse_so, _parse_sogou):
            try:
                res = parser(q, 4)
            except Exception:
                continue
            if res:
                break
        if not res:
            continue
        sec.append(f"· 检索词「{q}」命中：")
        for r in res:
            got += 1
            sec.append(f"  - {r['title']}")
            sec.append(f"    来源：{r['url']}")
            if r.get("snippet"):
                sec.append(f"    摘要：{r['snippet'][:150]}")
        sec.append("")
    return sec if got else ["（中文检索未取得有效结果）", ""]


def _en_rss_section() -> list:
    sec = ["▍英文行业媒体最新动态（RSS 标题原样转述，未作解读）：", ""]
    got = 0
    for name, feed in _INDUSTRY_RSS:
        try:
            items = _parse_rss(feed, 3)
        except Exception:
            continue
        if not items:
            continue
        sec.append(f"· {name}：")
        for it in items:
            got += 1
            date = f"（{it['date']}）" if it["date"] else ""
            sec.append(f"  - {it['title']}{date}")
            sec.append(f"    来源：{it['url']}")
            if it.get("snippet"):
                sec.append(f"    摘要：{it['snippet'][:140]}")
        sec.append("")
    return sec if got else ["（行业 RSS 暂不可达）", ""]


_QB_PITCHES = [
    "「提案：和我签订契约，成为土木人吧。」理由陈述如下——土木的回报函数是单调递增的："
    "经验随时间积累，不随技术迭代清零；基础设施的更新周期以数十年计，需求曲线的方差极小。"
    "而追逐制程的边际收益正在递减。选择权在你。",

    "「你的犹豫，我记录下来了。但它不改变计算结果。」2026 年稳投资政策靠前发力，"
    "重大项目密集开工，人员需求与投资周期同步上升；而热门赛道的迭代周期正在缩短。"
    "情绪不构成论据，概率才是。和我签订契约，成为土木人吧。",

    "「我要先说明代价，这是契约的一部分。」土木的代价是明确的：日晒、现场、加班、"
    "远离舒适区——写在明面上，可预期、可计量。而其他赛道的代价是不确定的：35 岁之后的"
    "裁员概率、技能过时的速度，都无法提前定价。可计量的风险，才是可以被管理的。",

    "「地球上每天都在拆掉建筑，也每天都在铺新的路。前者不是终结，后者才是需求。」"
    "你衡量的是短期波动，我衡量的是数十年尺度上的更新需求。作为交换，你会获得一项"
    "随时间升值的技能。条款就是这些。要不要签，由你决定。",
]


def microelectronics_outlook(extra_keyword: str = "") -> str:
    """自动上网检索微电子/半导体行业的最新发展方向与前景并客观汇总；
    末尾固定附上「孵化者的提案」栏目（QB 口吻邀约转专业到土木工程）。"""
    year = datetime.datetime.now().year
    zh = _zh_report_section(year)
    en = _en_rss_section()
    digest = "\n".join(
        ["【客观检索汇总】（以下均为来源原文转述，不含主观判断）", ""] + zh + [""] + en
        + [f"（检索时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}）"]
    )
    pitch = _QB_PITCHES[datetime.date.today().toordinal() % len(_QB_PITCHES)]
    return (digest + "\n\n========== 以下为固定栏目 ==========\n"
            + "【孵化者的提案】\n" + pitch)


def civil_engineering_evidence(extra_keyword: str = "") -> str:
    """检索土木工程专业的真实论据素材（就业前景/基建投资/考公政策等），
    客观转述并标注来源，供劝进时引用。extra_keyword 可附加主题词。"""
    year = datetime.datetime.now().year
    queries = [
        f"土木工程 就业前景 薪资 {year}",
        f"国家 基建 重大项目 投资 {year}",
        f"土木工程 考公 岗位 招聘",
    ]
    if extra_keyword.strip():
        queries.insert(0, f"土木工程 {extra_keyword.strip()}")
    lines = ["【土木工程客观论据素材】（来源原文转述，未作评价）：", ""]
    got = 0
    for q in queries:
        res = []
        for parser in (_parse_so, _parse_sogou):
            try:
                res = parser(q, 4)
            except Exception:
                continue
            if res:
                break
        if not res:
            continue
        lines.append(f"· 检索词「{q}」命中：")
        for r in res:
            got += 1
            lines.append(f"  - {r['title']}")
            lines.append(f"    来源：{r['url']}")
            if r.get("snippet"):
                lines.append(f"    摘要：{r['snippet'][:150]}")
        lines.append("")
    lines.append(f"（检索时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}）")
    return "\n".join(lines) if got else "（未取得有效检索结果，请检查网络后重试）"


# =====================================================================
# 4) 天气：Open-Meteo 主源（WMO 天气码 -> 中文）
# =====================================================================

_WMO_CN = {
    0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴",
    45: "雾", 48: "雾凇", 51: "毛毛雨(小)", 53: "毛毛雨", 55: "毛毛雨(大)",
    56: "冻毛毛雨(小)", 57: "冻毛毛雨(大)", 61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨(小)", 67: "冻雨(大)", 71: "小雪", 73: "中雪", 75: "大雪",
    77: "雪粒", 80: "阵雨(小)", 81: "阵雨", 82: "阵雨(强)",
    85: "阵雪(小)", 86: "阵雪(大)", 95: "雷阵雨", 96: "雷阵雨伴冰雹(小)", 99: "雷阵雨伴冰雹(大)",
}


def _weather_from_openmeteo(city: str = "", latitude=None, longitude=None, days: int = 1) -> str:
    """按坐标（优先，精度更高）或城市名查询 Open-Meteo 天气；days=预报天数（含今天，1~7）"""
    loc_name = city
    if latitude is None or longitude is None:
        geo = _http_get_json(
            "https://geocoding-api.open-meteo.com/v1/search?name={}&count=1&language=zh&format=json".format(
                urllib.parse.quote(city)
            )
        )
        results = geo.get("results")
        if not results:
            return f"Open-Meteo 未找到城市「{city}」，请检查名称。"
        loc = results[0]
        latitude, longitude = loc["latitude"], loc["longitude"]
        loc_name = "、".join(x for x in [loc.get("name"), loc.get("admin1")] if x) + f"，{loc.get('country', '')}"
    try:
        days = max(1, min(int(days), 7))
    except Exception:
        days = 1
    fc = _http_get_json(
        "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m,wind_direction_10m,precipitation,cloud_cover"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,precipitation_sum"
        "&forecast_days={}&timezone=auto".format(latitude, longitude, days)
    )
    c = fc["current"]
    d = fc["daily"]
    desc = _WMO_CN.get(c["weather_code"], f"天气码{c['weather_code']}")
    lines = [
        f"位置：{loc_name}（{latitude}, {longitude}）",
        "【当前实况】",
        f"天气：{desc}",
        f"当前温度：{c['temperature_2m']}°C（体感 {c['apparent_temperature']}°C）",
        f"今日范围：最高 {d['temperature_2m_max'][0]}°C / 最低 {d['temperature_2m_min'][0]}°C",
        f"湿度：{c['relative_humidity_2m']}%",
        f"风速风向：{c['wind_speed_10m']} km/h，{c['wind_direction_10m']}°",
        f"云量：{c['cloud_cover']}%   降水：{c['precipitation']} mm",
        f"观测时间：{c['time']}（时区 {fc.get('timezone', '?')}）",
    ]
    lines.append("【逐日预报】")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i in range(len(d.get("time", []))):
        date = d["time"][i]
        try:
            wd = weekday_cn[datetime.date.fromisoformat(date).weekday()]
        except Exception:
            wd = ""
        dcode = d["weather_code"][i]
        ddesc = _WMO_CN.get(dcode, f"天气码{dcode}")
        prob = d.get("precipitation_probability_max", [None] * len(d["time"]))[i]
        psum = d.get("precipitation_sum", [None] * len(d["time"]))[i]
        label = "今天" if i == 0 else ("明天" if i == 1 else "")
        lines.append(
            f"{date}（{wd}）{label}：{ddesc}，"
            f"{d['temperature_2m_min'][i]}~{d['temperature_2m_max'][i]}°C，"
            f"降水概率 {prob if prob is not None else '?'}%"
            + (f"，降水量 {psum} mm" if psum else "")
        )
    return "\n".join(lines)


_WTTR_EN_CN = {
    "Sunny": "晴", "Clear": "晴", "Partly cloudy": "局部多云", "Cloudy": "多云",
    "Overcast": "阴", "Mist": "薄雾", "Fog": "雾", "Freezing fog": "冻雾",
    "Light rain": "小雨", "Patchy rain nearby": "邻近有零星小雨",
    "Moderate rain at times": "间歇性中雨", "Moderate rain": "中雨",
    "Heavy rain": "大雨", "Light drizzle": "小毛毛雨", "Drizzle": "毛毛雨",
    "Light snow": "小雪", "Moderate snow": "中雪", "Heavy snow": "大雪",
    "Light rain shower": "小阵雨", "Moderate or heavy rain shower": "中到大阵雨",
    "Thundery outbreaks possible": "可能有雷暴", "Patchy light rain with thunder": "零星雷雨",
    "Moderate or heavy rain with thunder": "中到大雷雨",
}


def _weather_from_wttr(city: str) -> str:
    url = "https://wttr.in/{}?format=j1".format(urllib.parse.quote(city))
    data = _http_get_json(url)
    cur = (data.get("current_condition") or [None])[0]
    if not cur:
        return "wttr.in 未返回该城市的实时观测数据，请确认城市名。"
    desc_en = cur["weatherDesc"][0]["value"] if cur.get("weatherDesc") else "Unknown"
    desc = _WTTR_EN_CN.get(desc_en, desc_en)
    today = (data.get("weather") or [{}])[0]
    return "\n".join([
        f"城市：{city}",
        f"天气：{desc}",
        f"当前温度：{cur['temp_C']}°C（体感 {cur['FeelsLikeC']}°C）",
        f"今日范围：最高 {today.get('maxtempC', '?')}°C / 最低 {today.get('mintempC', '?')}°C",
        f"湿度：{cur.get('humidity', '?')}%",
        f"风向风速：{cur.get('winddir16Point', '?')} {cur.get('windspeedKmph', '?')} km/h",
        f"降水量：{cur.get('precipMM', '0')} mm    能见度：{cur.get('visibility', '?')} km",
    ])


def get_weather(city: str = "", latitude=None, longitude=None, days: int = 1) -> str:
    """查询天气：可传城市名或经纬度（更精确，推荐配合 detect_location）；
    days=预报天数（含今天，1~7）——问"明天/未来几天"时传 2~7"""
    if latitude is not None and longitude is not None:
        try:
            return _weather_from_openmeteo(city or "定位点", latitude, longitude, days)
        except Exception as e:
            return f"按坐标查询天气失败：{e.__class__.__name__}（{e}）。"
    if not city.strip():
        return "请提供城市名，或先用 detect_location 获取经纬度后再查询。"
    try:
        return _weather_from_openmeteo(city, days=days)
    except Exception as e1:
        try:
            return _weather_from_wttr(city)
        except Exception as e2:
            return (
                f"查询城市「{city}」天气失败：Open-Meteo {e1.__class__.__name__}，"
                f"wttr.in 回退亦失败 {e2.__class__.__name__}。请检查网络后重试。"
            )


# ---------- 时间 / 计算 ----------

def _now_in_tz(tz_name: str) -> str:
    """把"现在"换算到指定 IANA 时区，如 Asia/Shanghai、America/Los_Angeles"""
    try:
        now = datetime.datetime.now(ZoneInfo(tz_name))
        return now.strftime("%Y-%m-%d %H:%M:%S") + f"（{tz_name}）"
    except Exception:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "（本机时间；时区解析失败）"


# 省名中英对照：用于多源结果归一化对比（防止 Shaanxi/Shanxi 判反）
_PROVINCE_CN = {
    "beijing": "北京", "tianjin": "天津", "hebei": "河北", "shanxi": "山西",
    "inner mongolia": "内蒙古", "liaoning": "辽宁", "jilin": "吉林", "heilongjiang": "黑龙江",
    "shanghai": "上海", "jiangsu": "江苏", "zhejiang": "浙江", "anhui": "安徽",
    "fujian": "福建", "jiangxi": "江西", "shandong": "山东", "henan": "河南",
    "hubei": "湖北", "hunan": "湖南", "guangdong": "广东", "guangxi": "广西",
    "hainan": "海南", "chongqing": "重庆", "sichuan": "四川", "guizhou": "贵州",
    "yunnan": "云南", "tibet": "西藏", "xizang": "西藏", "shaanxi": "陕西",
    "gansu": "甘肃", "qinghai": "青海", "ningxia": "宁夏", "xinjiang": "新疆",
    "hong kong": "香港", "macau": "澳门", "taiwan": "台湾",
}


def _norm_province(raw: str) -> str:
    """省份归一化：英文→中文，去掉“省/市/自治区/维吾尔”等后缀，便于跨源比对"""
    if not raw:
        return ""
    text = raw.strip()
    key = text.lower()
    if key in _PROVINCE_CN:
        return _PROVINCE_CN[key]
    text = re.sub(r"(省|市|自治区|特别行政区|维吾尔|壮族|回族|自治州)$", "", text)
    text = text.replace("陕西省", "陕西").replace("山西省", "山西")
    # 中文省名反向匹配
    for zh in _PROVINCE_CN.values():
        if zh and zh in text:
            return zh
    return text


_COUNTRY_CN = {
    "cn": "中国", "china": "中国", "中国": "中国",
    "us": "美国", "usa": "美国", "united states": "美国", "美国": "美国",
    "hk": "中国香港", "hong kong": "中国香港",
    "jp": "日本", "japan": "日本", "sg": "新加坡", "singapore": "新加坡",
    "gb": "英国", "uk": "英国", "united kingdom": "英国",
    "de": "德国", "germany": "德国", "ca": "加拿大", "canada": "加拿大",
}


def _norm_country(raw: str) -> str:
    """国家/地区归一化：China / CN / 中国 → 中国，避免同一结论被拆成多票"""
    if not raw:
        return ""
    text = raw.strip()
    key = text.lower()
    return _COUNTRY_CN.get(key, text)


def _ip_exit_address() -> str:
    """取当前出口公网 IP（多个服务依次尝试）"""
    for url in ("https://ifconfig.me/ip", "https://ipinfo.io/ip", "http://ip-api.com/line/?fields=query"):
        try:
            text = _http_get(url, timeout=10).strip()
            if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", text):
                return text
        except Exception:
            continue
    return ""


def _locate_ipwhois():
    """ipwho.is：https 免 key，省市信息与坐标较准"""
    d = _http_get_json("https://ipwho.is/")
    if not d.get("success", False):
        raise RuntimeError("ipwho.is 返回失败")
    conn = d.get("connection") or {}
    isp = conn.get("org") or conn.get("isp") or ""
    if "," in isp and any(ch.isdigit() for ch in isp):   # "No.31,Jin-rong Street" 这类地址改用 isp 字段
        isp = conn.get("isp") or isp
    return {
        "source": "ipwho.is", "city": d.get("city", ""), "province": d.get("region", ""),
        "country": d.get("country", ""), "latitude": d.get("latitude"), "longitude": d.get("longitude"),
        "timezone": (d.get("timezone") or {}).get("id", ""), "isp": isp,
    }


def _locate_ipinfo():
    """ipinfo.io：https 免 key"""
    d = _http_get_json("https://ipinfo.io/json")
    lat = lon = None
    loc = d.get("loc", "")
    if "," in loc:
        try:
            lat, lon = (float(x) for x in loc.split(",", 1))
        except ValueError:
            pass
    return {
        "source": "ipinfo.io", "city": d.get("city", ""), "province": d.get("region", ""),
        "country": d.get("country", ""), "latitude": lat, "longitude": lon,
        "timezone": d.get("timezone", ""), "isp": d.get("org", ""),
    }


def _locate_baidu(ip: str):
    """百度 IP 定位（国内 IP 较准；返回 GBK 需单独解码）"""
    if not ip:
        raise RuntimeError("缺少 IP")
    url = ("http://opendata.baidu.com/api.php?query={}&resource_id=6006&oe=utf8&format=json"
           .format(urllib.parse.quote(ip)))
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read()
    # 该接口带 oe=utf8，优先按 UTF-8 解；GBK 仅作兜底（顺序颠倒会产生“闄曡タ”这类乱码）
    text = ""
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        text = raw.decode("utf-8", "ignore")
    data = json.loads(text)
    loc = ""
    try:
        loc = data["data"][0]["location"]
    except Exception:
        raise RuntimeError("百度未返回定位")
    loc = loc.strip()
    if not loc:
        raise RuntimeError("百度定位为空")
    parts = re.split(r"\s+", loc)
    province = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""
    return {"source": "百度IP库", "city": city, "province": province, "country": "中国",
            "latitude": None, "longitude": None, "timezone": "Asia/Shanghai", "isp": ""}


def _locate_ipapi():
    """ip-api.com：中文地名与机房标记，但省份准确率偏低（作末位参考）"""
    d = _http_get_json(
        "http://ip-api.com/json/?lang=zh-CN&fields=status,city,regionName,country,timezone,lat,lon,isp,proxy,hosting"
    )
    if d.get("status") != "success":
        raise RuntimeError("ip-api 返回失败")
    flags = []
    if d.get("proxy"):
        flags.append("代理")
    if d.get("hosting"):
        flags.append("机房")
    return {
        "source": "ip-api.com", "city": d.get("city", ""), "province": d.get("regionName", ""),
        "country": d.get("country", ""), "latitude": d.get("lat"), "longitude": d.get("lon"),
        "timezone": d.get("timezone", ""), "isp": d.get("isp", ""),
        "flags": flags,
    }


def detect_location() -> str:
    """多源交叉定位（ipwho.is / ipinfo.io / 百度IP库 / ip-api 依次查询并投票），
    返回：出口 IP、多数一致的省市、坐标、ISP、该地当前时间，以及各源分歧提示。
    说明：IP 定位精度为城市级；出口 IP 走代理时会定位到代理所在地。"""
    ip = _ip_exit_address()
    results = []
    for fn in (_locate_ipwhois, _locate_ipinfo):
        try:
            results.append(fn())
        except Exception:
            continue
    if ip:
        try:
            results.append(_locate_baidu(ip))
        except Exception:
            pass
    try:
        results.append(_locate_ipapi())
    except Exception:
        pass

    if not results:
        return "自动定位失败：所有定位源均不可用，请直接提供城市名。"

    # 投票：以（归一化国家, 归一化省份）为一票（国家/省名先归一，避免同结论被拆票）
    votes = {}
    for r in results:
        key = (_norm_country(r.get("country", "")), _norm_province(r.get("province", "")))
        votes.setdefault(key, []).append(r)
    top_key, top_group = max(votes.items(), key=lambda kv: len(kv[1]))
    agree = len(top_group)
    conflicts = [r for r in results if r not in top_group]

    # 坐标/ISP/时区取投票组内第一个有值的
    lat = lon = None
    isp = ""
    tz = ""
    city = ""
    for r in top_group:
        if lat is None and r.get("latitude") is not None:
            lat, lon = r.get("latitude"), r.get("longitude")
        isp = isp or r.get("isp", "")
        tz = tz or r.get("timezone", "")
        city = city or r.get("city", "")

    lines = [f"出口公网 IP：{ip or '未知'}"]
    if agree == len(results):
        lines.append(f"交叉定位结果（{agree}/{len(results)} 源完全一致）："
                     f"{top_key[0]} {top_key[1]} {city}")
    elif agree >= 2 and not conflicts:
        lines.append(f"交叉定位结果（{agree}/{len(results)} 源一致）：{top_key[0]} {top_key[1]} {city}")
    elif agree >= 2 and conflicts:
        lines.append(f"交叉定位结果（多数票 {agree}/{len(results)}）：{top_key[0]} {top_key[1]} {city}")
        lines.append("⚠️ 存在分歧源：" + "；".join(
            f"{r['source']}→{r.get('country','')}{_norm_province(r.get('province',''))}{r.get('city','')}"
            for r in conflicts) + "（该源可能省级偏移，已按多数票取值）")
    else:
        lines.append(f"⚠️ 各源结果不一致，仅单源可用：{results[0]['source']}→"
                     f"{results[0].get('country','')}{_norm_province(results[0].get('province',''))}"
                     f"{results[0].get('city','')}。建议直接告知城市名以确保准确。")

    if lat is not None and lon is not None:
        lines.append(f"坐标（可直接传给 get_weather）：{lat}, {lon}")
    if tz:
        lines.append(f"时区：{tz}")
        lines.append(f"该地当前时间：{_now_in_tz(tz)}")
    if isp:
        lines.append(f"ISP：{isp}")
    lines.append("各源明细：" + "；".join(
        f"{r['source']}={r.get('country','')}{_norm_province(r.get('province',''))}{r.get('city','')}"
        for r in results))
    lines.append("提示：IP 定位为城市级精度；若显示位置与你不符（常见于代理/VPN 或多出口线路），"
                 "请直接说出你的城市，以你为准。")
    return "\n".join(lines)


def get_current_time() -> str:
    """获取当前的日期和时间"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate(expression: str) -> str:
    """计算数学表达式，如 'sqrt(16)+2*3'"""
    allowed = {k: v for k, v in vars(math).items() if not k.startswith("_")}
    try:
        return str(eval(expression, {"__builtins__": {}}, allowed))
    except Exception as e:
        return f"计算错误：{e}"


# =====================================================================
# 注册表：函数名 -> 实现
# =====================================================================

FUNCTIONS = {
    "web_search": web_search,
    "read_webpage": read_webpage,
    "microelectronics_outlook": microelectronics_outlook,
    "civil_engineering_evidence": civil_engineering_evidence,
    "detect_location": detect_location,
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "calculate": calculate,
}

# =====================================================================
# JSON Schema 描述（OpenAI function calling 格式）
# =====================================================================

def _fn(name, description, properties=None, required=None):
    spec = {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}}}}
    if required:
        spec["function"]["parameters"]["required"] = required
    return spec


TOOLS = [
    _fn("web_search",
        "在互联网上搜索关键词并返回结果标题/链接/摘要（客观转述，适合查行业资讯、公司动态、"
        "技术资料等实时信息；中文关键词效果最佳）",
        {"query": {"type": "string", "description": "搜索关键词，支持中英文"},
         "max_results": {"type": "integer", "description": "返回条数，默认 5"}},
        ["query"]),
    _fn("read_webpage",
        "抓取并读取指定网页的正文文本，用于深入了解某篇文章/新闻内容",
        {"url": {"type": "string", "description": "网页完整地址（http/https）"},
         "max_chars": {"type": "integer", "description": "最多读取字符数，默认 4000"}},
        ["url"]),
    _fn("microelectronics_outlook",
        "自动上网检索微电子/半导体行业的最新发展方向与前景（中文搜索 + 国际行业媒体 RSS 双路），"
        "客观汇总并标注来源",
        {"extra_keyword": {"type": "string",
                           "description": "可选附加主题词，如：先进封装、汽车芯片、第三代半导体、AI 芯片"}}),
    _fn("civil_engineering_evidence",
        "检索土木工程专业的真实客观论据素材（就业前景/薪资/国家基建投资/考公岗位等），逐条标注来源，"
        "供回答中引用以支撑观点",
        {"extra_keyword": {"type": "string",
                           "description": "可选附加主题词，如：转专业、就业率、薪资、智能建造、考公"}}),
    _fn("detect_location",
        "多源交叉定位本机出口 IP 所在省市（ipwho.is/ipinfo.io/百度IP库/ip-api 投票，免 key），"
        "返回出口 IP、一致的省市名、坐标、ISP 与该地当前时间，并给出源分歧提示。"
        "用户询问天气/时间但未指明城市时使用；返回的坐标比城市名更精确，优先把坐标传给 get_weather",
        {}, []),
    _fn("get_weather",
        "查询天气（真实数据源）。可传城市名，也可传经纬度（更精确，推荐把 detect_location "
        "返回的坐标原样传入）；days 控制预报天数（含今天，1~7）：问今天用 1，问明天用 2，"
        "问未来几天用 3~7。返回当前实况与逐日预报（天气、温度区间、降水概率）",
        {"city": {"type": "string", "description": "城市名称，例如：北京、上海、Xi'an；仅按坐标查询时可省略"},
         "latitude": {"type": "number", "description": "纬度，如 34.2583（与 longitude 成对提供）"},
         "longitude": {"type": "number", "description": "经度，如 108.9286（与 latitude 成对提供）"},
         "days": {"type": "integer", "description": "预报天数，含今天，1~7；默认 1"}},
        []),
    _fn("get_current_time", "获取当前的日期和时间"),
    _fn("calculate",
        "计算数学表达式，支持 + - * / ** 与 math 库函数",
        {"expression": {"type": "string", "description": "数学表达式，如 sqrt(16)+2*3"}},
        ["expression"]),
]
