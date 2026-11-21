# chitchat

**一个「人格化 agent」的表达层与注入层。**

大多数 agent 只解决"能不能答对"；chitchat 解决另一半——**答出来的东西像不像一个具体的人说的**：

- 输出**形态**：一段变几条、每条多长、有没有 Markdown 痕迹（表达层）
- 上下文**装配**：这一轮该注入时间、情绪、记忆摘要还是行为规则，按什么顺序（注入层）

它不生成内容、不存人设——人设和记忆属于宿主（skill / 文件 / 数据库）。它负责让这些内容在正确的时机、以正确的形态出现。

零依赖纯函数核心 + 一个 Hermes 适配器；不用 Hermes 也能当库用。

```
pip install -e .
python examples/demo.py     # 153 字 → 6 条气泡，不用任何宿主
```

## 在人格化 agent 里，它站在哪一层

一个"长期在线的 AI 角色"通常拆成五层，chitchat 只占最右两列：

| 层 | 职责 | 典型载体 | 本仓库 |
|---|---|---|---|
| 身份 | 它是谁、长什么样、过着什么生活 | persona 文本、角色卡 | ❌ 宿主 |
| 记忆 | 记得什么、忘掉什么、多久蒸馏一次 | 3 天原文 → 14 天蒸馏 → 永久归档 | 🔌 提供读取接口 |
| **注入** | 每轮把哪些片段塞进上下文、顺序与长度预算 | 钩子 + 配置文件 | ✅ |
| 行为 | 什么场景怎么说、什么时候闭嘴 | 行为规则文档（skill） | ❌ 宿主 |
| **表达** | 几条、多长、什么格式、失败怎么办 | 本仓库 core + pipeline | ✅ |

所以：**仓库里没有人设内容，但它是为人格化 agent 设计的那两层**。你可以只拿表达层当排版工具，也可以把它接到自己的角色系统上。

---

## 30 秒上手（当库用）

```python
from chitchat import transform

bubbles = transform(model_output, {
    "strip_markdown": True,
    "dedup_repetition": True,
    "blacklist": {"总之": "", "希望这能帮到你": ""},
    "bubble": {"target_chars": 70, "pack_limit": 140, "max_bubbles": 12},
})

for b in bubbles[:-1]:      # 前 N-1 条自己发
    send(chat_id, b)
return bubbles[-1]          # 最后一条走正常回复
```

返回 `["...", "...", "..."]`。含代码块 / 表格 / `MEDIA:` 的回复原样返回一条，不拆。

## 它做什么

| 能力 | 说明 |
|---|---|
| 分气泡 | 换行=气泡边界；行内按句打包到 `target_chars`，单条不超 `pack_limit`，超出 `max_bubbles` 合并尾部（不丢内容） |
| 复读防护 | 尾部整块重复迭代删除；短促重复（"哈哈"）保留 |
| 禁词表 | `{"禁词": "替换值"}`，值为空串即删除 |
| Markdown 剥离 | 标题井号、`**加粗**`、`__下划线__`、列表符号 |
| 上下文注入 | 时间（可多时区）、情绪/人设文本、按日期召回历史、当前模式 |
| 模式 | `/work` 休眠、`/chat` 恢复、`/en` `/zh` 语言、`/voice` 语音 |
| 守卫 | 名单内 skill 不许加载、状态文件不许乱改（都可关） |

## 它不做什么

- ❌ 不生成、不存储人设——只从宿主给的文件里**读**（`providers.persona` / `mood` / `digest`）
- ❌ 不实现记忆生命周期（提炼、蒸馏、归档），只提供按日期**查询**接口
- ❌ 不合成语音，只提示模型输出 `MEDIA:`
- ❌ 不决定"说什么"，只决定**说成什么样**
- ❌ 不绑定任何 IM：发送由 `Transport` 协议提供，自带 Hermes 实现

## 注入顺序为什么重要

`pre_llm_call` 的注入块不是随便拼的。顺序决定模型把注意力放在哪：

```
1. 本轮问题清单      ← 先保证"这几件事都要答"
2. 时间              ← 防止把预测当已发生
3. 情绪 / 人设摘要    ← 决定语气
4. 记忆召回          ← 只在命中"日期+记忆动词"时出现
5. 语言/语音模式      ← 决定输出形态
6. 输出完整性约束     ← 最后一句，防止"只说不做"
```

每一段都有长度上限（`inject.mood_max_chars`、provider 默认 600–800 字），超了截断加省略号——**注入不是越多越好，多了会稀释规则**。

## 安装

### A. 当 Python 库

```bash
git clone https://github.com/FSWei/chitchat
cd chitchat
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

Python ≥ 3.9，无运行时依赖。

### B. 当 Hermes 插件

插件目录里必须有 `plugin.yaml` 和 `__init__.py`。本仓库的 `hermes_plugin/` 就是这样一个目录：

```bash
git clone https://github.com/FSWei/chitchat ~/chitchat

# 1. 挂进 profile（软链，改代码即时生效；也可直接 cp -r）
ln -s ~/chitchat/hermes_plugin ~/.hermes/profiles/<profile>/plugins/chitchat

