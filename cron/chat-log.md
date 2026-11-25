# 聊天记忆任务书（模板）

> 占位符：`{{DATA_DIR}}` 数据目录 · `{{QUERY_CMD}}` 你的取消息命令（见下）

## 0. 分工

机械操作走脚本，你只负责**总结**和**蒸馏**。四层文件：

| 文件 | 保留 | 谁读 |
|---|---|---|
| `chat-log.md` | 3 天 | 模型每轮 |
| `chat-archive.md` | 永久 | 只给人看 |
| `long-term-memory.md` | 14 天 | 模型可读 |
| `deep-archive.md` | 永久 | 只给人看 |

## 1. 自检上一轮

```bash
python3 {{DATA_DIR}}/lifecycle.py check
```

- 输出 `WARNING`：说明上一轮查到消息但没推进 checkpoint。本轮必须补完；完不成就在报告里写明。
- 输出 `OK`：继续。

## 2. 取新消息

```bash
{{QUERY_CMD}}
```

`query` 这一步跟宿主强相关，仓库不提供：你要从自己的会话库里取出「checkpoint 之后」的消息（`role` 只取 user/assistant，跳过纯工具调用和系统注入前缀）。

取到 N 条后记一下：

```bash
python3 {{DATA_DIR}}/lifecycle.py pending <N>
```

输出 `NO_NEW_MESSAGES` → 直接跳到第 5 步（归档维护仍要跑），结束。

## 3. 总结（写）

把对话压成要点，追加到 `chat-log.md`：

```markdown
## YYYY-MM-DD

### HH:MM - HH:MM（北京时间）
- 要点 1（具体，有细节）
- 要点 2
- 氛围：xxx
```

规则：

- **只追加**，不覆盖、不删已有内容。
- 跳过纯技术/工作过程（配置、调试、部署），记「人和人的部分」：情绪、决定、承诺、关系变化。
- 同一天已有条目 → 追加到那天末尾，不要新建第二个 `##` 头。

## 4. 推进 checkpoint（必须）

```bash
python3 {{DATA_DIR}}/lifecycle.py advance <最新消息时间戳>
```

- 只在第 3 步**写成功之后**才执行。
- 脚本拒绝倒退；如果报 `REFUSED`，说明消息时间戳取错了。

## 5. 归档 + 蒸馏

```bash
python3 {{DATA_DIR}}/lifecycle.py archive --days 3
```

输出里会带**被移出的原文**。把它们蒸馏成场景式记忆，追加到 `long-term-memory.md`：

```markdown
### YYYY-MM-DD
他那天说想辞职，说过两次，第二次比第一次轻。
```

保留：情感锚点、关系里程碑、重要决定、未来计划和承诺、反复出现的主题、被纠正过的行为。
丢掉：日常寒暄、一次性技术调试、已过期的待办。

**只复制，不删原文。**

## 6. 深度归档

```bash
python3 {{DATA_DIR}}/lifecycle.py deep --days 14
```

## 7. 回报

一行即可：「处理 N 条；归档 M 条；蒸馏 K 条」。有 WARNING 或任何一步失败，写清故障——不要只回 ok。
