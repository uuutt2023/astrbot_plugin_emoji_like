#!/usr/bin/env python3
"""情感判定质量离线评测：拿真实 Jev API 跑一批标注好的中文群聊消息。

用法：

    export JEVMODEL_API_KEY=sk-xxxx
    python scripts/eval_emotion.py
    python scripts/eval_emotion.py --base-url https://api.typesafe.ai
    python scripts/eval_emotion.py --compare          # 对比「带/不带标签候选」

判定标准：

- Jev 选中的标签必须落在候选标签里；
- 准确率低于 ``--min-accuracy``（默认 0.7）时以非零码退出，方便挂 CI。

改完 prompts/jev_emotion.py 的 instructions 或 criteria 之后，跑一次这个脚本
就知道判定质量有没有退化。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_ROOT.parent))

from astrbot_plugin_emoji_like.core import jev_emotion  # noqa: E402
from astrbot_plugin_emoji_like.core.jev_transport import JevClient  # noqa: E402

# 候选标签（跟插件默认的「情感映射表」一致）
LABELS = [
    "开心", "得意", "害羞", "难过", "纠结", "生气",
    "惊讶", "疑惑", "恳求", "可怕", "尴尬", "无语", "恶心", "无聊",
]

# 人工标注：消息 → 可接受的标签集合
CASES = [
    ("今天天气真好出去玩！", {"开心"}),
    ("哈哈哈哈太逗了", {"开心"}),
    ("这波操作我服了", {"得意"}),
    ("谢谢哥哥～", {"害羞"}),
    ("今天真的很难过", {"难过"}),
    ("好纠结啊到底选哪个", {"纠结"}),
    ("你tm有病吧", {"生气"}),
    ("居然还有这种操作", {"惊讶"}),
    ("为什么是这样", {"疑惑"}),
    ("求求你帮帮我", {"恳求"}),
    ("这也太吓人了吧", {"可怕"}),
    ("额那个", {"尴尬"}),
    ("算了不说了", {"无语"}),
    ("这玩意儿真恶心", {"恶心"}),
    ("好无聊啊", {"无聊"}),
]


async def run(args) -> int:
    cfg = {
        "proxy_url": args.gateway,
        "proxy_protocol": args.protocol,
        "timeout_sec": args.timeout_sec,
        "retries": 1,
        "gate_mode": "threshold",
        "min_confidence": args.min_confidence,
        "prompt_language": "auto",
    }

    client = JevClient()
    hits = 0
    total = 0
    rows = []
    try:
        for text, expected in CASES:
            result = await jev_emotion.judge_via_jev(client, cfg, text, LABELS)
            got = result.get("emotion") or ""
            ok = got in expected
            total += 1
            hits += 1 if ok else 0
            rows.append((text, sorted(expected), got, result.get("confidence"), ok, result.get("reason", "")))
    finally:
        await client.close()

    width = 42
    print(f"{'消息':<{width}} {'期望':<12} {'Jev 判定':<10} {'置信度':>7}  结果")
    print("-" * (width + 40))
    for text, expected, got, confidence, ok, reason in rows:
        mark = "✓" if ok else "✗"
        conf = f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "-"
        note = "" if ok else f"  ← {reason}" if reason else ""
        print(f"{text:<{width}} {','.join(expected):<12} {got or '-':<10} {conf:>7}  {mark}{note}")

    accuracy = hits / total if total else 0.0
    print()
    print(f"准确率：{hits}/{total} = {accuracy:.1%}（门槛 {args.min_accuracy:.0%}）")
    if accuracy < args.min_accuracy:
        print("❌ 低于门槛")
        return 1
    print("✅ 通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Jev 情感判定离线评测")
    parser.add_argument("--gateway", default="http://127.0.0.1:8770", help="Jev 决策网关地址")
    parser.add_argument("--protocol", default="systemone", help="网关里登记的协议名")
    parser.add_argument("--timeout-sec", type=float, default=10.0, help="单次请求超时（秒）")
    parser.add_argument("--min-confidence", type=float, default=0.6, help="采信阈值")
    parser.add_argument("--min-accuracy", type=float, default=0.7, help="准确率门槛")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
