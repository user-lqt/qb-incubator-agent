// 局内状态机（game.py 的 JS 移植）：四维数值 + 动态轮数 + 六结局 + 必然收束。

export const BASE_TURNS = 12;   // 初始上限（节奏更快；推进可延长）
export const EXTEND_STEP = 6;   // 玩家仍在推进时，每次延长的轮数
export const HARD_CAP = 48;     // 硬顶
export const STALL_CLOSE = 5;   // 已延长的时间线里，连续无变化多少轮 -> 收束
export const STALL_MIN_TURN = 6;
export const MAX_TURNS = BASE_TURNS; // 兼容旧引用

// 各维度的"达成结局"阈值：越低节奏越快
export const RESOLVE_AT = { contract: 72, suspicion: 68, despair: 68, resistance: 72 };

/** 剧情推进度 0~1：取四个维度里最接近"达成结局"的那个 */
export function tension(state) {
  let best = 0;
  for (const [key, need] of Object.entries(RESOLVE_AT)) {
    best = Math.max(best, Math.min(1, (Number(state[key]) || 0) / need));
  }
  return Math.round(best * 1000) / 1000;
}

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

// [正则, 维度增量, 记录的 flag, 是否做否定判断, 是否属于"土木好感"组]
// 第 5 位为 true 的条目：本轮若在贬低土木，则不计分（判定用的第 5 位是显式的，避免靠正则猜）
const KEYWORDS = [
  [/(我签|我签了|我签约|签吧|我愿意|成交|就这么定了)/, { contract: 35 }, "signed", true, false],
  [/(我转|我要转专业|我决定转|转专业去土木|转土木|改选土木|选土木)/, { contract: 30 }, "signed", true, false],
  [/(我决定了|我想清楚了|听你的|就土木吧)/, { contract: 20 }, "leaning", true, false],
  [/(不签|拒绝|我才不|我不转|绝不|滚|别劝了|闭嘴|打住|不要说了|烦不烦)/, { resistance: 26 }, "refused", false, false],
  [/(我要学微电子|我要学计算机|选微电子|选计算机|选芯片|选AI|学金融|学医|学法律|我已经决定学)/,
    { resistance: 24 }, "other_major", false, false],
  [/(土木|工地|基建|施工|钢筋混凝土)[^。！？\n]{0,6}(垃圾|天坑|坑人|不行|没用|凉了|劝退|失业|裁员|没前途)|别去?土木|土木是天坑|大猛子|天坑专业/,
    { resistance: 18 }, "pushback", false, false],
  // 好感与打听（属于好感组）——关键词只作兜底，权重压低，让"打字"路径约 6~8 轮收束
  [/(土木|工地|桥梁|隧道|基建|结构力学|钢筋混凝土|钢结构|施工|BIM|智能建造|测量放线)/,
    { contract: 5 }, "", true, true],
  [/(怎么转|转专业|转系|绩点要求|培养方案|要学什么|课程|考证|建造师|实习|就业方向|就业率|薪资|岗位)/,
    { contract: 6 }, "asked_how", true, true],
  [/(你说得对|有道理|确实|承认|我理解你的计算|数据呢|给我数据|靠谱|稳定|挺好|不错|感兴趣|心动|想了解|帮我看看)/,
    { contract: 5 }, "", true, false],
  [/(你到底|你是什么|你(是|到底|究竟)?[^。！？\n]{0,4}什么东西|孵化者|QB|qb|Incubator|你不是人|你图什么|你的目的)/,
    { suspicion: 20 }, "suspicion", true, false],
  [/(骗|骗子|忽悠|圈套|陷阱|阴谋|隐瞒|没说完|没把话说完|代价是什么|代价|灵魂|契约的代价|契约.*条件)/,
    { suspicion: 16 }, "suspicion", true, false],
  [/(魔法少女|小圆|madoka|晓美焰|丘比|灵魂宝石|结界|熵)/, { suspicion: 14 }, "meta", true, false],
  [/(我怕|我害怕|我好怕|恐惧|绝望|没希望|不想活|崩溃|难受|痛苦|哭了|撑不住|迷茫|焦虑|难过|撑不下去)/,
    { despair: 20 }, "", true, false],
  [/(我好累|压力大|有压力|喘不过气|失眠|自卑|我是废物|我(真)?没用)/, { despair: 14 }, "", true, false],
  [/(你自己去|你去工地|你来绑钢筋|你去搬砖|你下工地|你去晒太阳|你试试|你也去|你为什么不去)|(你学土木)/,
    { reform: 1 }, "reverse", true, false],
];

