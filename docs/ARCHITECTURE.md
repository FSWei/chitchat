# 架构

四层，依赖方向单向：`adapters → pipeline → core`，`context/providers` 只被适配器读取。

```
adapters/hermes.py     钩子接线（transform / pre_llm / pre_tool）+ 命令
   ├─ pipeline.py      文本 → 气泡（纯计算）
   │    └─ core.py     纯函数：切分 / 打包 / 去重 / 禁词 / markdown
   ├─ context.py       注入块拼装（时间、情绪、人设、模式）
   │    └─ providers/   TextProvider / HistoryProvider
   ├─ modes.py         工作模式 flag、语言/语音模式（文件状态）
   └─ adapters/transport.py  发送通道（Protocol + Hermes 实现）
```

## 为什么这么切

| 层 | 换掉它意味着 | 不换的理由 |
|---|---|---|
| `core` | 重写算法 | 零依赖，单测覆盖，谁都能 import |
| `pipeline` | 换处理顺序 | 一条链路看清楚"改了什么" |
| `context` | 换注入内容 | 配置驱动，不写死任何人的资料 |
| `adapters` | 换宿主 | 只有这一层知道 Hermes 的钩子名和发送 API |

## 一次回复的完整链路

```
模型输出
  │
  ├─ 后台复盘 / 非目标会话 / 工作模式 → 原样放行（None）
  │
  ├─ core.is_structured（代码块 / MEDIA / 表格）→ 整条放行
  ├─ 黑名单替换 → markdown 剥离 → 复读去重
  ├─ core.split_to_bubbles → [b1, b2, ..., bn]
  │
  └─ 发 b1..bn-1（Transport，带 delay）→ 返回 bn（宿主正常投递）
```

任何一步抛异常 → 记日志 → 返回 `None`（原文照发）。**不允许吞消息。**

## 状态

| 文件 | 作用 | TTL |
|---|---|---|
| `state/work.flag` | 工作模式：插件完全休眠 | `work_ttl_hours`（默认 12h） |
| `state/chat-ok.flag` | "用户批准切回闲聊"的一次性凭证 | `chat_ok_ttl_minutes`（默认 10min） |
| `state/mode.json` | 语言 / 语音开关 | 无（持久） |
| `state/recall/*.json` | 按日期召回缓存 | `cache_days`（默认 90 天） |
| `state/chitchat.log` | 审计：每次决策一行 | 1MB 轮转 |

## 失败模式

| 场景 | 行为 |
|---|---|
| config.json 坏了 | 用上次成功加载的值；从没成功过则 `enabled=false` |
| 发送第 k 条失败 | 把剩下的拼成一条返回，内容不丢不重 |
| 历史库不存在 | 召回功能静默关闭 |
| provider 文件缺失 | 跳过该段注入 |
| 钩子内部异常 | 返回 `None`，原文照发 |
