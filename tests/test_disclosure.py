"""分级披露的回归测试：级别判定、禁用词、越级检测（不调模型）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import (DISCLOSURE_FORBIDDEN, PROLOGUE, detect_leak,  # noqa: E402
                  disclosure_stage, fallback_choices, new_state, parse_choices,
                  parse_state_marker)

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

# 对话选项：标记解析 + 兜底
clean, chs = parse_choices('僕这样说。[[STATE:{"contract":1}]]\n[[CHOICES:["继续问","我考虑一下","算了"]]]')
check("选项标记被剥离", "CHOICES" not in clean)
check("解析出 3 个选项", chs == ["继续问", "我考虑一下", "算了"])
_, bad = parse_choices("嗯[[CHOICES:[不是数组}]]")
check("坏选项返回空数组", bad == [])
_, not_array = parse_choices('[[CHOICES:"字符串不算"]]')
check("非数组选项被丢弃", not_array == [])
for stage_patch, expect_min in [({"suspicion": 0, "turn": 1}, 3), ({"suspicion": 70, "turn": 13}, 3)]:
    st = new_state()
    st.update(stage_patch)
    fb = fallback_choices(st)
    check(f"兜底选项 >= {expect_min} 条（实际 {len(fb)}）", len(fb) >= expect_min)

# 畸形标记容错：模型经常少写一个右括号
MALFORMED = [
    '正文。[[CHOICES:["甲","乙","丙"]]',          # 少一个 ]
    '正文。[[CHOICES:["甲","乙"]]]]',             # 多一个 ]
    '正文。[[STATE:{"contract":5}]',              # STATE 少一个 ]
    '正文。[[STATE:{"contract":5}]]]',
]
for text in MALFORMED:
    clean1, _ = parse_state_marker(text)
    clean2, chs = parse_choices(clean1)
    leftover = [t for t in ("[[STATE", "[[CHOICES", "]]") if t in clean2]
    check(f"畸形标记被清理：{text[:22]}… 残留={leftover or '无'}", not leftover)
    if "CHOICES" in text and "少一个" not in text:
        check(f"  且解析出选项：{len(chs)} 条", len(chs) >= 2)

print("\n结论:", "全部通过 ✅" if ok else "存在问题 ❌")
sys.exit(0 if ok else 1)
