"""极简 Agent 内核：思考 -> 调工具 -> 观察 的循环。

运行前提：
  1. pip install -r requirements.txt
  2. 同级目录建 .env，写入 DEEPSEEK_API_KEY=sk-xxx
  3. python agent.py
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from tools import FUNCTIONS, TOOLS

# Windows 控制台默认 GBK，强制 UTF-8 避免打印 emoji/中文出错
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 先读“本脚本所在目录”的 .env（这样在任意目录下运行都能拿到 key），再兜底读当前目录的 .env
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("MODEL", "deepseek-v4-flash")

from persona import SYSTEM_PROMPT  # 人设与行为守则（换角色只改 persona.py）


def run_agent(question: str, max_steps: int = 10, history=None,
              return_history: bool = False, extra_system: str = ""):
    """主循环：每轮把模型回复（可能带 tool_calls）追加入 messages，
    执行工具并把结果以 role=tool 追加，直到模型给出纯文本答案。

    history：上一轮的对话记录（不含 system），传入即可实现多轮记忆；
    return_history=True 时返回 (答案, 更新后的history)；
    extra_system：额外的主持/规则指令（如 game.py 注入的局内状态），优先级高于人设。
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if extra_system:
        messages.append({"role": "system", "content": extra_system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    def _done(answer: str):
        return (answer, messages[1:]) if return_history else answer

    for step in range(max_steps):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        assistant_msg = resp.choices[0].message
        messages.append(assistant_msg)  # 保留其中的 tool_calls

        # 模型不再请求工具 -> 输出最终答案
        if not assistant_msg.tool_calls:
            return _done(assistant_msg.content or "(空回复)")

        # 逐个执行模型请求的工具
        for tc in assistant_msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"[step {step}] 调用工具: {name}({args})")
            result = FUNCTIONS[name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps({"result": result}, ensure_ascii=False),
            })

    return _done("已达最大步数，未得到最终答案。")


if __name__ == "__main__":
    # 结局玩法模式：python agent.py --game
    if "--game" in sys.argv:
        import game

        state = game.new_state()
        history = None
        print("\n【对局开始】孵化者·土木支线｜共 %d 轮，六个结局。输入 exit 退出。" % game.MAX_TURNS)
        print("提示：签约线/真相线/悲剧线/抗拒线/彩蛋线，任君选择。\n")
        while True:
            q = input("你 > ").strip()
            if q.lower() in ("exit", "quit"):
                break
            if not q:
                continue
            result = game.chat(q, history=history, state=state)
            history, state = result["history"], result["state"]
            print("\n" + game.state_brief(state))
            print(result["answer"] + "\n")
            if result["ending"]:
                print("=" * 58)
                print(f"【结局：{result['ending_title']}】{result['ending_tagline']}")
                print("=" * 58)
                again = input("再来一条时间线？(y/n) > ").strip().lower()
                if again == "y":
                    state, history = game.new_state(), None
                    print("\n【时间线重置】第十二次记录已归档。\n")
                else:
                    break
        sys.exit(0)

    # 支持命令行直接提问：python agent.py "你的问题"
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:]).strip()
        print("\n问题:", q)
        print("\n" + run_agent(q))
    else:
        while True:
            q = input("\n你问（输入 exit 退出）> ").strip()
            if q.lower() in ("exit", "quit"):
                break
            print("\n" + run_agent(q))