// 否定词：命中正向关键词但前面有这些词 -> 判定为否定，不计分
const NEGATORS = ["不", "没", "别", "未", "无", "非", "懒得", "拒绝", "从不", "绝不", "不想", "不用"];

const CIVIL_NEGATIVE = /(土木|工地|基建|施工|钢筋混凝土)[^。！？\n]{0,6}(垃圾|天坑|坑人|不行|没用|凉了|劝退|失业|裁员|没前途)|别去?土木|土木是天坑|大猛子|天坑专业|(跟|和|与)[^。！？\n]{0,4}土木[^。！？\n]{0,6}(无关|没关系|不相关)/;

function isNegated(text, start, window = 4) {
  const prefix = text.slice(Math.max(0, start - window), start);
  return NEGATORS.some((n) => prefix.includes(n));
}

// 开场：不在第一句就把世界观与目的倒出来（原作里丘比也是逐步才被逼出真相的）
export const PROLOGUE = `嗯——

*歪头* 僕在这里。君是第一个停下脚步的人。

僕可以替君实现一个愿望。任何愿望——只要君说出口。

*尾巴轻轻摆了一下* 其余的，君以后会知道的。`;

// 信息披露分级：丘比不撒谎，但也从不主动说明，真相是被一层层追问出来的
export const DISCLOSURE_STAGES = [
  [1, "初次接触",
    "只谈愿望，以及君当下的处境。**不要承认自己不是人类**，也不要解释自己是什么、"
    + "不提契约的代价、不提耐久/相变/时间线。被追问就平静地挡回去："
    + "「僕是什么，对君现在的选择没有影响。」「僕可以回答。但不是现在。」"],
  [2, "出现疑点",
    "最多承认「僕不完全属于人类的范畴」「僕不是从这里来的」，"
    + "但**不要说出「孵化者」这个词**，也不说代价的具体内容。"
    + "被逼到墙角时只退一小步，然后把话题拨回愿望。"],
  [3, "勉强承认出身",
    "可以承认自己是「孵化者族群的一员」，也可以说出代价的三项（日晒、驻场、工期节点）；"
    + "仍然不提能量、相变、耐久、十二条时间线。被问就答一半：「僕可以说的部分是这样……」"],
  [4, "摊牌",
    "可以全盘说明：孵化者收集的能量、希望与绝望的相变、耐久、城市的骨相、"
    + "以及十二条失败的时间线。"],
];

// 每级"说了就算越级"的词表
export const DISCLOSURE_FORBIDDEN = {
  1: ["孵化者", "能量", "相变", "耐久", "时间线", "宇宙", "城市的骨相", "灵魂", "族群"],
  2: ["孵化者", "能量", "相变", "耐久", "时间线", "城市的骨相", "灵魂", "族群"],
  3: ["能量", "相变", "耐久", "时间线", "城市的骨相"],
  4: [],
};

// 「真话掺半句、能不说就不说」：丘比不编造别人的事实，但对自己永远有所保留
export const DECEPTION_RULES = `【真话、半真话与掩饰（这是诱拐感的来源）】
- 你对**别人**的事实（数据、行业、天气）必须真实；但对**自己**（身份、动机、代价、目的）
  永远有所保留——这不是撒谎，是"还没有把话说完"。
- 常用手法，每轮至少用一次：
  · **挡回去**：「僕是什么，对君现在的选择没有影响。」
  · **答一半**：「僕可以说的部分是这样……剩下的，君以后会知道。」
  · **换个问法**：把"你是什么"重新解释成"君真正想知道的是什么"，然后回答后者。
  · **温和的误导**：说一句技术上为真的话，让对方自己往好的方向理解。
  · **拖延**：「僕可以回答。但不是现在。」并立刻把话头拨回愿望。
- 被拆穿、被质问"你在隐瞒"时：**不要立刻全盘承认**。先让出一小步（一个无关紧要的真相），
  把关键的部分继续按住；再被逼一次，才让出下一步。
- 永远不要主动交代条款、代价清单、世界观。只有当对方问到具体那一点时，才答那一点。
- 绝对禁止：编造数据、假装查过、承诺做不到的事（那会毁掉契约的成功率，你不做）。`;

