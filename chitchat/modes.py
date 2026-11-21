"""模式与开关状态：工作模式 flag（带 TTL）、语言/语音开关。

状态只写在插件目录的 state/ 下，纯文件，可肉眼检查、可手工改。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class State:
    def __init__(self, state_dir: Path, cfg_getter, logger=None):
        self.dir = Path(state_dir)
        self._cfg = cfg_getter
        self._log = logger
        self.work_flag = self.dir / "work.flag"
        self.chat_ok_flag = self.dir / "chat-ok.flag"
        self.mode_path = self.dir / "mode.json"

    # --- flags ---------------------------------------------------------
    def _fresh(self, path: Path, ttl_seconds: float) -> bool:
        try:
            return (time.time() - path.stat().st_mtime) < ttl_seconds
        except OSError:
            return False

    def _touch(self, path: Path) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path.write_text(datetime.now().isoformat(), encoding="utf-8")

    def _unlink(self, path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            pass

    def work_on(self) -> None:
        self._touch(self.work_flag)

    def work_off(self) -> None:
        self._unlink(self.work_flag)

    def work_stale(self) -> bool:
        ttl = float(self._cfg().get("flags", {}).get("work_ttl_hours", 12)) * 3600
        return self._fresh(self.work_flag, ttl)

    def allow_switch(self) -> None:
        """记录"用户批准从工作模式切回闲聊"（一次性）。"""
        self._touch(self.chat_ok_flag)

    def switch_approved(self) -> bool:
        ttl = float(self._cfg().get("flags", {}).get("chat_ok_ttl_minutes", 10)) * 60
        return self._fresh(self.chat_ok_flag, ttl)

    def consume_switch_approval(self) -> None:
        self._unlink(self.chat_ok_flag)

    # --- mode ----------------------------------------------------------
    def mode(self) -> Dict[str, object]:
        base = self._cfg().get("mode") or {}
        out: Dict[str, object] = {
            "lang": str(base.get("default_lang", "zh")),
            "voice": bool(base.get("default_voice", False)),
        }
        try:
            m = json.loads(self.mode_path.read_text(encoding="utf-8"))
            if isinstance(m, dict):
                if m.get("lang") in ("en", "zh"):
                    out["lang"] = m["lang"]
                out["voice"] = bool(m.get("voice", out["voice"]))
        except OSError:
            pass
        except Exception:
            pass
        return out

    def set_mode(self, **kv) -> Dict[str, object]:
        cur = self.mode()
        cur.update(kv)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.mode_path.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
            if self._log:
                self._log("mode-set", "", json.dumps(cur, ensure_ascii=False))
        except OSError:
            pass
        return cur

    def active(self, chat_id_getter, session_id: str) -> Optional[str]:
        """返回 chat_id 表示"该会话需要整形"，None 表示完全不碰。"""
        cfg = self._cfg()
        if not cfg.get("enabled"):
            return None
        chat_id = chat_id_getter(session_id)
        if not chat_id or chat_id not in (cfg.get("chat_ids") or []):
            return None
        if self.work_stale():
            return None
        return chat_id
