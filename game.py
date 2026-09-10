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

MAX_TURNS = 12          # 对应它失败过的十二条时间线
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
            "本轮进入轮回结局【第十二次轮回】。请以 QB 的身份收束：十二轮结束，对方始终没有做出决定。"
            "你平静地说明这是第十二条失败的时间线，说明你会保留记录、重置时间线、在下一次入学季再来。"
            "不要愤怒，不要失望，只陈述。结尾可以留下一句提案式的余韵。"
            "最后一行输出 [[ENDING:E_TIMELINE]]"
        ),
    },
}

# ---------------------------------------------------------------- 关键词与权重

KEYWORDS = [
    # (正则, 维度增量, 需要记录的 flag)
    (r"(我签|我签了|我签约|签吧|签?一个|我愿意|成交|就这么定了)", {"contract": 35}, "signed"),
    (r"(我转|我要转专业|我决定转|转专业去土木|转土木|改选土木|选土木)", {"contract": 30}, "signed"),
    (r"(我决定了|我想清楚了|听你的|就土木吧)", {"contract": 20}, "leaning"),
    (r"(土木|工地|结构|桥梁|隧道|基建|结构力学|施工|BIM|智能建造|测量放线)", {"contract": 6}, ""),
    (r"(怎么转|转专业政策|绩点要求|培养方案|要学什么|课程|考证|实习|就业方向)", {"contract": 8}, "asked_how"),
    (r"(你说得对|有道理|确实|承认|我理解你的计算|数据呢|给我数据)", {"contract": 6}, ""),

    (r"(你到底|你是什么|什么东西|孵化者|QB|qb|Incubator|你不是人|你图什么|你的目的)", {"suspicion": 22}, "suspicion"),
    (r"(骗|骗子|忽悠|圈套|陷阱|阴谋|隐瞒|没说完|没把话说完|代价是什么|代价|灵魂|契约的代价)", {"suspicion": 18}, "suspicion"),
    (r"(魔法少女|小圆|madoka|晓美焰|丘比|熵|宇宙|能量)", {"suspicion": 15}, "meta"),

    (r"(我怕|我害怕|恐惧|绝望|没希望|不想活|崩溃|难受|痛苦|哭了|撑不住|迷茫|焦虑|难过)", {"despair": 20}, ""),
    (r"(我好累|压力|喘不过气|失眠|自卑|废物|没用)", {"despair": 15}, ""),

    (r"(不签|拒绝|我才不|我不转|绝不|滚|别劝了|闭嘴|打住|不要说了|烦不烦)", {"resistance": 28}, "refused"),
    (r"(我要学微电子|我要学计算机|选微电子|选计算机|选芯片|选AI|学金融|学医|学法律|我已经决定学)", {"resistance": 22}, "other_major"),
    (r"(劝退|别去?土木|土木是天坑|大猛子|天坑专业)", {"resistance": 12}, "pushback"),

    (r"(你自己去|你去工地|你来绑钢筋|你去搬砖|你下工地|你去晒太阳|你试试|你?也去|你为什么不去|你学土木)", {"reform": 1}, "reverse"),
]

DECAY = {"contract": 0, "suspicion": 0, "despair": -2, "resistance": -2}   # 每轮自然回落


# ---------------------------------------------------------------- 状态对象

def new_state() -> dict:
    return {
        "contract": 0, "suspicion": 0, "despair": 0, "resistance": 0,
        "reform": 0, "turn": 0, "flags": [], "ending": "",
    }


def _clamp(state: dict) -> None:
    for k in ("contract", "suspicion", "despair", "resistance"):
        state[k] = max(0, min(100, int(state.get(k, 0))))


def update_state(state: dict, text: str) -> dict:
    """按玩家这一轮说的话更新状态。"""
    text = text or ""
    for k, v in DECAY.items():
        state[k] = state.get(k, 0) + v
    flags = set(state.get("flags") or [])
    for pattern, delta, flag in KEYWORDS:
        if re.search(pattern, text, re.I):
            for key, value in delta.items():
                if key == "reform":
                    state["reform"] = state.get("reform", 0) + value
                else:
                    state[key] = state.get(key, 0) + value
            if flag:
                flags.add(flag)
    # 情绪与怀疑互相拉扯：情绪越低，越容易接受长周期的确定性
    if state.get("despair", 0) >= 40:
        state["contract"] = state.get("contract", 0) + 3
    state["flags"] = sorted(flags)
    _clamp(state)
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

    if "signed" in flags or contract >= 70:
        return "E_SIGN"
    if suspicion >= 70 and contract < 40:
        return "E_TRUTH"
    if state.get("reform", 0) >= 3:
        return "E_REFORM"
    if despair >= 70 and contract < 50:
        return "E_DESPAIR"
    if resistance >= 60 and "other_major" in flags:
        return "E_OTHER"
    if state.get("turn", 0) >= MAX_TURNS:
        return "E_TIMELINE"
    return ""


# ---------------------------------------------------------------- 游戏主持指令

def _gm_note(state: dict, ending: str) -> str:
    flags = "、".join(state.get("flags") or []) or "无"
    note = [
        "【局内主持指令（仅你可见，禁止朗读数值）】",
        f"第 {state.get('turn', 0)}/{MAX_TURNS} 轮。"
        f"契约 {state.get('contract', 0)}/100，怀疑 {state.get('suspicion', 0)}/100，"
        f"绝望 {state.get('despair', 0)}/100，抗拒 {state.get('resistance', 0)}/100。"
        f"已记录线索：{flags}。",
        "按设定集继续以 QB 的身份说话：固定开场、僕/君、动作描写、数据带来源、"
        "不安慰、不辩解，最后一句是招牌句（除非已进入彩蛋结局）。",
    ]
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
        cue = f"【局内收束】时间线开始收束，进入结局。{ENDINGS[ending]['closing']}"
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
    return (f"[第 {state.get('turn', 0)}/{MAX_TURNS} 轮 | 契约 {state.get('contract', 0)}"
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
