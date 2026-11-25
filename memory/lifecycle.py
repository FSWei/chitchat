#!/usr/bin/env python3
"""记忆链路的机械层：按日期归档、深度归档、推进 checkpoint。

分工：脚本只做**能算准的事**（日期比较、文件移动、水位前进），
蒸馏（哪些话值得记）交给模型。提示词里写日期逻辑，迟早写错——
所以这里一条日期规则都不留给模型。

四层文件（默认就在本目录）：

    chat-log.md          最近 3 天的原文摘要（模型可读）
    chat-archive.md      超过 3 天的原文（永久，模型不读）
    long-term-memory.md  蒸馏后的长期记忆，2 周（模型可读）
    deep-archive.md      超过 14 天的长期记忆（永久，模型不读）

用法：

    python3 memory/lifecycle.py status
    python3 memory/lifecycle.py archive --days 3
    python3 memory/lifecycle.py deep --days 14
    python3 memory/lifecycle.py advance 1795570000
    python3 memory/lifecycle.py pending 12
    python3 memory/lifecycle.py check

`query`（从会话库取新消息）故意不在这里：那一段跟宿主强相关，
接你自己的库，取到消息后调用 `pending N`，总结完再 `advance <最大时间戳>`。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
CHAT_LOG = "chat-log.md"
CHAT_ARCHIVE = "chat-archive.md"
LONG_TERM = "long-term-memory.md"
DEEP_ARCHIVE = "deep-archive.md"
CHECKPOINT = "chat-log-checkpoint.json"
STATE = "chat-log-state.json"

ENTRY_HEAD_RE = re.compile(r"(?m)^(#{2,3} \d{4}-\d{2}-\d{2}[^\n]*)$")
ENTRY_DATE_RE = re.compile(r"#{2,3} (\d{4}-\d{2}-\d{2})")


# --- 基础 IO ---------------------------------------------------------------

def _read(path: Path) -> str:
    """读文件，容忍 Windows 上用 ANSI/GBK 编辑器改过的文件。

    优先 UTF-8（带不带 BOM 都行），再试 GB18030（GBK 的超集）；
    都解不了就报错，不静默替换——记忆文件被乱码覆盖是不可逆的。
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return ""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"{path} 既不是 UTF-8 也不是 GB18030，先转码再跑（不要直接覆盖）")


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# --- 条目拆分 --------------------------------------------------------------

