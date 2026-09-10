// 浏览器版工具集：只用支持 CORS 的公开接口，无需任何 key。
// 与 tools.py 相比少了「360/搜狗抓取、行业 RSS、土木论据库」（浏览器跨域拿不到），
// 这些能力保留在 Python 版（本地运行时可用）。

const UA = { "Accept": "application/json" };

async function getJSON(url, timeoutMs = 12000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { headers: UA, signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------- 定位

const PROVINCE_CN = {
  beijing: "北京", tianjin: "天津", hebei: "河北", shanxi: "山西", "inner mongolia": "内蒙古",
  liaoning: "辽宁", jilin: "吉林", heilongjiang: "黑龙江", shanghai: "上海", jiangsu: "江苏",
  zhejiang: "浙江", anhui: "安徽", fujian: "福建", jiangxi: "江西", shandong: "山东",
  henan: "河南", hubei: "湖北", hunan: "湖南", guangdong: "广东", guangxi: "广西",
  hainan: "海南", chongqing: "重庆", sichuan: "四川", guizhou: "贵州", yunnan: "云南",
  tibet: "西藏", xizang: "西藏", shaanxi: "陕西", gansu: "甘肃", qinghai: "青海",
  ningxia: "宁夏", xinjiang: "新疆", "hong kong": "香港", macau: "澳门", taiwan: "台湾",
};

const COUNTRY_CN = {
  cn: "中国", china: "中国", 中国: "中国", us: "美国", usa: "美国", "united states": "美国",
  美国: "美国", jp: "日本", japan: "日本", gb: "英国", uk: "英国",
};

function normProvince(raw = "") {
  const key = String(raw).trim().toLowerCase();
  if (PROVINCE_CN[key]) return PROVINCE_CN[key];
  const text = String(raw).replace(/(省|市|自治区|特别行政区)$/, "");
  for (const zh of Object.values(PROVINCE_CN)) if (zh && text.includes(zh)) return zh;
  return text;
}

function normCountry(raw = "") {
  const key = String(raw).trim().toLowerCase();
  return COUNTRY_CN[key] || String(raw).trim();
}

async function locateIpwho() {
  const d = await getJSON("https://ipwho.is/");
  if (!d.success) throw new Error("ipwho.is 返回失败");
  const conn = d.connection || {};
  return {
    source: "ipwho.is", city: d.city || "", province: d.region || "", country: d.country || "",
    lat: d.latitude, lon: d.longitude, tz: (d.timezone || {}).id || "",
    isp: conn.org || conn.isp || "",
  };
}

async function locateIpinfo() {
  const d = await getJSON("https://ipinfo.io/json");
  let lat = null, lon = null;
  if (typeof d.loc === "string" && d.loc.includes(",")) {
    const [a, b] = d.loc.split(",").map(Number);
    if (!Number.isNaN(a) && !Number.isNaN(b)) { lat = a; lon = b; }
  }
  return {
    source: "ipinfo.io", city: d.city || "", province: d.region || "", country: d.country || "",
    lat, lon, tz: d.timezone || "", isp: d.org || "",
  };
}

function localTime(tz) {
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: tz, dateStyle: "full", timeStyle: "medium",
    }).format(new Date()) + `（${tz}）`;
  } catch {
    return new Date().toLocaleString("zh-CN") + "（本机时间）";
  }
}

async function detect_location() {
  const results = [];
  for (const fn of [locateIpwho, locateIpinfo]) {
    try { results.push(await fn()); } catch { /* 忽略单个源失败 */ }
  }
  if (!results.length) return "自动定位失败：定位服务不可用，请直接提供城市名。";

  const votes = new Map();
  for (const r of results) {
    const key = `${normCountry(r.country)}|${normProvince(r.province)}`;
    if (!votes.has(key)) votes.set(key, []);
    votes.get(key).push(r);
  }
  const [topKey, topGroup] = [...votes.entries()].sort((a, b) => b[1].length - a[1].length)[0];
  const conflicts = results.filter((r) => !topGroup.includes(r));
  const pick = topGroup[0];
  const lines = [`交叉定位结果（${topGroup.length}/${results.length} 源一致）：${topKey.replace("|", " ")} ${pick.city}`];
  if (conflicts.length) {
    lines.push("⚠️ 存在分歧源：" + conflicts.map((r) =>
      `${r.source}→${r.country}${normProvince(r.province)}${r.city}`).join("；"));
  }
  if (pick.lat != null && pick.lon != null) lines.push(`坐标（可直接传给 get_weather）：${pick.lat}, ${pick.lon}`);
  if (pick.tz) {
    lines.push(`时区：${pick.tz}`);
    lines.push(`该地当前时间：${localTime(pick.tz)}`);
  }
  if (pick.isp) lines.push(`ISP：${pick.isp}`);
  lines.push("提示：这是浏览器出口 IP 的城市级定位；若与你不符，直接说出城市名。");
  return lines.join("\n");
}

