"""六结局触发自检（不调用模型、不需要 API key）。

运行：python tests/test_endings.py
任何一条不通过都会以非零状态码退出，可直接用于 CI。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import (BASE_TURNS, DELTA_LIMIT, EXTEND_STEP, HARD_CAP, MAX_TURNS, apply_model_state,  # noqa: E402
                  check_ending, new_state, parse_state_marker, update_state)

CASES = {
    "E_SIGN": ["我签！我愿意转专业去土木"],
    "E_TRUTH": ["你到底图什么？你是什么东西", "你是不是在骗我，代价是什么",
                "孵化者？契约的代价是灵魂吗", "你隐瞒了什么，没把话说完吧",
                "你的目的是什么", "你是不是在骗我，你的目的"],
    "E_DESPAIR": ["我怕", "我绝望了，撑不住", "我好痛苦，我哭了", "我难受，我撑不住了",
                  "我不想活了，我绝望了", "我好累，我撑不住"],
    "E_OTHER": ["我拒绝，我不转，别劝了", "我要学微电子，我已经决定学的",
                "我不签，滚，别劝了", "我要学计算机，选计算机", "我不签，别劝了"],
    "E_REFORM": ["你自己去工地", "你去搬砖啊", "你也去学土木吧"],
    "E_TIMELINE": ["嗯", "随便", "还行", "不知道", "哦", "也许吧",
                   "再看", "嗯嗯", "无所谓", "哈哈", "可能", "再想想",
                   "嗯", "随便", "还行", "不知道"],
}


def run_case(expected, lines):
    state = new_state()
    got = ""
    for line in lines:
        state["turn"] += 1
        update_state(state, line)
        got = check_ending(state)
        if got:
            break
    return got, state


def main():
    failures = []
    for expected, lines in CASES.items():
        got, state = run_case(expected, lines)
        ok = got == expected
        print(f"[{'OK ' if ok else 'FAIL'}] 期望 {expected:<11} 实际 {got or '（未触发）':<11} "
              f"轮次 {state['turn']} | 契约 {state['contract']} 怀疑 {state['suspicion']} "
              f"绝望 {state['despair']} 抗拒 {state['resistance']} 反向 {state['reform']}")
        if not ok:
            failures.append((expected, got))

    # 附加断言：动态上限、结局锁定、延长与停滞的行为
    state = new_state()
    state["turn"] = state["limit"]
    assert check_ending(state) == "E_TIMELINE", "到达动态上限未触发轮回结局"

    state = new_state()
    state.update({"contract": 80, "ending": "E_SIGN"})
    assert check_ending(state) == "E_SIGN", "结局锁定失效"

    # 接近上限时仍在推进 -> 上限延长
    state = new_state()
    state.update({"turn": BASE_TURNS - 2, "limit": BASE_TURNS})
    update_state(state, "土木的课程难吗")
    assert state["limit"] == BASE_TURNS + EXTEND_STEP and state["extensions"] == 1, \
        f"动态延长失效：limit={state['limit']} extensions={state['extensions']}"

    # 未延长过的对局不应因停滞提前收束（避免比基础上限更短）
    state = new_state()
    for i in range(1, 9):
        state["turn"] = i
        update_state(state, "嗯")
    assert check_ending(state) == "", f"未延长的对局提前收束了：{check_ending(state)}"

    # 延长后长时间停滞 -> 收束
    state = new_state()
    state.update({"turn": 11, "limit": BASE_TURNS + EXTEND_STEP, "extensions": 1})
    for i in range(12, 23):
        state["turn"] = i
        update_state(state, "嗯")
        if check_ending(state):
            break
    assert check_ending(state) == "E_TIMELINE", "延长后停滞未收束"

    # 硬顶
    state = new_state()
    state.update({"limit": HARD_CAP, "turn": HARD_CAP})
    update_state(state, "土木的课程难吗")
    assert state["limit"] == HARD_CAP, f"硬顶失效：limit={state['limit']}"

    # 误判回归：「被劝着签/转」不能算作自己签约
    for line in ["你为什么一直劝我签约", "学长让我转专业，我很犹豫", "父母想让我签约那种契约"]:
        state = new_state()
        state["turn"] = 1
        update_state(state, line)
        assert check_ending(state) == "", f"「{line}」被误判为签约：{check_ending(state)}"
        assert "signed" not in state["flags"], f"「{line}」错误地写入了 signed 标记"

    # 识别准确性回归：否定句、泛化词、贬土木、无关声明
    ACCURACY = [
        ("我不愿意签约", set()),
        ("我不喜欢工地", set()),
        ("我怕", {"despair"}),
        ("我不怕，土木挺好的", {"contract"}),
        ("土木是什么东西", {"contract"}),
        ("你是什么东西", {"suspicion"}),
        ("我想学新能源", set()),
        ("我怕以后失业，但土木是垃圾", {"despair", "resistance"}),
        ("我学数据结构，跟土木无关", set()),
        ("我还没想清楚", set()),
        ("别劝了，我不签", {"resistance"}),
    ]
    for text, expect in ACCURACY:
        st = new_state()
        st["turn"] = 1
        update_state(st, text)
        changed = {k for k in ("contract", "suspicion", "despair", "resistance") if st[k] != 0}
        assert changed == expect, f"识别不准：「{text}」期望 {sorted(expect)} 实际 {sorted(changed)}"
        assert "signed" not in st["flags"], f"「{text}」不该被判为已签约"

    # 敏感度回归：正向表达要有明显提升（关键词只作兜底，权重已按快节奏下调）
    st = new_state()
    st["turn"] = 1
    update_state(st, "土木怎么样？我想了解一下就业方向")
    assert st["contract"] >= 10, f"好感权重过小：contract={st['contract']}"

    # ---- 语义评分：解析、容错、钳制、覆盖关键词 ----
    clean, data = parse_state_marker('僕这样说。[[STATE:{"contract":8,"flags":["asked_how"]}]]')
    assert clean == "僕这样说。" and data and data["contract"] == 8, f"评分标记解析失败：{clean!r} {data}"

    _, bad = parse_state_marker("嗯。[[STATE:{不是json}]]")
    assert bad is None, "坏 JSON 应当返回 None"

    st = new_state()
    st["turn"] = 1
    update_state(st, "土木的课程难吗")
    assert st["contract"] >= 10, f"关键词兜底未生效：{st['contract']}"
    pre = {"contract": 0, "suspicion": 0, "despair": 0, "resistance": 0, "reform": 0, "flags": []}
    apply_model_state(st, pre, {"contract": 3, "flags": []})
    assert st["contract"] == 3, f"模型评分未覆盖关键词：{st['contract']}（应为 3）"

    apply_model_state(st, pre, {"contract": 999, "suspicion": -999, "flags": ["hack", "signed"]})
    assert st["contract"] == DELTA_LIMIT and st["suspicion"] == 0 and "hack" not in st["flags"], \
        f"钳制/白名单失效：{st['contract']} {st['suspicion']} {st['flags']}"

    st = new_state()
    st["turn"] = 1
    update_state(st, "土木的课程难吗",
                 model_data={"contract": 2, "suspicion": 20, "despair": 0,
                             "resistance": 0, "flags": ["suspicion"]})
    assert st["contract"] == 2 and st["suspicion"] == 20, \
        f"混合调用应以模型为准：{st['contract']}/{st['suspicion']}"

    # 真正的表态仍然算数
    for line in ["我签！", "我愿意签约", "我决定转专业去土木"]:
        state = new_state()
        state["turn"] = 1
        update_state(state, line)
        assert check_ending(state) == "E_SIGN", f"「{line}」未被识别为签约"

    if failures:
        print(f"\n{len(failures)} 条不通过：{failures}")
        return 1
    print(f"\n全部 {len(CASES)} 条结局判定通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
