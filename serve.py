"""把 Agent 变成一个网页服务：同学用浏览器就能玩，你的 API key 始终留在本机。

启动：python serve.py
访问：同一 WiFi 的同学打开终端里打印的 http://<你的局域网IP>:8080
可选配置（写在同目录 .env）：
  PORT=8080              # 端口
  ACCESS_PASSWORD=xxx    # 访问口令（建议设置，防止陌生人白嫖你的额度）
  DAILY_LIMIT=200        # 每日总提问上限（0 表示不限）
  GAME_MODE=1            # 1=开启结局玩法（状态条 + 6 个结局），0=纯聊天
"""
import json
import os
import re
import socket
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))   # 脚本旁的 .env 优先
load_dotenv()                              # 再兜底当前目录

import game  # noqa: E402
from agent import run_agent  # noqa: E402

PORT = int(os.getenv("PORT", "8080"))
PASSWORD = os.getenv("ACCESS_PASSWORD", "").strip()
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "200"))
GAME_MODE = os.getenv("GAME_MODE", "1").strip() not in ("0", "false", "False")

_sessions = {}          # sid -> {"history": [...], "state": {...}}
_lock = threading.Lock()
_counter = {"day": "", "n": 0}

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>孵化者 · 契约终端</title>
<style>
  :root { --pink:#ff9ec7; --ink:#2b2b33; --bg:#fdf7fa; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font: 15px/1.75 "Microsoft YaHei", "PingFang SC", system-ui, sans-serif; }
  header { padding:12px 18px; background:#fff; border-bottom:1px solid #f0e2e9;
           display:flex; align-items:center; gap:10px; position:sticky; top:0; z-index:5; }
  header b { font-size:16px; }
  header .dot { width:10px; height:10px; border-radius:50%; background:var(--pink); }
  #pw { margin-left:auto; border:1px solid #ecd9e2; border-radius:8px; padding:6px 10px; width:130px; }
  #bars { display:none; gap:14px; padding:10px 18px; background:#fff; border-bottom:1px solid #f0e2e9;
          position:sticky; top:52px; z-index:4; flex-wrap:wrap; font-size:12px; color:#7b6270; }
  #bars .m { display:flex; align-items:center; gap:6px; }
  #bars .track { width:74px; height:6px; border-radius:3px; background:#f3e8ee; overflow:hidden; }
  #bars .fill { height:100%; width:0; background:var(--pink); transition:width .3s; }
  #banner { display:none; margin:14px auto 0; max-width:820px; padding:12px 16px; border-radius:12px;
            background:#fff0f6; border:1px dashed var(--pink); color:#7a3355; }
  #banner b { display:block; font-size:15px; margin-bottom:4px; }
  main { max-width:820px; margin:0 auto; padding:18px; }
  #log { display:flex; flex-direction:column; gap:14px; }
  .b { border-radius:14px; padding:12px 14px; white-space:pre-wrap; word-break:break-word; }
  .me { align-self:flex-end; background:#fff; border:1px solid #f0e2e9; max-width:78%; }
  .qb { align-self:flex-start; background:var(--pink); color:#3a2030; max-width:88%; }
  .sys { align-self:center; color:#a38f9a; font-size:13px; text-align:center; }
  footer { position:sticky; bottom:0; background:#fff; border-top:1px solid #f0e2e9; padding:12px 18px; }
  .row { max-width:820px; margin:0 auto; display:flex; gap:10px; align-items:flex-end; }
  textarea { flex:1; resize:vertical; min-height:46px; max-height:140px; padding:12px;
             border:1px solid #ecd9e2; border-radius:10px; font:inherit; }
  button { border:0; border-radius:10px; padding:12px 18px; font:inherit; cursor:pointer; }
  #send { background:var(--pink); color:#3a2030; font-weight:600; }
  #reset { background:#f3e8ee; color:#7b6270; }
  button[disabled] { opacity:.5; cursor:default; }
</style>
</head>
<body>
<header><span class="dot"></span><b>孵化者 · 契约终端</b>
  <input id="pw" placeholder="口令（若已设置）">
</header>
<div id="bars"></div>
<div id="banner"></div>
<main><div id="log">
  <div class="b qb">嗯——僕在。
君想问什么都可以：天气、行业、专业选择。僕会先给事实，再给提案。
一共十二轮。要不要签，由君决定。</div>
</div></main>
<footer><div class="row">
  <textarea id="q" placeholder="输入问题，Enter 发送（Shift+Enter 换行）"></textarea>
  <button id="send">发送</button><button id="reset">重新开始</button>
</div></footer>
<script>
const log = document.getElementById('log'), q = document.getElementById('q');
const send = document.getElementById('send'), pw = document.getElementById('pw');
const bars = document.getElementById('bars'), banner = document.getElementById('banner');
const sid = (localStorage.qb_sid = localStorage.qb_sid || Math.random().toString(36).slice(2));
pw.value = localStorage.qb_pw || '';
pw.onchange = () => localStorage.qb_pw = pw.value;

function add(cls, text){ const d = document.createElement('div'); d.className = 'b ' + cls;
  d.textContent = text; log.appendChild(d); window.scrollTo(0, document.body.scrollHeight); return d; }

function metric(label, value){
  const m = document.createElement('div'); m.className = 'm';
  m.innerHTML = `<span>${label}</span><span class="track"><span class="fill" style="width:${value}%"></span></span>`;
  return m;
}
function renderBars(st){
  if (!st) return;
  bars.style.display = 'flex'; bars.innerHTML = '';
  bars.appendChild(metric('契约', st.contract));
  bars.appendChild(metric('怀疑', st.suspicion));
  bars.appendChild(metric('绝望', st.despair));
  bars.appendChild(metric('抗拒', st.resistance));
  const t = document.createElement('div'); t.className = 'm';
  t.textContent = `第 ${st.turn}/${st.max_turns || 12} 轮`; bars.appendChild(t);
}
function showEnding(title, tagline){
  if (!title) return;
  banner.style.display = 'block';
  banner.innerHTML = `<b>结局：${title}</b>${tagline || ''}<br>点「重新开始」可开启下一条时间线。`;
}

async function ask(){
  const text = q.value.trim(); if (!text) return;
  add('me', text); q.value = ''; send.disabled = true;
  const waiting = add('sys', '僕在计算……');
  try {
    const r = await fetch('/api/chat', { method:'POST',
      headers: {'Content-Type':'application/json', 'X-Access-Password': pw.value},
      body: JSON.stringify({ sid, message: text }) });
    const data = await r.json();
    waiting.remove();
    add(r.ok ? 'qb' : 'sys', data.answer || data.error || '未知错误');
    if (data.state) renderBars(data.state);
    showEnding(data.ending_title, data.ending_tagline);
  } catch (e) { waiting.remove(); add('sys', '连接失败：' + e); }
  finally { send.disabled = false; q.focus(); }
}
send.onclick = ask;
document.getElementById('reset').onclick = async () => {
  await fetch('/api/reset', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ sid }) });
  log.innerHTML = ''; banner.style.display = 'none'; bars.innerHTML = '';
  add('sys', '时间线已重置。第十二次轮回开始——或者，是第十三次。');
};
q.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } });
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "QB-Agent/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, payload):
        self._send(code, json.dumps(payload, ensure_ascii=False))

    def do_GET(self):
        if urlparse(self.path).path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}") if length else {}
        except (ValueError, json.JSONDecodeError):
            payload = {}

        if PASSWORD and self.headers.get("X-Access-Password", "").strip() != PASSWORD:
            return self._json(401, {"error": "口令不正确（请向分享者索取）"})

        sid = str(payload.get("sid") or "anon")[:64]

        if path == "/api/reset":
            with _lock:
                _sessions.pop(sid, None)
            return self._json(200, {"ok": True})

        if path != "/api/chat":
            return self._json(404, {"error": "not found"})

        message = str(payload.get("message") or "").strip()
        if not message:
            return self._json(400, {"error": "消息为空"})

        with _lock:
            today = time.strftime("%Y-%m-%d")
            if _counter["day"] != today:
                _counter["day"], _counter["n"] = today, 0
            if DAILY_LIMIT and _counter["n"] >= DAILY_LIMIT:
                return self._json(429, {"error": f"今日额度已用完（{DAILY_LIMIT} 条），请明天再来。"})
            _counter["n"] += 1

        session = _sessions.get(sid) or {}
        history = session.get("history")
        state = session.get("state") or (game.new_state() if GAME_MODE else None)

        try:
            if GAME_MODE:
                result = game.chat(message, history=history, state=state)
                answer, history, state = result["answer"], result["history"], result["state"]
                snapshot = dict(state, max_turns=game.MAX_TURNS)
                ending_title, ending_tagline = result["ending_title"], result["ending_tagline"]
            else:
                answer, history = run_agent(message, history=history, return_history=True)
                snapshot, ending_title, ending_tagline = None, "", ""
        except Exception as e:
            return self._json(500, {"error": f"服务端错误：{e.__class__.__name__}: {e}"})

        with _lock:
            _sessions[sid] = {"history": history[-60:], "state": state}   # 控制上下文长度与花费
        self._json(200, {"answer": answer, "state": snapshot,
                         "ending_title": ending_title, "ending_tagline": ending_tagline})

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), re.sub(r"\s+", " ", fmt % args)))


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = lan_ip()
    print("=" * 58)
    print("孵化者 · 契约终端 已启动" + ("（结局玩法：开）" if GAME_MODE else "（纯聊天模式）"))
    print(f"  本机访问：   http://127.0.0.1:{PORT}")
    print(f"  同 WiFi 同学：http://{ip}:{PORT}")
    print(f"  访问口令：   {PASSWORD if PASSWORD else '（未设置，任何人都能连）'}")
    print(f"  每日限额：   {DAILY_LIMIT if DAILY_LIMIT else '不限'}")
    print("  Ctrl+C 停止服务")
    print("=" * 58)
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