// ---------------------------------------------------------------- 天气

const WMO_CN = {
  0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴", 45: "雾", 48: "雾凇",
  51: "毛毛雨(小)", 53: "毛毛雨", 55: "毛毛雨(大)", 56: "冻毛毛雨(小)", 57: "冻毛毛雨(大)",
  61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨(小)", 67: "冻雨(大)",
  71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒", 80: "阵雨(小)", 81: "阵雨", 82: "阵雨(强)",
  85: "阵雪(小)", 86: "阵雪(大)", 95: "雷阵雨", 96: "雷阵雨伴冰雹(小)", 99: "雷阵雨伴冰雹(大)",
};

async function get_weather({ city = "", latitude = null, longitude = null, days = 1 } = {}) {
  let lat = latitude, lon = longitude, label = city;
  if (lat == null || lon == null) {
    if (!String(city).trim()) return "请提供城市名，或先用 detect_location 取得坐标。";
    const geo = await getJSON(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=zh&format=json`);
    const hit = (geo.results || [])[0];
    if (!hit) return `Open-Meteo 未找到城市「${city}」，请检查名称。`;
    lat = hit.latitude; lon = hit.longitude;
    label = [hit.name, hit.admin1].filter(Boolean).join("、") + `，${hit.country || ""}`;
  }
  const n = Math.max(1, Math.min(Number(days) || 1, 7));
  const url = "https://api.open-meteo.com/v1/forecast"
    + `?latitude=${lat}&longitude=${lon}`
    + "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,"
    + "wind_speed_10m,wind_direction_10m,precipitation,cloud_cover"
    + "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum"
    + `&forecast_days=${n}&timezone=auto`;
  const fc = await getJSON(url);
  const c = fc.current, d = fc.daily;
  const week = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const lines = [
    `位置：${label || "定位点"}（${lat}, ${lon}）`,
    "【当前实况】",
    `天气：${WMO_CN[c.weather_code] || "天气码" + c.weather_code}`,
    `当前温度：${c.temperature_2m}°C（体感 ${c.apparent_temperature}°C）`,
    `今日范围：最高 ${d.temperature_2m_max[0]}°C / 最低 ${d.temperature_2m_min[0]}°C`,
    `湿度：${c.relative_humidity_2m}%`,
    `风速风向：${c.wind_speed_10m} km/h，${c.wind_direction_10m}°`,
    `云量：${c.cloud_cover}%   降水：${c.precipitation} mm`,
    `观测时间：${c.time}（时区 ${fc.timezone}）`,
    "【逐日预报】",
  ];
  d.time.forEach((date, i) => {
    const wd = week[new Date(date + "T00:00:00").getDay()] || "";
    const tag = i === 0 ? "今天" : i === 1 ? "明天" : "";
    lines.push(`${date}（${wd}）${tag}：${WMO_CN[d.weather_code[i]] || "天气码" + d.weather_code[i]}，`
      + `${d.temperature_2m_min[i]}~${d.temperature_2m_max[i]}°C，降水概率 ${d.precipitation_probability_max[i]}%`);
  });
  return lines.join("\n");
}

// ---------------------------------------------------------------- 时间 / 计算

function get_current_time() {
  const now = new Date();
  return now.toLocaleString("zh-CN", { hour12: false }) + `（浏览器本地时间，时区 ${Intl.DateTimeFormat().resolvedOptions().timeZone}）`;
}

function calculate({ expression = "" } = {}) {
  // 白名单替换：把常见数学函数映射到 Math，禁止任意 JS 执行
  const map = {
    sqrt: "Math.sqrt", abs: "Math.abs", sin: "Math.sin", cos: "Math.cos", tan: "Math.tan",
    log: "Math.log", log10: "Math.log10", exp: "Math.exp", floor: "Math.floor",
    ceil: "Math.ceil", round: "Math.round", pow: "Math.pow", min: "Math.min", max: "Math.max",
    pi: "Math.PI", e: "Math.E",
  };
  let expr = String(expression);
  for (const [k, v] of Object.entries(map)) expr = expr.replace(new RegExp(`\\b${k}\\b`, "g"), v);
  if (!/^[0-9+\-*/%().,\sMathsqrtabspowlogexpiouflcrndmE]*$/.test(expr)) {
    return "计算错误：表达式里含不允许的字符（只支持数字与常见数学函数）。";
  }
  try {
    const value = Function(`"use strict"; return (${expr});`)();
    return Number.isFinite(value) ? String(value) : "计算错误：结果不是有限数。";
  } catch (e) {
    return `计算错误：${e.message}`;
  }
}

// ---------------------------------------------------------------- 资讯搜索（CORS 可用）

async function search_tech({ query = "", max_results = 6 } = {}) {
  const q = String(query).trim();
  if (!q) return "请提供搜索关键词。";
  const n = Math.max(1, Math.min(Number(max_results) || 6, 15));
  const d = await getJSON(`https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(q)}&tags=story&hitsPerPage=${n}`);
  const hits = (d.hits || []).filter((h) => h.title);
  if (!hits.length) return `未检索到与「${q}」相关的资讯，可换关键词重试。`;
  const lines = [`搜索词：${q}（来源：Hacker News Algolia，客观转述、未作解读）`, ""];
  hits.forEach((h, i) => {
    const date = (h.created_at || "").slice(0, 10);
    const url = h.url || `https://news.ycombinator.com/item?id=${h.objectID}`;
    lines.push(`${i + 1}. ${h.title}（${date}）`);
    lines.push(`   链接：${url}`);
    if (h.story_text) lines.push(`   摘要：${String(h.story_text).replace(/<[^>]+>/g, " ").slice(0, 160)}`);
  });
  lines.push("");
  lines.push("注意：这是英文科技社区的资讯源，不含中文行业报告；中文检索能力保留在 Python 版本里。");
  return lines.join("\n");
}

