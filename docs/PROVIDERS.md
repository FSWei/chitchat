# 上下文源（Provider）

插件只认两个协议，具体数据从哪来由你决定。没有 provider 就什么都不注入，插件照常工作。

## TextProvider

```python
class TextProvider(Protocol):
    def text(self, max_chars: int = 800) -> str: ...
```

结果会被包上标签注入（如 `[chitchat·当前情绪档案]`）。仓库自带两个实现：

| 实现 | 用途 |
|---|---|
| `FileText(path)` | 读一个 Markdown 文件 |
| `StaticText(s)` | 直接给字符串（测试用） |

配置里最简单的接法（不用写代码）：

```json
"providers": {
  "mood": "/绝对/路径/mood.md",
  "persona": "/绝对/路径/persona.md",
  "digest": "/绝对/路径/digest.md"
}
```

## HistoryProvider

```python
class HistoryProvider(Protocol):
    def day(self, target: date, max_sessions: int, max_quotes: int) -> dict | None: ...
```

返回结构：

```json
{
  "date": "2026-11-20",
  "weekday": "五",
  "total": 42,
  "sessions": [
    {"title": "写代码", "chat_type": "group", "n": 12, "quotes": ["在改记忆", "明天继续"]}
  ]
}
```

自带 `SqliteHistory(db_path)`：默认按 Hermes 的 `state.db` 结构读（`sessions` / `messages` 两张表），
只读打开、`busy_timeout` 3s、任何异常返回 `None`。

配置：

```json
"providers": {"history_db": "/绝对/路径/state.db"},
"recall": {"enabled": true, "max_days_back": 365, "max_sessions": 6, "max_quotes": 2}
```

## 召回触发条件（两道闸，缺一不查）

1. 句子里有**日期表达**：`2026-11-20` / `11月20日` / `昨天` / `上周三`
2. 句子里有**记忆动词**：`记得` / `那天` / `做了什么` / `聊了什么`

命中才查库；查不到就明说"记不清"，不编。缓存写 `state/recall/<date>.json`，默认 90 天清理。

## 接自己的记忆系统

```python
# my_host.py
from chitchat.adapters.hermes import HermesAdapter
from chitchat.providers.base import HistoryProvider

class MyMemory(HistoryProvider):
    def day(self, target, max_sessions=6, max_quotes=2):
        return my_store.query_by_date(target, limit=max_sessions)

adapter = HermesAdapter(plugin_dir)
adapter._history = lambda: MyMemory()   # 或者自己包一层 register()
```

不想动 `_history` 也行：把它做成 `SqliteHistory` 同结构的适配器，用 `providers.history_db` 指向你的库。
