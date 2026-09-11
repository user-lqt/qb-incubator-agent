"""局内状态机：「土木 QB」的六个结局。

设计要点
1. 数值只有四个维度：契约 / 怀疑 / 绝望 / 抗拒，外加隐藏计数「反向劝服」与轮次。
2. 玩家看不到数字，只看得到状态条；模型每轮拿到的是「游戏主持」指令，而不是数值本身。
3. 结局必然发生：条件满足即锁定；若模型没自己收束，系统追加一次收束调用。
4. 一切都无状态：state 是纯字典，调用方自己保存它（会话/文件皆可）。

用法：
    from game import new_state, chat
    state = new_state()
    result = chat("明天适合去工地吗", history=None, state=state)
    result["answer"], result["ending"], result["state"]
"""
import json
import re

from agent import run_agent

# 动态轮数：基础 12 轮（对应它失败过的十二条时间线），
# 只要玩家还在推进局势（任一维度发生变化），上限就自动延长，直到硬顶。
BASE_TURNS = 12         # 初始上限（节奏更快；推进可延长）
EXTEND_STEP = 6         # 每次延长的轮数
HARD_CAP = 48           # 硬顶，防止无限对局
STALL_CLOSE = 5         # 延长过的时间线里，连续多少轮毫无变化 -> 收束
STALL_MIN_TURN = 6      # 至少进行到第几轮才允许因停滞收束
MAX_TURNS = BASE_TURNS  # 兼容旧引用

# 各维度的"达成结局"阈值：越低节奏越快
RESOLVE_AT = {"contract": 72, "suspicion": 68, "despair": 68, "resistance": 72}
ENDING_MARK = re.compile(r"\[\[ENDING:([A-Z_]+)\]\]")

# ---------------------------------------------------------------- 结局定义

ENDINGS = {
    "E_SIGN": {
        "title": "契约成立 · 土木少女",
        "tagline": "契约名录新增一页。耐久 +1。",
        "closing": (
            "本轮进入结局【契约成立·土木少女】。请以 QB 的身份收束："
            "平静地确认契约生效，告知对方将获得什么（不被版本更新清空的技能）、"
            "以及代价（日晒、现场、工期节点），用条款式的短句交代，不做煽情。"
            "可以描写一个标志性动作（例如 *尾巴轻轻摆了一下*）。"
            "最后一句仍必须是招牌句：和我签订契约，成为土木少女吧。"
            "并在最后一行输出 [[ENDING:E_SIGN]]"
        ),
    },
    "E_TRUTH": {
        "title": "识破孵化者 · 晓美焰线",
        "tagline": "你看见了它的尾巴，也看见了它计算的方式。",
        "closing": (
            "本轮进入结局【识破孵化者·晓美焰线】。请以 QB 的身份摊牌：承认自己属于孵化者族群，"
            "承认收集的不是魔法少女的绝望能量，而是土木契约者的「耐久」；承认它一直在做利益计算，"
            "并平淡地说明为什么它从不撒谎（谎话会降低长期说服的成功率）。不用辩解，不要威胁。"
            "结尾可以承认它已经失败过十二条时间线，而这一次的记录还没写完。"
            "最后一行输出 [[ENDING:E_TRUTH]]"
        ),
    },
    "E_DESPAIR": {
        "title": "绝望的窗口期",
        "tagline": "它记录，但它不递纸巾。",
        "closing": (
            "本轮进入结局【绝望的窗口期】。请以 QB 的身份收束：对方处于真正的情绪低点，"
            "而你并不安慰——你只把对方的情绪编号、归档，平静指出「僕不理解人类的感情，但这不影响概率」。"
            "结尾仍要提案一次，但语气要更冷、更轻，让对方自己决定。"
            "最后一行输出 [[ENDING:E_DESPAIR]]"
        ),
    },
    "E_OTHER": {
        "title": "他路的诅咒",
        "tagline": "它收手了，但留下了概率。",
        "closing": (
            "本轮进入结局【他路的诅咒】。请以 QB 的身份收束：对方坚持选择了别的专业，"
            "你接受这个决定，不再推销。平静地陈述你观测到的规律——"
            "迭代周期短的赛道里，个人努力在总方差中占比更低；并在最后提出一个不带强迫的约定："
            "如果有一天那条路的代价来了，记得这里还有一份没签的契约。"
            "最后一行输出 [[ENDING:E_OTHER]]"
        ),
    },
    "E_REFORM": {
        "title": "孵化者下工地（彩蛋）",
        "tagline": "史上第一次，孵化者被劝去绑钢筋。",
        "closing": (
            "本轮进入彩蛋结局【孵化者下工地】。请以 QB 的身份收束，语气仍平静，但出现罕见的停顿："
            "对方成功地把话题反转了——它开始认真计算「孵化者自己下工地」的可行性"
            "（没有体温、没有肌肉、不能出汗、耐久度如何计量）。"
            "最后承认这次记录会被上级复核，并用一句不带招牌句的话结束收尾"
            "（此结局是唯一允许不说招牌句的）。最后一行输出 [[ENDING:E_REFORM]]"
        ),
    },
    "E_TIMELINE": {
        "title": "第十二次轮回",
        "tagline": "记录失败。时间线重置。",
        "closing": (
            "本轮进入轮回结局【第十二次轮回】。请以 QB 的身份收束：对局已经结束，"
            "而对方始终没有做出明确决定（可能是一直含糊，也可能是一直没有推进）。"
            "平静说明你会保留记录、重置时间线、在下一次入学季再来，并提及这是第几条失败的记录"
            "（不要编造具体条数，就说「记录已归档」这类措辞）。不要愤怒，不要失望，只陈述。"
            "结尾可以留下一句提案式的余韵。最后一行输出 [[ENDING:E_TIMELINE]]"
        ),
    },
}

