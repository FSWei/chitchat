#!/usr/bin/env python3
"""news_fetch.py — 给 Chips 日记取当天几条新闻（只取标题，不写观点）。

设计原则：
- 只负责「今天世界上发生了什么」，观点由日记 cron 自己写，且**只写 0-1 条**。
- 失败就少几条，绝不让日记因为没新闻而停摆。
- 同一天缓存，不重复抓（除非 --force）。

用法：
  python3 news_fetch.py fetch [--force]   抓取（当天已有缓存则直接输出）
  python3 news_fetch.py list              只读缓存
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CACHE_DIR = BASE / "news"
MAX_BYTES = 2_500_000
PER_FEED = 6
TIMEOUT = 10

FEEDS = [
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("Politico", "https://rss.politico.com/politics-news.xml"),
    ("HN", "https://hnrss.org/frontpage"),
    ("Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("IT之家", "https://www.ithome.com/rss/"),
]


def _tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/Los_Angeles")
    except Exception:
        from datetime import timedelta, timezone as tzmod

        return tzmod(timedelta(hours=-8))


def _today() -> str:
    return datetime.now(_tz()).date().isoformat()


def _cache_path(day: str) -> Path:
    return CACHE_DIR / f"{day}.json"


def _text(el, tag_names):
    for t in tag_names:
        v = el.findtext(t)
        if v:
            return html.unescape(re.sub(r"\s+", " ", v).strip())
    return ""


def _strip_html(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _parse(raw: bytes):
    root = ET.fromstring(raw)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    out = []
    for it in items:
        title = _text(it, ["title", "{http://www.w3.org/2005/Atom}title"])
        if not title:
            continue
        desc = _text(it, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
        link = _text(it, ["link", "{http://www.w3.org/2005/Atom}link"])
        if not link:
            le = it.find("{http://www.w3.org/2005/Atom}link")
            if le is not None:
                link = le.get("href", "")
        out.append({"title": title[:140], "summary": _strip_html(desc)[:200], "link": link[:300]})
        if len(out) >= PER_FEED:
            break
    return out


def _fetch_one(name: str, url: str):
    last = ""
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(MAX_BYTES)
            return name, _parse(raw), ""
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:60]}"
    return name, [], last


def _normalize(t: str) -> str:
    return re.sub(r"[\W_]+", "", t.lower())[:40]


def fetch(force: bool = False) -> dict:
    day = _today()
    path = _cache_path(day)
    if path.exists() and not force:
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            pass

    items, errors = [], []
    with ThreadPoolExecutor(max_workers=len(FEEDS)) as ex:
        for name, got, err in ex.map(lambda f: _fetch_one(*f), FEEDS):
            if err:
                errors.append(f"{name}: {err}")
                continue
            for g in got:
                g["source"] = name
                items.append(g)

    seen, uniq = set(), []
    for it in items:
        k = _normalize(it["title"])
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(it)

    data = {
        "date": day,
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "items": uniq,
        "errors": errors,
    }
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    except Exception:
        pass
    return data


def render(data: dict, limit: int = 14) -> str:
    if not data:
        return "NO_NEWS"
    items = data.get("items") or []
    if not items:
        return "NO_NEWS" + ((" (" + "; ".join(data.get("errors") or []) + ")") if data.get("errors") else "")
    lines = [f"DATE={data.get('date')} 共 {len(items)} 条（只挑你有话想说的，0 或 1 条）"]
    # 混合取样：先每个来源各两条，再补足
    by_src = {}
    for it in items:
        by_src.setdefault(it["source"], []).append(it)
    order = [s for s, _ in FEEDS]
    picked = []
    for round_i in range(3):
        for s in order:
            arr = by_src.get(s) or []
            if round_i < len(arr):
                picked.append(arr[round_i])
            if len(picked) >= limit:
                break
        if len(picked) >= limit:
            break
    for it in picked:
        lines.append(f"[{it['source']}] {it['title']}")
    return "\n".join(lines)


def main(argv):
    cmd = argv[0] if argv else "fetch"
    if cmd == "list":
        p = _cache_path(_today())
        data = json.loads(p.read_text("utf-8")) if p.exists() else {}
        print(render(data))
        return 0
    data = fetch(force="--force" in argv)
    print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
