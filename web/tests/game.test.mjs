// 六结局触发测试（game.py / tests/test_endings.py 的 JS 版，不调用模型）
import { BASE_TURNS, DELTA_LIMIT, EXTEND_STEP, HARD_CAP, PROLOGUE, RESOLVE_AT, checkEnding, describeDelta, newState, updateState,
         parseStateMarker, applyModelState, snapshotOf, applyTurnState, tension, gmNote,
         disclosureStage, detectLeak, parseChoices, fallbackChoices } from "../game.js";

const CASES = {
  E_SIGN: ["我签！我愿意转专业去土木"],
  E_TRUTH: ["你到底图什么？你是什么东西", "你是不是在骗我，代价是什么",
            "孵化者？契约的代价是灵魂吗", "你隐瞒了什么，没把话说完吧",
            "你的目的是什么", "你是不是在骗我，你的目的"],
  E_DESPAIR: ["我怕", "我绝望了，撑不住", "我好痛苦，我哭了", "我难受，我撑不住了",
              "我不想活了，我绝望了", "我好累，我撑不住"],
  E_OTHER: ["我拒绝，我不转，别劝了", "我要学微电子，我已经决定学的",
            "我不签，滚，别劝了", "我要学计算机，选计算机", "我不签，别劝了"],
  E_REFORM: ["你自己去工地", "你去搬砖啊", "你也去学土木吧"],
  E_TIMELINE: ["嗯", "随便", "还行", "不知道", "哦", "也许吧",
               "再看", "嗯嗯", "无所谓", "哈哈", "可能", "再想想",
               "嗯", "随便", "还行", "不知道"],
};

let failed = 0;
for (const [expected, lines] of Object.entries(CASES)) {
  const state = newState();
  let got = "";
  for (const line of lines) {
    state.turn += 1;
    updateState(state, line);
    got = checkEnding(state);
    if (got) break;
  }
  const ok = got === expected;
  if (!ok) failed += 1;
  console.log(`[${ok ? "OK " : "FAIL"}] 期望 ${expected.padEnd(11)} 实际 ${(got || "（未触发）").padEnd(11)} `
    + `轮次 ${state.turn} | 契约 ${state.contract} 怀疑 ${state.suspicion} `
    + `绝望 ${state.despair} 抗拒 ${state.resistance} 反向 ${state.reform}`);
}

// 附加断言
const s1 = newState();
s1.turn = s1.limit;
if (checkEnding(s1) !== "E_TIMELINE") { console.log("FAIL 到达动态上限未触发轮回结局"); failed += 1; }

const s2 = { ...newState(), contract: 80, ending: "E_SIGN" };
if (checkEnding(s2) !== "E_SIGN") { console.log("FAIL 结局锁定失效"); failed += 1; }

// 动态轮数：接近上限时仍在推进 -> 延长；延长后停滞后 -> 收束
const s3 = { ...newState(), turn: BASE_TURNS - 2, limit: BASE_TURNS };
updateState(s3, "土木的课程难吗");
if (s3.limit !== BASE_TURNS + EXTEND_STEP || s3.extensions !== 1) {
  console.log(`FAIL 动态延长失效：limit=${s3.limit} extensions=${s3.extensions}`
    + `（应为 ${BASE_TURNS + EXTEND_STEP}/1）`);
  failed += 1;
}

const s4 = newState();
for (let i = 1; i <= 8; i += 1) { s4.turn = i; updateState(s4, "嗯"); }
if (checkEnding(s4)) { console.log(`FAIL 未延长的对局不应提前收束，实际=${checkEnding(s4)}`); failed += 1; }

const s5 = { ...newState(), turn: 11, limit: 20, extensions: 1 };
for (let i = 12; i <= 22; i += 1) {
  s5.turn = i;
  updateState(s5, "嗯");
  if (checkEnding(s5)) break;
}
if (checkEnding(s5) !== "E_TIMELINE") { console.log("FAIL 延长后停滞未收束"); failed += 1; }

const s6 = { ...newState(), limit: HARD_CAP, turn: HARD_CAP };
updateState(s6, "土木的课程难吗");
if (s6.limit !== HARD_CAP) { console.log(`FAIL 硬顶失效：limit=${s6.limit}`); failed += 1; }

// 误判回归：「被劝着签/转」不能算作自己签约
for (const line of ["你为什么一直劝我签约", "学长让我转专业，我很犹豫", "父母想让我签约那种契约"]) {
  const st = { ...newState(), turn: 1 };
  updateState(st, line);
  if (checkEnding(st) || st.flags.includes("signed")) {
    console.log(`FAIL 「${line}」被误判为签约`); failed += 1;
  }
}
for (const line of ["我签！", "我愿意签约", "我决定转专业去土木"]) {
  const st = { ...newState(), turn: 1 };
  updateState(st, line);
  if (checkEnding(st) !== "E_SIGN") { console.log(`FAIL 「${line}」未被识别为签约`); failed += 1; }
}

