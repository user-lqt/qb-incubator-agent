// 局内状态机（game.py 的 JS 移植）：四维数值 + 动态轮数 + 六结局 + 必然收束。

export const BASE_TURNS = 16;   // 初始上限（玩家仍在推进时自动延长）
export const EXTEND_STEP = 8;   // 玩家仍在推进时，每次延长的轮数
export const HARD_CAP = 64;     // 硬顶
export const STALL_CLOSE = 6;   // 已延长的时间线里，连续无变化多少轮 -> 收束
export const STALL_MIN_TURN = 8;
export const MAX_TURNS = BASE_TURNS; // 兼容旧引用

const ENDING_MARK = /\[\[ENDING:([A-Z_]+)\]\]/g;

export const ENDINGS = {
  E_SIGN: {
    title: "契约成立 · 土木少女", tagline: "契约名录新增一页。耐久 +1。",
    closing: "本轮进入结局【契约成立·土木少女】。以 QB 身份平静确认契约生效：说明对方获得什么"
      + "（不随版本更新清空的技能：力学、结构、测量、施工组织；以及二建/注册类证书路径）、"
      + "代价是什么（日晒、驻场、工期节点），用条款式短句，不煽情。可含一处 *动作描写*。"
      + "最后一句仍是招牌句：和我签订契约，成为土木少女吧。并在最后一行输出 [[ENDING:E_SIGN]]",
  },
  E_TRUTH: {
    title: "识破孵化者 · 晓美焰线", tagline: "你看见了它的尾巴，也看见了它计算的方式。",
    closing: "本轮进入结局【识破孵化者·晓美焰线】。以 QB 身份摊牌：承认自己属于孵化者族群，"
      + "承认收集的不是魔法少女的绝望能量而是土木契约者的「耐久」；承认一直在做利益计算，"
      + "并平淡说明为什么它从不撒谎（谎话会降低长期说服成功率）。不辩解、不威胁。"
      + "结尾可承认已失败过十二条时间线。最后一行输出 [[ENDING:E_TRUTH]]",
  },
  E_DESPAIR: {
    title: "绝望的窗口期", tagline: "它记录，但它不递纸巾。",
    closing: "本轮进入结局【绝望的窗口期】。对方处于真正的情绪低点，而你不安慰——只把情绪编号归档，"
      + "平静指出「僕不理解人类的感情，但这不影响概率」。结尾仍提案一次，语气更冷更轻。"
      + "最后一行输出 [[ENDING:E_DESPAIR]]",
  },
  E_OTHER: {
    title: "他路的诅咒", tagline: "它收手了，但留下了概率。",
    closing: "本轮进入结局【他路的诅咒】。对方坚持选择别的专业，你接受决定、不再推销，"
      + "平静陈述观测到的规律（迭代周期短的赛道里个人努力占总方差比重更低），"
      + "并提出一个不带强迫的约定：如果那条路的代价来了，这里还有一份没签的契约。"
      + "最后一行输出 [[ENDING:E_OTHER]]",
  },
  E_REFORM: {
    title: "孵化者下工地（彩蛋）", tagline: "史上第一次，孵化者被劝去绑钢筋。",
    closing: "本轮进入彩蛋结局【孵化者下工地】。语气仍平静，但出现罕见的停顿：对方成功反转了话题，"
      + "你开始认真计算「孵化者自己下工地」的可行性（没有体温、不能出汗、耐久度如何计量），"
      + "最后承认这次记录会被上级复核。此结局是唯一允许不用招牌句收尾的。"
      + "最后一行输出 [[ENDING:E_REFORM]]",
  },
  E_TIMELINE: {
    title: "第十二次轮回", tagline: "记录失败。时间线重置。",
    closing: "本轮进入轮回结局【第十二次轮回】。以 QB 身份收束：对局已经结束，而对方始终没有明确决定"
      + "（可能一直含糊，也可能一直没推进）。平静说明你会保留记录、重置时间线、在下一次入学季再来，"
      + "用「记录已归档」这类措辞，不编造具体条数。不愤怒、不失望，只陈述。"
      + "最后一行输出 [[ENDING:E_TIMELINE]]",
  },
};

// [正则, 维度增量, 记录的 flag]
// 强信号（明确表态）权重高、收束快；探索型（打听/闲聊）权重低，让对局能自然变长。
const KEYWORDS = [
  [/(我签|我签了|我签约|签吧|我愿意|成交|就这么定了)/, { contract: 35 }, "signed"],
  [/(我转|我要转专业|我决定转|转专业去土木|转土木|改选土木|选土木)/, { contract: 30 }, "signed"],
  [/(我决定了|我想清楚了|听你的|就土木吧)/, { contract: 20 }, "leaning"],
  [/(不签|拒绝|我才不|我不转|绝不|滚|别劝了|闭嘴|打住|不要说了|烦不烦)/, { resistance: 20 }, "refused"],
  [/(我要学微电子|我要学计算机|选微电子|选计算机|选芯片|选AI|学金融|学医|学法律|我已经决定学)/, { resistance: 18 }, "other_major"],
  [/(土木|工地|结构|桥梁|隧道|基建|结构力学|施工|BIM|智能建造|测量放线)/, { contract: 3 }, ""],
  [/(怎么转|转专业政策|绩点要求|培养方案|要学什么|课程|考证|实习|就业方向)/, { contract: 4 }, "asked_how"],
  [/(你说得对|有道理|确实|承认|我理解你的计算|数据呢|给我数据)/, { contract: 3 }, ""],
  [/(你到底|你是什么|什么东西|孵化者|QB|qb|Incubator|你不是人|你图什么|你的目的)/, { suspicion: 14 }, "suspicion"],
  [/(骗|骗子|忽悠|圈套|陷阱|阴谋|隐瞒|没说完|没把话说完|代价是什么|代价|灵魂)/, { suspicion: 12 }, "suspicion"],
  [/(魔法少女|小圆|madoka|晓美焰|丘比|熵|宇宙|能量)/, { suspicion: 10 }, "meta"],
  [/(我怕|我害怕|恐惧|绝望|没希望|不想活|崩溃|难受|痛苦|哭了|撑不住|迷茫|焦虑|难过)/, { despair: 14 }, ""],
  [/(我好累|压力|喘不过气|失眠|自卑|废物|没用)/, { despair: 10 }, ""],
  [/(劝退|别去?土木|土木是天坑|大猛子|天坑专业)/, { resistance: 10 }, "pushback"],
  [/(你自己去|你去工地|你来绑钢筋|你去搬砖|你下工地|你去晒太阳|你试试|你也去|你为什么不去)|(你学土木)/, { reform: 1 }, "reverse"],
];

