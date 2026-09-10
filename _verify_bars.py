"""等部署并校验线上状态条修复。"""
import hashlib
import json
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


head = __import__("subprocess").run(["git", "rev-parse", "--short", "HEAD"],
                                    capture_output=True, text=True, cwd=here).stdout.strip()
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

local = (here / "web" / "index.html").read_bytes()
remote = urllib.request.urlopen(urllib.request.Request(SITE + "index.html", headers=UA), timeout=60).read()
print("index.html 线上与本地:", "一致 ✅" if local == remote else "待部署")

page = remote.decode("utf-8", "ignore")
print("\n线上修复项：")
for key in ["#bars .fill { display:block", "#bars .track { display:inline-block",
            "fill.contract", "fill.suspicion", "fill.despair", "fill.resistance", "min-width:6px"]:
    print(f"  {key}: {key in page}")
