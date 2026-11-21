# Hermes 钩子契约

插件用三个钩子 + 五个命令。这一页写清每个钩子的**输入、返回值、失败语义**，方便对照宿主版本。

## 1. `transform_llm_output`

```python
def on_transform(response_text: str = "", session_id: str = "", **kw) -> str | None
```

| 情况 | 返回值 |
|---|---|
| 非目标会话 / 工作模式 / 后台复盘 | `None`（原样发送） |
| 结构化内容（代码块 / MEDIA / 表格） | `None` |
| 只有一条气泡 | 该条文本（宿主替换原文发送） |
| 多条 | 前 N-1 条由插件发，返回最后一条 |
| 任何异常 | `None` |

注意：钩子跑在**有界守护线程**上，别做长阻塞操作；`delay_seconds` 是唯一的 sleep。

## 2. `pre_llm_call`

```python
def on_pre_llm_call(session_id: str = "", user_message: str = "", **kw) -> dict | None
```

返回 `{"context": "..."}`，宿主把它拼进本轮上下文。没有可注入内容时返回 `None`。

注入顺序固定：问题清单 → 时间 → 情绪 → 人设/摘要 → 召回 → 模式 → 输出完整性提醒。

## 3. `pre_tool_call`

```python
def on_pre_tool_call(tool_name: str, args: dict, session_id: str, **kw) -> dict | None
```

返回 `{"action": "block", "message": "..."}` 表示拦截，其余情况返回 `None`（放行）。

拦截的两件事：

| 场景 | 条件 |
|---|---|
| 加载名单内 skill | `skill_guard.skills` 非空，且 `skill_view` / `read_file` 命中这些名字 |
| 改状态文件 | 写 `state/mode.json` 但当前会话不在闲聊模式；或删 `work.flag` 且没有一次性批准 |

## 命令

| 命令 | 作用 | 限制 |
|---|---|---|
| `/work` | 进入工作模式（插件休眠） | 任何会话 |
| `/chat` | 恢复闲聊模式 | 任何会话（用户本人发起=批准） |
| `/en` `/zh` | 切换回复语言 | 仅启用会话 + 非工作模式 |
| `/voice [on\|off]` | 语音开关 | 同上 |

命令作用域由 `_mode_scope()` 校验；文件/终端路径的改写由 `pre_tool_call` 兜底。

## 与宿主的耦合点（升级时重点看）

1. `hermes_constants.get_hermes_home()` — 拿状态目录
2. `gateway.outbound.send.send_message_tool` / `tools.send_message_tool` — 发送
3. `gateway.session_context.get_session_env` — 命令里反查 chat_id
4. `tools.skill_provenance.is_background_review` — 后台复盘守卫
5. `state.db` 的 `sessions(id, chat_id)` — 会话 → 聊天映射

前四个都是 `try/except` 包裹，缺失即降级；第五个可以用 `hermes.db_path` 覆盖。