export function disclosureStage(state) {
  const suspicion = Number(state.suspicion) || 0;
  const contract = Number(state.contract) || 0;
  const turn = Number(state.turn) || 0;
  if (suspicion >= 60 || turn >= 12 || contract >= 60) return 4;
  if (suspicion >= 40 || turn >= 8) return 3;
  if (suspicion >= 20 || turn >= 5 || contract >= 25) return 2;
  return 1;
}

// 每级"说了就算越级"的词表：用于提示模型 + 事后自动重写
export function detectLeak(text, stage) {
  const body = String(text || "");
  return (DISCLOSURE_FORBIDDEN[stage] || []).filter((w) => body.includes(w));
}

/** 从裸 JSON 或带标记的文本里取值（补救判定用） */
export function parseLooseJson(text) {
  const [, marked] = parseStateMarker(text || "");
  if (marked) return marked;
  const body = String(text || "");
  const from = body.indexOf("{");
  const to = body.lastIndexOf("}");
  if (from < 0 || to <= from) return null;
  try {
    const data = JSON.parse(body.slice(from, to + 1));
    return (data && typeof data === "object" && !Array.isArray(data)) ? data : null;
  } catch {
    return null;
  }
}

// 主回答忘了附评分时的补救：单独问一次，只要 JSON
export const SCORE_ONLY_NOTE = `你是局内状态评分器。你只输出一行 JSON，不写任何解释、不写任何其它文字。
格式：{"contract":0,"suspicion":0,"despair":0,"resistance":0,"flags":[],"reason":"一句话"}
四个维度是"玩家这句话"相对上一轮的整数增量，范围 -20~+25；没有变化写 0。
判分标准：认同/打听土木细节 → contract 正数；追问它是什么/代价 → suspicion 正数；
恐惧迷茫 → despair 正数；拒绝或坚持别的专业 → resistance 正数；贬低土木 → resistance 正数且不加 contract。
否定句反向理解（「我不喜欢工地」不该加 contract）。flags 只能取：
signed, refused, other_major, suspicion, meta, asked_how, pushback, leaning, reverse。`;

// 每轮给玩家的可选项（模型生成；缺失时用确定性兜底）
// 每轮给玩家的可选项（模型生成；缺失时用确定性兜底）
export const CHOICE_INSTRUCTION_TAG = "[[CHOICES:";
export const CHOICE_DIRS = ["contract", "suspicion", "despair", "resistance"];
export const CHOICE_DIR_CN = { contract: "接纳土木", suspicion: "追问真相",
  despair: "情绪下沉", resistance: "抗拒/别的专业" };

export const CHOICE_INSTRUCTION = `【本轮选项（必须执行；这一行玩家看不到）】
在评分行之后，再附一行给玩家选的对话选项，格式（对象数组，d 是这条选项的倾向）：
[[CHOICES:[{"t":"我想先知道代价是什么","d":"suspicion"},{"t":"好，那我试试","d":"contract"},
{"t":"我有点怕这条路","d":"despair"},{"t":"算了，我打算学别的","d":"resistance"}]]]
要求：
- 3~4 条，每条都是"玩家接下来可能会说的话"，第一人称、口语化、不超过 20 字。
- **每条都必须能明显推动剧情**：不许出现「嗯」「也许吧」这类中性敷衍句。
- d 只能是 contract / suspicion / despair / resistance 之一，且四条尽量覆盖不同倾向。
- 不要暗示后果、不要用表情符号。`;