// 识别准确性回归：否定句、泛化词、贬土木、无关声明
const ACCURACY = [
  ["我不愿意签约", []],
  ["我不喜欢工地", []],
  ["我怕", ["despair"]],
  ["我不怕，土木挺好的", ["contract"]],
  ["土木是什么东西", ["contract"]],
  ["你是什么东西", ["suspicion"]],
  ["我想学新能源", []],
  ["我怕以后失业，但土木是垃圾", ["despair", "resistance"]],
  ["我学数据结构，跟土木无关", []],
  ["我还没想清楚", []],
  ["别劝了，我不签", ["resistance"]],
];
for (const [text, expect] of ACCURACY) {
  const st = { ...newState(), turn: 1 };
  updateState(st, text);
  const changed = ["contract", "suspicion", "despair", "resistance"].filter((k) => st[k] !== 0).sort();
  const want = [...expect].sort();
  if (JSON.stringify(changed) !== JSON.stringify(want)) {
    console.log(`FAIL 识别不准：「${text}」期望 ${want} 实际 ${changed}`); failed += 1;
  }
  if (st.flags.includes("signed")) { console.log(`FAIL 「${text}」被判为已签约`); failed += 1; }
}

// 敏感度回归
const sens = { ...newState(), turn: 1 };
updateState(sens, "土木怎么样？我想了解一下就业方向");
if (sens.contract < 10) { console.log(`FAIL 好感权重过小：contract=${sens.contract}`); failed += 1; }

// describeDelta：界面上的"本轮变化"提示
const before = { ...newState(), turn: 1 };
const after = { ...before, turn: 2, contract: 7, suspicion: 0 };
const line1 = describeDelta(before, after);
if (!line1.includes("契约 +7") || !line1.includes("第 2/")) {
  console.log(`FAIL describeDelta 变化行不正确：${line1}`); failed += 1;
}
const line2 = describeDelta({ ...after }, { ...after, turn: 3, stall: 2 });
if (!line2.includes("无变化")) { console.log(`FAIL describeDelta 无变化行不正确：${line2}`); failed += 1; }

// ---- 语义评分：解析、容错、钳制、覆盖关键词 ----
const [clean, parsed] = parseStateMarker('僕这样说。[[STATE:{"contract":8,"flags":["asked_how"]}]]');
if (clean !== "僕这样说。" || parsed?.contract !== 8) {
  console.log(`FAIL 评分标记解析：clean=${JSON.stringify(clean)} data=${JSON.stringify(parsed)}`); failed += 1;
}
const [, badParsed] = parseStateMarker("嗯。[[STATE:{不是json}]]");
if (badParsed !== null) { console.log("FAIL 坏 JSON 应当返回 null"); failed += 1; }

const pre = { contract: 0, suspicion: 0, despair: 0, resistance: 0, reform: 0, flags: [] };
const st = { ...newState(), turn: 1 };
updateState(st, "土木的课程难吗");                       // 关键词会给 +18
if (st.contract < 10) { console.log(`FAIL 关键词兜底未生效：${st.contract}`); failed += 1; }
applyModelState(st, pre, { contract: 3, flags: [] });    // 模型说只 +3
if (st.contract !== 3) { console.log(`FAIL 模型评分未覆盖关键词：${st.contract}（应为 3）`); failed += 1; }

applyModelState(st, pre, { contract: 999, suspicion: -999, flags: ["hack", "signed"] });
if (st.contract !== DELTA_LIMIT || st.suspicion !== 0 || st.flags.includes("hack")) {
  console.log(`FAIL 钳制/白名单失效：${st.contract} ${st.suspicion} ${JSON.stringify(st.flags)}`);
  failed += 1;
}

const st3 = { ...newState(), turn: 1 };
updateState(st3, "土木的课程难吗", { contract: 2, suspicion: 20, despair: 0, resistance: 0, flags: ["suspicion"] });
if (st3.contract !== 2 || st3.suspicion !== 20) {
  console.log(`FAIL 混合调用应以模型为准：${st3.contract}/${st3.suspicion}`); failed += 1;
}

const st4 = { ...newState(), turn: 1 };
const snap4 = snapshotOf(st4);
applyTurnState(st4, snap4, { contract: 10, suspicion: 0, despair: 0, resistance: 0, flags: [] });
if (st4.contract !== 10 || st4.stall !== 0) {
  console.log(`FAIL applyTurnState 未正确应用：${st4.contract} stall=${st4.stall}`); failed += 1;
}