# 2. 配置：放插件目录或 CHITCHAT_HOME 指向的目录
mkdir -p ~/.hermes/chitchat && cp ~/chitchat/examples/config.example.json ~/.hermes/chitchat/config.json
# 在 profile 的 env 里设：CHITCHAT_HOME=~/.hermes/chitchat

# 3. 启用 + 校验
hermes plugins validate ~/chitchat/hermes_plugin   # 应输出 Validation passed
hermes plugins enable chitchat
```

启用后**重启网关进程**（插件只在启动时加载）。`hermes plugins validate` 会实跑一次 `register()`，能过就说明钩子声明和真实注册一致。

`config.json` 按 mtime 热加载，改完不用重启；`chat_ids` 只填你想管的会话，其它会话完全不受影响（`enabled: false` 时全局休眠）。

## 配置

完整示例见 [`examples/config.example.json`](examples/config.example.json)。常改的几项：

| 键 | 默认 | 说明 |
|---|---|---|
| `enabled` | `false` | 总开关 |
| `chat_ids` | `[]` | 只管这些会话；空 = 谁都不管 |
| `bubble.target_chars` | `70` | 单条目标长度 |
| `bubble.pack_limit` | `140` | 单条硬上限 |
| `bubble.max_bubbles` | `12` | 超过则合并尾部 |
| `bubble.delay_seconds` | `1.2` | 气泡间间隔 |
| `blacklist` | `{}` | 禁词 → 替换值（空串=删） |
| `strip_markdown` | `true` | 去掉 Markdown 结构 |
| `dedup_repetition` | `true` | 复读防护 |
| `inject.*` | 全开 | 时间 / 情绪 / 人设 / 模式 / 问题清单 / 中文片段 |
| `recall.enabled` | `false` | 按日期召回（需 `providers.history_db`） |
| `providers.*` | 空 | mood / persona / digest 文件路径、history_db |

细节：[`docs/RUNTIME.md`](docs/RUNTIME.md)（人格化 agent 的分层与记忆生命周期）、[`docs/PROVIDERS.md`](docs/PROVIDERS.md)（上下文源）、[`docs/SKILL-TEMPLATE.md`](docs/SKILL-TEMPLATE.md)（人设/风格该写在哪）。

## 命令（Hermes 内）

| 命令 | 作用 | 作用域 |
|---|---|---|
| `/work` | 进入工作模式（插件完全休眠） | 任何会话 |
| `/chat` | 恢复闲聊模式 | 任何会话 |
| `/en` `/zh` | 切换回复语言 | 仅启用会话、非工作模式 |
| `/voice [on\|off]` | 语音开关 | 同上 |

工作模式默认 12h 自动过期（`flags.work_ttl_hours`），不会把你永久静音。

## 目录

```
chitchat/
├── chitchat/
│   ├── core.py        分气泡 / 打包 / 去重 / 禁词 / markdown（纯函数）
│   ├── config.py      schema + 校验 + mtime 热加载
│   ├── context.py     注入块拼装
│   ├── recall.py      按日期召回（日期 + 记忆动词双闸）
│   ├── modes.py       工作模式 flag、语言/语音模式
│   ├── pipeline.py    core 的处理链
│   ├── providers/     TextProvider / HistoryProvider + SqliteHistory
│   └── adapters/      hermes.py（三钩子五命令）、transport.py
├── hermes_plugin/     Hermes 插件目录（plugin.yaml + shim）
├── examples/          demo.py、config.example.json
├── tests/             33 个用例
├── docs/              ARCHITECTURE / RUNTIME / PROVIDERS / HOOKS / SKILL-TEMPLATE
└── scripts/privacy_scan.py
```

## 设计取舍

1. **失败即放行**：任何异常返回 `None`（原文照发）——插件不能吞消息。
2. **状态是文件**：`state/work.flag`、`state/mode.json` 肉眼可查、可手改，不用数据库。
3. **上下文靠 provider**：两个 Protocol，接自己的记忆系统不用改源码；没有 provider 就什么都不注入。
4. **仓库无个人内容**：人设、词表、chat_id 全在 `config.json` 或 provider 指向的文件里。

## 测试

```bash
python -m pytest                    # 33 passed（core / config / modes / context / adapter）
python examples/demo.py             # 冒烟
python scripts/privacy_scan.py      # 发布前自检：姓名、手机、邮箱、密钥、绝对路径
```

`docs/ci.yml.example` 是 GitHub Actions 配置（pytest + 隐私扫描 + demo），复制到 `.github/workflows/ci.yml` 即可启用。

## 已知限制

- 钩子名绑定 Hermes 的 `transform_llm_output` / `pre_llm_call` / `pre_tool_call`；换宿主需要写新的 adapter（约 150 行，参考 `adapters/hermes.py`）。
- 召回只支持按天查；默认表结构是 Hermes 的 `sessions` / `messages`。
- 语音模式只负责提示模型调用 TTS 并输出 `MEDIA:`，具体 TTS 由宿主提供。

## License

MIT