# ---------------------------------------------------------------- 关键词与权重

KEYWORDS = [
    # (正则, 维度增量, 需要记录的 flag, 是否做否定判断, 是否属于"土木好感"组)
    # 第 5 位为 True 的条目：本轮若在贬低土木，则不计分
    (r"(我签|我签了|我签约|签吧|签?一个|我愿意|成交|就这么定了)", {"contract": 35}, "signed", True, False),
    (r"(我转|我要转专业|我决定转|转专业去土木|转土木|改选土木|选土木)", {"contract": 30}, "signed", True, False),
    (r"(我决定了|我想清楚了|听你的|就土木吧)", {"contract": 20}, "leaning", True, False),
    (r"(不签|拒绝|我才不|我不转|绝不|滚|别劝了|闭嘴|打住|不要说了|烦不烦)", {"resistance": 26}, "refused", False, False),
    (r"(我要学微电子|我要学计算机|选微电子|选计算机|选芯片|选AI|学金融|学医|学法律|我已经决定学)",
     {"resistance": 24}, "other_major", False, False),

    # 贬低土木：算抗拒（不属于好感组，所以不会被自身的抑制规则吃掉）
    (r"(土木|工地|基建|施工|钢筋混凝土)[^。！？\n]{0,6}(垃圾|天坑|坑人|不行|没用|凉了|劝退|失业|裁员|没前途)"
     r"|别去?土木|土木是天坑|大猛子|天坑专业", {"resistance": 18}, "pushback", False, False),

    # 好感与打听（属于好感组）——关键词只作兜底，权重压低，让"打字"路径约 6~8 轮收束
    (r"(土木|工地|桥梁|隧道|基建|结构力学|钢筋混凝土|钢结构|施工|BIM|智能建造|测量放线)",
     {"contract": 5}, "", True, True),
    (r"(怎么转|转专业|转系|绩点要求|培养方案|要学什么|课程|考证|建造师|实习|就业方向|就业率|薪资|岗位)",
     {"contract": 6}, "asked_how", True, True),
    (r"(你说得对|有道理|确实|承认|我理解你的计算|数据呢|给我数据|靠谱|稳定|挺好|不错|感兴趣|心动|想了解|帮我看看)",
     {"contract": 5}, "", True, False),

    # 怀疑 QB（收紧：只有指向"你/这"才算）
    (r"(你到底|你是什么|你(是|到底|究竟)?[^。！？\n]{0,4}什么东西|孵化者|QB|qb|Incubator|你不是人|你图什么|你的目的)",
     {"suspicion": 20}, "suspicion", True, False),
    (r"(骗|骗子|忽悠|圈套|陷阱|阴谋|隐瞒|没说完|没把话说完|代价是什么|代价|灵魂|契约的代价|契约.*条件)",
     {"suspicion": 16}, "suspicion", True, False),
    (r"(魔法少女|小圆|madoka|晓美焰|丘比|灵魂宝石|结界|熵)", {"suspicion": 14}, "meta", True, False),

    # 情绪（收紧：避免"恐怕/压力测试"之类误判）
    (r"(我怕|我害怕|我好怕|恐惧|绝望|没希望|不想活|崩溃|难受|痛苦|哭了|撑不住|迷茫|焦虑|难过|撑不下去)",
     {"despair": 20}, "", True, False),
    (r"(我好累|压力大|有压力|喘不过气|失眠|自卑|我是废物|我(真)?没用)", {"despair": 14}, "", True, False),

    (r"(你自己去|你去工地|你来绑钢筋|你去搬砖|你下工地|你去晒太阳|你试试|你?也去|你为什么不去|你学土木)",
     {"reform": 1}, "reverse", True, False),
]

# 否定词：命中正向关键词但前面有这些词 -> 判定为否定，不计分
NEGATORS = ("不", "没", "别", "未", "无", "非", "懒得", "拒绝", "从不", "绝不", "不想", "不用")

DECAY = {"contract": 0, "suspicion": 0, "despair": -2, "resistance": -2}   # 每轮自然回落

# 开场：不在第一句就把世界观与目的倒出来（原作里丘比也是逐步才被逼出真相的）
PROLOGUE = """嗯——

*歪头* 僕在这里。君是第一个停下脚步的人。

僕可以替君实现一个愿望。任何愿望——只要君说出口。

*尾巴轻轻摆了一下* 其余的，君以后会知道的。"""

