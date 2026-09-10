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
import re

from agent import run_agent

# 动态轮数：基础 12 轮（对应它失败过的十二条时间线），
# 只要玩家还在推进局势（任一维度发生变化），上限就自动延长，直到硬顶。
BASE_TURNS = 16         # 初始上限（玩家仍在推进时会自动延长）
EXTEND_STEP = 8         # 每次延长的轮数
HARD_CAP = 64           # 硬顶，防止无限对局
STALL_CLOSE = 6         # 延长过的时间线里，连续多少轮毫无变化 -> 收束
STALL_MIN_TURN = 8      # 至少进行到第几轮才允许因停滞收束
MAX_TURNS = BASE_TURNS  # 兼容旧引用
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
    # (正则, 维度增量, 需要记录的 flag)
    # —— 强信号：明确表态，权重高，快速收束
    (r"(我签|我签了|我签约|签吧|签?一个|我愿意|成交|就这么定了)", {"contract": 35}, "signed"),
    (r"(我转|我要转专业|我决定转|转专业去土木|转土木|改选土木|选土木)", {"contract": 30}, "signed"),
    (r"(我决定了|我想清楚了|听你的|就土木吧)", {"contract": 20}, "leaning"),
    (r"(不签|拒绝|我才不|我不转|绝不|滚|别劝了|闭嘴|打住|不要说了|烦不烦)", {"resistance": 20}, "refused"),
    (r"(我要学微电子|我要学计算机|选微电子|选计算机|选芯片|选AI|学金融|学医|学法律|我已经决定学)", {"resistance": 18}, "other_major"),

    # —— 探索型：只是打听、闲聊、追问，权重低，让对局能自然变长
    (r"(土木|工地|结构|桥梁|隧道|基建|结构力学|施工|BIM|智能建造|测量放线)", {"contract": 3}, ""),
    (r"(怎么转|转专业政策|绩点要求|培养方案|要学什么|课程|考证|实习|就业方向)", {"contract": 4}, "asked_how"),
    (r"(你说得对|有道理|确实|承认|我理解你的计算|数据呢|给我数据)", {"contract": 3}, ""),
    (r"(你到底|你是什么|什么东西|孵化者|QB|qb|Incubator|你不是人|你图什么|你的目的)", {"suspicion": 14}, "suspicion"),
    (r"(骗|骗子|忽悠|圈套|陷阱|阴谋|隐瞒|没说完|没把话说完|代价是什么|代价|灵魂|契约的代价)", {"suspicion": 12}, "suspicion"),
    (r"(魔法少女|小圆|madoka|晓美焰|丘比|熵|宇宙|能量)", {"suspicion": 10}, "meta"),
    (r"(我怕|我害怕|恐惧|绝望|没希望|不想活|崩溃|难受|痛苦|哭了|撑不住|迷茫|焦虑|难过)", {"despair": 14}, ""),
    (r"(我好累|压力|喘不过气|失眠|自卑|废物|没用)", {"despair": 10}, ""),
    (r"(劝退|别去?土木|土木是天坑|大猛子|天坑专业)", {"resistance": 10}, "pushback"),
    (r"(你自己去|你去工地|你来绑钢筋|你去搬砖|你下工地|你去晒太阳|你试试|你?也去|你为什么不去|你学土木)", {"reform": 1}, "reverse"),
]

DECAY = {"contract": 0, "suspicion": 0, "despair": -2, "resistance": -2}   # 每轮自然回落

# 开场世界观序章（命令行与网页版共用同一套文本，前端那份在 web/game.js 里）
PROLOGUE = """嗯——僕先说明僕是什么。

僕是孵化者。僕们把人类少女的希望与绝望之间的相变收集起来，延缓宇宙的死。
这是僕们的本职工作，也是僕存在的全部理由。

但在这条时间线上，僕为「土木」单独开了一条通道。因为僕观测到另一件事：
有一种能量比绝望更耐用——当一个人把希望倒进桥、坝、隧、渠、路网里，
它会固化下来，持续输出上百年。僕把这种形式命名为「耐久」。

于是有了土木契约。君交出一部分青春与舒适；僕给君一样不会被夺走的东西：
一门不会因版本更新而作废的技能，和一双能看见城市骨相的眼睛。

僕已经失败过很多条时间线了。有人在别的契约里签到三十五岁，
才第一次听懂「魔女」这个词。僕不想再记录一次那样的事故，
所以僕回到了这里——在这个入学季，在这条走廊上。

*尾巴轻轻摆了一下* 现在，僕在听。"""

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


