"""配置：schema + 默认值 + 校验 + 按 mtime 热加载。

一份 config 就是插件的全部行为开关；没有任何个人内容写死在代码里。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "chat_ids": [],
    "blacklist": {},
    "strip_markdown": True,
    "dedup_repetition": True,
    "bubble": {"target_chars": 70, "pack_limit": 140, "max_bubbles": 12, "delay_seconds": 1.2},
    "flags": {"work_ttl_hours": 12, "chat_ok_ttl_minutes": 10},
    "keywords": {"work_on": "/work", "work_off": "/chat"},
    "mode": {"default_lang": "zh", "default_voice": False, "rules_en": ""},
    "inject": {
        "time": True,
        "mood": True,
        "mood_max_chars": 800,
        "mode": True,
        "attention": True,
        "peer": True,
    },
    "recall": {"enabled": False, "max_days_back": 365, "max_sessions": 6, "max_quotes": 2, "cache_days": 90},
    "providers": {
        "mood": "",       # 文本文件路径，空=不注入
        "persona": "",    # 文本文件路径
        "digest": "",     # 文本文件路径（昨日摘要）
        "history_db": "", # SQLite 路径（按日期召回），空=关闭
    },
    "transport": {"target_template": "{channel}:{chat_id}"},
}

MAX_MOOD_CHARS = 4000


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def validate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """把明显不合理的值拉回安全范围；返回新 dict，不修改入参。"""
    c = _deep_merge(DEFAULTS, cfg or {})
    c["enabled"] = bool(c.get("enabled"))
    c["chat_ids"] = [str(x) for x in (c.get("chat_ids") or []) if str(x).strip()]
    c["blacklist"] = {
        str(k): str(v if v is not None else "")
        for k, v in (c.get("blacklist") or {}).items()
        if str(k)
    }
    b = c["bubble"]
    b["target_chars"] = max(10, min(500, int(b.get("target_chars", 70))))
    b["pack_limit"] = max(b["target_chars"], min(2000, int(b.get("pack_limit", 140))))
    b["max_bubbles"] = max(1, min(50, int(b.get("max_bubbles", 12))))
    b["delay_seconds"] = max(0.0, min(10.0, float(b.get("delay_seconds", 1.2))))
    c["inject"]["mood_max_chars"] = max(0, min(MAX_MOOD_CHARS, int(c["inject"].get("mood_max_chars", 800))))
    mode = c["mode"]
    if mode.get("default_lang") not in ("zh", "en"):
        mode["default_lang"] = "zh"
    rc = c["recall"]
    rc["max_sessions"] = max(1, min(20, int(rc.get("max_sessions", 6))))
    rc["max_quotes"] = max(0, min(5, int(rc.get("max_quotes", 2))))
    return c


class ConfigLoader:
    """按 mtime 热加载：改文件不用重启进程。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._mtime = -1.0
        self._cfg: Dict[str, Any] = dict(DEFAULTS)

    def load(self) -> Dict[str, Any]:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return dict(DEFAULTS)
        if mtime != self._mtime:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._cfg = validate(raw)
                self._mtime = mtime
            except Exception as exc:  # 坏配置不能把消息吞了
                logger.warning("chitchat: config reload failed: %s", exc)
        return self._cfg