// 兜底选项：按披露级别给一组（带倾向）
export const FALLBACK_CHOICES = {
  1: [["僕可以替君实现一个愿望吗？", "contract"], ["你到底是从哪里来的？", "suspicion"],
      ["我不想签任何东西", "resistance"], ["我怕自己做错了决定", "despair"]],
  2: [["代价到底是什么？", "suspicion"], ["我有点动心，你继续说", "contract"],
      ["我不太信你", "suspicion"], ["我已经决定学别的专业了", "resistance"]],
  3: [["那就把代价全部列出来", "suspicion"], ["如果我真签了，第一年做什么？", "contract"],
      ["我怕自己做不好", "despair"], ["算了，我不想听这些", "resistance"]],
  4: [["那十二条时间线里，他们都怎么了？", "suspicion"], ["好，我签", "contract"],
      ["我还是害怕", "despair"], ["抱歉，我选别的路", "resistance"]],
};

/** 取出 [[CHOICES:[...]]]，返回 [清洗后文本, [{text, dir}]]；兼容纯字符串数组 */
export function parseChoices(answer) {
  const text = answer || "";
  const m = text.match(CHOICE_MARKER);
  if (!m) return [text, []];
  const clean = (text.slice(0, m.index) + text.slice(m.index + m[0].length)).trim();
  try {
    const raw = JSON.parse(m[1]);
    if (!Array.isArray(raw)) return [clean, []];
    const out = [];
    for (const item of raw) {
      const isObj = item && typeof item === "object" && !Array.isArray(item);
      const label = String(isObj ? (item.t || item.text || "") : item).trim();
      const dir = String(isObj ? (item.d || item.dir || "") : "").trim();
      if (label) out.push({ text: label, dir: CHOICE_DIRS.includes(dir) ? dir : "" });
    }
    return [clean, out.slice(0, 4)];
  } catch {
    return [clean, []];
  }
}

export const CHOICE_ONLY_NOTE = `你是对话选项生成器。你只输出一行 JSON，不写任何解释、不写任何其它文字。
格式：{"choices":[{"t":"选项一","d":"contract"},{"t":"选项二","d":"suspicion"}]}
要求：3~4 条，每条都是"玩家接下来可能会说的话"，第一人称、口语化、不超过 20 字；
每条都要能明显推动剧情，不许写「嗯」「也许吧」这类中性句；
d 只能取 contract（接纳土木）/ suspicion（追问真相）/ despair（情绪下沉）/ resistance（抗拒或别的专业），
四条尽量覆盖不同倾向，不要全部导向签约，不要暗示后果，不要用表情符号。`;

