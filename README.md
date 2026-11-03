
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_emoji_like?name=astrbot_plugin_emoji_like&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_emoji_like

_✨ 智能贴表情 ✨_  

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

调用LLM判断消息的情感，智能地给消息贴上QQ表情。

> 上游仓库（Zhalslar/astrbot_plugin_emoji_like）已停止维护，本仓库为其续作版本。
> 情感判断新增了 **Jev 决策后端**：更快、更便宜，且不改变原有行为。

## 🧠 Jev 决策后端（可选）

贴表情前要先判断消息是什么情绪——这本质上是一次**从固定选项里选一个**的分类，
不需要生成任何文字，正好是 [Jev](https://jevmodel.org/zh/docs/) 决策模型擅长的类型化判断。

| 后端 | 行为 | 适合谁 |
|---|---|---|
| `llm`（默认） | 调用 LLM 生成 `{"emotion": "..."}` 再解析 | 维持原样，行为与升级前完全一致 |
| `jev` | 只用 Jev 决策模型，不调用大模型 | 想要更快更便宜；Jev 拿不到判定时随机贴表情，不会报错 |
| `hybrid` | 先用 Jev 判断，把握不大时才回退 LLM | 想省 token 又不想要随机表情 |

Jev 的候选选项**直接取自「情感映射表」里配的情感标签**——标签名就是选项名，
选回来即可贴表情，不需要额外映射。

使用步骤：

1. 在「Jev 判断」分组里打开「启用 Jev 判断」，填入 API Key
   （[jevmodel.org 控制台](https://jevmodel.org/zh/docs/) 或
   [TypeSafe](https://console.typesafe.ai)）；
2. 把「情感判断的后端」改成 `jev` 或 `hybrid`；
3. 重载插件。

Jev 只对输入 token 计费、输出免费，上游失败不计费且可安全重试。
想验证判定质量，跑 `python scripts/eval_emotion.py`（需要 `JEVMODEL_API_KEY`）。

## 🗂️ 目录结构

```
astrbot_plugin_emoji_like/
├── main.py                  # 插件入口：命令、事件监听、贴表情
├── core/
│   ├── config.py            # 强类型配置节点（ConfigNode）
│   ├── emotion.py           # 情感判断：llm / jev / hybrid 三种后端分发
│   ├── jev_emotion.py       # Jev 判定层：state 构造、选项映射、置信度门控
│   └── jev_transport.py     # Jev 传输层：预检、幂等键、错误码映射
├── prompts/                 # 所有提示词都在这里
│   ├── llm_emotion.py       #   LLM 后端（输出 JSON）
│   └── jev_emotion.py       #   Jev 后端（instructions + criteria）
├── tests/                   # pytest + 最小 astrbot 桩件
└── scripts/eval_emotion.py  # 判定质量离线评测（需 JEVMODEL_API_KEY）
```

## 📦 安装

在astrbot的插件市场搜索astrbot_plugin_emoji_like，点击安装即可


## ⌨️ 使用说明

### 命令表

|     命令      |        说明         |
|:-------------:|:----------------------------:|
| {一条消息}     | 概率触发贴表情，触发概率可在配置里设置  |
| 贴表情 <数量>  | 若不填数量，则默认贴5个    |

### 示例图

![download](https://github.com/user-attachments/assets/22d4a258-1d84-430e-9832-de2b12cdd9cf)

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
