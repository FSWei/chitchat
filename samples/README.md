# 样例

这些是**虚构的示例数据**，用来演示这套骨架跑起来长什么样。仓库里没有任何真实的人设、聊天记录或照片。

## 里面有什么

| 文件 | 是什么 |
|---|---|
| `journal/2026-03-02.md` … `2026-03-04.md` | 三篇日记，格式与 [docs/LIFE.md](../docs/LIFE.md) 一致（分段、五个字段、碎碎念） |
| `chat.md` | 一段对话，展示分条后的形态和她的说话方式 |
| `images/*.jpg` | 五张示例图，由 `images/prompts.json` 生成 |
| `images/prompts.json` | 五条完整提示词，三层架构拼好的结果 |
| `images/generate.py` | 生成脚本，支持 3.0（AK/SK）和 5.0 Flash（Ark Key） |

## 日期为什么是 3 月

样例是三月的一个周一到周三，跟真实使用时的日记不重叠，避免混淆。西雅图三月的典型天气：阴、小雨、偶尔放晴。

## 怎么用

**看日记格式**：直接读 `journal/2026-03-02.md`，对照 `docs/LIFE.md` 里的规则检查——段落、字段、字数、有没有预报。

**跑水位脚本**：把样例拷进一个工作目录，然后：

```bash
cp samples/journal/*.md /tmp/her-life/journal.md
cd /tmp/her-life && python3 ../../life/journal_state.py status
```

**重新出图**：改 `images/prompts.json` 里的提示词，然后：

```bash
export VOLCENGINE_AK=... VOLCENGINE_SK=...
python samples/images/generate.py --provider volcengine3
```

成本约 0.26 元一张（3.0）。脚本会跳过已存在的图，删掉哪张就重出哪张。

## 注意

- 图里的角色是 AI 生成的虚构人物，不是真人。
- 日记里的人物、客户、猫都是虚构的；不要拿样例当真实记忆灌进你自己的实例。
- 想换成自己的角色，改 `character/` 里的人设、衣橱、场景，样例只当格式参考。