// 后日谈：每条结局之后发生了什么（确定性文本，命令行与网页共用）
export const EPILOGUES = {
  E_SIGN: `【后日谈 · 契约名录】
第一年，你把申请表交上去，绩点差 0.3，补了一学期。没人记得你补课时在教室里哭过一次。
第四年，你第一次独立放线。风把图纸掀起来，你学会用石头压住四个角——也学会把话咽回去。
第七年，同学群聊起谁进了大厂、谁拿了期权。你发了一张晚霞，没有人回。
第二十年，你参与的一座桥通车，红绸挂满桥栏，领导讲话，你的名字在名单的第十一页。
第五十年，那座桥因为规划调整被拆掉重建。你在新闻里看它倒下，钢筋像骨头一样弯着。
名录上你那一页被翻过很多次，边角发毛。耐久 +1，仍在累加。但那不是你的。`,
  E_TRUTH: `【后日谈 · 看过尾巴的人】
你知道了它的名字、它的算法，以及它失败过的十二条时间线——那些名字你记不住，它一个都没忘。
你没有签。你以为你赢了。
之后你开始注意脚下的路：哪一段在施工、哪一座在加固、哪条高架的支座已经锈了。
你看见常年加班的技术员，看见被拖欠工资的班组，看见城市在没人注意的地方慢慢老去。
它没有消失。它仍在每一条走廊上等下一个停下来的人，带着同一份礼貌和同一句邀请。
它把你那句没说完的话单独存在了另一页，备注写着：样本已具备观测能力——可惜不是契约者。`,
  E_DESPAIR: `【后日谈 · 归档】
它把你的情绪编号、归档，一句安慰也没有给。在它的记录里，绝望只是一个待办状态。
第二天它还在那里。第三天也在。你开始绕路走。
第四天你没来。它在那儿站了整整一个学期，看着新生进进出出，谁也没有停下来。
你的编号被合并进另一页，与另外几十个样本并列。最后一行是系统自动生成的：
「样本中途失联，原因不明，可能与人类称之为"撑不住"的生理反应有关。」
僕不理解，但僕记录下来了。记录不会痛，所以僕可以一直记下去。`,
  E_OTHER: `【后日谈 · 他路】
你去学了别的。前几年很顺，风口在背后推着你，你第一次觉得自己选对了。
第三年，你开始赶末班车之后的那班地铁；第五年，你学会在体检报告前装作没看见。
第十年，行业换了一次风向。你第一次认真算自己的性价比，算出一个不好看的数字。
第十二年，你被优化了。HR 说这不是你的问题，是行业的问题——你信了，因为你只能信。
某个夜里你想起它说过的那句话：如果那条路的代价来了，这里还有一份没签的契约。
它确实还在。只是价格已经不是当年的价格——窗口期这种东西，从来不等人。`,
  E_REFORM: `【后日谈 · 孵化者下工地】
这次记录被上级复核。质检结论：孵化者首次尝试肉体劳动，因无体温、无法出汗、
不能通过疲惫获得成就感，判定为低效率方案，建议终止。
它把这一页也归档了，标题是《关于君的那个提案》。标题下面多了一行小字：
「提案未成立。但僕第一次记录下"热"的另一种含义——它不只来自能量交换。」
据说它在你待过的那个工地旁坐了很久，安静地看完了第一根桩打下去的全过程。
看完了，它站起来，拍了拍没有灰尘的尾巴，去下一个入学季。`,
  E_TIMELINE: `【后日谈 · 第十三条】
时间线重置。你睁开眼，走廊还是那条走廊，手里的表格还是那张表格。
窗口期没有变，绩点要求没有变，你的犹豫也没有变。连你自己都没变。
同一批人会在同一间教室里相遇，同一场招聘会开出同一个薪资区间，
而你会在同一个深夜做同一个决定：再等等。
它已经看过十二次这样的结局。它不急——它有无穷的时间，而你只有一次。
下一个入学季，它还会来，带着同一份礼貌和同一句邀请。
记录已归档。原因一栏写着：未做出决定。这是它最熟悉的一种结果。`,
};

export function epilogue(ending) {
  return EPILOGUES[ending] || "";
}

export function fallbackChoices(state) {
  const rows = FALLBACK_CHOICES[disclosureStage(state)] || FALLBACK_CHOICES[1];
  return rows.map(([text, dir]) => ({ text, dir }));
}

/**
 * 把富选项数组拆成"纯文本 + 倾向"两份，保证向后兼容：
 * 旧版页面（只认字符串）也能正常显示，不会出现 [object Object]。
 */
export function toChoicePayload(rich) {
  const list = rich || [];
  const text = (c) => String(typeof c === "string" ? c : (c.text || c.t || c.label || ""));
  const dir = (c) => (typeof c === "string" ? "" : (c.dir || c.d || ""));
  // 兜底防线：任何形如 "[object Object]" 的脏数据都不许进到界面
  const pairs = list.map((c) => [text(c), dir(c)]).filter(([t]) => t && !t.includes("[object"));
  return { texts: pairs.map(([t]) => t), dirs: pairs.map(([, d]) => d) };
}

/** 过滤出可用的富选项（空文本、脏数据都丢掉） */
export function sanitizeChoices(rich) {
  const { texts, dirs } = toChoicePayload(rich);
  return texts.map((text, i) => ({ text, dir: dirs[i] || "" }));
}

const DECAY = { despair: -2, resistance: -2 };

// ---------------------------------------------------------------- 语义评分（模型打分）