def split_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    """按 '## YYYY-MM-DD' 或 '### YYYY-MM-DD' 切开，返回 (头部, [(标题行, 正文)])。

    两种级别都要认：长期记忆的蒸馏格式是三级标题。
    """
    parts = ENTRY_HEAD_RE.split(text)
    header = parts[0]
    entries: list[tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        entries.append((parts[i], body))
    return header, entries


def entry_date(header_line: str) -> date | None:
    m = ENTRY_DATE_RE.match(header_line)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


# --- 子命令 ----------------------------------------------------------------

def cmd_status(args) -> int:
    base = Path(args.dir)
    print(f"DIR={base}")
    for name in (CHAT_LOG, LONG_TERM):
        path = base / name
        header, entries = split_entries(_read(path))
        dates = [entry_date(h) for h, _ in entries]
        dates = [d for d in dates if d]
        span = f"{min(dates)} → {max(dates)}" if dates else "-"
        print(f"{name}: entries={len(entries)} span={span} bytes={path.stat().st_size if path.exists() else 0}")
    cp = _load_json(base / CHECKPOINT, {})
    st = _load_json(base / STATE, {})
    print(f"CHECKPOINT last_msg_ts={cp.get('last_msg_ts', 0)} processed_at={cp.get('processed_at', 'never')}")
    print(f"PENDING={st.get('pending', 0)}")
    return 0


def _archive_file(base: Path, src: str, dst: str, days: int, today: date, echo: bool) -> int:
    src_path, dst_path = base / src, base / dst
    header, entries = split_entries(_read(src_path))
    cutoff = today - timedelta(days=days)
    keep, move = [], []
    for head, body in entries:
        d = entry_date(head)
        (move if (d and d < cutoff) else keep).append((head, body))

    if not move:
        print(f"无需归档 {src}（cutoff={cutoff}）")
        return 0

    _write(src_path, header + "".join(h + b for h, b in keep))
    with open(dst_path, "a", encoding="utf-8") as fh:
        for head, body in move:
            fh.write("\n" + head + body)

    print(f"已从 {src} 移出 {len(move)} 条到 {dst}（保留 {len(keep)} 条，cutoff={cutoff}）")
    if echo:
        print("\n以下是被移出的原文，蒸馏后追加到 long-term-memory.md（格式：### YYYY-MM-DD + 场景式描述）：")
        for head, body in move:
            print(head)
            print(body.rstrip())
    return 0


def cmd_archive(args) -> int:
    return _archive_file(Path(args.dir), CHAT_LOG, CHAT_ARCHIVE, args.days, args.today, echo=True)


def cmd_deep(args) -> int:
    return _archive_file(Path(args.dir), LONG_TERM, DEEP_ARCHIVE, args.days, args.today, echo=False)


def cmd_rotate(args) -> int:
    """通用轮转：同一条日期规则，换成任意两个文件（日记归档就走这里）。"""
    return _archive_file(Path(args.dir), args.file, args.to, args.days, args.today, echo=args.echo)


def cmd_advance(args) -> int:
    base = Path(args.dir)
    cp = _load_json(base / CHECKPOINT, {"last_msg_ts": 0, "processed_at": "never"})
    old = float(cp.get("last_msg_ts", 0))
    if args.ts <= old:
        print(f"REFUSED: {args.ts} <= 当前 {old}（checkpoint 只能前进）", file=sys.stderr)
        return 1
    now = datetime.now().isoformat(timespec="seconds")
    _save_json(base / CHECKPOINT, {"last_msg_ts": args.ts, "processed_at": now})
    _save_json(base / STATE, {"pending": 0, "advanced_at": now})
    print(f"ADVANCED: {old} -> {args.ts}")
    return 0


def cmd_pending(args) -> int:
    base = Path(args.dir)
    st = _load_json(base / STATE, {})
    st["pending"] = max(0, args.count)
    st["queried_at"] = datetime.now().isoformat(timespec="seconds")
    _save_json(base / STATE, st)
    print(f"PENDING={st['pending']}")
    return 0


def cmd_check(args) -> int:
    """给任务书用的自检：上轮有没有没推进的 pending。"""
    base = Path(args.dir)
    cp = _load_json(base / CHECKPOINT, {"last_msg_ts": 0})
    st = _load_json(base / STATE, {"pending": 0})
    if st.get("pending", 0) > 0:
        print(
            f"WARNING: 上一轮查到 {st['pending']} 条消息但 checkpoint 停在 "
            f"{cp.get('last_msg_ts', 0)}（上轮中途失败）。本轮必须补完并 advance，否则在报告里说明。"
        )
        return 0
    print("OK")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="lifecycle", description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=str(BASE), help="数据目录（默认脚本所在目录）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="看三层文件的条目数与 checkpoint")

    for name, help_text in (("archive", "按日期归档 chat-log → chat-archive"), ("deep", "按日期归档 long-term → deep-archive")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--days", type=int, default=3 if name == "archive" else 14)
        p.add_argument("--today", type=date.fromisoformat, default=date.today())

    p = sub.add_parser("advance", help="推进 checkpoint（只前进）")
    p.add_argument("ts", type=float)

    p = sub.add_parser("pending", help="记录本轮查到多少条（0 = 已处理完）")
    p.add_argument("count", type=int)

    sub.add_parser("check", help="上轮是否有没推进的 pending")

    p = sub.add_parser("rotate", help="任意文件的日期轮转（例如日记 journal.md → archive.md）")
    p.add_argument("--file", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--today", type=date.fromisoformat, default=date.today())
    p.add_argument("--echo", action="store_true", help="打印被移出的原文（供蒸馏）")

    args = ap.parse_args(argv)
    return {
        "status": cmd_status,
        "archive": cmd_archive,
        "deep": cmd_deep,
        "advance": cmd_advance,
        "pending": cmd_pending,
        "check": cmd_check,
        "rotate": cmd_rotate,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
