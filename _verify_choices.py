"""等部署 + 校验选项系统上线。"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

SITE = "https://user-lqt.github.io/qb-incubator-agent/"
REPO = "https://api.github.com/repos/user-lqt/qb-incubator-agent"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}
here = Path(__file__).resolve().parent


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


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                      text=True, cwd=here).stdout.strip()
deadline = time.time() + 420
while time.time() < deadline:
    runs = [x for x in api(REPO + "/actions/runs?per_page=8")["workflow_runs"]
            if x["name"].startswith("Deploy web") and x["head_sha"].startswith(head)]
    if runs and runs[0]["status"] == "completed":
        break
    time.sleep(20)
for x in [y for y in api(REPO + "/actions/runs?per_page=8")["workflow_runs"]
          if y["name"].startswith("Deploy web")][:2]:
    print(f"Pages 部署: {x['status']}/{x['conclusion']} ← {x['head_sha'][:7]}")
print("CI:", [r["conclusion"] for r in api(REPO + "/actions/runs?per_page=6")["workflow_runs"]
              if r["name"] == "CI"][:2])

page = urllib.request.urlopen(urllib.request.Request(SITE, headers=UA), timeout=60).read().decode("utf-8", "ignore")
gj = urllib.request.urlopen(urllib.request.Request(SITE + "game.js?v=13", headers=UA), timeout=60).read().decode("utf-8", "ignore")
aj = urllib.request.urlopen(urllib.request.Request(SITE + "agent.js?v=13", headers=UA), timeout=60).read().decode("utf-8", "ignore")
print("\n线上要素：")
for k, src in [("选项按钮样式 .choice", page), ("showChoices", page), ("版本 v13", page),
               ("CHOICE_MARKER 容错", gj), ("cleanMarkers", gj), ("_choicesOnly", aj)]:
    print(f"  {k}: {k in src}")

local = (here / "web" / "index.html").read_bytes()
remote = urllib.request.urlopen(urllib.request.Request(SITE + "index.html", headers=UA), timeout=60).read()
print("\nindex.html 线上与本地:", "一致 ✅" if local == remote else "待部署")
