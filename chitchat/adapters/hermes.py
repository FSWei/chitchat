"""Hermes 适配器：把三个钩子接到 core / pipeline / context 上。

设计原则：钩子只做"取聊天 ID、判断是否该管、调 pipeline、发气泡、注入上下文"，
任何业务规则都不写在这里——规则在 core/config/context 里，那部分与宿主无关。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ..config import ConfigLoader
from ..context import build_injection
from ..modes import State
from ..pipeline import transform
from ..recall import build_recall_block, cleanup_cache, resolve_target_date
from ..providers.base import NullHistory
from ..providers.sqlite_memory import SqliteHistory
from .transport import Transport, make_transport

logger = logging.getLogger(__name__)

_LOG_MAX_BYTES = 1_000_000


class HermesAdapter:
    def __init__(self, plugin_dir: Path, transport: Optional[Transport] = None):
        self.dir = Path(plugin_dir)
        self.loader = ConfigLoader(self.dir / "config.json")
        self.state = State(self.dir / "state", self.loader.load)
        self.log_path = self.dir / "state" / "chitchat.log"
        self._chat_cache: Dict[str, Optional[str]] = {}
        self._transport = transport
        self._transport_spec = None

    # --- logging -------------------------------------------------------
    def log(self, action: str, session_id: str = "", detail: str = "") -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if self.log_path.exists() and self.log_path.stat().st_size > _LOG_MAX_BYTES:
                self.log_path.replace(self.log_path.with_suffix(".log.old"))
            line = f"{datetime.now().isoformat(timespec='seconds')} | {action} | {session_id} | {detail}\n"
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            pass

    # --- host lookups --------------------------------------------------
    def _home(self) -> Path:
        try:
            from hermes_constants import get_hermes_home  # type: ignore

            return Path(get_hermes_home())
        except Exception:
            import os

            return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))

    def chat_id_of(self, session_id: str) -> Optional[str]:
        if session_id in self._chat_cache:
            return self._chat_cache[session_id]
        chat_id = None
        cfg = self.loader.load()
        db_path = (cfg.get("hermes") or {}).get("db_path") or (self._home() / "state.db")
        try:
            import sqlite3

            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
            try:
                row = con.execute("SELECT chat_id FROM sessions WHERE id=?", (session_id,)).fetchone()
                chat_id = row[0] if row else None
            finally:
                con.close()
        except Exception as exc:
            logger.debug("chitchat: chat_id lookup failed: %s", exc)
            return None
        if len(self._chat_cache) > 2000:
            self._chat_cache.clear()
        self._chat_cache[session_id] = chat_id
        return chat_id

    def active(self, session_id: str) -> Optional[str]:
        return self.state.active(self.chat_id_of, session_id)

    def transport(self) -> Transport:
        if self._transport is not None:
            return self._transport
        cfg = self.loader.load()
        spec = (cfg.get("transport") or {}).get("impl") or "hermes"
        if spec != self._transport_spec:
            self._transport = make_transport(spec)
            self._transport_spec = spec
        return self._transport

    def _history(self):
        cfg = self.loader.load()
        db_path = (cfg.get("providers") or {}).get("history_db")
        if not db_path:
            return NullHistory()
        return SqliteHistory(Path(db_path).expanduser())

    # --- hooks ---------------------------------------------------------
    def on_transform(self, response_text: str = "", session_id: str = "", **kw):
        try:
            if not response_text:
                return None
            if self._is_background():
                self.log("passthrough", session_id, "bg-review")
                return None
            chat_id = self.active(session_id)
            if not chat_id:
                return None

            cfg = self.loader.load()
            bubbles = transform(response_text, cfg)
            if not bubbles:
                return ""
            if len(bubbles) == 1:
                self.log("single", session_id, f"len={len(response_text)}")
                return bubbles[0]

            delay = float((cfg.get("bubble") or {}).get("delay_seconds", 1.2))
            sent = 0
            for bubble in bubbles[:-1]:
                try:
                    self.transport().send(chat_id, bubble)
                except Exception as exc:
                    rest = "".join(bubbles[sent:])
                    self.log("send-fallback", session_id, f"after {sent}: {exc}")
                    return rest
                sent += 1
                if delay > 0:
                    time.sleep(delay)
            self.log("split", session_id, f"bubbles={len(bubbles)}")
            return bubbles[-1]
        except Exception as exc:
            logger.warning("chitchat transform failed: %s", exc)
            self.log("error", session_id, str(exc))
            return None

    def on_pre_llm_call(self, session_id: str = "", user_message: str = "", **kw):
        try:
            cfg = self.loader.load()
            if not cfg.get("enabled"):
                return None
            chat_id = self.chat_id_of(session_id)
            if not chat_id or chat_id not in (cfg.get("chat_ids") or []):
                return None

            kw_cfg = cfg.get("keywords") or {}
            text = (user_message or "").lstrip()
            if kw_cfg.get("work_off") and text.startswith(kw_cfg["work_off"]):
                self.state.work_off()
                self.log("work-off", session_id, "via keyword")
            if kw_cfg.get("work_on") and text.startswith(kw_cfg["work_on"]):
                self.state.work_on()
                self.log("work-on", session_id, "via keyword")
            if self.active(session_id) is None:
                return None

            recall = ""
            if (cfg.get("recall") or {}).get("enabled"):
                recall = build_recall_block(
                    user_message or "",
                    cfg,
                    provider=self._history(),
                    cache_dir=self.dir / "state" / "recall",
                )
                if recall:
                    self.log("recall-hit", session_id, "")

            ctx = build_injection(cfg, user_message or "", self.state.mode(), recall)
            if not ctx:
                return None
            self.log("inject", session_id, "")
            return {"context": ctx}
        except Exception as exc:
            logger.warning("chitchat pre_llm_call failed: %s", exc)
            self.log("error", session_id, f"pre: {exc}")
            return None

    def on_pre_tool_call(self, tool_name: str, args: Optional[dict] = None, session_id: str = "", **kwargs):
        try:
            blocked = self._guard_skill_scope(tool_name, args or {}, session_id)
            if blocked:
                return blocked
            blocked = self._guard_state_file(tool_name, args or {}, session_id)
            if blocked:
                return blocked
        except Exception as exc:
            logger.debug("chitchat guard failed: %s", exc)
        return None

    # --- guards --------------------------------------------------------
    def _guard_skill_scope(self, tool_name: str, args: dict, session_id: str):
        names = (self.loader.load().get("skill_guard") or {}).get("skills") or []
        if not names:
            return None
        target = None
        if tool_name == "skill_view":
            name = str(args.get("name") or "")
            target = name if name in names else None
        elif tool_name in {"read_file", "search_files"}:
            path = str(args.get("path") or args.get("file_path") or "").replace("\\", "/")
            for name in names:
                if f"/skills/{name}/" in path or path.rstrip("/").endswith(f"/skills/{name}"):
                    target = name
                    break
        if not target:
            return None
        self.log("skill-guard", session_id, tool_name)
        return {
            "action": "block",
            "message": (
                f"这个会话不允许加载 `{target}`（skill_guard 名单）。"
                "换个窗口，或让用户在自己的会话里打开它。"
            ),
        }

    def _guard_state_file(self, tool_name: str, args: dict, session_id: str):
        """work.flag 的删除需要用户批准；mode.json 的写入只允许在启用会话里。"""
        cfg = self.loader.load()
        work_flag = self.state.work_flag
        if tool_name == "terminal":
            cmd = str(args.get("command") or "")
            if "work.flag" in cmd and any(k in cmd for k in ("rm ", "unlink ", "mv ")):
                if self.state.switch_approved():
                    self.state.consume_switch_approval()
                    self.log("work-off-approved", session_id, "approval consumed")
                    return None
                self.log("work-off-guard", session_id, "blocked")
                return {
                    "action": "block",
                    "message": (
                        "切回闲聊模式需要用户同意：先问用户，同意后 touch "
                        f"{work_flag.parent.name}/chat-ok.flag（一次性），再删 work.flag。"
                    ),
                }
        writes = False
        if tool_name in {"write_file", "patch"}:
            p = str(args.get("path") or args.get("file_path") or "").replace("\\", "/")
            writes = p.endswith("state/mode.json")
        elif tool_name in {"terminal", "execute_code"}:
            cmd = str(args.get("command") or args.get("code") or "")
            writes = "mode.json" in cmd and any(
                k in cmd for k in (">", "tee", "write_text", "json.dump", "open(")
            )
        if writes and not self.active(session_id):
            self.log("mode-write-guard", session_id, tool_name)
            return {
                "action": "block",
                "message": "state/mode.json 只允许在启用会话的闲聊模式下修改（先发 /chat 退出工作模式）。",
            }
        return None

    @staticmethod
    def _is_background() -> bool:
        if threading.current_thread().name.startswith("bg-review"):
            return True
        try:
            from tools.skill_provenance import is_background_review  # type: ignore

            return bool(is_background_review())
        except Exception:
            return False

    # --- commands ------------------------------------------------------
    def cmd_work(self, raw_args: str = "") -> str:
        self.state.work_on()
        ttl = (self.loader.load().get("flags") or {}).get("work_ttl_hours", 12)
        self.log("work-on", "", "via /work")
        return f"✅ 工作模式：插件休眠（{ttl}h 后自动过期）。发 /chat 恢复。"

    def cmd_chat(self, raw_args: str = "") -> str:
        self.state.work_off()
        self.log("work-off", "", "via /chat")
        return "✅ 闲聊模式恢复：分气泡 / 黑名单 / 上下文注入生效。"

    def _mode_scope(self, cmd: str):
        cfg = self.loader.load()
        if not cfg.get("enabled"):
            return False, "插件未启用。"
        chat_id = self._session_chat_id()
        if not chat_id or chat_id not in (cfg.get("chat_ids") or []):
            return False, f"❌ /{cmd} 只在启用会话里生效。"
        if self.state.work_stale():
            return False, f"❌ 工作模式下不能切：先发 /chat。"
        return True, ""

    def _session_chat_id(self) -> Optional[str]:
        try:
            from gateway.session_context import get_session_env  # type: ignore

            cid = (get_session_env("HERMES_SESSION_CHAT_ID") or "").strip()
            if cid:
                return cid
            key = (get_session_env("HERMES_SESSION_KEY") or "").strip()
            if key:
                return self.chat_id_of(key)
        except Exception:
            return None
        return None

    def cmd_lang(self, lang: str, raw_args: str = "") -> str:
        ok, why = self._mode_scope(lang)
        if not ok:
            return why
        self.state.set_mode(lang=lang)
        return "✅ English mode ON." if lang == "en" else "✅ 中文模式。"

    def cmd_voice(self, raw_args: str = "") -> str:
        ok, why = self._mode_scope("voice")
        if not ok:
            return why
        arg = (raw_args or "").strip().lower()
        cur = self.state.mode()
        on = (arg == "on") if arg in ("on", "off") else (not cur["voice"])
        self.state.set_mode(voice=on)
        return "✅ 语音模式开" if on else "✅ 语音模式关"


def register(ctx) -> None:
    """Hermes 插件入口。"""
    import os

    plugin_dir = Path(os.environ.get("CHITCHAT_HOME") or Path(__file__).resolve().parents[2])
    if plugin_dir.name == "hermes_plugin":
        plugin_dir = plugin_dir  # 插件目录就是 config/state 的家
    adapter = HermesAdapter(plugin_dir)
    ctx.register_hook("transform_llm_output", adapter.on_transform)
    ctx.register_hook("pre_llm_call", adapter.on_pre_llm_call)
    ctx.register_hook("pre_tool_call", adapter.on_pre_tool_call)
    for name, fn in (
        ("work", adapter.cmd_work),
        ("chat", adapter.cmd_chat),
        ("en", lambda raw="": adapter.cmd_lang("en", raw)),
        ("zh", lambda raw="": adapter.cmd_lang("zh", raw)),
        ("voice", adapter.cmd_voice),
    ):
        try:
            ctx.register_command(name, fn)
        except Exception:
            pass
    # 启动时清一次过期缓存，别等用户问起来才发现磁盘涨了
    cleanup_cache(plugin_dir / "state" / "recall", adapter.loader.load())
    adapter.log("registered", "", f"dir={plugin_dir}")
