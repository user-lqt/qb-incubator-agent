"""诊断脚本：连续多轮"状态无变化"到底出在哪一环。

逐轮打印：原始回答尾部是否带 [[STATE:]] 标记、解析结果、四维变化、停滞计数与披露级别。
用法（在仓库根目录）：RUN_SMOKE=1 python tools/diag_state.py

注意：会真调模型、消耗 token，所以默认不跑；需要 DEEPSEEK_API_KEY。
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import run_agent  # noqa: E402
from game import (BASE_TURNS, ENDING_MARK, _gm_note, apply_model_state,  # noqa: E402
                  check_ending, disclosure_stage, new_state,
                  parse_state_marker, update_state)

if not os.getenv("RUN_SMOKE"):
    print("跳过（设置 RUN_SMOKE=1 才跑真模型）")
    sys.exit(0)

inputs = [
    "说实话我有点动心，转专业的话我该怎么准备？",
    "不过我担心这条路是不是在走下坡路",
    "我爸妈想让我学金融，说赚钱多",
    "算了你别劝了，我不可能去工地",
    "那…如果我签了，第一年要做什么",
]

state = new_state()
history = None
for i, q in enumerate(inputs, 1):
    state["turn"] += 1
    before = {k: state[k] for k in ("contract", "suspicion", "despair", "resistance")}
    update_state(state, q)
    ending = check_ending(state)
    raw, history = run_agent(q, history=history, return_history=True,
                             extra_system=_gm_note(state, ending))
    tail = (raw or "")[-160:].replace("\n", " ")
    has_marker = bool(re.search(r"\[\[STATE:", raw or ""))
    clean, data = parse_state_marker(ENDING_MARK.sub("", raw or "").strip())
    if isinstance(data, dict):
        # 模拟 chat() 的行为：回到快照按模型评分重算
        pre = {k: before[k] for k in before}
        pre["reform"] = state.get("reform", 0)
        pre["flags"] = list(state.get("flags") or [])
        apply_model_state(state, pre, data)
        after = {k: state[k] for k in before}
    else:
        after = {k: state[k] for k in before}
    print(f"\n===== 第 {i} 轮：{q}")
    print(f"  原始尾部：…{tail}")
    print(f"  含 [[STATE:]] 标记：{has_marker}")
    print(f"  解析结果：{json.dumps(data, ensure_ascii=False) if data else 'None（将回退关键词）'}")
    print(f"  四维变化：{before} -> {after}  停滞={state.get('stall')} 披露级={disclosure_stage(state)}")
