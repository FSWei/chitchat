#!/usr/bin/env python3
"""不用任何宿主跑一遍：喂一段模型输出，看它被切成几条气泡。

    python examples/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chitchat.pipeline import transform  # noqa: E402

SAMPLE = """# 今日进度

先说我这边的情况：**镇子里的 NPC 日志已经能自动生成了**，但还有两个问题没解决。

- 第一，日志里的时间线偶尔会跳；
- 第二，图片和文字的对应关系不稳。

你昨天提到的那个方案我看了，确实更省事。要不要今天就按这个来？

如果我们今天先把时间线修掉，明天再做图片，你觉得可行吗？"""


def main() -> int:
    cfg_path = Path(__file__).with_name("config.example.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["blacklist"] = {"先说我这边的情况：": ""}

    bubbles = transform(SAMPLE, cfg)
    print(f"输入 {len(SAMPLE)} 字 → {len(bubbles)} 条气泡\n")
    for i, b in enumerate(bubbles, 1):
        print(f"[{i}] ({len(b)}字) {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
