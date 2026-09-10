// 动态轮数冒烟：连续 15 轮“温和推进”，观察上限是否延长、结局是否更晚到来。
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { QBClient } from "../agent.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const env = readFileSync(resolve(root, ".env"), "utf-8");
const key = (env.match(/^\s*DEEPSEEK_API_KEY\s*=\s*(.+)$/m) || [])[1]?.trim();
if (!key || !process.env.RUN_SMOKE) {
  console.log("跳过（需要 .env 里的 key，并设置 RUN_SMOKE=1 才跑真模型）");
  process.exit(0);
}

const client = new QBClient({ apiKey: key, model: "deepseek-chat" });
const rounds = [
  "土木的课程难吗",
  "你说得对，有道理",
  "土木的就业方向有哪些",
  "工地上的实习能学到什么",
  "考建造师需要什么条件",
  "结构力学难不难",
  "智能建造是做什么的",
  "土木的课程难吗",
  "你说得对，有道理",
  "土木的就业方向有哪些",
];

for (const q of rounds) {
  const r = await client.turn(q);
  const s = r.state;
  const ext = s.extensions ? `已延长 ${s.extensions} 次` : "未延长";
  console.log(`第 ${s.turn}/${s.max_turns} 轮（${ext}）｜契约 ${s.contract} 怀疑 ${s.suspicion} `
    + `绝望 ${s.despair} 抗拒 ${s.resistance}${r.ending ? ` ｜结局 ${r.ending_title}` : ""}`);
  if (r.ending) {
    console.log(r.answer.slice(0, 220));
    break;
  }
}
