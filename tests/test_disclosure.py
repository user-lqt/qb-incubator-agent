"""分级披露的回归测试：级别判定、禁用词、越级检测（不调模型）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import (DISCLOSURE_FORBIDDEN, PROLOGUE, detect_leak,  # noqa: E402
                  disclosure_stage, new_state)

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")


# 序章不得剧透世界观
check("序章不含世界观关键词",
      not any(w in PROLOGUE for w in ("孵化者", "耐久", "相变", "时间线", "能量")))
check("序章够短（<120 字）", len(PROLOGUE) < 120)
check("序章仍提出愿望", "愿望" in PROLOGUE)

# 级别判定
CASES = [
    ({"suspicion": 0, "turn": 1, "contract": 0}, 1),
    ({"suspicion": 0, "turn": 5, "contract": 0}, 2),
    ({"suspicion": 25, "turn": 3, "contract": 0}, 2),
    ({"suspicion": 0, "turn": 3, "contract": 30}, 2),
    ({"suspicion": 45, "turn": 9, "contract": 0}, 3),
    ({"suspicion": 70, "turn": 13, "contract": 0}, 4),
    ({"suspicion": 0, "turn": 3, "contract": 65}, 4),
]
for patch, expect in CASES:
    st = new_state()
    st.update(patch)
    got = disclosure_stage(st)
    check(f"{patch} -> 第 {expect} 级（实际 {got}）", got == expect)

# 越级检测
check("第 1 级禁用'孵化者'", detect_leak("僕是孵化者。", 1) == ["孵化者"])
check("第 1 级禁用'耐久'", "耐久" in detect_leak("这是耐久。", 1))
check("第 2 级允许说'孵化者'", detect_leak("僕是孵化者。", 2) == [])
check("第 2 级禁用'耐久'", detect_leak("这是耐久。", 2) == ["耐久"])
check("第 3 级禁用'相变'", detect_leak("希望到绝望的相变。", 3) == ["相变"])
check("第 3 级可以说代价三项", detect_leak("代价是日晒、驻场、工期节点。", 3) == [])
check("第 4 级不再限制", detect_leak("孵化者收集能量，形成耐久。", 4) == [])
check("第 1 级禁用词表非空", len(DISCLOSURE_FORBIDDEN[1]) >= 5)

print("\n结论:", "全部通过 ✅" if ok else "存在问题 ❌")
sys.exit(0 if ok else 1)