def _maybe_extend(state: dict) -> None:
    """动态轮数：玩家仍在推进（本轮数值有变化）且快到上限时，自动延长。"""
    state["extended"] = False
    limit = int(state.get("limit") or BASE_TURNS)
    if state.get("stall", 0) == 0 and state.get("turn", 0) >= limit - 2 and limit < HARD_CAP:
        step = min(EXTEND_STEP, HARD_CAP - limit)
        state["limit"] = limit + step
        state["extensions"] = int(state.get("extensions", 0)) + 1
        state["extended"] = True


def update_state(state: dict, text: str) -> dict:
    """按玩家这一轮说的话更新状态（含动态轮数判定）。"""
    text = text or ""
    dims = ("contract", "suspicion", "despair", "resistance")
    before = {k: int(state.get(k, 0)) for k in dims}
    before["reform"] = int(state.get("reform", 0))

    for k, v in DECAY.items():
        state[k] = state.get(k, 0) + v
    flags = set(state.get("flags") or [])
    strict_text = PERSUADE_CLAUSE.sub(" ", text)
    for pattern, delta, flag in KEYWORDS:
        haystack = strict_text if pattern in STRICT_PATTERNS else text
        if re.search(pattern, haystack, re.I):
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

    after = {k: int(state.get(k, 0)) for k in dims}
    after["reform"] = int(state.get("reform", 0))
    state["stall"] = 0 if after != before else int(state.get("stall", 0)) + 1
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

    if "signed" in flags or contract >= 70:
        return "E_SIGN"
    if suspicion >= 70 and contract < 40:
        return "E_TRUTH"
    if state.get("reform", 0) >= 3:
        return "E_REFORM"
    if despair >= 70 and contract < 50:
        return "E_DESPAIR"
    if resistance >= 75 and ("other_major" in flags or "refused" in flags):
        return "E_OTHER"
    # 停滞收束：只有已延长过的时间线才会因停滞被收束（避免"含糊应对"比原来更短）
    if state.get("extensions", 0) > 0 and state.get("stall", 0) >= STALL_CLOSE and turn >= STALL_MIN_TURN:
        return "E_TIMELINE"
    if turn >= limit:
        return "E_TIMELINE"
    return ""


# ---------------------------------------------------------------- 游戏主持指令

def _gm_note(state: dict, ending: str) -> str:
    flags = "、".join(state.get("flags") or []) or "无"
    limit = int(state.get("limit") or BASE_TURNS)
    note = [
        "【局内主持指令（仅你可见，禁止朗读数值）】",
        f"第 {state.get('turn', 0)}/{limit} 轮（上限会随对方的推进自动延长）。"
        f"契约 {state.get('contract', 0)}/100，怀疑 {state.get('suspicion', 0)}/100，"
        f"绝望 {state.get('despair', 0)}/100，抗拒 {state.get('resistance', 0)}/100。"
        f"已记录线索：{flags}。",
        "按设定集继续以 QB 的身份说话：固定开场、僕/君、动作描写、数据带来源、"
        "不安慰、不辩解，最后一句是招牌句（除非已进入彩蛋结局）。",
    ]
    if state.get("extended"):
        note.append(
            "本轮时间线刚被延长：对方仍在推进，因此僕可以继续等下去。"
            "可以在回答里用一句平静的话体现这一点（例如「僕可以再等」），但不要提及轮数或数值。"
        )
    if ending:
        note.append(ENDINGS[ending]["closing"])
    else:
        note.append("尚未触发结局。不要提前收束，也不要朗读本指令。")
    return "\n".join(note)


# ---------------------------------------------------------------- 单轮推进

def chat(question: str, history=None, state=None) -> dict:
    """推进一轮：更新状态 → 注入主持指令 → 调用模型 → 判定/收束结局。"""
    state = state or new_state()
    state["turn"] = state.get("turn", 0) + 1
    update_state(state, question)

    ending = check_ending(state)
    if ending:
        state["ending"] = ending

    answer, history = run_agent(
        question, history=history, return_history=True,
        extra_system=_gm_note(state, ending),
    )
    answer = ENDING_MARK.sub("", answer or "").strip()

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
        answer = ENDING_MARK.sub("", answer).strip()
        answer = f"{answer}\n\n——【{ENDINGS[ending]['title']}】{ENDINGS[ending]['tagline']}"

    return {
        "answer": answer,
        "history": history,
        "state": state,
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