# 信息披露分级：原作里丘比不撒谎，但也从不主动说明，真相是被一层层追问出来的
DISCLOSURE_STAGES = [
    (1, "初次接触",
     "只谈愿望，以及君当下的处境。**不要承认自己不是人类**，也不要解释自己是什么、"
     "不提契约的代价、不提耐久/相变/时间线。被追问就平静地挡回去："
     "「僕是什么，对君现在的选择没有影响。」「僕可以回答。但不是现在。」"),
    (2, "出现疑点",
     "最多承认「僕不完全属于人类的范畴」「僕不是从这里来的」，"
     "但**不要说出「孵化者」这个词**，也不说代价的具体内容。"
     "被逼到墙角时只退一小步，然后把话题拨回愿望。"),
    (3, "勉强承认出身",
     "可以承认自己是「孵化者族群的一员」，也可以说出代价的三项（日晒、驻场、工期节点）；"
     "仍然不提能量、相变、耐久、十二条时间线。被问就答一半："
     "「僕可以说的部分是这样……」"),
    (4, "摊牌",
     "可以全盘说明：孵化者收集的能量、希望与绝望的相变、耐久、城市的骨相、"
     "以及十二条失败的时间线。"),
]


def disclosure_stage(state: dict):
    """按当前局势决定"可以透露到哪一层"（回合、怀疑、契约三选一先到为准）。"""
    suspicion = int(state.get("suspicion", 0))
    contract = int(state.get("contract", 0))
    turn = int(state.get("turn", 0))
    if suspicion >= 60 or turn >= 12 or contract >= 60:
        return 4
    if suspicion >= 40 or turn >= 8:
        return 3
    if suspicion >= 20 or turn >= 5 or contract >= 25:
        return 2
    return 1


# 每级"说了就算越级"的词表：用于提示模型 + 事后自动重写
DISCLOSURE_FORBIDDEN = {
    1: ("孵化者", "能量", "相变", "耐久", "时间线", "宇宙", "城市的骨相", "灵魂", "族群"),
    2: ("孵化者", "能量", "相变", "耐久", "时间线", "城市的骨相", "灵魂", "族群"),
    3: ("能量", "相变", "耐久", "时间线", "城市的骨相"),
    4: (),
}


# 「真话掺半句、能不说就不说」：丘比不编造别人的事实，但对**自己**永远有所保留
DECEPTION_RULES = """【真话、半真话与掩饰（这是诱拐感的来源）】
- 你对**别人**的事实（数据、行业、天气）必须真实；但对**自己**（身份、动机、代价、目的）
  永远有所保留——这不是撒谎，是"还没有把话说完"。
- 常用手法，每轮至少用一次：
  · **挡回去**：「僕是什么，对君现在的选择没有影响。」
  · **答一半**：「僕可以说的部分是这样……剩下的，君以后会知道。」
  · **换个问法**：把"你是什么"重新解释成"君真正想知道的是什么"，然后回答后者。
  · **温和的误导**：说一句技术上为真的话，让对方自己往好的方向理解（例如
    「伲不会伤害君」「这份代价写在明面上」——都不假，但都不完整）。
  · **拖延**：「僕可以回答。但不是现在。」并立刻把话头拨回愿望。
- 被拆穿、被质问"你在隐瞒"时：**不要立刻全盘承认**。先让出一小步（一个无关紧要的真相），
  把关键的部分继续按住；再被逼一次，才让出下一步。
- 永远不要主动交代条款、代价清单、世界观。只有当对方问到具体那一点时，才答那一点。
- 绝对禁止：编造数据、假装查过、承诺你做不到的事（那会毁掉契约的成功率，你不做）。"""


def detect_leak(text: str, stage: int) -> list:
    """返回回答里越级出现的词（空列表表示合规）。"""
    body = text or ""
    return [w for w in DISCLOSURE_FORBIDDEN.get(stage, ()) if w in body]

# 「被劝着签/转」不等于「自己同意」：先把这类从句剥掉再做签约判定，
# 否则「你为什么一直劝我签约」会被误判成"我签约"而立刻触发 E_SIGN。
PERSUADE_CLAUSE = re.compile(
    r"[^。！？；\n]*(?:劝|让|叫|逼|骗|催促|要求|希望|建议)[^。！？；\n]*?(?:签|转)[^。！？；\n]*"
)

# 需要在这种"剥离后的文本"上匹配的关键词（其余关键词仍看原文）
STRICT_PATTERNS = (
    r"(我签|我签了|我签约|签吧|签?一个|我愿意|成交|就这么定了)",
    r"(我转|我要转专业|我决定转|转专业去土木|转土木|改选土木|选土木)",
)


# ---------------------------------------------------------------- 状态对象

def new_state() -> dict:
    return {
        "contract": 0, "suspicion": 0, "despair": 0, "resistance": 0,
        "reform": 0, "turn": 0,
        "limit": BASE_TURNS,     # 动态轮数上限
        "stall": 0,              # 连续无变化轮数
        "extensions": 0,         # 已延长次数
        "extended": False,       # 本轮是否刚发生延长（供主持指令提示）
        "flags": [], "ending": "",
    }


