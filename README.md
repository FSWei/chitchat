# chitchat

> 让 LLM 的输出看起来像**人在发消息**：拆成聊天气泡、砍复读、过禁词、去掉 Markdown 痕迹，可选注入时间/情绪/人设。

不依赖任何特定框架的核心逻辑，加一个 Hermes 插件适配器。`core` 是纯函数，5 行代码就能用。

```python
from chitchat import transform

bubbles = transform(model_output, {
    "strip_markdown": True,
    "dedup_repetition": True,
    "bubble": {"target_chars": 70, "pack_limit": 140, "max_bubbles": 12},
})
for b in bubbles[:-1]:      # 前 N-1 条自己发
    send(chat_id, b)
return bubbles[-1]          # 最后一条走正常回复
```

## 它做什么

| 能力 | 说明 |
|---|---|
| 分气泡 | 换行=气泡边界；行内按句打包到 `target_chars`，单条不超 `pack_limit`，超过 `max_bubbles` 合并尾部（不丢内容） |
| 复读防护 | 两道防线：尾部整块重复迭代删除 + 单行首次出现保留 |
| 禁词表 | `{"禁词": "替换值"}`，值为空即删除 |
| Markdown 剥离 | 标题井号、`**加粗**`、列表符号——聊天里这些像文档 |
| 上下文注入 | 时间（多时区）、情绪/人设文本、按日期召回历史、当前模式 |
| 模式 | `/work` 休眠、`/chat` 恢复、`/en` `/zh` 语言、`/voice` 语音开关 |
| 守卫 | 名单内 skill 不许加载、状态文件不许乱改（都可关） |

## 它不做什么

- ❌ 不做人设生成、不做记忆系统、不做 TTS 合成
- ❌ 不替你决定"说什么"，只改**怎么说**
- ❌ 不绑定任何一家 IM（发送由 `Transport` 协议提供）

## 安装

```bash
pip install -e .            # 或者 pip install chitchat（若 PyPI 名字可用）
python examples/demo.py     # 不用任何宿主，先看效果
```

## 接 Hermes

```bash
# 插件目录里放一个 3 行的 shim（examples/hermes_plugin/ 有现成的）
mkdir -p ~/.hermes/profiles/<profile>/plugins/chitchat
cp examples/hermes_plugin/__init__.py ~/.hermes/profiles/<profile>/plugins/chitchat/
cp examples/config.example.json          ~/.hermes/profiles/<profile>/plugins/chitchat/config.json
hermes -p <profile> plugins enable chitchat
```

`config.json` 热加载（按 mtime），改完不用重启；`chat_ids` 填你自己的会话 ID，其它会话完全不受影响。

配置项见 [`docs/PROVIDERS.md`](docs/PROVIDERS.md) 与 `examples/config.example.json`；
人设/风格该写在哪，见 [`docs/SKILL-TEMPLATE.md`](docs/SKILL-TEMPLATE.md)。

## 设计取舍

1. **失败即放行**：任何异常都返回 `None`（原文照发），插件不能把你的消息吞掉。
2. **状态是文件**：`state/work.flag`、`state/mode.json` 肉眼可查、可手动改，不用数据库。
3. **上下文靠 provider**：`TextProvider` / `HistoryProvider` 两个协议，接自己的记忆系统不用改源码。
4. **没有个人内容**：仓库里不含任何人设、词表、聊天 ID；你自己的东西放 `config.json` 和 provider 指向的文件里。

## 测试

```bash
python -m pytest          # 33 个用例：core / config / modes / context / adapter 契约
python scripts/privacy_scan.py   # 发布前自检：姓名、手机、邮箱、密钥、绝对路径
```

## CI

`docs/ci.yml.example` 是一份 GitHub Actions 配置（pytest + 隐私扫描 + demo 冒烟）。
复制到 `.github/workflows/ci.yml` 即可启用——需要 token 带 `workflow` 权限。

## License

MIT
