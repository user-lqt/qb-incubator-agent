// 娴忚鍣ㄧ増 Agent 鍐呮牳锛氫笌 agent.py 鍚屾牱鐨勩€屾€濊€?鈫?璋冨伐鍏?鈫?瑙傚療銆嶅惊鐜紝
// 鍙槸鎶?HTTP 瀹㈡埛绔粠 openai SDK 鎹㈡垚 fetch锛屽苟涓旇嚜甯︾粨灞€鐜╂硶锛坓ame.js锛夈€?
// 娉ㄦ剰锛氳祫婧愮増鏈彿瑕佷笌 index.html 閲岀殑 V 淇濇寔涓€鑷达紝閬垮厤"鏂颁唬鐮?+ 鏃х紦瀛樻ā鍧?娣锋惌
const V = "?v=13";

const { SYSTEM_PROMPT } = await import("./persona.js" + V);
const { FUNCTIONS, TOOLS, TOOL_AVAILABILITY_NOTE } = await import("./tools.js" + V);
const gameMod = await import("./game.js" + V);
const { ENDINGS, BASE_TURNS, checkEnding, gmNote, newState, updateState,
        applyTurnState, parseStateMarker, snapshotOf, parseLooseJson, SCORE_ONLY_NOTE,
        parseChoices, fallbackChoices, cleanMarkers, CHOICE_ONLY_NOTE,
        disclosureStage, detectLeak, DISCLOSURE_STAGES } = gameMod;

const DEFAULT_BASE = "https://api.deepseek.com";
const DEFAULT_MODEL = "deepseek-chat";