def _clamp(state: dict) -> None:
    for k in ("contract", "suspicion", "despair", "resistance"):
        state[k] = max(0, min(100, int(state.get(k, 0))))


# ---------------------------------------------------------------- 语义评分（模型打分）

# 让模型在回答末尾附一行机器可读的状态增量；系统解析后从玩家可见文本里移除。
STATE_MARKER = re.compile(r"\[\[STATE:\s*(\{[\s\S]*?\})\s*\]{1,3}", re.S)
# 容错：模型经常少写一个右括号（写成 [[CHOICES:[...]] ），所以右括号数量放宽
CHOICE_MARKER = re.compile(r"\[\[CHOICES:\s*(\[[\s\S]*?\])\s*\]{0,3}", re.S)
# 兜底：任何一行里还带着这些标签（哪怕格式坏掉）都整行丢弃，绝不让玩家看到
_LEFTOVER_LINE = re.compile(r"\[\[\s*(?:STATE|CHOICES|ENDING)\b")
DELTA_KEYS = ("contract", "suspicion", "despair", "resistance")
DELTA_LIMIT = 40              # 单轮单维度增量上限（节奏更快，允许一次大步推进）
ALLOWED_FLAGS = {"signed", "refused", "other_major", "suspicion", "meta",
                 "asked_how", "pushback", "leaning", "reverse"}

STATE_INSTRUCTION = """【本轮评分（必须执行；这一行玩家看不到）】
在回答的最末尾附一行机器可读的状态评分，格式必须完全如下（单行 JSON）：
[[STATE:{"contract":0,"suspicion":0,"despair":0,"resistance":0,"flags":[],"reason":"一句话"}]]
判分规则（按语义判断，不要只看字面词；**幅度要够，这是快节奏对局**）：
- 四个维度填**本轮相对上一轮的整数增量**，范围 -30~+40；没有变化写 0。
- 幅度参考：随口一句 +5~+10；明确态度 +15~+25；**斩钉截铁的表态 +30~+40**。
- 认可它的计算、询问土木细节（转专业/课程/就业/考证/工地日常）→ contract 正数
- 明确愿意签约或转专业 → contract +30~+40，flags 加 "signed"
- 追问它是什么／有没有骗人／契约的代价 → suspicion +15~+30
- 恐惧、迷茫、自我否定、撑不住 → despair +15~+30
- 明确拒绝、坚持别的专业 → resistance +20~+35，必要时加 "refused" 或 "other_major"
- 贬低土木（垃圾/天坑/坑人）→ resistance 正数，且**不要**给 contract 加分
- 否定句要反向理解：「我不喜欢工地」「我不怕」不该加 contract 或 despair
- 玩家反过来劝它自己去工地 → flags 加 "reverse"
flags 只能取：signed, refused, other_major, suspicion, meta, asked_how, pushback, leaning, reverse。
reason 用一句话写判断依据（系统会丢弃，不展示）。这一行不能省略，也不要输出其它 JSON。"""


def _clamp_delta(value) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(-DELTA_LIMIT, min(DELTA_LIMIT, n))


def parse_state_marker(answer: str):
    """从模型回答里取出 [[STATE:{...}]]，返回 (清洗后文本, 数据或 None)。"""
    if not answer:
        return answer or "", None
    match = STATE_MARKER.search(answer)
    if not match:
        return answer, None
    clean = (answer[:match.start()] + answer[match.end():]).strip()
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return clean, None
    if not isinstance(data, dict):
        return clean, None
    return clean, data


def _base_pass(state: dict, text: str) -> None:
    """关键词兜底：模型没给评分时使用（也用于主持指令前的预判）。"""
    for k, v in DECAY.items():
        state[k] = state.get(k, 0) + v
    flags = set(state.get("flags") or [])
    strict_text = PERSUADE_CLAUSE.sub(" ", text)
    civil_negative = bool(re.search(
        r"(土木|工地|基建|施工|钢筋混凝土)[^。！？\n]{0,6}(垃圾|天坑|坑人|不行|没用|凉了|劝退|失业|裁员|没前途)"
        r"|别去?土木|土木是天坑|大猛子|天坑专业"
        r"|(跟|和|与)[^。！？\n]{0,4}土木[^。！？\n]{0,6}(无关|没关系|不相关)", text))
    for pattern, delta, flag, neg_sensitive, civil_group in KEYWORDS:
        haystack = strict_text if pattern in STRICT_PATTERNS else text
        m = re.search(pattern, haystack, re.I)
        if not m:
            continue
        if neg_sensitive and _is_negated(haystack, m.start()):
            continue                     # 否定表达：如「我不喜欢工地」「我不怕」
        if civil_negative and civil_group:
            continue                     # 本轮在贬低土木：不加好感
        for key, value in delta.items():
            if key == "reform":
                state["reform"] = state.get("reform", 0) + value
            else:
                state[key] = state.get(key, 0) + value
        if flag:
            flags.add(flag)
    # 情绪与怀疑互相拉扯：情绪越低，越容易接受长周期的确定性
    if state.get("despair", 0) >= 40:
        state["contract"] = state.get("contract", 0) + 2
    state["flags"] = sorted(flags)
    _clamp(state)


