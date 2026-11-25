"""记忆链路机械层：条目拆分、按日期归档、checkpoint 只前进。"""

from argparse import Namespace
from datetime import date

from memory import lifecycle as lc


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_split_entries_accepts_two_and_three_level_heads():
    text = (
        "# 标题\n\n说明\n\n"
        "## 2026-03-01\n- 内容 A\n\n"
        "## 2026-03-02\n- 内容 B\n\n"
        "### 2026-03-03\n场景式记忆\n"
    )
    header, entries = lc.split_entries(text)
    assert header.startswith("# 标题")
    assert [h.strip() for h, _ in entries] == ["## 2026-03-01", "## 2026-03-02", "### 2026-03-03"]
    assert "- 内容 B" in entries[1][1]


def test_entry_date_parses_and_rejects():
    assert lc.entry_date("## 2026-03-01 周记") == date(2026, 3, 1)
    assert lc.entry_date("### 2026-03-01") == date(2026, 3, 1)
    assert lc.entry_date("## 不是日期") is None


def test_archive_moves_only_old_entries(tmp_path):
    _write(
        tmp_path / "chat-log.md",
        "# 聊天记录\n\n## 2026-03-01\n- 旧的\n\n## 2026-03-10\n- 新的\n",
    )
    rc = lc.cmd_archive(
        Namespace(dir=str(tmp_path), days=3, today=date(2026, 3, 11))
    )
    assert rc == 0
    kept = (tmp_path / "chat-log.md").read_text(encoding="utf-8")
    moved = (tmp_path / "chat-archive.md").read_text(encoding="utf-8")
    assert "2026-03-01" in moved and "2026-03-10" in kept
    assert "2026-03-01" not in kept


def test_archive_is_idempotent(tmp_path):
    _write(tmp_path / "chat-log.md", "## 2026-03-01\n- 旧的\n")
    args = Namespace(dir=str(tmp_path), days=3, today=date(2026, 3, 11))
    lc.cmd_archive(args)
    lc.cmd_archive(args)  # 第二次没有可归档的
    moved = (tmp_path / "chat-archive.md").read_text(encoding="utf-8")
    assert moved.count("2026-03-01") == 1


def test_deep_moves_long_term(tmp_path):
    _write(
        tmp_path / "long-term-memory.md",
        "# 长期记忆\n\n### 2026-02-01\n旧的场景\n\n### 2026-03-09\n新的场景\n",
    )
    lc.cmd_deep(Namespace(dir=str(tmp_path), days=14, today=date(2026, 3, 11)))
    kept = (tmp_path / "long-term-memory.md").read_text(encoding="utf-8")
    deep = (tmp_path / "deep-archive.md").read_text(encoding="utf-8")
    assert "2026-02-01" in deep and "2026-03-09" in kept


def test_advance_only_moves_forward(tmp_path):
    assert lc.cmd_advance(Namespace(dir=str(tmp_path), ts=100.0)) == 0
    assert lc.cmd_advance(Namespace(dir=str(tmp_path), ts=50.0)) == 1
    cp = (tmp_path / "chat-log-checkpoint.json").read_text(encoding="utf-8")
    assert "100.0" in cp


def test_pending_then_check_warns(tmp_path, capsys):
    lc.cmd_pending(Namespace(dir=str(tmp_path), count=3))
    lc.cmd_check(Namespace(dir=str(tmp_path)))
    assert "WARNING" in capsys.readouterr().out

    lc.cmd_pending(Namespace(dir=str(tmp_path), count=0))
    lc.cmd_check(Namespace(dir=str(tmp_path)))
    assert "OK" in capsys.readouterr().out


def test_read_tolerates_gbk_edited_files(tmp_path):
    path = tmp_path / "journal.md"
    path.write_bytes("## 2026-03-01\n- 中文条目\n".encode("gbk"))
    assert "中文条目" in lc._read(path)


def test_rotate_handles_journal_files(tmp_path):
    _write(
        tmp_path / "journal.md",
        "# 日记\n\n## 2026-03-01\n- 旧的\n\n## 2026-03-10\n- 新的\n",
    )
    lc.cmd_rotate(
        Namespace(
            dir=str(tmp_path), file="journal.md", to="archive.md",
            days=3, today=date(2026, 3, 11), echo=False,
        )
    )
    assert "2026-03-01" in (tmp_path / "archive.md").read_text(encoding="utf-8")
    kept = (tmp_path / "journal.md").read_text(encoding="utf-8")
    assert "2026-03-10" in kept and "2026-03-01" not in kept