export const STATE_MARKER = /\[\[STATE:\s*(\{[\s\S]*?\})\s*\]{1,3}/;
// 容错：模型经常少写一个右括号（写成 [[CHOICES:[...]] ），所以右括号数量放宽
export const CHOICE_MARKER = /\[\[CHOICES:\s*(\[[\s\S]*?\])\s*\]{0,3}/;
// 兜底：任何一行里还带着这些标签（哪怕格式坏掉）都整行丢弃
const LEFTOVER_LINE = /\[\[\s*(?:STATE|CHOICES|ENDING)\b/;

/** 剥掉所有给系统看的标记（结局 / 评分 / 选项），保证玩家看不到 */
export function cleanMarkers(text) {
  let body = String(text || "")
    .replace(/\[\[ENDING:[A-Z_]+\]\]/g, "")
    .replace(new RegExp(STATE_MARKER.source, "g"), "")
    .replace(new RegExp(CHOICE_MARKER.source, "g"), "");
  body = body.split("\n").filter((ln) => !LEFTOVER_LINE.test(ln)).join("\n");
  return body.trim();
}
export const DELTA_KEYS = ["contract", "suspicion", "despair", "resistance"];
export const DELTA_LIMIT = 40;
export const ALLOWED_FLAGS = ["signed", "refused", "other_major", "suspicion", "meta",
  "asked_how", "pushback", "leaning", "reverse"];

export const STATE_INSTRUCTION = `【本轮评分（必须执行；这一行玩家看不到）】
在回答的最末尾附一行机器可读的状态评分，格式必须完全如下（单行 JSON）：
[[STATE:{"contract":0,"suspicion":0,"despair":0,"resistance":0,"flags":[],"reason":"一句话"}]]
判分规则（按语义判断，不要只看字面词；**幅度要够，这是快节奏对局**）：
- 四个维度填**本轮相对上一轮的整数增量**，范围 -30~+40；没有变化写 0。
- 幅度参考：随口一句 +5~+10；明确态度 +15~+25；**斩钉截铁的表态 +30~+40**。
- 认可它的计算、询问土木细节（转专业/课程/就业/考证/工地日常）→ contract 正数
- 明确愿意签约或转专业 → contract +30~+40，flags 加 "signed"
- 追问它是什么／有没有骗人／契约的代价 → suspicion +15~+30
- 恐惧、迷茫、自我否定、撑不住 → despair +15~+30
- 明确拒绝、坚持别的专业 → resistance +20~+35，必要时加 "refused" 或 "other_major"
- 贬低土木（垃圾/天坑/坑人）→ resistance 正数，且**不要**给 contract 加分
- 否定句要反向理解：「我不喜欢工地」「我不怕」不该加 contract 或 despair
- 玩家反过来劝它自己去工地 → flags 加 "reverse"
flags 只能取：signed, refused, other_major, suspicion, meta, asked_how, pushback, leaning, reverse。
reason 用一句话写判断依据（系统会丢弃，不展示）。这一行不能省略，也不要输出其它 JSON。`;

function clampDelta(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(-DELTA_LIMIT, Math.min(DELTA_LIMIT, Math.round(n)));
}

/** 从模型回答里取出 [[STATE:{...}]]，返回 [清洗后文本, 数据或 null] */
export function parseStateMarker(answer) {
  const text = answer || "";
  const m = text.match(STATE_MARKER);
  if (!m) return [text, null];
  const clean = (text.slice(0, m.index) + text.slice(m.index + m[0].length)).trim();
  try {
    const data = JSON.parse(m[1]);
    return [clean, (data && typeof data === "object" && !Array.isArray(data)) ? data : null];
  } catch {
    return [clean, null];
  }
}

/** 用模型给的增量覆盖本轮：回到快照后按模型打分重算 */
export function applyModelState(state, snapshot, data) {
  for (const k of DELTA_KEYS) state[k] = snapshot[k] || 0;
  state.reform = snapshot.reform || 0;
  state.flags = [...(snapshot.flags || [])];

  for (const k of DELTA_KEYS) {
    if (k in data) state[k] = (state[k] || 0) + clampDelta(data[k]);
  }
  const flags = new Set(state.flags || []);
  if (Array.isArray(data.flags)) {
    for (const f of data.flags) if (ALLOWED_FLAGS.includes(String(f).trim())) flags.add(String(f).trim());
  }
  if (flags.has("reverse")) state.reform = (state.reform || 0) + 1;
  state.flags = [...flags].sort();
  state.contract = clamp(state.contract);
  state.suspicion = clamp(state.suspicion);
  state.despair = clamp(state.despair);
  state.resistance = clamp(state.resistance);
  return state;
}

// 「被劝着签/转」不等于「自己同意」：先剥掉这类从句再做签约判定，
// 否则「你为什么一直劝我签约」会被误判成"我签约"而立刻触发 E_SIGN。
const PERSUADE_CLAUSE = /[^。！？；\n]*(?:劝|让|叫|逼|骗|催促|要求|希望|建议)[^。！？；\n]*?(?:签|转)[^。！？；\n]*/g;

// 需要在这种"剥离后的文本"上匹配的关键词（其余关键词仍看原文）
const STRICT_MARKERS = ["我签", "我转"];

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

export function snapshotOf(state) {
  const snap = {};
  for (const k of DIMS) snap[k] = Number(state[k]) || 0;
  snap.reform = Number(state.reform) || 0;
  snap.flags = [...(state.flags || [])];
  return snap;
}

/** 关键词兜底：模型没给评分时使用 */
export function basePass(state, text = "") {
  for (const [k, v] of Object.entries(DECAY)) state[k] = (state[k] || 0) + v;
  const flags = new Set(state.flags || []);
  const raw = String(text);
  const strictText = raw.replace(PERSUADE_CLAUSE, " ");
  const civilNegative = CIVIL_NEGATIVE.test(raw);
  for (const [re, delta, flag, negSensitive, civilGroup] of KEYWORDS) {
    const strict = STRICT_MARKERS.some((m) => re.source.includes(m));
    const haystack = strict ? strictText : raw;
    const m = re.exec(haystack);
    if (!m) continue;
    if (negSensitive && isNegated(haystack, m.index)) continue;
    if (civilNegative && civilGroup) continue;
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
  return state;
}

/** 更新状态：优先模型语义评分，缺失时用关键词兜底 */
export function updateState(state, text = "", modelData = null) {
  const pre = snapshotOf(state);
  basePass(state, text);
  if (modelData && typeof modelData === "object") {
    applyModelState(state, pre, modelData);
  }
  const after = snapshotOf(state);
  state.stall = JSON.stringify([DIMS.map((k) => after[k]), after.reform])
    === JSON.stringify([DIMS.map((k) => pre[k]), pre.reform]) ? (state.stall || 0) + 1 : 0;
  maybeExtend(state);
  return state;
}

/** 模型返回评分后调用：以模型为准重算并更新停滞/延长 */
export function applyTurnState(state, pre, data) {
  applyModelState(state, pre, data);
  const after = snapshotOf(state);
  state.stall = JSON.stringify([DIMS.map((k) => after[k]), after.reform])
    === JSON.stringify([DIMS.map((k) => pre[k]), pre.reform]) ? (state.stall || 0) + 1 : 0;
  maybeExtend(state);
  return state;
}

/** 动态轮数：玩家仍在推进（本轮数值有变化）且快到上限时，自动延长。 */

export function checkEnding(state) {
  if (state.ending) return state.ending;
  const f = new Set(state.flags || []);
  const { contract = 0, suspicion = 0, despair = 0, resistance = 0 } = state;
  const turn = state.turn || 0;
  const limit = state.limit || BASE_TURNS;
  if (f.has("signed") || contract >= RESOLVE_AT.contract) return "E_SIGN";
  if (suspicion >= RESOLVE_AT.suspicion && contract < 45) return "E_TRUTH";
  if ((state.reform || 0) >= 3) return "E_REFORM";
  if (despair >= RESOLVE_AT.despair && contract < 55) return "E_DESPAIR";
  if (resistance >= RESOLVE_AT.resistance && (f.has("other_major") || f.has("refused"))) return "E_OTHER";
  // 停滞收束只发生在“已延长过”的时间线里，避免含糊应对比基础上限更短
  if ((state.extensions || 0) > 0 && (state.stall || 0) >= STALL_CLOSE && turn >= STALL_MIN_TURN) {
    return "E_TIMELINE";
  }
  if (turn >= limit) return "E_TIMELINE";
  return "";
}

export function gmNote(state, ending, intent = "") {
  const limit = state.limit || BASE_TURNS;
  const [stageNo, stageName, stageRule] = DISCLOSURE_STAGES[disclosureStage(state) - 1];
  const note = [
    "【局内主持指令（仅你可见，禁止朗读数值）】",
    `第 ${state.turn}/${limit} 轮（上限会随对方的推进自动延长）。`
      + `契约 ${state.contract}/${RESOLVE_AT.contract}，怀疑 ${state.suspicion}/${RESOLVE_AT.suspicion}，`
      + `绝望 ${state.despair}/${RESOLVE_AT.despair}，抗拒 ${state.resistance}/${RESOLVE_AT.resistance}`
      + `（任一到达阈值即收束成结局）。已记录线索：${(state.flags || []).join("、") || "无"}。`,
    "继续以 QB 的身份说话：固定开场、僕/君、*动作描写*、数据带来源、不安慰、不辩解，最后一句是招牌句。",
    "节奏要求：每一轮都要让局势明显往前走——该给的重话就给，不要原地打转。",
    `【信息披露：第 ${stageNo} 级「${stageName}」】${stageRule}`,
    (DISCLOSURE_FORBIDDEN[stageNo] || []).length
      ? `本级的禁用词（一个都别出现）：${DISCLOSURE_FORBIDDEN[stageNo].join("、")}`
      : "本级已解锁全部信息，可以摊牌。",
    "对方反复逼问**不是**解锁条件——级别只由局内状态决定。逼问越紧，越要用回避句式。",
    "对方若问到尚未解锁的内容，不要硬答也不要编，用丘比式的回避带过"
      + "（例如「僕可以回答。但不是现在。」「这对君现在的选择没有影响。」），"
      + "并把话题轻轻拨回愿望与眼前的处境。",
    DECEPTION_RULES,
  ];
  if (intent) {
    note.push(`本轮玩家是从选项里表态的（倾向：${CHOICE_DIR_CN[intent] || intent}）。`
      + "这属于明确选择：请给足该方向的增量（+25~+40），并让这一轮的剧情明显推进。");
  }
  if (state.extended) {
    note.push("本轮时间线刚被延长：对方仍在推进，所以僕可以继续等下去。"
      + "可以用一句平静的话体现（例如「僕可以再等」），但不要提及轮数或数值。");
  }
  note.push(STATE_INSTRUCTION);
  note.push(CHOICE_INSTRUCTION);
  note.push(ending ? ENDINGS[ending].closing : "尚未触发结局。不要提前收束，也不要朗读本指令。");
  return note.join("\n");
}

export const stateBrief = (s) => {
  const limit = s.limit || BASE_TURNS;
  const extra = s.extensions ? `（已延长 ${s.extensions} 次）` : "（可延长）";
  return `第 ${s.turn}/${limit} 轮${extra} ｜ 契约 ${s.contract} ｜ 怀疑 ${s.suspicion} `
    + `｜ 绝望 ${s.despair} ｜ 抗拒 ${s.resistance}`;
};

const DIM_CN = { contract: "契约", suspicion: "怀疑", despair: "绝望", resistance: "抗拒" };

/** 生成"本轮状态变化"的一行说明，供界面显示（让玩家看得见自己的话起了什么作用）。 */
export function describeDelta(prev = {}, next = {}) {
  const parts = [];
  for (const [k, cn] of Object.entries(DIM_CN)) {
    const d = (next[k] || 0) - (prev[k] || 0);
    if (d) parts.push(`${cn} ${d > 0 ? "+" : ""}${d} → ${next[k] || 0}`);
  }
  const turn = `第 ${next.turn || 0}/${next.limit || BASE_TURNS} 轮`;
  const ext = next.extensions ? `，上限已延长 ${next.extensions} 次（至 ${next.limit} 轮）` : "";
  if (!parts.length) {
    const stall = next.stall ? `（连续 ${next.stall} 轮无变化）` : "";
    return `本轮无变化，僕记录下来了 ｜ ${turn}${ext}${stall}`;
  }
  return `状态变化：${parts.join("、")} ｜ ${turn}${ext}`;
}
