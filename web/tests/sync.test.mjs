// 校验 web/persona.js 是否与 persona.py 同步（真正的比对在 Python 侧完成）
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..", "..");
const script = resolve(root, "tools", "sync_persona.py");

if (!existsSync(resolve(root, "web", "persona.js"))) {
  console.log("FAIL 缺少 web/persona.js，请运行：python tools/sync_persona.py");
  process.exit(1);
}

try {
  let out = "";
  for (const py of ["python", "python3"]) {
    try {
      out = execFileSync(py, [script, "--check"], { encoding: "utf-8" });
      break;
    } catch (e) {
      out = "FAIL " + (e.stdout || e.message);
    }
  }
  console.log(out.trim());
  if (out.startsWith("FAIL")) process.exit(1);
} catch (e) {
  console.log("FAIL " + (e.stdout || e.message));
  process.exit(1);
}
