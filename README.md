# 孵化者 QB · 一个只会劝你学土木的 Agent

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
| 🔑 **不打包密钥** | `.env` 已被 gitignore，仓库里只有 `.env.example` |

所有工具**免 API key**（除了模型本身需要你自己的 DeepSeek key），只用 Python 标准库实现联网。

## 🚀 快速开始

```bash
git clone https://github.com/<your-name>/qb-civil-agent.git
cd qb-civil-agent
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
```

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
agent.py          # 94 行核心：主循环 + 命令行入口
persona.py        # 人设与行为守则（换角色只改这里）
tools.py          # 工具车间：函数实现 + FUNCTIONS 电话本 + TOOLS 菜单
serve.py          # 网页版服务（纯标准库 HTTP + 内嵌聊天页）
requirements.txt  # 依赖（openai、python-dotenv、tzdata）
.env.example      # 配置模板（复制成 .env 并填 key）
setup.bat / run.bat / serve.bat   # Windows 一键脚本
使用说明.md        # 给同学看的玩法说明
```

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
