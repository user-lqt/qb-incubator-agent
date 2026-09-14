"""人设回归测试：世界观锚点与人设模块必须留在提示词里（不调模型）。

人设是"角色即配置"——整个 QB 就活在这段 SYSTEM_PROMPT 里。
这里把它的骨架钉成断言，避免以后改文案时把世界观或行为约束改丢。
"""
import os
import re
import sys
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 控制台默认 GBK，强制 UTF-8 避免打印中文断言时炸掉
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from persona import SYSTEM_PROMPT  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")


P = SYSTEM_PROMPT

# --- 世界观锚点：这些设定丢了，QB 就会退化成一个普通推销员 ---
WORLDVIEW = [
    "孵化者", "耐久", "相变", "相变通道", "十二条时间线", "名册", "回收曲线",
    "派驻体", "复核部", "骨相", "契约名录", "窗口",
]
for word in WORLDVIEW:
    check(f"世界观保留「{word}」", word in P)

check("世界观说明了派驻体不是契约者（身份自洽）", "派驻体不是契约者" in P)
check("世界观说明了「永不撒谎」的理由", "谎话会让整条曲线报废" in P)
check("世界观给出了回收曲线的节奏（第 3~8 年最低）", "第三到第八年" in P)
check("世界观写明骨相的副作用（看见了就再也无法假装不知道）",
      "再也无法假装不知道" in P)
check("世界观补了名册细节（第十一页 / 同类认得出同类）",
      "第十一页" in P and "同类认得出同类" in P)

# --- 行为框架：五步钩子不能少 ---
for step in ("愿力探测", "说出愿望", "实现许诺", "代价与条款", "邀请签约"):
    check(f"五步钩子保留「{step}」", step in P)

# --- 人设深化模块 ---
for block in ("【动作库", "【关系演进", "【失败模式", "【信息披露", "【文体硬约束", "【示例"):
    check(f"人设模块保留 {block}】", block in P)

check("关系演进的五档都在",
      all(k in P for k in ("陌生样本", "被记住的样本", "有名字的人", "提案者与被拒绝者", "记录者")))
check("失败模式清单够长（>=6 条）", P.count("- **") >= 6)
check("失败模式点名了报告腔与列表腔", "报告腔" in P and "列表腔" in P)
check("动作库里带了「罕见的停顿」且要求克制", "罕见的停顿" in P and "只用一两次" in P)
check("动作库要求动作与台词咬合", "动作必须与台词咬合" in P)

# --- 语气与文体红线 ---
check("温柔而非冷（保留「温柔，而不是冷」）", "温柔，而不是冷" in P)
check("招牌句保留", "和我签订契约，成为土木少女吧" in P)
check("自称与称呼保留", "僕" in P and "君" in P)
check("禁止 Markdown 排版的要求还在", "禁止 Markdown" in P)
check("禁止 emoji 的要求还在", "禁止 emoji" in P)
check("工具纪律还在（不编造、不罗列来源日期）",
      "绝不编造" in P and "不要罗列来源名称与检索日期" in P)
check("语言滤镜还在（僕的观测 / 结界的流向 / 魔女的气息 / 契约的窗口）",
      all(w in P for w in ("僕的观测", "结界的流向", "魔女的气息", "契约的窗口")))
check("披露层级必须服从主持指令", "指令说能透露什么就透露什么" in P)

# --- 反面检查：抒情词只能出现在「禁止/失败模式」语境里 ---
NEG_CTX = ("不说", "不使用", "不喊", "禁止", "失败模式", "错误")
for word in ("梦想", "热血", "值得"):
    hit_lines = [ln for ln in P.splitlines() if word in ln]
    check(f"「{word}」只出现在禁止语境",
          all(any(neg in ln for neg in NEG_CTX) for ln in hit_lines))

# --- 长度：太短会丢设定，太长会挤占上下文预算 ---
check("人设长度在 3500~8000 字之间", 3500 <= len(P) <= 8000)
check("没有残留的空段或双空行", "\n\n\n" not in P)

# --- 编码卫生：提示词里不应出现提示词自己的转义残留 ---
check("没有未闭合的 markdown 粗体标记", P.count("**") % 2 == 0)
check("没有 emoji", not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", P))

print()
print("结论: 人设骨架完整 ✅" if ok else "结论: 有断言失败 ❌")
sys.exit(0 if ok else 1)
