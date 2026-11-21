"""chitchat — 让 LLM 的输出看起来像人在发消息。

三层：
  core       纯函数（分气泡、去重、禁词、去 markdown）
  context    可选上下文（时间、情绪/人设文本、按日期召回）
  adapters   宿主接线（Hermes 钩子 + 发送通道）

没有宿主依赖也能用：`python examples/demo.py` 直接看效果。
"""

from __future__ import annotations

__version__ = "1.0.0"

from .config import ConfigLoader, validate  # noqa: E402
from .core import (  # noqa: E402
    apply_blacklist,
    is_structured,
    split_sentences,
    split_to_bubbles,
    strip_markdown_structure,
    strip_repeated_tail,
)
from .pipeline import transform  # noqa: E402

__all__ = [
    "__version__",
    "ConfigLoader",
    "validate",
    "apply_blacklist",
    "is_structured",
    "split_sentences",
    "split_to_bubbles",
    "strip_markdown_structure",
    "strip_repeated_tail",
    "transform",
]
