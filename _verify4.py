import hashlib
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

SITE = "https://user-lqt.github.io/qb-incubator-agent/"
REPO = "https://api.github.com/repos/user-lqt/qb-incubator-agent"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}
here = Path(__file__).resolve().parent

html = (here / "web" / "index.html").read_text(encoding="utf-8")
m = re.search(r'<script type="module">(.*?)</script>', html, re.S)
tmp = here / "_chk.mjs"
tmp.write_text(m.group(1), encoding="utf-8")
r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
tmp.unlink()
print("内联脚本语法:", "OK" if r.returncode == 0 else r.stderr[:300])
print("头像加载链:", '"./qb.png", "./qb.jpg", "./qb.svg"' in html)


def api(url, tries=5):
    last = None
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=40).read())
        except Exception as e:
            last = e
            time.sleep(4 * (i + 1))
    raise last


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                      cwd=here).stdout.strip()
deadline = time.time() + 360
while time.time() < deadline:
    runs = [x for x in api(REPO + "/actions/runs?per_page=8")["workflow_runs"]
            if x["name"].startswith("Deploy web") and x["head_sha"].startswith(head)]
    if runs and runs[0]["status"] == "completed":
        break
    time.sleep(20)

for x in [y for y in api(REPO + "/actions/runs?per_page=8")["workflow_runs"]
          if y["name"].startswith("Deploy web")][:2]:
    print(f"Pages 部署: {x['status']}/{x['conclusion']} ← {x['head_sha'][:7]}")

print("\n线上 vs 本地：")
ok = True
for name in ["index.html", "qb.png", "qb.svg", "agent.js", "game.js", "persona.js"]:
    local = (here / "web" / name).read_bytes()
    with urllib.request.urlopen(urllib.request.Request(SITE + name, headers=UA), timeout=40) as res:
        remote = res.read()
    same = hashlib.sha256(local).hexdigest() == hashlib.sha256(remote).hexdigest()
    ok &= same
    print(f"  {name:<12}{len(local):>7} vs {len(remote):>7}  {'一致' if same else '待部署'}")

print("\n状态:", "全部同步 🎉" if ok else "Pages 还在部署，稍等刷新")
