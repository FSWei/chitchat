"""上下文片段：时间、心情/人设文件、注意力清单。

所有读取都走配置里的路径，代码里没有任何写死的目录或个人内容。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

INTERROGATIVE_EN = re.compile(
    r"(?i)\b(what|why|how|when|where|who|whom|whose|which|do|does|did|can|could|would|should|"
    r"is|are|was|were|have|has|will|shall|may|might|tell me|you think)\b"
)
INTERROGATIVE_ZH = re.compile(r"(什么|怎么|为什么|为啥|哪|吗|呢|是不是|有没有|能不能|会不会|要不要|多久|多少)")
CJK_RUN = re.compile(r"[\u4e00-\u9fff][\u4e00-\u9fff\w，。！？、；：\s]{1,80}")

WEEKDAY_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def weekday_zh(dt: datetime) -> str:
    return WEEKDAY_ZH[dt.weekday()]


def time_context(timezones: List[str] | None = None) -> str:
    """默认只报本机时区；配置里可以再加几个，避免"把预测当已发生"这类时间错误。"""
    zones = timezones or ["Asia/Shanghai"]
    now_utc = datetime.now(ZoneInfo("UTC"))
    parts = []
    for name in zones:
        try:
            local = now_utc.astimezone(ZoneInfo(name))
        except Exception:
            continue
        period = "上午" if local.hour < 12 else ("下午" if local.hour < 18 else "晚上")
        parts.append(
            f"{name} 现在：{local.strftime('%Y-%m-%d')} {weekday_zh(local)} "
            f"{local.strftime('%H:%M')}（{period}）"
        )
    return "；".join(parts) + "。" if parts else ""


def read_text_file(path: str | Path | None, max_chars: int = 800) -> str:
    if not path:
        return ""
    try:
        content = Path(path).expanduser().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""
    if max_chars and len(content) > max_chars:
        content = content[:max_chars] + "……"
    return content


def question_segments(text: str, limit: int = 500) -> List[str]:
    """粗切这一轮问了几个问题。纯启发式，长文本一律不猜（防把文档里的问号当问题）。"""
    if not text or len(text) > limit:
        return []
    segs = []
    for clause in re.split(r"[?？!！;；,，.。\n]+", text):
        clause = clause.strip()
        if len(clause) < 2:
            continue
        if INTERROGATIVE_EN.match(clause) or INTERROGATIVE_ZH.search(clause):
            segs.append(clause)
    return segs


def cjk_fragments(text: str, min_run: int = 2) -> List[str]:
    """找出英文句子里夹的中文片段（整句中文不算）。"""
    if not text:
        return []
    total = len(re.sub(r"\s", "", text))
    if not total:
        return []
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk / total > 0.5:
        return []
    out = []
    for m in CJK_RUN.finditer(text):
        frag = m.group(0).strip()
        if len(re.sub(r"\s", "", frag)) >= min_run:
            out.append(frag)
    return out[:3]


def build_injection(
    cfg: Dict,
    user_message: str,
    mode: Dict[str, object],
    recall_block: str = "",
) -> str:
    """把这一轮要注入的上下文拼成一段。没东西可注入就返回空字符串。"""
    inject = cfg.get("inject") or {}
    parts: List[str] = []

    if inject.get("attention", True):
        qs = question_segments(user_message)
        if len(qs) >= 2:
            listing = "\n".join(f"  {i + 1}) {q}" for i, q in enumerate(qs[:5]))
            parts.append(f"[chitchat·本轮问题清单] 这一轮有 {len(qs)} 个问题，逐条回答：\n{listing}")
        if mode.get("lang") == "en":
            frags = cjk_fragments(user_message)
            if frags:
                joined = " / ".join(f"「{f}」" for f in frags)
                parts.append(f"[chitchat·中文片段] 句子里夹了中文：{joined} —— 给出自然的英文说法，然后继续。")

    if inject.get("time", True):
        zones = (cfg.get("inject") or {}).get("timezones") or ["Asia/Shanghai"]
        ctx = time_context(zones)
        if ctx:
            parts.append("[chitchat·时间] " + ctx)

    if inject.get("mood", True):
        mood = read_text_file((cfg.get("providers") or {}).get("mood"), int(inject.get("mood_max_chars", 800)))
        if mood:
            parts.append("[chitchat·当前情绪档案]\n" + mood)

    if inject.get("peer", True):
        for key, label in (("persona", "人设摘要"), ("digest", "最近摘要")):
            text = read_text_file((cfg.get("providers") or {}).get(key), 600)
            if text:
                parts.append(f"[chitchat·{label}]\n{text}")

    if recall_block:
        parts.append(recall_block)

    if inject.get("mode", True):
        if mode.get("lang") == "en":
            rules = (cfg.get("mode") or {}).get("rules_en") or (
                "English mode ON — reply in English, short chat-style bubbles, "
                "correct the user's mistakes in one short line then continue."
            )
            parts.append("[chitchat·语言模式] " + rules)
        else:
            parts.append("[chitchat·语言模式] 中文模式 —— 回复用中文。")
        if mode.get("voice"):
            parts.append(
                "[chitchat·语音模式] Voice mode ON — send the line as a voice message: "
                "call text_to_speech, then output MEDIA:<audio path> (keep one short text line too)."
            )
        parts.append(
            "[chitchat·输出完整性] Write the actual answer into the visible message: "
            "reasoning is not delivery, a promise of content is not content. "
            "Long content is fine — bubbles will split it."
        )

    return "\n\n".join(p for p in parts if p)