export class QBClient {
  constructor({ apiKey, baseUrl = DEFAULT_BASE, model = DEFAULT_MODEL, maxSteps = 8 } = {}) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.model = model;
    this.maxSteps = maxSteps;
    this.history = [];      // 瀵硅瘽璁板綍锛堜笉鍚?system锛?    this.state = newState(); // 灞€鍐呯姸鎬?  }

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
      throw new Error(`妯″瀷鎺ュ彛杩斿洖 ${res.status}锛?{detail.slice(0, 200)}`);
    }
    const data = await res.json();
    return data.choices?.[0]?.message;
  }

  /** 琛ユ晳鍒ゅ畾锛氳烦杩囦汉璁俱€佷笉甯﹀伐鍏凤紝鍙妯″瀷涓鸿繖鍙ヨ瘽鍚愪竴琛?JSON */
  async _scoreOnly(question) {
    const msg = await this._chat([
      { role: "system", content: SCORE_ONLY_NOTE },
      { role: "user", content: `鐜╁鍒氭墠璇达細銆?{question}銆峔n鐜板湪鍙緭鍑洪偅涓€琛?JSON銆俙 },
    ], null);
    return parseLooseJson(msg?.content || "");
  }

  /** 琛ユ晳閫夐」锛氫富鍥炵瓟娌＄粰 [[CHOICES:...]] 鏃讹紝鍗曠嫭璁╂ā鍨嬬敓鎴愪竴缁?*/
  async _choicesOnly(question, answer) {
    const msg = await this._chat([
      { role: "system", content: CHOICE_ONLY_NOTE },
      { role: "user", content: `鐜╁鍒氳锛氥€?{question}銆峔n瀵规柟锛堝鍖栬€咃級鍒氬洖绛旓細`
        + `銆?{String(answer || "").slice(0, 300)}銆峔n璇峰彧杈撳嚭閭ｄ竴琛?JSON銆俙 },
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

  /** 璺戜竴杞唴鏍稿惊鐜細妯″瀷鍙兘杩炵画璋冪敤澶氫釜宸ュ叿銆傝繑鍥炵函鏂囨湰绛旀銆?*/
  async _run(question, extraSystem = "") {
    const messages = [{ role: "system", content: SYSTEM_PROMPT }];
    if (extraSystem) messages.push({ role: "system", content: extraSystem });
    messages.push({ role: "system", content: TOOL_AVAILABILITY_NOTE });
    messages.push(...this.history, { role: "user", content: question });

    for (let step = 0; step < this.maxSteps; step += 1) {
      const msg = await this._chat(messages, TOOLS);
      if (!msg) return "(妯″瀷鏈繑鍥炲唴瀹?";
      messages.push(msg);
      if (!msg.tool_calls?.length) return msg.content || "(绌哄洖澶?";

      for (const call of msg.tool_calls) {
        const name = call.function?.name;
        let args = {};
        try { args = JSON.parse(call.function?.arguments || "{}"); } catch { args = {}; }
        const fn = FUNCTIONS[name];
        let result;
        try {
          result = fn ? await fn(args) : `娌℃湁鍚嶄负 ${name} 鐨勫伐鍏凤紙鏈増涓嶆彁渚涳級锛岃鎹釜鏂瑰紡鍥炵瓟銆俙;
        } catch (e) {
          result = `宸ュ叿 ${name} 鎵ц澶辫触锛?{e.message}`;
        }
        messages.push({
          role: "tool", tool_call_id: call.id,
          content: JSON.stringify({ result: String(result) }),
        });
      }
    }
    return "宸茶揪鏈€澶ф鏁帮紝鏈緱鍒版渶缁堢瓟妗堛€?;
  }

  /** 甯︾帺娉曠殑鍗曡疆鎺ㄨ繘锛堜笌 game.py 绛変环锛夈€?*/
  async turn(question) {
    const pre = snapshotOf(this.state);        // 鏈疆涔嬪墠鐨勫揩鐓э細妯″瀷澧為噺鐩稿浜庡畠
    this.state.turn += 1;
    updateState(this.state, question);         // 鍏抽敭璇嶉鍒わ紙涓绘寔鎸囦护璇诲綋鍓嶅眬鍔匡紝涔熸槸鍏滃簳锛?    let ending = checkEnding(this.state);
    if (ending) this.state.ending = ending;

    const raw = await this._run(question, gmNote(this.state, ending));
    // 璇箟璇勫垎锛氭ā鍨嬪湪鍥炵瓟鏈熬闄勭殑 [[STATE:{...}]] 鏄湰杞殑鏉冨▉鍒ゅ畾
    const [cleanRaw, parsedData] = parseStateMarker(raw);
    let modelData = parsedData;
    let scoreSource = modelData ? "model" : "";
    if (!modelData) {
      // 涓诲洖绛斿繕浜嗛檮璇勫垎 -> 琛ユ晳锛氳烦杩囦汉璁惧崟鐙棶涓€娆★紝鍙 JSON
      try {
        const rescued = await this._scoreOnly(question);
        if (rescued) { modelData = rescued; scoreSource = "rescue"; }
      } catch { /* 琛ユ晳澶辫触灏遍€€鍥炲叧閿瘝鏈?*/ }
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

    // 瓒婄骇娉勯湶妫€鏌ワ細璇翠簡鏈骇绂佺敤璇?-> 璁╂ā鍨嬬敤鍥為伩鍙ュ紡閲嶅啓涓€娆?    const stage = disclosureStage(this.state);
    const leaks = detectLeak(answer, stage);
    if (leaks.length && !ending) {
      const fix = `銆愬眬鍐呬慨姝ｃ€戝垰鎵嶇殑鍥炵瓟瓒婄骇閫忛湶浜嗭細${leaks.join("銆?)}銆俙
        + `褰撳墠鍙厑璁哥 ${stage} 绾с€?{DISCLOSURE_STAGES[stage - 1][1]}銆嶇殑淇℃伅銆俙
        + "璇风敤 QB 鐨勫彛鍚绘妸杩欎竴杞洖绛旈噸鍐欎竴閬嶏細涓嶅緱鍑虹幇涓婅堪璇嶏紝鏀圭敤鍥為伩鍙ュ紡"
        + "锛堛€屽儠鍙互鍥炵瓟銆備絾涓嶆槸鐜板湪銆傘€嶃€岃繖瀵瑰悰鐜板湪鐨勯€夋嫨娌℃湁褰卞搷銆傘€嶏級锛?
        + "骞舵妸璇濋鎷ㄥ洖鎰挎湜涓庡鏂圭溂鍓嶇殑澶勫銆備粛鐒朵繚鎸侊細鍥哄畾寮€鍦恒€佸儠/鍚涖€佸姩浣滄弿鍐欍€佹嫑鐗屽彞鏀跺熬銆?
        + "鍥炵瓟鏈€鍚庣収甯搁檮涓?[[STATE:...]] 璇勫垎琛屻€?;
      const rewrittenRaw = await this._run(fix, "");
      const rewritten = cleanMarkers(rewrittenRaw);
      if (rewritten && detectLeak(rewritten, stage).length === 0) {
        answer = rewritten;
        this.state.leak_rewrites = (this.state.leak_rewrites || 0) + 1;
      }
    }

    // 鍏滃簳锛氭棤璁鸿蛋鍝潯璺緞锛屾渶缁堟枃鏈噷閮戒笉鑳芥湁浠讳綍鏍囪
    answer = cleanMarkers(answer);

    // 妯″瀷娌＄粰閫夐」 -> 鍗曠嫭琛ヤ竴娆★紝浠嶅け璐ユ墠鐢ㄧ‘瀹氭€у厹搴?    let finalChoices = choices;
    if (!ending && !finalChoices.length) {
      try { finalChoices = await this._choicesOnly(question, answer); } catch { finalChoices = []; }
    }

    // 鍐呮牳閲岃拷鍔犵殑 messages 涓嶈繘 history锛堝彧淇濈暀 user/assistant 鏂囨湰锛屾帶鍒朵笂涓嬫枃闀垮害锛?    this.history.push({ role: "user", content: question });
    this.history.push({ role: "assistant", content: answer });
    if (this.history.length > 40) this.history.splice(0, this.history.length - 40);

    if (ending && !selfConcluded) {
      const cue = `銆愬眬鍐呮敹鏉熴€戞椂闂寸嚎寮€濮嬫敹鏉燂紝杩涘叆缁撳眬銆?{ENDINGS[ending].closing}`
        + `\n锛堟湰娆″灞€锛氱 ${this.state.turn} 杞紝褰撳墠涓婇檺 ${this.state.limit || BASE_TURNS} 杞紝`
        + `寤堕暱杩?${this.state.extensions || 0} 娆★級`;
      let closing = await this._run(cue, "");
      const hasMark = new RegExp(`\\[\\[ENDING:${ending}\\]\\]`).test(closing);
      closing = closing.replace(/\[\[ENDING:[A-Z_]+\]\]/g, "").trim();
      if (hasMark || closing) {
        answer = `${closing}\n\n鈥斺€斻€?{ENDINGS[ending].title}銆?{ENDINGS[ending].tagline}`;
        this.history.push({ role: "user", content: cue });
        this.history.push({ role: "assistant", content: closing });
      }
    }

    return {
      answer, state: { ...this.state, max_turns: this.state.limit || BASE_TURNS }, ending,
      choices: finalChoices.length ? finalChoices : fallbackChoices(this.state),
      ending_title: ending ? ENDINGS[ending].title : "",
      ending_tagline: ending ? ENDINGS[ending].tagline : "",
    };
  }
}
