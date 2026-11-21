"""纯函数核心：把一段模型输出变成"像人发的消息流"。

这里没有任何 IO、没有配置读取、没有宿主依赖——所有函数都是可单测的纯函数。
"""

from __future__ import annotations

import re
from typing import Dict, List

SENT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]*")
TABLE_RE = re.compile(r"(?m)^\s*\|.+\|")
HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ULINE_BOLD_RE = re.compile(r"__(.+?)__")
BULLET_RE = re.compile(r"(?m)^\s*[-*]\s+")

DEFAULT_BUBBLE = {"target_chars": 70, "pack_limit": 140, "max_bubbles": 12}


def apply_blacklist(text: str, blacklist: Dict[str, str] | None) -> str:
    """按词表替换（值可以为空字符串=删除）。"""
    for bad, repl in (blacklist or {}).items():
        if bad:
            text = text.replace(bad, repl or "")
    return text


def strip_markdown_structure(text: str) -> str:
    """去掉标题井号、加粗星号、列表符号——聊天里这些只会显得像文档。"""
    text = HEADING_RE.sub("", text)
    text = BOLD_RE.sub(r"\1", text)
    text = ULINE_BOLD_RE.sub(r"\1", text)
    text = BULLET_RE.sub("", text)
    return text


def split_sentences(line: str) -> List[str]:
    parts = [p for p in SENT_RE.findall(line) if p.strip()]
    return parts if parts else ([line] if line.strip() else [])


def split_to_bubbles(
    text: str,
    target_chars: int = DEFAULT_BUBBLE["target_chars"],
    pack_limit: int = DEFAULT_BUBBLE["pack_limit"],
    max_bubbles: int = DEFAULT_BUBBLE["max_bubbles"],
) -> List[str]:
    """切气泡。

    换行 = 气泡边界（真人聊天一行≈一条消息）；同一行内按句打包到 target_chars，
    单条不超过 pack_limit；超过 max_bubbles 时把尾部全部并进最后一条（不丢内容）。
    """
    bubbles: List[str] = []
    for para in re.split(r"\n{2,}", text.strip()):
        for line in para.splitlines():
            line = line.strip()
            if not line:
                continue
            line_bubbles: List[str] = []
            for sent in split_sentences(line):
                if (
                    line_bubbles
                    and len(line_bubbles[-1]) < target_chars
                    and len(line_bubbles[-1]) + len(sent) <= pack_limit
                ):
                    line_bubbles[-1] += sent
                else:
                    line_bubbles.append(sent)
            bubbles.extend(line_bubbles)
    if max_bubbles and len(bubbles) > max_bubbles:
        head = bubbles[: max_bubbles - 1]
        head.append("".join(bubbles[max_bubbles - 1 :]))
        bubbles = head
    return [b for b in bubbles if b]


def strip_repeated_tail(text: str, min_repeat_chars: int = 15, min_para_chars: int = 6) -> str:
    """砍掉复读退化。两道防线：整块重复迭代到不动点 + 单行首次出现保留。"""
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if len(paras) < 2:
        return text
    changed = False
    while len(paras) >= 2:
        n = len(paras)
        cut = False
        for tail_len in range(n - 1, 0, -1):
            tail = paras[n - tail_len :]
            if sum(len(p) for p in tail) < min_repeat_chars:
                continue
            for i in range(n - tail_len):
                if paras[i : i + tail_len] == tail:
                    paras = paras[: n - tail_len]
                    cut = changed = True
                    break
            if cut:
                break
        if not cut:
            break
    seen = set()
    kept = []
    for p in paras:
        if len(p) >= min_para_chars and p in seen:
            changed = True
            continue
        seen.add(p)
        kept.append(p)
    if not changed:
        return text
    return "\n".join(kept)


def is_structured(text: str) -> bool:
    """代码块 / 附件 / 表格 = 结构化工作内容，整条放行不切。"""
    return "```" in text or "MEDIA:" in text or bool(TABLE_RE.search(text))
