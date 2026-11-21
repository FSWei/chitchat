"""把配置 + 一段原始输出 → 一串气泡。纯函数，不碰网络和磁盘。"""

from __future__ import annotations

from typing import Dict, List, Optional

from .core import (
    apply_blacklist,
    is_structured,
    split_to_bubbles,
    strip_markdown_structure,
    strip_repeated_tail,
)


def transform(
    text: str,
    cfg: Dict,
    response_text_for_dedup: Optional[str] = None,
) -> List[str]:
    """返回要发的气泡列表；空列表表示"什么都不发"。

    - 含代码块 / MEDIA / 表格 → 返回 [原文]（整条放行，调用方判断"单条=不改写"）
    - 复读、黑名单、markdown 剥离都在这里做
    - response_text_for_dedup：需要落库原文去重的场景，调用方自己拿去做匹配
    """
    if not text or not text.strip():
        return []

    if is_structured(text):
        return [text]

    blacklist = (cfg.get("blacklist") or {}) if cfg.get("blacklist") is not None else {}
    if blacklist:
        text = apply_blacklist(text, blacklist)

    if cfg.get("strip_markdown", True):
        text = strip_markdown_structure(text)

    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    if not text:
        return []

    if cfg.get("dedup_repetition", True):
        text = strip_repeated_tail(text)

    bubble = cfg.get("bubble") or {}
    bubbles = split_to_bubbles(
        text,
        target_chars=int(bubble.get("target_chars", 70)),
        pack_limit=int(bubble.get("pack_limit", 140)),
        max_bubbles=int(bubble.get("max_bubbles", 12)),
    )
    return bubbles
