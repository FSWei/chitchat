#!/usr/bin/env python3
"""journal_state.py — Chips 日记的分段水位（机械层）。

日记从「每天一次生成整天」改成「每次只写已发生的一段」。
这个脚本负责所有需要精确计算的部分（日期、时区、间隔、水位），
模型只负责写文字，不再自己算时间。

用法：
  python3 journal_state.py status
  python3 journal_state.py commit [--chars N] [--to ISO]
  python3 journal_state.py finalize --date YYYY-MM-DD
  python3 journal_state.py reset [--date YYYY-MM-DD]

state.json：
  {"date": "2026-11-09",            # 西雅图日期（她的一天）
   "covered_until": "...",          # 已经写到哪个时刻
   "finalized": false,
   "segments": [{"from","to","chars","at"}]}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE_PATH = BASE / "state.json"
JOURNAL = BASE / "journal.md"
MIN_GAP_MINUTES = 90


def _tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/Los_Angeles")
    except Exception:
        # 11 月是 PST（UTC-8）；没有 tzdata 时兜底
        return timezone(timedelta(hours=-8))


TZ = _tz()
CN = timezone(timedelta(hours=8))


def now() -> datetime:
    return datetime.now(TZ)


def iso(d: datetime) -> str:
    return d.astimezone(TZ).isoformat(timespec="seconds")


def parse(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d.astimezone(TZ)


def load() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text("utf-8"))
        except Exception:
            pass
    return {}


def save(st: dict) -> None:
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, STATE_PATH)


def midnight(d) -> datetime:
    return datetime.combine(d, datetime.min.time(), TZ)


def fresh(date_str: str, covered: datetime) -> dict:
    return {
        "date": date_str,
        "covered_until": iso(covered),
        "finalized": False,
        "segments": [],
    }


def cmd_status(_args) -> int:
    n = now()
    today = n.date()
    st = load()
    prev_date = "-"
    note = ""

    if not st:
        # 首次启用：今天已有旧格式（整日预测）条目，不重写，从明天 00:00 起算
        covered = midnight(today + timedelta(days=1))
        st = fresh(today.isoformat(), covered)
        save(st)
        note = "init:skip-rest-of-today"
    elif st.get("date") != today.isoformat():
        prev_date = st.get("date", "-")
        covered = midnight(today)
        st = fresh(today.isoformat(), covered)
        save(st)
        note = "day-rolled"
    else:
        covered = parse(st["covered_until"])

    gap = (n - covered).total_seconds() / 60.0
    if gap < 0:
        gap = 0.0
    should = gap >= MIN_GAP_MINUTES
    to = n if should else covered

    print(f"DATE={st['date']}")
    print(f"PREV_DATE={prev_date}")
    print(f"COVERED_UNTIL={st['covered_until']}")
    print(f"GAP_MINUTES={int(gap)}")
    print(f"MIN_GAP_MINUTES={MIN_GAP_MINUTES}")
    print(f"SHOULD_RUN={'yes' if should else 'no'}")
    print(f"FROM={iso(covered)}")
    print(f"TO={iso(to)}")
    print(f"FROM_CN={covered.astimezone(CN).strftime('%Y-%m-%d %H:%M')}")
    print(f"TO_CN={to.astimezone(CN).strftime('%Y-%m-%d %H:%M')}")
    print(f"FROM_LOCAL={covered.strftime('%H:%M')}")
    print(f"TO_LOCAL={to.strftime('%H:%M')}")
    print(f"WINDOW_MINUTES={max(0, int((to - covered).total_seconds() // 60))}")
    print(f"SEGMENTS={len(st.get('segments') or [])}")
    print(f"FINALIZED={'yes' if st.get('finalized') else 'no'}")
    if note:
        print(f"NOTE={note}")
    return 0


def cmd_commit(args) -> int:
    n = now()
    st = load()
    if not st:
        print("ERROR=no-state (先跑 status)", file=sys.stderr)
        return 2
    if st.get("date") != n.date().isoformat():
        print("ERROR=day-changed (先跑 status 滚动日期)", file=sys.stderr)
        return 3
    covered = parse(st["covered_until"])
    to = parse(args.to) if args.to else n
    if to <= covered:
        print("ERROR=to<=covered", file=sys.stderr)
        return 4
    segs = list(st.get("segments") or [])
    segs.append({
        "from": iso(covered),
        "to": iso(to),
        "chars": int(args.chars or 0),
        "at": iso(n),
    })
    st["segments"] = segs
    st["covered_until"] = iso(to)
    save(st)
    print(f"OK committed {iso(covered)} -> {iso(to)} chars={int(args.chars or 0)} total_segments={len(segs)}")
    return 0


def cmd_finalize(args) -> int:
    st = load()
    if not st:
        print("ERROR=no-state", file=sys.stderr)
        return 2
    target = args.date or st.get("date")
    if st.get("date") != target:
        # 不是当前状态里的那天：只标记文件，不改水位
        print(f"OK finalize-declared date={target} (state.date={st.get('date')})")
        return 0
    st["finalized"] = True
    save(st)
    print(f"OK finalized date={target} segments={len(st.get('segments') or [])}")
    return 0


def cmd_reset(args) -> int:
    n = now()
    d = args.date or n.date().isoformat()
    covered = datetime.fromisoformat(d).replace(tzinfo=TZ) if args.date else midnight(n.date())
    save(fresh(d, covered))
    print(f"OK reset date={d} covered_until={iso(covered)}")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="journal_state")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    c = sub.add_parser("commit")
    c.add_argument("--chars", type=int, default=0)
    c.add_argument("--to", default="")

    f = sub.add_parser("finalize")
    f.add_argument("--date", default="")

    r = sub.add_parser("reset")
    r.add_argument("--date", default="")

    args = p.parse_args(argv)
    return {
        "status": cmd_status,
        "commit": cmd_commit,
        "finalize": cmd_finalize,
        "reset": cmd_reset,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
