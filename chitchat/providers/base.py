"""Provider 协议：插件只认接口，不认某个具体系统的文件路径。

想接自己的记忆系统，实现其中一个 Protocol 即可；没有就什么都不传。
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class TextProvider(Protocol):
    """一段可注入的文本（人设、情绪、摘要……）。"""

    def text(self, max_chars: int = 800) -> str: ...


@runtime_checkable
class HistoryProvider(Protocol):
    """按天查历史消息（用于"你还记得昨天吗"这类召回）。"""

    def day(self, target: date, max_sessions: int = 6, max_quotes: int = 2) -> Optional[Dict]: ...


class FileText(TextProvider):
    """最简单的文本 provider：读一个文件。"""

    def __init__(self, path: str):
        self.path = path

    def text(self, max_chars: int = 800) -> str:
        from ..context import read_text_file

        return read_text_file(self.path, max_chars)


class StaticText(TextProvider):
    def __init__(self, content: str):
        self.content = content

    def text(self, max_chars: int = 800) -> str:
        content = (self.content or "").strip()
        return content[:max_chars] + "……" if max_chars and len(content) > max_chars else content


class NullHistory(HistoryProvider):
    def day(self, target: date, max_sessions: int = 6, max_quotes: int = 2) -> Optional[Dict]:
        return None


class ListHistory(HistoryProvider):
    """测试/示例用：直接喂一份 {date: payload}。"""

    def __init__(self, days: Dict[str, Dict]):
        self.days = days

    def day(self, target: date, max_sessions: int = 6, max_quotes: int = 2) -> Optional[Dict]:
        payload = self.days.get(target.isoformat())
        if not payload:
            return None
        sessions = (payload.get("sessions") or [])[:max_sessions]
        return {
            "date": target.isoformat(),
            "weekday": payload.get("weekday", ""),
            "sessions": [
                {**s, "quotes": (s.get("quotes") or [])[:max_quotes]} for s in sessions
            ],
            "total": payload.get("total", sum(s.get("n", 0) for s in sessions)),
        }


__all__: List[str] = [
    "TextProvider",
    "HistoryProvider",
    "FileText",
    "StaticText",
    "NullHistory",
    "ListHistory",
]
