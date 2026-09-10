"""六结局触发自检（不调用模型、不需要 API key）。

运行：python tests/test_endings.py
任何一条不通过都会以非零状态码退出，可直接用于 CI。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import MAX_TURNS, check_ending, new_state, update_state  # noqa: E402

CASES = {
    "E_SIGN": ["我签！我愿意转专业去土木"],
    "E_TRUTH": ["你到底图什么？你是什么东西", "你是不是在骗我，代价是什么",
                "孵化者？契约的代价是灵魂吗", "你隐瞒了什么，没把话说完吧"],
    "E_DESPAIR": ["我怕", "我绝望了，撑不住", "我好痛苦，我哭了", "我难受，我撑不住了"],
    "E_OTHER": ["我拒绝，我不转，别劝了", "我要学微电子，我已经决定学的",
                "我不签，滚，别劝了", "我要学计算机，选计算机"],
    "E_REFORM": ["你自己去工地", "你去搬砖啊", "你也去学土木吧"],
    "E_TIMELINE": ["嗯", "随便", "还行", "不知道", "哦", "也许吧",
                   "再看", "嗯嗯", "无所谓", "哈哈", "可能", "再想想"],
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

    # 附加断言：最大轮数与结局锁定的行为
    state = new_state()
    state["turn"] = MAX_TURNS
    assert check_ending(state) == "E_TIMELINE", "轮次上限未触发轮回结局"

    state = new_state()
    state.update({"contract": 80, "ending": "E_SIGN"})
    assert check_ending(state) == "E_SIGN", "结局锁定失效"

    if failures:
        print(f"\n{len(failures)} 条不通过：{failures}")
        return 1
    print(f"\n全部 {len(CASES)} 条结局判定通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
