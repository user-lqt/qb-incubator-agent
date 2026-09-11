// 浏览器版 Agent 内核：与 agent.py 同样的「思考 → 调工具 → 观察」循环，
// 只是把 HTTP 客户端从 openai SDK 换成 fetch，并且自带结局玩法（game.js）。

// 注意：资源版本号要与 index.html 里的 V 保持一致，避免"新代码 + 旧缓存模块"混搭
const V = "?v=15";

const { SYSTEM_PROMPT } = await import("./persona.js" + V);
const { FUNCTIONS, TOOLS, TOOL_AVAILABILITY_NOTE } = await import("./tools.js" + V);
const gameMod = await import("./game.js" + V);
const { ENDINGS, BASE_TURNS, checkEnding, gmNote, newState, updateState,
        applyTurnState, parseStateMarker, snapshotOf, parseLooseJson, SCORE_ONLY_NOTE,
        parseChoices, fallbackChoices, cleanMarkers, CHOICE_ONLY_NOTE,
        disclosureStage, detectLeak, DISCLOSURE_STAGES } = gameMod;

const DEFAULT_BASE = "https://api.deepseek.com";
const DEFAULT_MODEL = "deepseek-chat";

// 兼容垫片：老页面（浏览器缓存的旧版）会把选项对象直接写进 textContent，
// 于是显示成 [object Object]。这里包装 textContent 的 setter，遇到对象就取其中的文字字段，
// 这样无论 HTML 与 JS 是哪两个版本混搭，玩家都不会再看到 [object Object]。
(function installTextShim() {
  try {
    const desc = Object.getOwnPropertyDescriptor(Node.prototype, "textContent");
    if (!desc || !desc.set || desc.set.__dshShim) return;
    const setter = function (value) {
      if (value && typeof value === "object" && !(value instanceof Node)) {
        const t = value.text ?? value.t ?? value.label ?? value.title;
        value = (typeof t === "string" && t) ? t : (() => {
          try { return JSON.stringify(value); } catch { return String(value); }
        })();
      }
      return desc.set.call(this, value);
    };
    setter.__dshShim = true;
    Object.defineProperty(Node.prototype, "textContent", { ...desc, set: setter });
  } catch { /* 垫片失败不影响主流程 */ }
})();

