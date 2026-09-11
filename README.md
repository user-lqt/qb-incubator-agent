# 孵化者 QB · 一个只会劝你学土木的 Agent

[![CI](https://github.com/user-lqt/qb-incubator-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/user-lqt/qb-incubator-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-pink.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/user-lqt/qb-incubator-agent?style=social)](https://github.com/user-lqt/qb-incubator-agent)

> 「和我签订契约，成为土木少女吧。」

《魔法少女小圆》里的孵化者 QB，用真实联网数据（天气、定位、行业资讯）把你劝进土木工程。
**100 行核心代码**的极简 Agent：模型 + 工具 + 循环，全部可读。**一局 16 轮起，六个结局。**

### ▶ 在线试玩：<https://user-lqt.github.io/qb-incubator-agent/>
填自己的 DeepSeek key（只存浏览器）即可开局，无需安装。

## 快速开始（本地 Python 版，功能最全）

```bash
git clone https://github.com/user-lqt/qb-incubator-agent.git && cd qb-incubator-agent
pip install -r requirements.txt
cp .env.example .env          # 填入自己的 DEEPSEEK_API_KEY（platform.deepseek.com）

python agent.py --game        # 开局：动态轮数 + 六个结局
python agent.py "明天适合去工地吗"   # 或单次提问
```

Windows 也可双击 `setup.bat` 装依赖、`run.bat` 启动。前端本地预览：`cd web && python -m http.server 8000`。

## 玩法

四个隐藏维度（契约 / 怀疑 / 绝望 / 抗拒）随你的每句话变化，**由模型语义打分**（关键词机仅兜底）。

QB **绝不主动交底**：开场只给一句「僕可以替君实现一个愿望」，世界观、代价、它的来历都是被一层层问出来的
（四级披露：初次接触 → 出现疑点 → 追问代价 → 摊牌）。追问不会让它松口，只有状态到了才解锁；
越级说话会被系统自动重写。详见 [docs/qb-设定集.md](docs/qb-设定集.md)。

| 结局 | 触发 |
|---|---|
| 契约成立 · 土木少女 | 明确签约或契约值拉满 |
| 识破孵化者 · 晓美焰线 | 追问身份与代价 |
| 绝望的窗口期 | 情绪崩坏 |
| 他路的诅咒 | 坚持别的专业或明确拒绝 |
| 孵化者下工地（彩蛋） | 反过来劝它自己去工地 |
| 第十二次轮回 | 走满轮数也没做出决定 |

轮数动态：起点 16 轮，只要你还在推进就 +8（上限 64）；含糊应付则 16 轮归档。
设定、动机、语言公式、结局规则见 **[docs/qb-设定集.md](docs/qb-设定集.md)**，给同学的说明见 **[使用说明.md](使用说明.md)**。

## 工具（`tools.py`，全部免 key）

`detect_location` 多源 IP 定位 · `get_weather` 真实天气（1~7 天） · `web_search` 联网搜索 ·
`read_webpage` 读网页 · `microelectronics_outlook` 行业展望 · `civil_engineering_evidence` 土木论据 ·
`get_current_time` · `calculate`

加工具只需三步：写函数 → `FUNCTIONS["名字"]=函数` → `TOOLS.append(_fn(...))`，`agent.py` 不用改。

## 结构

```
agent.py      # 93 行核心：主循环 + CLI（含 --game）
game.py       # 四维状态机 + 六结局 + 必胜收束
persona.py    # 人设与行为守则（换角色只改这里）
tools.py      # 工具实现 + FUNCTIONS 电话本 + TOOLS 菜单
web/          # 纯前端版（BYOK，GitHub Pages 托管）
docs/         # 世界观圣经
tests/        # 六结局触发测试（不调模型、不花钱）
```

换人设：改 `persona.py` 里的 `SYSTEM_PROMPT`，然后 `python tools/sync_persona.py` 同步到前端。
头像：`web/qb.png`（换图直接覆盖，或 `python tools/make_avatar.py 你的图.png`）。

## 说明

- 「劝进土木」是**设定与玩梗**，不是职业建议；数据来自公开检索，请自行核实。
- IP 定位为城市级精度，受代理/VPN 影响；抓取类接口可能因对方改版失效（代码有回退容错）。
- 仓库不含你的密钥：`.env` 已 gitignore，前端 key 只存访客浏览器。
- 角色相关图片版权请自行确认。

## License

[MIT](LICENSE) © 2026 LiuQiutong
