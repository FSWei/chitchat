# chitchat

一套让 agent 变成「一个人」的骨架。

模型能答对问题，但答得像不像一个具体的人，是另一回事：一次吐一整篇、把设定忘光、日子只有今天、说的话没有自己的味道。这套东西专门治这几件事。

八块，看这个仓库给了什么：

| 块 | 管什么 | 本仓 |
|---|---|---|
| 身份 | 她是谁、长什么样 | 待补：示例角色 + 人设模板（P2） |
| 生活 | 分段日记、水位、防漂移 | `life/` + [docs/LIFE.md](docs/LIFE.md) |
| 世界 | 新闻 0–1 条、真实天气一句 | `life/news_fetch.py` + [docs/WORLD.md](docs/WORLD.md) |
| 形象 | 日记 → 照片：三层提示词 | [docs/IMAGE.md](docs/IMAGE.md)（不含出图代码） |
| 记忆 | 3 天原文 → 14 天蒸馏 → 永久归档 | 读取接口 + [docs/RUNTIME.md](docs/RUNTIME.md) |
| 说话 | 几条、多长、什么格式 | `chitchat/core.py`、`pipeline.py` |
| 调度 | 谁替她跑：定时任务、任务书、水位 | [docs/RUNTIME.md](docs/RUNTIME.md)（跟宿主有关） |
| 约束 | 白名单、写闸、TTL、失败放行 | `chitchat/modes.py` + adapter |

分工一句话：**人设和记忆属于宿主，这套东西管「什么时候塞什么进上下文」和「塞进去之后长什么样」。**

## 为什么不能只靠提示词

三条，每条在本仓都有对应的代码或脚本：

1. 规则写在提示词里，模型会「合理化」绕过它。分条、去重、禁词、markdown 剥离是代码，不是建议 —— `chitchat/core.py`。
2. 日子只有今天，就只能靠预报；预报到第二天必然对账，对账会自我增殖。所以日记只写**已经过完的那一段**，水位脚本管到哪一刻 —— `life/journal_state.py`。
3. 记得一切等于什么都没记住。3 天原文、14 天蒸馏、永久归档；模型平时只读蒸馏后的结论。

## 30 秒上手（当库用）

```python
from chitchat import transform

bubbles = transform(model_output, {
    "strip_markdown": True,
    "dedup_repetition": True,
    "blacklist": {"总之": "", "希望这能帮到你": ""},
    "bubble": {"target_chars": 70, "pack_limit": 140, "max_bubbles": 12},
})

for b in bubbles[:-1]:
    send(chat_id, b)
return bubbles[-1]
```

返回气泡列表；含代码块 / 表格 / `MEDIA:` 的回复原样返回一条，不拆。

## 三分钟看它怎么跑

- **日记**：`python3 life/journal_state.py status` → 只有 `SHOULD_RUN=yes` 才写，写完 `commit` 推进水位；两次间隔不到 90 分钟直接跳过。
- **新闻**：`python3 life/news_fetch.py fetch` → 当天缓存，7 个源，混合取样最多 14 条标题；从里面挑 **0 或 1 条**写进日记，没有就不写。
- **照片**：日记每一段带「衣着 / 发型 / 情绪 / 位置 / 活动」五个字段；出图时拼 `基础特征 + 当天状态 + 场景`，光线按「情绪 × 天气 × 时间」查表。
- **记忆**：3 天原文 → 蒸馏成场景式记忆保留 14 天 → 进永久归档。蒸馏只复制、不删原文。

## 安装

### 当 Python 库

```bash
git clone https://github.com/FSWei/chitchat
cd chitchat
python -m venv .venv && . .venv/bin/activate
pip install -e .
python examples/demo.py
```

Python ≥ 3.9，无运行时依赖（Windows 会多装一个 `tzdata`）。

### 当 Hermes 插件

```bash
ln -s ~/chitchat/hermes_plugin ~/.hermes/profiles/<profile>/plugins/chitchat
mkdir -p ~/.hermes/chitchat
cp ~/chitchat/examples/config.example.json ~/.hermes/chitchat/config.json
# 在 profile 的环境变量里设 CHITCHAT_HOME=~/.hermes/chitchat，然后重启网关
```

`config.json` 按 mtime 热加载，改完不用重启；`chat_ids` 只填你想管的会话，其它会话完全不受影响。

## 隐私默认值

- `enabled: false`、`chat_ids: []`：装了什么都不做，必须显式指定会话。
- provider 路径默认为空：不填就不注入任何个人内容。
- 召回默认关闭；打开要自己给 `providers.history_db`。
- 仓库里没有作者的人设、聊天记录、照片。示例角色是虚构的，示例日记是新写的。
- 运行时产生的 `life/state.json`、`life/journal.md`、`life/news/` 都在 `.gitignore` 里。

## 现在到哪一步

| 阶段 | 内容 | 状态 |
|---|---|---|
| P1 | 表达层与注入层（分条 / 去重 / 禁词 / 召回 / 守卫）、33 个用例、隐私扫描 | ✅ 已有 |
| P1 | 日记水位脚本、新闻抓取脚本、八块文档 | ✅ 本次 |
| P2 | 示例角色、3 篇样例日记、1 段对话样例、5 张示例图 | 待做 |
| P3 | 记忆链路脚本、定时任务书模板、换宿主说明、出图脚本 | 待做 |

## 目录

```
chitchat/
├── chitchat/          库本体（纯函数 core、config、context、recall、modes、providers、adapters）
├── hermes_plugin/     Hermes 插件目录（plugin.yaml + shim）
├── life/              她的日子：日记水位、新闻抓取
├── examples/          demo.py、config.example.json
├── tests/             33 个用例
├── docs/              RUNTIME（总览）/ LIFE / WORLD / IMAGE / ARCHITECTURE / HOOKS / PROVIDERS / SKILL-TEMPLATE
└── scripts/           privacy_scan.py（发布前自检）
```

## 局限

- 钩子名绑 Hermes 的 `transform_llm_output` / `pre_llm_call` / `pre_tool_call`；换宿主写 adapter，约 150 行。
- 召回只支持按天查，默认表结构是 Hermes 的 `sessions` / `messages`。
- 形象模块只给方法，不含出图调用（出图要自己的 key）。
- 她的一天靠定时任务驱动：机器关着就不发生，开机后补跑会迟到。

## License

MIT