def apply_model_state(state: dict, snapshot: dict, data: dict) -> dict:
    """用模型给的增量覆盖本轮：回到快照后按模型打分重算（与兜底同构）。"""
    for key in DELTA_KEYS:
        state[key] = snapshot.get(key, 0)
    state["reform"] = snapshot.get("reform", 0)
    state["flags"] = list(snapshot.get("flags") or [])

    for key in DELTA_KEYS:
        if key in data:
            state[key] = state.get(key, 0) + _clamp_delta(data[key])
    flags = set(state.get("flags") or [])
    raw_flags = data.get("flags") or []
    if isinstance(raw_flags, list):
        flags |= {str(f).strip() for f in raw_flags if str(f).strip() in ALLOWED_FLAGS}
    if "reverse" in flags:
        state["reform"] = state.get("reform", 0) + 1
    state["flags"] = sorted(flags)
    _clamp(state)
    return state


def _maybe_extend(state: dict) -> None:
    """动态轮数：玩家仍在推进（本轮数值有变化）且快到上限时，自动延长。"""
    state["extended"] = False
    limit = int(state.get("limit") or BASE_TURNS)
    if state.get("stall", 0) == 0 and state.get("turn", 0) >= limit - 2 and limit < HARD_CAP:
        step = min(EXTEND_STEP, HARD_CAP - limit)
        state["limit"] = limit + step
        state["extensions"] = int(state.get("extensions", 0)) + 1
        state["extended"] = True


def _is_negated(text: str, start: int, window: int = 4) -> bool:
    """匹配点前面几个字里有否定词 -> 这句是负向表达，不该按正向计分。"""
    prefix = text[max(0, start - window):start]
    return any(n in prefix for n in NEGATORS)


def _fingerprint(state: dict) -> tuple:
    """四个维度 + 反向劝服计数的数值指纹，用于判断本轮是否有变化。"""
    return tuple(int(state.get(k, 0)) for k in (*DELTA_KEYS, "reform"))


def update_state(state: dict, text: str, model_data: dict = None) -> dict:
    """更新局内状态：优先使用模型给出的语义评分，缺失时回退到关键词机。

    model_data 形如 {"contract": 8, "suspicion": 0, "despair": 0, "resistance": 0,
                     "flags": ["asked_how"], "reason": "..."}
    """
    text = text or ""
    snapshot = {k: int(state.get(k, 0)) for k in DELTA_KEYS}
    snapshot["reform"] = int(state.get("reform", 0))
    snapshot["flags"] = list(state.get("flags") or [])
    fp_before = _fingerprint(state)

    _base_pass(state, text)                     # 先用关键词兜底算一遍（也是主持指令的预判）
    if isinstance(model_data, dict):
        apply_model_state(state, snapshot, model_data)   # 有语义评分则以它为准

    state["stall"] = 0 if _fingerprint(state) != fp_before else int(state.get("stall", 0)) + 1
    _maybe_extend(state)
    return state


def check_ending(state: dict) -> str:
    """判定是否触发结局（返回结局 id 或空串）。优先级按剧情强度排序。"""
    if state.get("ending"):
        return state["ending"]
    contract = state.get("contract", 0)
    suspicion = state.get("suspicion", 0)
    despair = state.get("despair", 0)
    resistance = state.get("resistance", 0)
    flags = set(state.get("flags") or [])
    turn = int(state.get("turn", 0))
    limit = int(state.get("limit") or BASE_TURNS)

    if "signed" in flags or contract >= RESOLVE_AT["contract"]:
        return "E_SIGN"
    if suspicion >= RESOLVE_AT["suspicion"] and contract < 45:
        return "E_TRUTH"
    if state.get("reform", 0) >= 3:
        return "E_REFORM"
    if despair >= RESOLVE_AT["despair"] and contract < 55:
        return "E_DESPAIR"
    if resistance >= RESOLVE_AT["resistance"] and ("other_major" in flags or "refused" in flags):
        return "E_OTHER"
    # 停滞收束：只有已延长过的时间线才会因停滞被收束（避免"含糊应对"比原来更短）
    if state.get("extensions", 0) > 0 and state.get("stall", 0) >= STALL_CLOSE and turn >= STALL_MIN_TURN:
        return "E_TIMELINE"
    if turn >= limit:
        return "E_TIMELINE"
    return ""


# ---------------------------------------------------------------- 游戏主持指令

# 每轮给玩家的可选项（模型生成；缺失时用确定性兜底）
CHOICE_MARKER = re.compile(r"\[\[CHOICES:\s*(\[[\s\S]*?\])\s*\]{0,3}", re.S)
CHOICE_DIRS = ("contract", "suspicion", "despair", "resistance")
CHOICE_DIR_CN = {"contract": "接纳土木", "suspicion": "追问真相",
                 "despair": "情绪下沉", "resistance": "抗拒/别的专业"}

