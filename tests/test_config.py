"""配置与状态：默认值、校验、热加载、工作模式 TTL。"""

import json
import time

from chitchat.config import DEFAULTS, ConfigLoader, validate
from chitchat.modes import State


def test_defaults_are_off_by_default():
    cfg = validate({})
    assert cfg["enabled"] is False
    assert cfg["chat_ids"] == []
    assert cfg["bubble"]["target_chars"] == DEFAULTS["bubble"]["target_chars"]


def test_validate_clamps_bad_numbers():
    cfg = validate({"bubble": {"target_chars": 1, "pack_limit": 5, "max_bubbles": 999}})
    assert cfg["bubble"]["target_chars"] >= 10
    assert cfg["bubble"]["pack_limit"] >= cfg["bubble"]["target_chars"]
    assert cfg["bubble"]["max_bubbles"] <= 50


def test_config_hot_reload(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    loader = ConfigLoader(path)
    assert loader.load()["enabled"] is False
    time.sleep(0.01)
    path.write_text(json.dumps({"enabled": True, "chat_ids": ["c1"]}), encoding="utf-8")
    assert loader.load()["enabled"] is True
    assert loader.load()["chat_ids"] == ["c1"]


def test_broken_config_keeps_last_good(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"enabled": True}), encoding="utf-8")
    loader = ConfigLoader(path)
    assert loader.load()["enabled"] is True
    time.sleep(0.01)
    path.write_text("{ not json", encoding="utf-8")
    assert loader.load()["enabled"] is True


def test_work_flag_ttl(tmp_path):
    cfg = {"enabled": True, "chat_ids": ["c1"], "flags": {"work_ttl_hours": 0.0001}}
    st = State(tmp_path, lambda: cfg)
    st.work_on()
    assert st.work_stale() is True
    time.sleep(0.5)
    assert st.work_stale() is False


def test_active_gate(tmp_path):
    cfg = {"enabled": True, "chat_ids": ["c1"], "flags": {"work_ttl_hours": 12}}
    st = State(tmp_path, lambda: cfg)
    lookup = lambda sid: {"s1": "c1", "s2": "other"}.get(sid)  # noqa: E731
    assert st.active(lookup, "s1") == "c1"
    assert st.active(lookup, "s2") is None
    st.work_on()
    assert st.active(lookup, "s1") is None


def test_mode_persists(tmp_path):
    st = State(tmp_path, lambda: {"mode": {"default_lang": "zh"}})
    assert st.mode()["lang"] == "zh"
    st.set_mode(lang="en")
    assert State(tmp_path, lambda: {"mode": {"default_lang": "zh"}}).mode()["lang"] == "en"
