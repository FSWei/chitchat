"""按日期召回："你还记得昨天聊了啥" 这一类问题。

意图闸：必须同时命中"日期表达"和"记忆动词"才去查库，否则零成本返回空。
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .providers.base import HistoryProvider, NullHistory

DATE_MD_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
DATE_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DATE_REL_RE = re.compile(r"(大前天|前天|昨天|上周[一二三四五六日天]|上个?星期[一二三四五六日天])")
RECALL_VERB_RE = re.compile(
    r"记得|记不记得|还记|有没有记|那天|做(了)?(什么|啥)|干(了)?(什么|啥|嘛)|聊了什么|忙什么|什么情况"
)
WEEKDAY_CN = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def resolve_target_date(text: str, today: Optional[date] = None) -> Optional[date]:
    today = today or date.today()
    m = DATE_ISO_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = DATE_MD_RE.search(text)
    if m:
        mo, dd = int(m.group(1)), int(m.group(2))
        for year in (today.year, today.year - 1):
            try:
                cand = date(year, mo, dd)
            except ValueError:
                continue
            if cand <= today:
                return cand
        return None
    m = DATE_REL_RE.search(text)
    if m:
        word = m.group(1)
        if word == "昨天":
            return today - timedelta(days=1)
        if word == "前天":
            return today - timedelta(days=2)
        if word == "大前天":
            return today - timedelta(days=3)
        wd = WEEKDAY_CN.get(word[-1])
        if wd is not None:
            delta = (today.weekday() - wd) % 7 or 7
            return today - timedelta(days=delta)
    return None


def format_recall(payload: Dict) -> str:
    head = f"[chitchat·查到的记录 {payload['date']} 周{payload.get('weekday', '')}]"
    if not payload.get("sessions"):
        return head + " 那天没有任何记录。不要编，直接说记不清。"
    lines = [head, f"那天在 {len(payload['sessions'])} 个窗口说过话，共 {payload['total']} 条："]
    for i, s in enumerate(payload["sessions"], 1):
        line = f"{i}. {s['title']}（{s['n']}条）"
        if s.get("quotes"):
            line += "：" + " ".join(f"「{q}」" for q in s["quotes"])
        lines.append(line)
    lines.append("这是记录，不是台词：用「我记得那天你在弄…」的口吻，最多提 1-2 件，不要报日程表。")
    return "\n".join(lines)


def build_recall_block(
    user_message: str,
    cfg: Dict,
    provider: HistoryProvider | None = None,
    today: Optional[date] = None,
    cache_dir: str | Path | None = None,
) -> str:
    rc = cfg.get("recall") or {}
    if not rc.get("enabled", False):
        return ""
    if not user_message or len(user_message) > 500:
        return ""
    if not (DATE_MD_RE.search(user_message) or DATE_ISO_RE.search(user_message) or DATE_REL_RE.search(user_message)):
        return ""
    if not RECALL_VERB_RE.search(user_message):
        return ""
    target = resolve_target_date(user_message, today)
    if not target:
        return ""
    today = today or date.today()
    if target > today or (today - target).days > int(rc.get("max_days_back", 365)):
        return ""

    cache_path = Path(cache_dir) / f"{target.isoformat()}.json" if cache_dir else None
    payload = None
    if cache_path and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
    if payload is None:
        provider = provider or NullHistory()
        payload = provider.day(
            target,
            int(rc.get("max_sessions", 6)),
            int(rc.get("max_quotes", 2)),
        )
        if not payload:
            return ""
        if cache_path:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError:
                pass
    return format_recall(payload)


def cleanup_cache(cache_dir: str | Path | None, cfg: Dict, today: Optional[date] = None) -> List[str]:
    """清掉超过 cache_days 的召回缓存，返回被删文件名。"""
    days = int((cfg.get("recall") or {}).get("cache_days", 90))
    if not cache_dir or days <= 0:
        return []
    root = Path(cache_dir)
    if not root.exists():
        return []
    cutoff = ((today or date.today()) - timedelta(days=days)).isoformat()
    removed = []
    for p in root.glob("*.json"):
        if p.stem < cutoff:
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    return removed
