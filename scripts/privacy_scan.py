#!/usr/bin/env python3
"""发布前自检：仓库里不应该出现个人身份、密钥、真实路径。

    python scripts/privacy_scan.py [root]

命中即返回 1（CI 里会失败）。允许列表在 ALLOW 里显式声明。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "build", "dist", ".pytest_cache", "node_modules"}
SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mp3", ".zip", ".woff", ".woff2", ".ttf"}

PATTERNS = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "身份证": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "邮箱": re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"),
    "公网IP": re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    "密钥": re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}|LTAI[A-Za-z0-9]{12,})"),
    "私钥": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
    "绝对路径": re.compile(r"(/mnt/[a-z]/|[A-Z]:\\\\Users\\\\|/home/[a-z]+/|\.hermes/profiles/[a-z]+)"),
    "聊天ID": re.compile(r"\b(oc|ou)_[0-9a-f]{16,}"),
    "连接串": re.compile(r"(?i)\b(mysql|redis|postgres|mongodb)://[^\s\"']+"),
}

# 允许出现的通用值（示例/文档占位）
ALLOW: set[str] = set()
ALLOW_LINE_HINTS = ("127.0.0.1", "0.0.0.0", "example.com", "example.org", "localhost", "x.x.x.x")


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIX:
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        yield path


def main() -> int:
    hits = 0
    for path in iter_files(ROOT):
        rel = path.relative_to(ROOT)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if any(hint in line for hint in ALLOW_LINE_HINTS):
                continue
            for name, pat in PATTERNS.items():
                for m in pat.finditer(line):
                    token = m.group(0)
                    if token in ALLOW:
                        continue
                    hits += 1
                    print(f"{rel}:{lineno}: [{name}] {token[:40]}")
    if hits:
        print(f"\n隐私扫描失败：{hits} 处命中。")
        return 1
    print("隐私扫描通过：0 命中。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
