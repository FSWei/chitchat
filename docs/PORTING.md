# 换宿主：要改哪三处

约束只有一句话：**宿主提供三个事件 + 一个发送通道，其余与宿主无关。**

仓库里能跨宿主的部分：`core`（纯函数）、`pipeline`、`context`、`recall`、`modes`、`config`、`providers`、`memory/lifecycle.py`、`life/*.py`。
只有 `adapters/hermes.py` 是宿主专用的。

## 三处改造

### 1. 输出前拦截 → 分条

宿主在消息发出前给你一次改写机会，或者给你一个「发消息」的 API：

| 宿主 | 对应物 |
|---|---|
| Hermes | `transform_llm_output` 钩子（返回原文 = 放行，返回值 = 替换） |
| 其他 | 发送前的中间件；或直接接管发送函数 |

拿到模型输出后：

```python
bubbles = transform(text, cfg)          # 返回列表
if len(bubbles) == 1: return bubbles[0] # 单条 = 不改写
for b in bubbles[:-1]: send(chat_id, b) # 前 N-1 条自己发
return bubbles[-1]                      # 最后一条走宿主正常投递
```

发送失败时把剩下的拼回一条返回——**不许吞消息**。

### 2. 每轮上下文注入 → 注入

宿主在调用模型前给你一次加料机会：

```python
ctx = build_injection(cfg, user_message, state.mode(), recall_block)
if ctx:
    return {"context": ctx}   # Hermes：拼进 system/context
```

没有这个事件也能退化：把 `ctx` 写进你的 system prompt 模板，效果差一点（不能按轮变化）。

### 3. 工具调用前拦截 → 守卫

宿主在执行工具前给你一次否决机会（Hermes 是 `pre_tool_call`）：

```python
return {"action": "block", "message": "这个会话不允许加载 X"}
```

没有这个事件就删掉守卫——守卫是加分项，不是骨架必需。

## 还要接的

| 东西 | 怎么接 |
|---|---|
| 会话标识 | 宿主的 session id → 你的 chat/conversation id；白名单按它判断 |
| 发送通道 | 实现 `Transport`（一个 `send(chat_id, text)` 方法，20 行） |
| 配置 | `config.json` 放 `CHITCHAT_HOME` 指向的目录，按 mtime 热加载 |
| 状态 | `state/work.flag`、`state/mode.json`、`state/recall/`，都是文件 |
| 命令 | 可选。`/work` `/chat` `/en` `/zh` `/voice`，没有也能用配置文件切 |

## 最小适配器骨架

```python
from pathlib import Path
from chitchat.config import ConfigLoader
from chitchat.modes import State
from chitchat.pipeline import transform
from chitchat.context import build_injection

class MyHostAdapter:
    def __init__(self, home: Path):
        self.home = home
        self.loader = ConfigLoader(home / "config.json")
        self.state = State(home / "state", self.loader.load)

    def before_send(self, text: str, conv_id: str):
        if not self.state.active(lambda _: conv_id, conv_id):
            return None                      # 不管这个会话
        bubbles = transform(text, self.loader.load())
        for b in bubbles[:-1]:
            self.send(conv_id, b)
        return bubbles[-1] if bubbles else ""

    def before_llm(self, conv_id: str, user_message: str):
        if not self.state.active(lambda _: conv_id, conv_id):
            return None
        return build_injection(
            self.loader.load(), user_message, self.state.mode()
        )

    def send(self, conv_id: str, text: str):
        raise NotImplementedError
```

## 验收三点

1. **分条生效**：发一句长回答，收到的是几条而不是一条；含代码块/表格的回复**不拆**。
2. **白名单生效**：不配置的会话里，长回答原样返回一条。
3. **失败放行**：把 `config.json` 改成非法 JSON，消息仍然照常发出（用上次成功的配置，或全放行）。

三条都过，就说明接线是对的；剩下的都是配置文件里的开关。