// ---------------------------------------------------------------- 工具注册表

function schema(name, description, properties = {}, required = []) {
  const params = { type: "object", properties };
  if (required.length) params.required = required;
  return { type: "function", function: { name, description, parameters: params } };
}

export const TOOLS = [
  schema("detect_location",
    "交叉定位访客出口 IP 所在省市（ipwho.is + ipinfo.io），返回一致性、坐标、ISP 与该地当前时间。用户问天气却没给城市时先调用它。",
    {}, []),
  schema("get_weather",
    "查询真实天气（Open-Meteo）。可按城市名或坐标查询；days 控制预报天数（含今天，1~7）：问明天传 2，问未来几天传 3~7。",
    {
      city: { type: "string", description: "城市名，如：北京、Xi'an；按坐标查询时可省略" },
      latitude: { type: "number", description: "纬度，与 longitude 成对提供" },
      longitude: { type: "number", description: "经度，与 latitude 成对提供" },
      days: { type: "integer", description: "预报天数（含今天），1~7，默认 1" },
    }, []),
  schema("search_tech",
    "检索英文科技社区最新资讯（Hacker News），返回标题、日期、链接。适合查芯片/半导体/AI 等方向的动态。",
    {
      query: { type: "string", description: "搜索关键词，英文效果最好，如 semiconductor market" },
      max_results: { type: "integer", description: "返回条数，默认 6" },
    }, ["query"]),
  schema("get_current_time", "获取浏览器当前时间与时区", {}, []),
  schema("calculate",
    "计算数学表达式，支持 + - * / % ** 与 sqrt/log/sin 等常见函数",
    { expression: { type: "string", description: "表达式，如 sqrt(81)+15*2" } }, ["expression"]),
];

export const FUNCTIONS = {
  detect_location, get_weather, search_tech, get_current_time, calculate,
};

// 给模型的「可用工具说明」，避免它去调用只存在于 Python 版的工具
export const TOOL_AVAILABILITY_NOTE = [
  "【本版可用能力说明】浏览器版只提供：detect_location（IP 定位）、get_weather（真实天气，含 1~7 天预报）、",
  "search_tech（英文科技社区资讯，英文关键词更准）、get_current_time、calculate。",
  "microelectronics_outlook、civil_engineering_evidence、web_search(中文抓取)、read_webpage 只在 Python 版可用；",
  "本版没有这些工具时，不要假装调用，也不要编造数据——如实说明并改用 search_tech 或让用户参考公开报告。",
].join("");
