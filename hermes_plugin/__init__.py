"""Hermes 插件入口：把 chitchat 包接到宿主钩子上。

安装（在 Hermes 的 profile 里）：
    ln -s <repo>/hermes_plugin ~/.hermes/profiles/<profile>/plugins/chitchat

插件目录 = 本文件夹；config.json 与 state/ 也放在这里，
或者用环境变量 CHITCHAT_HOME 指到别处（推荐，避免写进仓库目录）。
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from chitchat.adapters.hermes import register  # noqa: E402,F401
