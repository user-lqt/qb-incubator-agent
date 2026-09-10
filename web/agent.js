// 浏览器版 Agent 内核：与 agent.py 同样的「思考 → 调工具 → 观察」循环，
// 只是把 HTTP 客户端从 openai SDK 换成 fetch，并且自带结局玩法（game.js）。

// 注意：资源版本号要与 index.html 里的 V 保持一致，避免"新代码 + 旧缓存模块"混搭
const V = "?v=9";

const { SYSTEM_PROMPT } = await import("./persona.js" + V);
const { FUNCTIONS, TOOLS, TOOL_AVAILABILITY_NOTE } = await import("./tools.js" + V);
const gameMod = await import("./game.js" + V);
const { ENDINGS, BASE_TURNS, checkEnding, gmNote, newState, updateState } = gameMod;

const DEFAULT_BASE = "https://api.deepseek.com";
const DEFAULT_MODEL = "deepseek-chat";

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
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify({ model: this.model, messages, tools, tool_choice: "auto" }),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`模型接口返回 ${res.status}：${detail.slice(0, 200)}`);
    }
    const data = await res.json();
    return data.choices?.[0]?.message;
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

  /** 带玩法的单轮推进（与 game.py 等价）。 */
  async turn(question) {
    this.state.turn += 1;
    updateState(this.state, question);
    let ending = checkEnding(this.state);
    if (ending) this.state.ending = ending;

    const raw = await this._run(question, gmNote(this.state, ending));
    const selfConcluded = new RegExp(`\\[\\[ENDING:${ending || ""}\\]\\]`).test(raw);
    let answer = raw.replace(/\[\[ENDING:[A-Z_]+\]\]/g, "").trim();
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
      closing = closing.replace(/\[\[ENDING:[A-Z_]+\]\]/g, "").trim();
      if (hasMark || closing) {
        answer = `${closing}\n\n——【${ENDINGS[ending].title}】${ENDINGS[ending].tagline}`;
        this.history.push({ role: "user", content: cue });
        this.history.push({ role: "assistant", content: closing });
      }
    }

    return {
      answer, state: { ...this.state, max_turns: this.state.limit || BASE_TURNS }, ending,
      ending_title: ending ? ENDINGS[ending].title : "",
      ending_tagline: ending ? ENDINGS[ending].tagline : "",
    };
  }
}
