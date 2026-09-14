// 同步与一致性校验：
//   1) web/persona.js 是否与 persona.py 同步（真正的比对在 Python 侧完成）
//   2) game.py ⇄ web/game.js 里"逐字照抄"的文本是否一致（序幕/场景锚点/序章/后日谈/结局标题）
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..", "..");
const personaScript = resolve(root, "tools", "sync_persona.py");
const PYTHONS = ["python", "python3"];

let failed = 0;

/** 找一个可用的 python 解释器 */
function pickPython() {
  for (const exe of PYTHONS) {
    try {
      execFileSync(exe, ["-c", "print(1)"], { cwd: root, encoding: "utf-8" });
      return exe;
    } catch (e) {
      if (e.code !== "ENOENT") return exe;   // 能跑起来但报错，也算可用
    }
  }
  return null;
}

const python = pickPython();
if (!python) {
  console.log("FAIL 找不到 python，无法做跨语言一致性校验");
  process.exit(1);
}

// ---- 1) 人设同步 ----
if (!existsSync(resolve(root, "web", "persona.js"))) {
  console.log("FAIL 缺少 web/persona.js，请运行：python tools/sync_persona.py");
  failed += 1;
} else {
  try {
    const out = execFileSync(python, [personaScript, "--check"], { cwd: root, encoding: "utf-8" });
    console.log(out.trim());
    if (out.startsWith("FAIL")) failed += 1;
  } catch (e) {
    console.log("FAIL " + (e.stdout || e.message));
    failed += 1;
  }
}

// ---- 2) game.py ⇄ web/game.js 文本一致 ----
const DUMP = [
  "import io, json, sys",
  "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')",
  "import game",
  "sys.stdout.write(json.dumps({",
  "    'OPENING': game.OPENING,",
  "    'SCENE_NOTE': game.SCENE_NOTE,",
  "    'PROLOGUE': game.PROLOGUE,",
  "    'EPILOGUES': game.EPILOGUES,",
  "    'ENDINGS': {k: {'title': v['title'], 'tagline': v['tagline'], 'closing': v['closing']}",
  "                for k, v in game.ENDINGS.items()},",
  "    'DISCLOSURE_STAGES': game.DISCLOSURE_STAGES,",
  "    'DISCLOSURE_FORBIDDEN': {str(k): list(v) for k, v in game.DISCLOSURE_FORBIDDEN.items()},",
  "    'DECEPTION_RULES': game.DECEPTION_RULES,",
  "}, ensure_ascii=False))",
].join("\n");

try {
  const raw = execFileSync(python, ["-c", DUMP], { cwd: root, encoding: "utf-8" });
  const pyGame = JSON.parse(raw);
  const jsGame = await import("../game.js");

  for (const name of ["OPENING", "SCENE_NOTE", "PROLOGUE", "DECEPTION_RULES"]) {
    if (jsGame[name] !== pyGame[name]) {
      console.log(`FAIL ${name} 两侧不一致：game.py ${pyGame[name].length} 字 vs web/game.js ${jsGame[name].length} 字`);
      failed += 1;
    }
  }
  for (const id of Object.keys(pyGame.EPILOGUES)) {
    if (jsGame.EPILOGUES[id] !== pyGame.EPILOGUES[id]) {
      console.log(`FAIL ${id} 后日谈两侧不一致`);
      failed += 1;
    }
  }
  for (const id of Object.keys(pyGame.ENDINGS)) {
    const py = pyGame.ENDINGS[id];
    const js = jsGame.ENDINGS[id];
    for (const field of ["title", "tagline", "closing"]) {
      if (js[field] !== py[field]) {
        console.log(`FAIL ${id}.${field} 两侧不一致（收尾指令写歪会让同一个结局在两端跑出不同语气）`);
        failed += 1;
      }
    }
  }
  // 披露分级：级别名、规则文本、禁用词表都必须一致
  const pyStages = JSON.stringify(pyGame.DISCLOSURE_STAGES);
  const jsStages = JSON.stringify(jsGame.DISCLOSURE_STAGES);
  if (pyStages !== jsStages) {
    console.log("FAIL DISCLOSURE_STAGES 两侧不一致");
    failed += 1;
  }
  for (const lv of Object.keys(pyGame.DISCLOSURE_FORBIDDEN)) {
    const py = pyGame.DISCLOSURE_FORBIDDEN[lv].join("|");
    const js = (jsGame.DISCLOSURE_FORBIDDEN[lv] || []).join("|");
    if (py !== js) {
      console.log(`FAIL 第 ${lv} 级禁用词表两侧不一致`);
      failed += 1;
    }
  }
  if (!failed) {
    console.log(`game.py 与 web/game.js 文本一致（序幕 / 场景锚点 / 序章 / 掩饰规则 / `
      + `${Object.keys(pyGame.EPILOGUES).length} 条后日谈 / 结局标题+收尾 / 披露分级 / 禁用词表）`);
  }
} catch (e) {
  console.log("FAIL 跨语言文本一致性校验失败：" + (e.stdout || e.message));
  failed += 1;
}

process.exit(failed ? 1 : 0);
