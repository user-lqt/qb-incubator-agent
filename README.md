# 孵化者 QB · 一个只会劝你学土木的 Agent

[![CI](https://github.com/user-lqt/qb-incubator-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/user-lqt/qb-incubator-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-pink.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/user-lqt/qb-incubator-agent?style=social)](https://github.com/user-lqt/qb-incubator-agent)

> 「和我签订契约，成为土木少女吧。」

《魔法少女小圆》里的孵化者 QB，用真实联网数据（天气、定位、行业资讯）把你劝进土木工程。
**100 行核心代码**的极简 Agent（模型 + 工具 + 循环），外面套了一层**文字冒险玩法**：
四维隐藏状态、动态轮数、六个结局、后日谈，以及一张可保存的结局卡片。

### ▶ 在线试玩：<https://user-lqt.github.io/qb-incubator-agent/>
填自己的 DeepSeek key（只存浏览器，不上传）即可开局。对话会自动存在本机，**刷新不丢进度**。

## 快速开始（本地 Python 版，功能最全）

```bash
git clone https://github.com/user-lqt/qb-incubator-agent.git && cd qb-incubator-agent
pip install -r requirements.txt
cp .env.example .env          # 填入自己的 DEEPSEEK_API_KEY（platform.deepseek.com）

python agent.py --game        # 开局：动态轮数 + 六个结局 + 后日谈
python agent.py "明天适合去工地吗"   # 或单次提问
```

Windows 可双击 `setup.bat` / `run.bat`；前端本地预览：`cd web && python -m http.server 8000`。

## 玩法

**一局 12 轮起**，四个隐藏维度随你的话变化：契约 / 怀疑 / 绝望 / 抗拒。

- **语义打分**：由模型判断每句话的影响（关键词机只作兜底），所以"我担心这条路走下坡路"这种
  含蓄表达也能被识别成情绪下沉。
- **动态轮数**：只要你在推进局势，上限就 +6（12 → 18 → … 上限 48）；含糊应付则 12 轮就归档。
- **分级披露 + 掩饰**：QB **绝不主动交底**。开场只给一句「僕可以替君实现一个愿望」，
  身份、代价、世界观被一层层逼出来（四级：初次接触 → 出现疑点 → 勉强承认出身 → 摊牌）；
  逼问不是解锁条件，越级说话会被系统自动重写。它对自己永远有所保留——不撒谎，只是没说完整。
- **对话选项**：每轮给 4 个带倾向的选项（接纳土木 / 追问真相 / 情绪下沉 / 抗拒），
  点一下就作为"明确表态"大幅推进剧情；也可以自由打字。

| 结局 | 触发 |
|---|---|
| 契约成立 · 土木少女 | 明确签约或契约值拉满 |
| 识破孵化者 · 晓美焰线 | 追问身份与代价 |
| 绝望的窗口期 | 情绪崩坏 |
| 他路的诅咒 | 坚持别的专业或明确拒绝 |
| 孵化者下工地（彩蛋） | 反过来劝它自己去工地 |
| 第十二次轮回 | 走满轮数也没做出决定 |

每条结局都有**后日谈**（200 字以上，调子偏黑）：签了约的人会看到自己的名字在名单第十一页、
第五十年那座桥因规划调整被拆掉；没签的人会看见城市在没人注意的地方慢慢老去。
唯一的例外是**「他路」**（坚持别的专业）：这是全场唯一一条**亮色**后日谈——
它留下的那句预言没有兑现，你没有被优化，名字也没被印在名单的任何一页，
但每天有人用着你顺手做的那一小块东西，家里的灯一直亮着。QB 在自己的记录末尾写下：
样本拒绝，状态良好。这一次，僕的预测错了。
结局触发时弹出**结局卡片**，可下载 PNG 或复制文案：

![结局卡片预览](docs/example-ending-card.png)

设定、动机、语言公式、后日谈与结局规则见 **[docs/qb-设定集.md](docs/qb-设定集.md)**；
给同学看的玩法说明见 **[使用说明.md](使用说明.md)**。

## 工具（`tools.py`，全部免 key、纯标准库联网）

`detect_location` 多源 IP 交叉定位 · `get_weather` 真实天气（1~7 天预报） · `web_search` 联网搜索 ·
`read_webpage` 读网页 · `microelectronics_outlook` 行业展望（中文检索 + 行业 RSS） ·
`civil_engineering_evidence` 土木论据库 · `get_current_time` · `calculate`

加工具只需三步：写函数 → `FUNCTIONS["名字"] = 函数` → `TOOLS.append(_fn(...))`，`agent.py` 不用改。

## 结构

```
agent.py      # 93 行核心：主循环 + CLI（含 --game 对局模式）
game.py       # 四维状态机 + 六结局 + 后日谈 + 语义评分与披露规则
persona.py    # 人设与行为守则（换角色只改这里，含掩饰规则）
tools.py      # 工具实现 + FUNCTIONS 电话本 + TOOLS 菜单
web/          # 纯前端版（BYOK，GitHub Pages 托管）
  ├─ index.html  # 界面：状态条、选项按钮、结局卡片、会话自动存档
  ├─ agent.js    # fetch 版内核 + 会话序列化/恢复 + 兼容垫片
  ├─ game.js     # 状态机/结局/后日谈（game.py 的 JS 移植）
  └─ tests/      # 前端回归测试（node，不调模型）
docs/         # 世界观圣经 + 结局卡片示例图
tests/        # 结局、披露、后日谈测试（不调模型、不花钱）
tools/        # 人设同步、头像与背景图、favicon 生成脚本
```

换人设：改 `persona.py` 的 `SYSTEM_PROMPT`，再 `python tools/sync_persona.py` 同步到前端（CI 会校验）。
换头像/背景：`web/qb.png`、`web/bg.jpg` 直接覆盖，或用 `tools/make_avatar.py`、`tools/make_background.py` 生成。

## 说明

- 「劝进土木」是**设定与玩梗**，不是职业建议；数据来自公开检索，请自行核实。
- IP 定位为城市级精度，受代理/VPN 影响；抓取类接口可能因对方改版失效（代码里有回退容错）。
- 仓库不含任何密钥：`.env` 已 gitignore，前端 key 与对话记录只存在访客自己的浏览器里。
- 角色相关图片版权请自行确认。

## License

[MIT](LICENSE) © 2026 LiuQiutong
