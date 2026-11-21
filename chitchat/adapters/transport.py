"""发送通道：把"前 N-1 条气泡"真的发出去。

适配器只依赖 Transport 协议，换宿主时在外面实现它就行。
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager, nullcontext
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class Transport(Protocol):
    def send(self, chat_id: str, text: str) -> None: ...


class NullTransport:
    """什么都不发（demo / 测试用）。"""

    def __init__(self):
        self.sent = []

    def send(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


class HermesTransport:
    """通过 Hermes 的 send_message_tool 发消息。

    0.23+ 在 gateway.outbound.send，旧版在 tools.send_message_tool，两个都试。
    """

    def __init__(self, channel: str = "feishu"):
        self.channel = channel

    @staticmethod
    def _sender():
        try:
            from gateway.outbound.send import send_message_tool
        except ImportError:
            from tools.send_message_tool import send_message_tool
        return send_message_tool

    @contextmanager
    def _suppress_mirror(self, chat_id: str):
        """尽量不在发送镜像里落一份（不同版本 API 不同，拿不到就退化为 no-op）。"""
        try:
            from tools.memory_mirror import suppress as _suppress  # type: ignore

            with _suppress(chat_id):
                yield
            return
        except Exception:
            pass
        with nullcontext():
            yield

    def send(self, chat_id: str, text: str) -> None:
        target = f"{self.channel}:{chat_id}"
        with self._suppress_mirror(chat_id):
            raw = self._sender()({"target": target, "message": text})
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict) and parsed.get("error"):
            raise RuntimeError(parsed["error"])


def make_transport(spec: Optional[str]) -> Transport:
    """把配置里的字符串变成 Transport 实例；未知值退化成 NullTransport。"""
    if not spec or spec in ("null", "none"):
        return NullTransport()
    if spec.startswith("hermes"):
        channel = spec.split(":", 1)[1] if ":" in spec else "feishu"
        return HermesTransport(channel)
    return NullTransport()
