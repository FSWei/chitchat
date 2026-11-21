"""core 纯函数：分气泡、去重、黑名单、markdown 剥离。"""

from chitchat.core import (
    apply_blacklist,
    is_structured,
    split_sentences,
    split_to_bubbles,
    strip_markdown_structure,
    strip_repeated_tail,
)

BUB = {"target_chars": 20, "pack_limit": 40, "max_bubbles": 12}


def test_split_by_lines():
    text = "第一行\n第二行\n第三行"
    assert split_to_bubbles(text, **BUB) == ["第一行", "第二行", "第三行"]


def test_pack_sentences_until_target():
    text = "这是一句比较长的话用来测试打包逻辑。这是第二句也很长的话。第三句同样足够长。"
    out = split_to_bubbles(text, target_chars=12, pack_limit=20, max_bubbles=10)
    assert len(out) >= 2
    assert all(len(b) <= 20 for b in out)
    assert "".join(out).replace("。", "") == text.replace("。", "")


def test_max_bubbles_merges_tail_without_losing_text():
    text = "\n".join(f"第{i}条消息内容" for i in range(1, 21))
    out = split_to_bubbles(text, target_chars=10, pack_limit=20, max_bubbles=3)
    assert len(out) == 3
    assert "第20条" in out[-1]
    assert sum(len(b) for b in out) >= len("第1条消息内容") * 20 - 20


def test_blacklist_replaces_and_deletes():
    assert apply_blacklist("嘿 老王 你好", {"老王": "你", "嘿 ": ""}) == "你 你好"


def test_strip_markdown_structure():
    text = "# 标题\n**重点** 和 __次要__\n- 列表项"
    out = strip_markdown_structure(text)
    assert "#" not in out and "**" not in out and "__" not in out
    assert "标题" in out and "重点" in out and "列表项" in out


def test_strip_repeated_tail_blocks():
    para = "这是一段比较长的内容用来触发整块阈值"
    text = "\n".join([para, para, para])
    assert strip_repeated_tail(text) == para


def test_strip_repeated_tail_keeps_short_repeats():
    text = "哈哈\n哈哈\n哈哈"
    assert strip_repeated_tail(text) == text


def test_structured_passthrough():
    assert is_structured("看代码\n```py\nprint(1)\n```")
    assert is_structured("| a | b |\n|---|---|\n| 1 | 2 |")
    assert not is_structured("普通一句话")


def test_split_sentences_keeps_punctuation():
    assert split_sentences("你好。在吗？") == ["你好。", "在吗？"]