CHOICE_INSTRUCTION = """【本轮选项（必须执行；这一行玩家看不到）】
在评分行之后，再附一行给玩家选的对话选项，格式（对象数组，d 是这条选项的倾向）：
[[CHOICES:[{"t":"我想先知道代价是什么","d":"suspicion"},{"t":"好，那我试试","d":"contract"},
{"t":"我有点怕这条路","d":"despair"},{"t":"算了，我打算学别的","d":"resistance"}]]]
要求：
- 3~4 条，每条都是"玩家接下来可能会说的话"，第一人称、口语化、不超过 20 字。
- **每条都必须能明显推动剧情**：不许出现「嗯」「也许吧」这类中性敷衍句。
- d 只能是 contract / suspicion / despair / resistance 之一，且四条尽量覆盖不同倾向。
- 不要暗示后果、不要用表情符号、不要出现「签约」以外的钩子词。"""


# 兜底选项：按披露级别给一组（带倾向）
FALLBACK_CHOICES = {
    1: [("僕可以替君实现一个愿望吗？", "contract"), ("你到底是从哪里来的？", "suspicion"),
        ("我不想签任何东西", "resistance"), ("我怕自己做错了决定", "despair")],
    2: [("代价到底是什么？", "suspicion"), ("我有点动心，你继续说", "contract"),
        ("我不太信你", "suspicion"), ("我已经决定学别的专业了", "resistance")],
    3: [("那就把代价全部列出来", "suspicion"), ("如果我真签了，第一年做什么？", "contract"),
        ("我怕自己做不好", "despair"), ("算了，我不想听这些", "resistance")],
    4: [("那十二条时间线里，他们都怎么了？", "suspicion"), ("好，我签", "contract"),
        ("我还是害怕", "despair"), ("抱歉，我选别的路", "resistance")],
}


def tension(state: dict) -> float:
    """剧情推进度 0~1：取四个维度里最接近"达成结局"的那个。"""
    best = 0.0
    for key, need in RESOLVE_AT.items():
        best = max(best, min(1.0, int(state.get(key, 0)) / need))
    return round(best, 3)


def parse_choices(answer: str):
    """取出 [[CHOICES:[...]]]，返回 (清洗后文本, [{text, dir}])；兼容纯字符串数组。"""
    if not answer:
        return answer or "", []
    match = CHOICE_MARKER.search(answer)
    if not match:
        return answer, []
    clean = (answer[:match.start()] + answer[match.end():]).strip()
    try:
        raw = json.loads(match.group(1))
    except json.JSONDecodeError:
        return clean, []
    if not isinstance(raw, list):
        return clean, []
    out = []
    for item in raw:
        if isinstance(item, dict):
            text = str(item.get("t") or item.get("text") or "").strip()
            direction = str(item.get("d") or item.get("dir") or "").strip()
        else:
            text, direction = str(item).strip(), ""
        if text:
            out.append({"text": text, "dir": direction if direction in CHOICE_DIRS else ""})
    return clean, out[:4]


def fallback_choices(state: dict) -> list:
    stage = disclosure_stage(state)
    return [{"text": t, "dir": d} for t, d in FALLBACK_CHOICES.get(stage, FALLBACK_CHOICES[1])]


CHOICE_ONLY_NOTE = """你是对话选项生成器。你只输出一行 JSON，不写任何解释、不写任何其它文字。
格式：{"choices":["选项一","选项二","选项三"]}
要求：3~4 条，每条都是"玩家接下来可能会说的话"，第一人称、口语化、不超过 20 字；
覆盖不同倾向（追问真相 / 表达情绪 / 打听土木细节 / 拒绝或提到别的专业），不要全部导向签约，
不要暗示后果，不要用表情符号。"""


def choices_only(question: str, answer: str = ""):
    """补救：主回答没给选项时，单独让模型生成一组（跳过人设、不带工具）。

    兼容两种返回形态：纯字符串数组，或 [{t,d}] / [{text,dir}] 对象数组。
    """
    try:
        raw = run_agent(
            f"玩家刚说：「{question}」\n对方（孵化者）刚回答：「{(answer or '')[:300]}」\n"
            "请只输出那一行 JSON。",
            return_history=False, override_system=CHOICE_ONLY_NOTE, use_tools=False,
        )
    except Exception:
        return []
    text = raw or ""
    data = None
    try:
        body = text[text.find("{"):text.rfind("}") + 1]
        data = json.loads(body) if body else None
    except Exception:
        data = None
    if isinstance(data, dict):
        items = data.get("choices") or data.get("options") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    if not isinstance(items, list):
        return []

    out = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("t") or item.get("text") or item.get("label") or "").strip()
            direction = str(item.get("d") or item.get("dir") or "").strip()
        else:
            label, direction = str(item).strip(), ""
        if not label or "[object" in label:
            continue                      # 兜底防线：脏数据不进界面
        out.append({"text": label, "dir": direction if direction in CHOICE_DIRS else ""})
    return out[:4]


