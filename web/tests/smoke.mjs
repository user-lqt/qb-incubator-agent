// 手动冒烟测试（会真实调用模型，消耗少量额度，CI 不跑）：
//   node web/tests/smoke.mjs
// key 取自环境变量 QB_KEY，或上一级目录的 .env（DEEPSEEK_API_KEY）。
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { QBClient } from "../agent.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadKey() {
  if (process.env.QB_KEY) return process.env.QB_KEY.trim();
  try {
    const env = readFileSync(resolve(root, ".env"), "utf-8");
    const m = env.match(/^\s*DEEPSEEK_API_KEY\s*=\s*(.+)$/m);
    if (m) return m[1].trim().replace(/^["']|["']$/g, "");
  } catch { /* 忽略 */ }
  return "";
}

const apiKey = loadKey();
if (!apiKey) {
  console.log("跳过：未找到 key（设置 QB_KEY 或写好 .env 后再跑）");
  process.exit(0);
}

const client = new QBClient({ apiKey, model: process.env.QB_MODEL || "deepseek-chat" });

const rounds = ["明天适合去工地吗？", "我签！我愿意转专业去土木"];
for (const q of rounds) {
  const t0 = Date.now();
  const r = await client.turn(q);
  const secs = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(`\n===== 你说：${q}（${secs}s）=====`);
  console.log(`状态：第 ${r.state.turn}/${r.state.max_turns} 轮 ｜ 契约 ${r.state.contract} `
    + `怀疑 ${r.state.suspicion} 绝望 ${r.state.despair} 抗拒 ${r.state.resistance}`);
  console.log(`回答（${r.answer.length} 字）：\n${r.answer.slice(0, 400)}${r.answer.length > 400 ? "……" : ""}`);
  if (r.ending) console.log(`>>> 结局：${r.ending_title} —— ${r.ending_tagline}`);
}
console.log("\n冒烟测试完成：浏览器版内核（fetch + 工具循环 + 玩法收束）工作正常。");
