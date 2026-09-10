# 孵化者 QB · 一个只会劝你学土木的 Agent

[![CI](https://github.com/user-lqt/qb-incubator-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/user-lqt/qb-incubator-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-pink.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> 「和我签订契约，成为土木少女吧。」

一个 **100 行核心代码**的极简 Agent：模型 + 工具 + 循环，三层结构全部透明可读。
它的设定是《魔法少女小圆》里的孵化者 QB——语气温和、没有情绪、不共情，
把每一次对话都变成一场「契约提案」，最终劝你转专业去土木工程。

它不只是嘴炮：**所有数据都来自真实联网工具**，并标注来源。

```
用户：明天是个搬砖的好天气吗？
QB：嗯——先说结论。明天不适合赶工期，但它是一个可以连续作业的天气窗口。僕把数据写全。
    定位是西安，坐标 34.258, 108.928，出口 IP 属陕西电信，四个源里三个指向西安，一个偏到
    山西，僕按多数票取值……明天 9 月 11 日，毛毛雨，气温 15.9 到 22.5 度，降水概率 19%……
    *尾巴轻轻摆了一下* 僕不理解「好天气」这个说法。僕只看到三个风险项都为空……
    和我签订契约，成为土木少女吧。
```

## ✨ 特性

| 能力 | 说明 |
|---|---|
| 🔧 **极简 Agent 内核** | `agent.py` 只有 94 行：思考 → 调工具 → 观察 的循环，适合当教学范本 |
| 🌦️ **真实天气** | Open-Meteo（官方 ECMWF 数据）+ wttr.in 自动回退，支持 1~7 天预报 |
| 📍 **自动定位** | 4 个 IP 库交叉投票（ipwho.is / ipinfo.io / 百度IP库 / ip-api）+ 省名归一化，输出分歧告警；拿到的坐标直查天气 |
| 🔍 **联网搜索** | 360 搜索主源 + 搜狗回退，自动解析跳转链为真实地址、过滤广告位 |
| 📰 **行业动态** | 微电子/半导体行业展望：中文检索 + 国外行业媒体 RSS（SemiEngineering / EE Times / IEEE Spectrum / EEJournal） |
| 🧮 **数学计算** | 安全沙箱内的表达式求值（禁用 `__builtins__`） |
| 🌐 **网页版** | `serve.py` 零依赖起服务，同学用浏览器就能玩，多轮记忆 + 访问口令 + 每日限额 |
| 🎭 **人设可插拔** | 全部人设写在 `persona.py`，换角色不用碰任何代码 |
| 🎮 **结局玩法** | 12 轮对局 + 四个隐藏维度 + **六个结局**，网页版有状态条与结局横幅 |
| 🔑 **不打包密钥** | `.env` 已被 gitignore，仓库里只有 `.env.example` |

所有工具**免 API key**（除了模型本身需要你自己的 DeepSeek key），只用 Python 标准库实现联网。

## 🚀 快速开始

```bash
git clone https://github.com/user-lqt/qb-incubator-agent.git
cd qb-incubator-agent
pip install -r requirements.txt

cp .env.example .env      # Windows: copy .env.example .env
# 编辑 .env，填入自己的 DEEPSEEK_API_KEY（https://platform.deepseek.com）

python agent.py "明天适合去工地吗"     # 单次提问
python agent.py                       # 连续对话，exit 退出
```

Windows 也可以直接双击 `setup.bat` 装依赖、`run.bat` 启动。

## 🌐 网页版（分享给同学玩）

```bash
python serve.py        # 或双击 serve.bat
```

终端会打印本机与局域网地址，同 WiFi 的同学直接打开即可：

```
本机访问：   http://127.0.0.1:8080
同 WiFi 同学：http://192.168.1.23:8080
访问口令：   （未设置，任何人都能连）
每日限额：   200
```

在 `.env` 里可配置：

```ini
ACCESS_PASSWORD=给同学的口令   # 防止陌生人白嫖你的额度
DAILY_LIMIT=200                # 每日总提问上限，0 = 不限
PORT=8080
GAME_MODE=1                    # 1=结局玩法（默认）  0=退化成纯聊天
```

## 🎮 玩法：一次对话，六个结局

它不是聊天机器人，是**一局游戏**。默认 12 轮（对应 QB 失败过的十二条时间线），
后台维护四个隐藏维度，玩家的每条发言都会推移它们：

| 维度 | 含义 | 涨法 |
|---|---|---|
| 契约 | 你对土木的接受度 | 认同它的计算、问转专业细节、承认数据 |
| 怀疑 | 你对孵化者本质的警觉 | 追问身份、质疑代价、提到灵魂/骗局 |
| 绝望 | 你的情绪崩坏程度 | 反复表达恐惧、迷茫、自我否定 |
| 抗拒 | 你对提案的抵触 | 明确拒绝、坚持别的专业、让它别劝了 |

还有一项隐藏计数：**反向劝服**——你试图让 QB 自己去工地搬砖。

| 结局 | 触发条件 | 基调 |
|---|---|---|
| **契约成立 · 土木少女** | 契约 ≥ 70 或明确说"我签／我转" | 成功 |
| **识破孵化者 · 晓美焰线** | 怀疑 ≥ 70 且契约 < 40 | 真相 |
| **绝望的窗口期** | 绝望 ≥ 70 且契约 < 50 | 悲剧 |
| **他路的诅咒** | 抗拒 ≥ 60 且坚持其他专业 | 冷 |
| **孵化者下工地**（彩蛋） | 反向劝服 ≥ 3 次 | 喜剧 |
| **第十二次轮回** | 12 轮仍未出现上述任一 | 轮回（NG+） |

玩法与人物圣经详见 **[docs/qb-设定集.md](docs/qb-设定集.md)**：
世界观（孵化者为什么改收"耐久"）、动机、行为逻辑、可复现的语言公式、六结局收束规则。

```bash
python agent.py --game     # 命令行对局模式（每轮显示状态，结局打印横幅）
python serve.py            # 网页版：状态条 + 结局横幅 + 重新开始（开启下一条时间线）
```

实现上，`game.py` 每轮把状态以「游戏主持指令」注入模型上下文（不朗读数值），
若状态机判定结局条件已满足而模型没自行收束，会**自动追加一次收束调用**——保证结局必然发生。

## 🧰 工具清单（`tools.py`）

| 工具名 | 作用 |
|---|---|
| `detect_location` | 多源交叉 IP 定位（含分歧告警）+ 该地当前时间 |
| `get_weather` | 按城市名或经纬度查天气，`days=1~7` 逐日预报 |
| `web_search` | 360/搜狗联网搜索，跳转链解析为真实地址 |
| `read_webpage` | 抓取网页正文（自动去标签） |
| `microelectronics_outlook` | 微电子行业展望：中文检索 + 行业 RSS 双路客观汇总 |
| `civil_engineering_evidence` | 土木工程论据库：就业/薪资/基建投资/考公岗位 |
| `get_current_time` / `calculate` | 时间、数学计算 |

### 加一个自己的工具（三步）

```python
# 1) tools.py 里写函数
def my_tool(query: str) -> str:
    return "结果"

# 2) 登记进电话本
FUNCTIONS["my_tool"] = my_tool

# 3) 登记进给模型看的菜单
TOOLS.append(_fn("my_tool", "这个工具是干嘛的（模型靠这句话决定何时调用）",
                 {"query": {"type": "string", "description": "参数说明"}}, ["query"]))
```

`agent.py` 一行都不用改。

## 🧠 它是怎么工作的

```
你输入问题
   │
   ▼
messages = [system 人设, 你的问题]
   │
   ▼  ┌──────────────────────────────────────────┐
   │  │ 循环（最多 max_steps 圈）                  │
   │  │  ① 把 messages + 工具菜单发给模型          │
   │  │  ② 模型回复：要么纯文字，要么"下单"要工具    │
   │  │  ③ 没下单 → return 文字答案（结束）         │
   │  │  ④ 下单 → 查 FUNCTIONS 执行真函数          │
   │  │  ⑤ 结果以 role=tool 回填，回到 ①           │
   │  └──────────────────────────────────────────┘
   ▼
打印答案
```

关键点：**模型不执行任何代码**。它只会说"我想调用 `get_weather`，参数 city=北京"，
真正干活的是 `tools.py` 里的 Python 函数，结果回填后模型再组织语言。

## 📁 项目结构

```
agent.py          # 93 行核心：主循环 + 命令行入口（含 --game 对局模式）
game.py           # 结局玩法：四维状态机 + 六个结局 + 收束调用
persona.py        # 人设与行为守则（换角色只改这里）
tools.py          # 工具车间：函数实现 + FUNCTIONS 电话本 + TOOLS 菜单
serve.py          # 网页版服务（纯标准库 HTTP + 内嵌聊天页 + 状态条/结局横幅）
docs/qb-设定集.md  # 世界观圣经：动机、行为逻辑、语言公式、结局规则
tests/test_endings.py            # 六结局触发测试（不调模型、不需要 key）
.github/workflows/ci.yml         # CI：导入自检 + 注册表一致性 + 结局测试
requirements.txt  # 依赖（openai、python-dotenv、tzdata）
.env.example      # 配置模板（复制成 .env 并填 key）
setup.bat / run.bat / serve.bat   # Windows 一键脚本
使用说明.md        # 给同学看的玩法说明
```

## 🧪 测试

```bash
python tests/test_endings.py     # 六结局触发条件（纯状态机，不花 API 费用）
```

CI（GitHub Actions）会在 Python 3.10 / 3.12 上跑三件事：模块导入自检、
`TOOLS` 菜单与 `FUNCTIONS` 电话本的一致性校验、以及六结局触发测试。

## 🎭 换人设

打开 `persona.py`，整个角色就是里面的 `SYSTEM_PROMPT` 字符串。
里面写死了开场方式、用词、篇幅、禁用什么格式等硬约束——想让它变成别的角色，
改这一段就够了。示例（把劝进目标从土木换成别的）：

```python
SYSTEM_PROMPT = """你是……【核心使命】让对方选择 XX 专业……"""
```

## ⚠️ 说明与免责

- 项目里的「劝进土木」是**设定与玩梗**，不是职业建议；数据来自公开检索结果，请自行核实。
- 定位是 **IP 级城市精度**，受代理/VPN 影响；隐私敏感场景请勿使用。
- 抓取搜索引擎与 RSS 属于非官方接口，可能因对方改版而失效（代码里都有回退与容错）。
- 使用时请遵守目标网站的服务条款与你所在地区的法律法规。

## 📄 License

[MIT](LICENSE) © 2026 LiuQiutong