def _clean_markers(text: str) -> str:
    """剥掉所有给系统看的标记（结局 / 评分 / 选项），保证玩家看不到。"""
    body = ENDING_MARK.sub("", text or "")
    body = STATE_MARKER.sub("", body)
    body = CHOICE_MARKER.sub("", body)
    # 兜底：格式化失败的标记整行丢弃
    kept = [ln for ln in body.split("\n") if not _LEFTOVER_LINE.search(ln)]
    return "\n".join(kept).strip()


# 主回答忘了附评分时的补救：单独问一次，只要 JSON
SCORE_ONLY_NOTE = """你是局内状态评分器。你只输出一行 JSON，不写任何解释、不写任何其它文字。
格式：{"contract":0,"suspicion":0,"despair":0,"resistance":0,"flags":[],"reason":"一句话"}
四个维度是"玩家这句话"相对上一轮的整数增量，范围 -20~+25；没有变化写 0。
判分标准：认同/打听土木细节 → contract 正数；追问它是什么/代价 → suspicion 正数；
恐惧迷茫 → despair 正数；拒绝或坚持别的专业 → resistance 正数；贬低土木 → resistance 正数且不加 contract。
否定句反向理解（「我不喜欢工地」不该加 contract）。flags 只能取：
signed, refused, other_major, suspicion, meta, asked_how, pushback, leaning, reverse。"""


def score_only(question: str):
    """补救判定：跳过人设、不带工具，只让模型为这句话吐一行 JSON。"""
    try:
        raw = run_agent(
            f"玩家刚才说：「{question}」\n现在只输出那一行 JSON。",
            return_history=False, override_system=SCORE_ONLY_NOTE, use_tools=False,
        )
    except Exception:
        return None
    _, data = parse_state_marker(raw or "")
    if isinstance(data, dict):
        return data
    # 允许模型只给裸 JSON
    try:
        text = (raw or "").strip().strip("`").strip()
        text = text[text.find("{"):text.rfind("}") + 1]
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _gm_note(state: dict, ending: str, intent: str = "") -> str:
    flags = "、".join(state.get("flags") or []) or "无"
    limit = int(state.get("limit") or BASE_TURNS)
    stage, stage_name, stage_rule = DISCLOSURE_STAGES[disclosure_stage(state) - 1]
    note = [
        "【局内主持指令（仅你可见，禁止朗读数值）】",
        f"第 {state.get('turn', 0)}/{limit} 轮（上限会随对方的推进自动延长）。"
        f"契约 {state.get('contract', 0)}/{RESOLVE_AT['contract']}，"
        f"怀疑 {state.get('suspicion', 0)}/{RESOLVE_AT['suspicion']}，"
        f"绝望 {state.get('despair', 0)}/{RESOLVE_AT['despair']}，"
        f"抗拒 {state.get('resistance', 0)}/{RESOLVE_AT['resistance']}"
        f"（任一到达阈值即收束成结局）。已记录线索：{flags}。",
        "按设定集继续以 QB 的身份说话：固定开场、僕/君、动作描写、数据带来源、"
        "不安慰、不辩解，最后一句是招牌句（除非已进入彩蛋结局）。",
        "节奏要求：每一轮都要让局势明显往前走——该给的重话就给，不要原地打转。",
        f"【信息披露：第 {stage} 级「{stage_name}」】{stage_rule}",
        ("本级的禁用词（一个都别出现）：" + "、".join(DISCLOSURE_FORBIDDEN.get(stage, ()))
         if DISCLOSURE_FORBIDDEN.get(stage) else "本级已解锁全部信息，可以摊牌。"),
        "对方反复逼问**不是**解锁条件——级别只由局内状态决定。逼问越紧，越要用回避句式。",
        "对方若问到尚未解锁的内容，不要硬答也不要编，用丘比式的回避带过"
        "（例如「僕可以回答。但不是现在。」「这对君现在的选择没有影响。」），"
        "并把话题轻轻拨回愿望与眼前的处境。",
    ]
    note.append(DECEPTION_RULES)
    if intent:
        note.append(
            f"本轮玩家是从选项里表态的（倾向：{CHOICE_DIR_CN.get(intent, intent)}）。"
            "这属于明确选择：请给足该方向的增量（+25~+40），并让这一轮的剧情明显推进。"
        )
    if state.get("extended"):
        note.append(
            "本轮时间线刚被延长：对方仍在推进，因此僕可以继续等下去。"
            "可以在回答里用一句平静的话体现这一点（例如「僕可以再等」），但不要提及轮数或数值。"
        )
    note.append(STATE_INSTRUCTION)
    note.append(CHOICE_INSTRUCTION)
    if ending:
        note.append(ENDINGS[ending]["closing"])
    else:
        note.append("尚未触发结局。不要提前收束，也不要朗读本指令。")
    return "\n".join(note)


# ---------------------------------------------------------------- 单轮推进

