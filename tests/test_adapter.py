"""适配器契约：钩子签名、气泡发送顺序、失败放行。"""

import json
import sqlite3

import pytest

from chitchat.adapters.hermes import HermesAdapter, register
from chitchat.adapters.transport import NullTransport


class FakeCtx:
    def __init__(self):
        self.hooks = {}
        self.commands = {}

    def register_hook(self, name, fn):
        self.hooks[name] = fn

    def register_command(self, name, fn):
        self.commands[name] = fn


def make_adapter(tmp_path, transport=None):
    con = sqlite3.connect(tmp_path / "state.db")
    con.execute("CREATE TABLE sessions (id TEXT, chat_id TEXT, chat_type TEXT, title TEXT, source TEXT)")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL)")
    con.execute("INSERT INTO sessions VALUES ('s1','c1','group','测试窗口','cli')")
    con.commit()
    con.close()
    cfg = {
        "enabled": True,
        "chat_ids": ["c1"],
        "strip_markdown": True,
        "dedup_repetition": True,
        "bubble": {"target_chars": 12, "pack_limit": 30, "max_bubbles": 10, "delay_seconds": 0},
        "inject": {"time": False, "mood": False, "mode": True, "attention": False, "peer": False},
        "providers": {},
        "hermes": {"db_path": str(tmp_path / "state.db")},
        "transport": {"impl": "null"},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return HermesAdapter(tmp_path, transport=transport or NullTransport())


def test_transform_sends_all_but_last(tmp_path):
    t = NullTransport()
    a = make_adapter(tmp_path, t)
    out = a.on_transform("第一句话在这。第二句话在这。第三句话在这。", "s1")
    assert out and len(t.sent) >= 1
    assert t.sent[-1][1] != out  # 最后一条由宿主正常回复，不重复发
    assert all(chat == "c1" for chat, _ in t.sent)


def test_transform_noop_outside_configured_chat(tmp_path):
    a = make_adapter(tmp_path)
    assert a.on_transform("随便一句比较长的话，应该原样返回。", "unknown") is None


def test_pre_llm_call_injects_mode(tmp_path):
    a = make_adapter(tmp_path)
    res = a.on_pre_llm_call("s1", "在吗")
    assert res and "语言模式" in res["context"]


def test_pre_llm_call_skips_other_sessions(tmp_path):
    a = make_adapter(tmp_path)
    assert a.on_pre_llm_call("nope", "在吗") is None


def test_work_mode_silences_plugin(tmp_path):
    a = make_adapter(tmp_path)
    a.state.work_on()
    assert a.on_transform("这句话不该被切。", "s1") is None
    assert a.on_pre_llm_call("s1", "在吗") is None


def test_transform_failure_passes_through(tmp_path):
    class Boom(NullTransport):
        def send(self, chat_id, text):
            raise RuntimeError("network down")

    a = make_adapter(tmp_path, Boom())
    out = a.on_transform("第一句。第二句。第三句。", "s1")
    assert out is None or isinstance(out, str)


def test_register_wires_hooks_and_commands(tmp_path, monkeypatch):
    ctx = FakeCtx()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import chitchat.adapters.hermes as mod

    monkeypatch.setattr(mod, "Path", mod.Path)
    register(ctx)
    assert set(ctx.hooks) == {"transform_llm_output", "pre_llm_call", "pre_tool_call"}
    assert {"work", "chat", "en", "zh", "voice"} <= set(ctx.commands)
