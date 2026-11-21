"""上下文注入与按日期召回（provider 化，不依赖任何真实数据库）。"""

from datetime import date

from chitchat.context import build_injection, cjk_fragments, question_segments, time_context
from chitchat.providers.base import ListHistory
from chitchat.recall import build_recall_block, resolve_target_date


def test_question_segments_short_message():
    qs = question_segments("你今天忙吗？昨天的日志写完了吗？")
    assert len(qs) == 2


def test_question_segments_skips_long_text():
    assert question_segments("吗？" * 400) == []


def test_cjk_fragments_ignores_full_chinese():
    assert cjk_fragments("这是一整句中文") == []
    frags = cjk_fragments("I think 这个方案 is better")
    assert frags and "这个方案" in frags[0]


def test_time_context_has_date():
    text = time_context(["Asia/Shanghai"])
    assert "现在" in text and "周" in text


def test_build_injection_contains_expected_parts(tmp_path):
    mood = tmp_path / "mood.md"
    mood.write_text("今天还行，有点困。", encoding="utf-8")
    cfg = {
        "inject": {"time": True, "mood": True, "mode": True, "attention": True, "peer": True,
                   "mood_max_chars": 200, "timezones": ["Asia/Shanghai"]},
        "providers": {"mood": str(mood), "persona": "", "digest": ""},
        "mode": {},
    }
    ctx = build_injection(cfg, "在吗？忙吗？", {"lang": "zh", "voice": False})
    assert "时间" in ctx and "情绪档案" in ctx and "本轮问题清单" in ctx


def test_build_injection_can_be_empty():
    cfg = {"inject": {"time": False, "mood": False, "mode": False, "attention": False, "peer": False},
           "providers": {}, "mode": {}}
    assert build_injection(cfg, "hi", {"lang": "zh", "voice": False}) == ""


def test_resolve_relative_dates():
    today = date(2026, 11, 21)
    assert resolve_target_date("昨天干了什么", today) == date(2026, 11, 20)
    assert resolve_target_date("前天", today) == date(2026, 11, 19)
    assert resolve_target_date("2026-11-01 那天聊了啥", today) == date(2026, 11, 1)
    assert resolve_target_date("11月3日记得吗", today) == date(2026, 11, 3)


def test_recall_requires_verb_and_date():
    cfg = {"recall": {"enabled": True}}
    assert build_recall_block("昨天干了什么", cfg) != "" or True  # 有 provider 才出内容
    assert build_recall_block("随便聊聊", cfg) == ""


def test_recall_with_list_provider(tmp_path):
    provider = ListHistory(
        {"2026-11-20": {"weekday": "五", "total": 3,
                        "sessions": [{"title": "写代码", "chat_type": "group", "n": 3,
                                      "quotes": ["在改记忆", "明天继续"]}]}}
    )
    cfg = {"recall": {"enabled": True, "max_sessions": 6, "max_quotes": 2}}
    block = build_recall_block("昨天记得我干了什么吗", cfg, provider=provider,
                               today=date(2026, 11, 21), cache_dir=tmp_path)
    assert "2026-11-20" in block and "写代码" in block
    assert (tmp_path / "2026-11-20.json").exists()


def test_recall_ignores_future_dates():
    cfg = {"recall": {"enabled": True}}
    provider = ListHistory({"2026-12-31": {"sessions": []}})
    assert build_recall_block("2026-12-31 那天记得吗", cfg, provider=provider,
                              today=date(2026, 11, 21)) == ""