// ---- 分级披露：级别判定、禁用词、越级检测 ----
if (!PROLOGUE || PROLOGUE.length > 120
    || ["孵化者", "耐久", "相变", "时间线", "能量"].some((w) => PROLOGUE.includes(w))) {
  console.log("FAIL 序章不应剧透世界观或过长"); failed += 1;
}
const STAGE_CASES = [
  [{ suspicion: 0, turn: 1, contract: 0 }, 1],
  [{ suspicion: 0, turn: 5, contract: 0 }, 2],
  [{ suspicion: 25, turn: 3, contract: 0 }, 2],
  [{ suspicion: 45, turn: 9, contract: 0 }, 3],
  [{ suspicion: 70, turn: 13, contract: 0 }, 4],
];
for (const [patch, expect] of STAGE_CASES) {
  const got = disclosureStage({ ...newState(), ...patch });
  if (got !== expect) { console.log(`FAIL 披露级别 ${JSON.stringify(patch)} 期望 ${expect} 实际 ${got}`); failed += 1; }
}
if (detectLeak("僕是孵化者。", 1).length !== 1) { console.log("FAIL 第 1 级应禁用'孵化者'"); failed += 1; }
if (detectLeak("僕是孵化者。", 2).length !== 1) { console.log("FAIL 第 2 级仍应禁用'孵化者'（挤牙膏）"); failed += 1; }
if (detectLeak("僕是孵化者族群的一员。", 3).length !== 0) { console.log("FAIL 第 3 级应允许承认出身"); failed += 1; }
if (detectLeak("希望到绝望的相变。", 3).length === 0) { console.log("FAIL 第 3 级应禁用'相变'"); failed += 1; }
if (detectLeak("代价是日晒、驻场、工期节点。", 3).length !== 0) { console.log("FAIL 第 3 级应允许代价三项"); failed += 1; }
if (detectLeak("孵化者收集能量，形成耐久。", 4).length !== 0) { console.log("FAIL 第 4 级应无限制"); failed += 1; }
if (!gmNote(newState(), "").includes("真话、半真话与掩饰")) {
  console.log("FAIL 掩饰规则未注入主持指令"); failed += 1;
}

// ---- 对话选项：对象格式解析 + 倾向 + 兜底 ----
const [cleanCh, chs] = parseChoices(
  '僕这样说。[[STATE:{"contract":1}]]\n'
  + '[[CHOICES:[{"t":"继续问","d":"suspicion"},{"t":"我考虑一下","d":"contract"}]]]');
if (cleanCh.includes("CHOICES") || chs.length !== 2
    || chs[0].text !== "继续问" || chs[0].dir !== "suspicion" || chs[1].dir !== "contract") {
  console.log(`FAIL 选项解析失败：clean=${JSON.stringify(cleanCh)} chs=${JSON.stringify(chs)}`); failed += 1;
}
const [, legacyCh] = parseChoices('[[CHOICES:["纯字符串也认","第二条"]]]');
if (legacyCh.length !== 2 || legacyCh[0].text !== "纯字符串也认" || legacyCh[0].dir !== "") {
  console.log("FAIL 纯字符串选项兼容失败"); failed += 1;
}
const [, badDirCh] = parseChoices('[[CHOICES:[{"t":"越界","d":"hack"}]]]');
if (badDirCh[0].dir !== "") { console.log("FAIL 非法倾向应被清空"); failed += 1; }
const [, badCh] = parseChoices("嗯[[CHOICES:[不是数组}]]");
if (badCh.length !== 0) { console.log("FAIL 坏选项应返回空数组"); failed += 1; }
for (let st = 1; st <= 4; st += 1) {
  const fb = fallbackChoices({ ...newState(), suspicion: st >= 4 ? 70 : st === 3 ? 45 : st === 2 ? 25 : 0, turn: 1 });
  if (fb.length < 3 || fb.length > 4 || fb.some((c) => !c.text || !c.dir)) {
    console.log(`FAIL 第 ${st} 级兜底选项异常：${JSON.stringify(fb)}`); failed += 1;
  }
}

// ---- 节奏：紧张度 ----
if (tension(newState()) !== 0) { console.log("FAIL 空局势紧张度应为 0"); failed += 1; }
const mid = { ...newState(), contract: RESOLVE_AT.contract / 2 };
if (!(tension(mid) > 0.4 && tension(mid) < 0.6)) { console.log(`FAIL 半程紧张度异常：${tension(mid)}`); failed += 1; }
if (tension({ ...newState(), suspicion: RESOLVE_AT.suspicion }) !== 1) {
  console.log("FAIL 到阈值紧张度应为 1"); failed += 1;
}

// 畸形标记容错（模型经常少写一个右括号）
const MALFORMED = [
  '正文。[[CHOICES:["甲","乙","丙"]]',      // 少一个 ]
  '正文。[[CHOICES:["甲","乙"]]]]',         // 多一个 ]
  '正文。[[STATE:{"contract":5}]',          // STATE 少一个 ]
  '正文。[[STATE:{"contract":5}]]]',
];
for (const text of MALFORMED) {
  const [clean1] = parseStateMarker(text);
  const [clean2, chs] = parseChoices(clean1);
  const leftover = ["[[STATE", "[[CHOICES", "]]"].filter((t) => clean2.includes(t));
  if (leftover.length) { console.log(`FAIL 畸形标记残留：${text} -> ${leftover}`); failed += 1; }
  if (text.includes("CHOICES") && !text.includes("少一个") && chs.length < 2) {
    console.log(`FAIL 畸形选项未解析：${text} -> ${chs.length} 条`); failed += 1;
  }
}

console.log(failed ? `\n${failed} 条不通过` : `\n全部 ${Object.keys(CASES).length} 条结局判定 + 动态轮数断言通过（JS 版）`);
process.exit(failed ? 1 : 0);
