// 六结局触发测试（game.py / tests/test_endings.py 的 JS 版，不调用模型）
import { MAX_TURNS, checkEnding, newState, updateState } from "../game.js";

const CASES = {
  E_SIGN: ["我签！我愿意转专业去土木"],
  E_TRUTH: ["你到底图什么？你是什么东西", "你是不是在骗我，代价是什么",
            "孵化者？契约的代价是灵魂吗", "你隐瞒了什么，没把话说完吧"],
  E_DESPAIR: ["我怕", "我绝望了，撑不住", "我好痛苦，我哭了", "我难受，我撑不住了"],
  E_OTHER: ["我拒绝，我不转，别劝了", "我要学微电子，我已经决定学的",
            "我不签，滚，别劝了", "我要学计算机，选计算机"],
  E_REFORM: ["你自己去工地", "你去搬砖啊", "你也去学土木吧"],
  E_TIMELINE: ["嗯", "随便", "还行", "不知道", "哦", "也许吧",
               "再看", "嗯嗯", "无所谓", "哈哈", "可能", "再想想"],
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
s1.turn = MAX_TURNS;
if (checkEnding(s1) !== "E_TIMELINE") { console.log("FAIL 轮次上限未触发轮回结局"); failed += 1; }

const s2 = { ...newState(), contract: 80, ending: "E_SIGN" };
if (checkEnding(s2) !== "E_SIGN") { console.log("FAIL 结局锁定失效"); failed += 1; }

console.log(failed ? `\n${failed} 条不通过` : `\n全部 ${Object.keys(CASES).length} 条结局判定通过（JS 版）`);
process.exit(failed ? 1 : 0);
