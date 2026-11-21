"""SQLite 历史 provider（默认表结构 = Hermes 的 state.db）。

只读、带 busy_timeout、任何异常都返回 None —— 查不到就不注入，不影响回话。
表名/列名可以改，适配别的宿主。
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

NOISE_PREFIXES = (
    "[IMPORTANT:",
    "[CONTEXT COMPACTION",
    "Gateway message origin",
    "Session turn lease",
    "[chitchat",
    "[SYSTEM",
)


class SqliteHistory:
    def __init__(
        self,
        db_path: str | Path,
        sessions_table: str = "sessions",
        messages_table: str = "messages",
    ):
        self.db_path = Path(db_path).expanduser()
        self.sessions_table = sessions_table
        self.messages_table = messages_table

    def _connect(self):
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=3)

    def day(self, target: date, max_sessions: int = 6, max_quotes: int = 2) -> Optional[Dict]:
        if not self.db_path.exists():
            return None
        start = datetime(target.year, target.month, target.day).timestamp()
        end = start + 86400
        out: Dict = {
            "date": target.isoformat(),
            "weekday": "一二三四五六日"[target.weekday()],
            "sessions": [],
            "total": 0,
        }
        try:
            con = self._connect()
            try:
                con.execute("PRAGMA busy_timeout=3000")
                rows = con.execute(
                    f"SELECT s.id, s.chat_type, s.title, COUNT(m.id) "
                    f"FROM {self.messages_table} m JOIN {self.sessions_table} s ON s.id = m.session_id "
                    "WHERE m.timestamp >= ? AND m.timestamp < ? AND m.role = 'user' "
                    "AND s.source != 'cron' AND m.content IS NOT NULL AND length(trim(m.content)) > 1 "
                    "AND m.content NOT LIKE '[%' "
                    "GROUP BY s.id ORDER BY COUNT(m.id) DESC LIMIT ?",
                    (start, end, max_sessions),
                ).fetchall()
                for sid, chat_type, title, n in rows:
                    quotes = []
                    for (content,) in con.execute(
                        f"SELECT content FROM {self.messages_table} WHERE session_id=? AND role='user' "
                        "AND timestamp >= ? AND timestamp < ? AND content IS NOT NULL "
                        "AND length(trim(content)) > 3 AND content NOT LIKE '[%' "
                        "ORDER BY timestamp ASC LIMIT 12",
                        (sid, start, end),
                    ).fetchall():
                        q = re.sub(r"\s+", " ", (content or "").strip())
                        if not q or q.startswith(NOISE_PREFIXES) or q in quotes:
                            continue
                        quotes.append(q[:50])
                        if len(quotes) >= max_quotes:
                            break
                    name = (title or "").strip() or (quotes[0][:18] if quotes else "untitled")
                    out["sessions"].append(
                        {"title": name[:24], "chat_type": chat_type or "", "n": n, "quotes": quotes}
                    )
                    out["total"] += n
            finally:
                con.close()
        except Exception as exc:
            logger.debug("chitchat: history lookup failed: %s", exc)
            return None
        return out