export class QBClient {
  constructor({ apiKey, baseUrl = DEFAULT_BASE, model = DEFAULT_MODEL, maxSteps = 8 } = {}) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.model = model;
    this.maxSteps = maxSteps;
    this.history = [];      // 对话记录（不含 system）
    this.state = newState(); // 局内状态
  }

  reset() {
    this.history = [];
    this.state = newState();
  }

  async _chat(messages, tools) {
    const body = { model: this.model, messages };
    if (tools && tools.length) {
      body.tools = tools;
      body.tool_choice = "auto";
    }
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`模型接口返回 ${res.status}：${detail.slice(0, 200)}`);
    }
    const data = await res.json();
    return data.choices?.[0]?.message;
  }

  /** 补救判定：跳过人设、不带工具，只让模型为这句话吐一行 JSON */
  async _scoreOnly(question) {
    const msg = await this._chat([
      { role: "system", content: SCORE_ONLY_NOTE },
      { role: "user", content: `玩家刚才说：「${question}」\n现在只输出那一行 JSON。` },
    ], null);
    return parseLooseJson(msg?.content || "");
  }

  /** 补救选项：主回答没给 [[CHOICES:...]] 时，单独让模型生成一组 */
  async _choicesOnly(question, answer) {
    const msg = await this._chat([
      { role: "system", content: CHOICE_ONLY_NOTE },
      { role: "user", content: `玩家刚说：「${question}」\n对方（孵化者）刚回答：`
        + `「${String(answer || "").slice(0, 300)}」\n请只输出那一行 JSON。` },
    ], null);
    const text = msg?.content || "";
    const from = text.indexOf("{");
    const to = text.lastIndexOf("}");
    if (from < 0 || to <= from) return [];
    try {
      const data = JSON.parse(text.slice(from, to + 1));
      const items = Array.isArray(data) ? data : (data.choices || data.options || []);
      return items.map((x) => String(x).trim()).filter(Boolean).slice(0, 4);
    } catch {
      return [];
    }
  }

  /** 跑一轮内核循环：模型可能连续调用多个工具。返回纯文本答案。 */
  async _run(question, extraSystem = "") {
    const messages = [{ role: "system", content: SYSTEM_PROMPT }];
    if (extraSystem) messages.push({ role: "system", content: extraSystem });
    messages.push({ role: "system", content: TOOL_AVAILABILITY_NOTE });
    messages.push(...this.history, { role: "user", content: question });

    for (let step = 0; step < this.maxSteps; step += 1) {
      const msg = await this._chat(messages, TOOLS);
      if (!msg) return "(模型未返回内容)";
      messages.push(msg);
      if (!msg.tool_calls?.length) return msg.content || "(空回复)";

      for (const call of msg.tool_calls) {
        const name = call.function?.name;
        let args = {};
        try { args = JSON.parse(call.function?.arguments || "{}"); } catch { args = {}; }
        const fn = FUNCTIONS[name];
        let result;
        try {
          result = fn ? await fn(args) : `没有名为 ${name} 的工具（本版不提供），请换个方式回答。`;
        } catch (e) {
          result = `工具 ${name} 执行失败：${e.message}`;
        }
        messages.push({
          role: "tool", tool_call_id: call.id,
          content: JSON.stringify({ result: String(result) }),
        });
      }
    }
    return "已达最大步数，未得到最终答案。";
  }

  /** 带玩法的单轮推进（与 game.py 等价）。intent 为选项倾向，可选。 */
  async turn(question, intent = "") {
    const pre = snapshotOf(this.state);        // 本轮之前的快照：模型增量相对于它
    this.state.turn += 1;
    updateState(this.state, question);         // 关键词预判（主持指令读当前局势，也是兜底）
    let ending = checkEnding(this.state);
    if (ending) this.state.ending = ending;

    const raw = await this._run(question, gmNote(this.state, ending, intent));
    // 语义评分：模型在回答末尾附的 [[STATE:{...}]] 是本轮的权威判定
    const [cleanRaw, parsedData] = parseStateMarker(raw);
    let modelData = parsedData;
    let scoreSource = modelData ? "model" : "";
    if (!modelData) {
      // 主回答忘了附评分 -> 补救：跳过人设单独问一次，只要 JSON
      try {
        const rescued = await this._scoreOnly(question);
        if (rescued) { modelData = rescued; scoreSource = "rescue"; }
      } catch { /* 补救失败就退回关键词机 */ }
    }
    const selfConcluded = new RegExp(`\\[\\[ENDING:${ending || ""}\\]\\]`).test(raw);
    const [withoutChoices, choices] = parseChoices(cleanRaw);
    let answer = cleanMarkers(withoutChoices);

    if (modelData) {
      applyTurnState(this.state, pre, modelData);
      ending = checkEnding(this.state);
      if (ending) this.state.ending = ending;
    }
    this.state.score_source = scoreSource || "keywords";

    // 越级泄露检查：说了本级禁用词 -> 让模型用回避句式重写一次
    const stage = disclosureStage(this.state);
    const leaks = detectLeak(answer, stage);
    if (leaks.length && !ending) {
      const fix = `【局内修正】刚才的回答越级透露了：${leaks.join("、")}。`
        + `当前只允许第 ${stage} 级「${DISCLOSURE_STAGES[stage - 1][1]}」的信息。`
        + "请用 QB 的口吻把这一轮回答重写一遍：不得出现上述词，改用回避句式"
        + "（「僕可以回答。但不是现在。」「这对君现在的选择没有影响。」），"
        + "并把话题拨回愿望与对方眼前的处境。仍然保持：固定开场、僕/君、动作描写、招牌句收尾。"
        + "回答最后照常附上 [[STATE:...]] 评分行。";
      const rewrittenRaw = await this._run(fix, "");
      const rewritten = cleanMarkers(rewrittenRaw);
      if (rewritten && detectLeak(rewritten, stage).length === 0) {
        answer = rewritten;
        this.state.leak_rewrites = (this.state.leak_rewrites || 0) + 1;
      }
    }

    // 兜底：无论走哪条路径，最终文本里都不能有任何标记
    answer = cleanMarkers(answer);

    // 模型没给选项 -> 单独补一次，仍失败才用确定性兜底
    let finalChoices = choices;
    if (!ending && !finalChoices.length) {
      try { finalChoices = await this._choicesOnly(question, answer); } catch { finalChoices = []; }
    }

    // 内核里追加的 messages 不进 history（只保留 user/assistant 文本，控制上下文长度）
    this.history.push({ role: "user", content: question });
    this.history.push({ role: "assistant", content: answer });
    if (this.history.length > 40) this.history.splice(0, this.history.length - 40);

    if (ending && !selfConcluded) {
      const cue = `【局内收束】时间线开始收束，进入结局。${ENDINGS[ending].closing}`
        + `\n（本次对局：第 ${this.state.turn} 轮，当前上限 ${this.state.limit || BASE_TURNS} 轮，`
        + `延长过 ${this.state.extensions || 0} 次）`;
      let closing = await this._run(cue, "");
      const hasMark = new RegExp(`\\[\\[ENDING:${ending}\\]\\]`).test(closing);
      closing = cleanMarkers(closing);
      if (hasMark || closing) {
        answer = `${closing}\n\n——【${ENDINGS[ending].title}】${ENDINGS[ending].tagline}`;
        this.history.push({ role: "user", content: cue });
        this.history.push({ role: "assistant", content: closing });
      }
    }

    // 向后兼容：choices 一律回传**纯字符串**（旧版页面也能正确显示），
    // 倾向单独放在 choiceDirs 里，新页面按索引取用。
    const rich = finalChoices.length ? finalChoices : fallbackChoices(this.state);
    const { texts, dirs } = gameMod.toChoicePayload(rich);
    return {
      answer, state: { ...this.state, max_turns: this.state.limit || BASE_TURNS }, ending,
      choices: texts,
      choiceDirs: dirs,
      choicesRich: rich,
      tension: gameMod.tension(this.state),
      ending_title: ending ? ENDINGS[ending].title : "",
      ending_tagline: ending ? ENDINGS[ending].tagline : "",
    };
  }
}
