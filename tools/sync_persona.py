"""把 persona.py 里的人设同步到 web/persona.js（单一数据源，避免两份提示词各改各的）。

用法：
    python tools/sync_persona.py          # 生成/更新 web/persona.js
    python tools/sync_persona.py --check  # 只校验是否同步（CI 用），不同步则退出码 1
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONA_PY = ROOT / "persona.py"
PERSONA_JS = ROOT / "web" / "persona.js"

HEADER = """// 本文件由 tools/sync_persona.py 从 persona.py 自动生成，请勿手工编辑。
// 要改人设：编辑 persona.py，然后运行 python tools/sync_persona.py
"""


def extract_prompt() -> str:
    source = PERSONA_PY.read_text(encoding="utf-8")
    match = re.search(r'SYSTEM_PROMPT\s*=\s*"""(.*?)"""', source, re.S)
    if not match:
        raise SystemExit("persona.py 里找不到 SYSTEM_PROMPT 三引号字符串")
    return match.group(1)


def to_js(prompt: str) -> str:
    # 模板字符串里需要转义的只有反引号与 ${ —— 其余中文原样保留
    body = prompt.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    return f'{HEADER}\nexport const SYSTEM_PROMPT = `{body}`;\n'


def main() -> int:
    js = to_js(extract_prompt())
    check = "--check" in sys.argv
    if check:
        current = PERSONA_JS.read_text(encoding="utf-8") if PERSONA_JS.exists() else ""
        # 换行符归一化比较：仓库统一存 LF，Windows 检出可能是 CRLF
        if current.replace("\r\n", "\n") != js:
            print("web/persona.js 与 persona.py 不同步，请运行：python tools/sync_persona.py")
            return 1
        print("web/persona.js 与 persona.py 同步")
        return 0
    PERSONA_JS.parent.mkdir(parents=True, exist_ok=True)
    # 固定 LF：避免 Windows 上生成 CRLF、导致与仓库/线上文件字节不一致
    with open(PERSONA_JS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(js)
    print(f"已写入 {PERSONA_JS.relative_to(ROOT)}（{len(js)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