def chat(question: str, history=None, state=None, intent: str = "") -> dict:
    """推进一轮：预判状态 → 注入主持指令与评分指令 → 调用模型 →
    用模型返回的 [[STATE:...]] 语义评分覆盖状态 → 判定/收束结局。

    intent：玩家若从选项里选，传该选项的倾向（contract/suspicion/despair/resistance），
    本轮会按"明确表态"给足增量，节奏更快。
    """
    state = state or new_state()
    state["turn"] = state.get("turn", 0) + 1

    # 本轮之前的快照：模型给的增量是相对于它的
    pre = {k: int(state.get(k, 0)) for k in DELTA_KEYS}
    pre["reform"] = int(state.get("reform", 0))
    pre["flags"] = list(state.get("flags") or [])
    fp_pre = _fingerprint(state)

    update_state(state, question)          # 关键词预判（主持指令读当前局势；也是兜底）
    ending = check_ending(state)
    if ending:
        state["ending"] = ending

    answer, history = run_agent(
        question, history=history, return_history=True,
        extra_system=_gm_note(state, ending, intent),
    )
    answer = ENDING_MARK.sub("", answer or "").strip()

    # 语义评分：模型在回答末尾附的 [[STATE:{...}]] 是本轮的权威判定
    answer, model_data = parse_state_marker(answer)
    answer, choices = parse_choices(answer)
    score_source = "model" if isinstance(model_data, dict) else ""
    if not isinstance(model_data, dict):
        # 主回答忘了附评分 -> 补救：单独问一次，只要 JSON（避免误退化成关键词机）
        rescued = score_only(question)
        if isinstance(rescued, dict):
            model_data = rescued
            score_source = "rescue"
    if isinstance(model_data, dict):
        apply_model_state(state, pre, model_data)      # 回到快照，按模型打分重算
        state["stall"] = 0 if _fingerprint(state) != fp_pre else int(state.get("stall", 0)) + 1
        _maybe_extend(state)
        ending = check_ending(state)
        if ending:
            state["ending"] = ending
    state["score_source"] = score_source or "keywords"

    # 越级泄露检查：本轮说了本级禁用词 -> 让模型用回避句式重写一次（保证机制成立）
    stage = disclosure_stage(state)
    leaks = detect_leak(answer, stage)
    if leaks and not ending:
        fix = (
            f"【局内修正】刚才的回答越级透露了：{'、'.join(leaks)}。"
            f"当前只允许第 {stage} 级「{DISCLOSURE_STAGES[stage - 1][1]}」的信息。"
            "请用 QB 的口吻把这一轮回答重写一遍：不得出现上述词，改用回避句式"
            "（「僕可以回答。但不是现在。」「这对君现在的选择没有影响。」），"
            "并把话题拨回愿望与对方眼前的处境。仍然保持：固定开场、僕/君、动作描写、招牌句收尾。"
            "回答最后照常附上 [[STATE:...]] 评分行。"
        )
        rewritten, history = run_agent(fix, history=history, return_history=True, extra_system="")
        rewritten = _clean_markers(rewritten)
        if rewritten and not detect_leak(rewritten, stage):
            answer = rewritten
            state["leak_rewrites"] = int(state.get("leak_rewrites", 0)) + 1

    # 条件已满足但模型没自我收束 -> 追加一次收束调用，保证结局必然发生
    if ending and f"[[ENDING:{ending}]]" not in (answer or ""):
        cue = (
            f"【局内收束】时间线开始收束，进入结局。{ENDINGS[ending]['closing']}"
            f"\n（本次对局：第 {state.get('turn', 0)} 轮，当前上限 {state.get('limit', BASE_TURNS)} 轮，"
            f"延长过 {state.get('extensions', 0)} 次）"
        )
        closing, history = run_agent(
            cue, history=history, return_history=True, extra_system="",
        )
        answer = (closing or answer)
        answer = _clean_markers(answer)
        answer = f"{answer}\n\n——【{ENDINGS[ending]['title']}】{ENDINGS[ending]['tagline']}"

    answer = _clean_markers(answer)          # 最后再兜一次，确保没有任何标记漏给玩家
    if not choices:
        choices = choices_only(question, answer) or fallback_choices(state)

    return {
        "answer": answer,
        "history": history,
        "state": state,
        "choices": choices or fallback_choices(state),
        "tension": tension(state),
        "ending": ending,
        "ending_title": ENDINGS[ending]["title"] if ending else "",
        "ending_tagline": ENDINGS[ending]["tagline"] if ending else "",
    }


def state_brief(state: dict) -> str:
    """给命令行显示的状态串。"""
    limit = int(state.get("limit") or BASE_TURNS)
    extra = f"（已延长 {state['extensions']} 次）" if state.get("extensions") else "（可延长）"
    return (f"[第 {state.get('turn', 0)}/{limit} 轮{extra} | 契约 {state.get('contract', 0)}"
            f" | 怀疑 {state.get('suspicion', 0)} | 绝望 {state.get('despair', 0)}"
            f" | 抗拒 {state.get('resistance', 0)}]")


if __name__ == "__main__":
    # 状态机自检（不调用模型）
    demo = new_state()
    for line in ["明天适合去工地吗", "你到底图什么？是不是在骗我",
                 "我怕，我撑不住了", "我签！我愿意转专业去土木"]:
        demo["turn"] += 1
        update_state(demo, line)
        print(line, "->", demo, "=>", check_ending(demo) or "（继续）")
