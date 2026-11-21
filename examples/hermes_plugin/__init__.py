"""Hermes 插件 shim：把已安装的 chitchat 包接到宿主。

放到 ~/.hermes/profiles/<profile>/plugins/<plugin-name>/__init__.py
"""

from chitchat.adapters.hermes import register  # noqa: F401