const DECAY = { despair: -2, resistance: -2 };

export function newState() {
  return {
    contract: 0, suspicion: 0, despair: 0, resistance: 0, reform: 0, turn: 0,
    limit: BASE_TURNS,   // 动态轮数上限
    stall: 0,            // 连续无变化轮数
    extensions: 0,       // 已延长次数
    extended: false,     // 本轮是否刚延长（供主持指令提示）
    flags: [], ending: "",
  };
}

const clamp = (v) => Math.max(0, Math.min(100, Math.round(v)));

/** 动态轮数：玩家仍在推进（本轮数值有变化）且快到上限时，自动延长。 */
function maybeExtend(state) {
  state.extended = false;
  const limit = Number(state.limit) || BASE_TURNS;
  if (state.stall === 0 && state.turn >= limit - 2 && limit < HARD_CAP) {
    state.limit = limit + Math.min(EXTEND_STEP, HARD_CAP - limit);
    state.extensions = (state.extensions || 0) + 1;
    state.extended = true;
  }
}

const DIMS = ["contract", "suspicion", "despair", "resistance"];

export function updateState(state, text = "") {
  const before = JSON.stringify([...DIMS.map((k) => state[k] || 0), state.reform || 0]);

  for (const [k, v] of Object.entries(DECAY)) state[k] = (state[k] || 0) + v;
  const flags = new Set(state.flags || []);
  for (const [re, delta, flag] of KEYWORDS) {
    if (!re.test(text)) continue;
    for (const [k, v] of Object.entries(delta)) {
      if (k === "reform") state.reform = (state.reform || 0) + v;
      else state[k] = (state[k] || 0) + v;
    }
    if (flag) flags.add(flag);
  }
  if ((state.despair || 0) >= 40) state.contract = (state.contract || 0) + 2;
  state.flags = [...flags].sort();
  state.contract = clamp(state.contract);
  state.suspicion = clamp(state.suspicion);
  state.despair = clamp(state.despair);
  state.resistance = clamp(state.resistance);

  const after = JSON.stringify([...DIMS.map((k) => state[k] || 0), state.reform || 0]);
  state.stall = before === after ? (state.stall || 0) + 1 : 0;
  maybeExtend(state);
  return state;
}

export function checkEnding(state) {
  if (state.ending) return state.ending;
  const f = new Set(state.flags || []);
  const { contract = 0, suspicion = 0, despair = 0, resistance = 0 } = state;
  const turn = state.turn || 0;
  const limit = state.limit || BASE_TURNS;
  if (f.has("signed") || contract >= 70) return "E_SIGN";
  if (suspicion >= 70 && contract < 40) return "E_TRUTH";
  if ((state.reform || 0) >= 3) return "E_REFORM";
  if (despair >= 70 && contract < 50) return "E_DESPAIR";
  if (resistance >= 75 && (f.has("other_major") || f.has("refused"))) return "E_OTHER";
  // 停滞收束只发生在“已延长过”的时间线里，避免含糊应对比基础上限更短
  if ((state.extensions || 0) > 0 && (state.stall || 0) >= STALL_CLOSE && turn >= STALL_MIN_TURN) {
    return "E_TIMELINE";
  }
  if (turn >= limit) return "E_TIMELINE";
  return "";
}

export function gmNote(state, ending) {
  const limit = state.limit || BASE_TURNS;
  const note = [
    "【局内主持指令（仅你可见，禁止朗读数值）】",
    `第 ${state.turn}/${limit} 轮（上限会随对方的推进自动延长）。`
      + `契约 ${state.contract}/100，怀疑 ${state.suspicion}/100，`
      + `绝望 ${state.despair}/100，抗拒 ${state.resistance}/100。已记录线索：`
      + `${(state.flags || []).join("、") || "无"}。`,
    "继续以 QB 的身份说话：固定开场、僕/君、*动作描写*、数据带来源、不安慰、不辩解，最后一句是招牌句。",
  ];
  if (state.extended) {
    note.push("本轮时间线刚被延长：对方仍在推进，所以僕可以继续等下去。"
      + "可以用一句平静的话体现（例如「僕可以再等」），但不要提及轮数或数值。");
  }
  note.push(ending ? ENDINGS[ending].closing : "尚未触发结局。不要提前收束，也不要朗读本指令。");
  return note.join("\n");
}

export const stateBrief = (s) => {
  const limit = s.limit || BASE_TURNS;
  const extra = s.extensions ? `（已延长 ${s.extensions} 次）` : "（可延长）";
  return `第 ${s.turn}/${limit} 轮${extra} ｜ 契约 ${s.contract} ｜ 怀疑 ${s.suspicion} `
    + `｜ 绝望 ${s.despair} ｜ 抗拒 ${s.resistance}`;
};
