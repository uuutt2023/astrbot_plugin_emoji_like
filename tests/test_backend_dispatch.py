"""情感判断后端分发：llm / jev / hybrid 三条路的接线行为。

判定层（core/jev_emotion.py）的纯逻辑在 test_jev_emotion.py 里测，
这里测的是「插件怎么选路、怎么回落」。
"""

import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_ROOT.parent))
_emotion = importlib.import_module(f"{_ROOT.name}.core.emotion")


class FakeEvent:
    """够用的消息事件替身：只带情感缓存要用的那两方法。"""

    def __init__(self):
        self._extra = {}
        self.unified_msg_origin = "test@Group"

    def get_extra(self, key):
        return self._extra.get(key)

    def set_extra(self, key, value):
        self._extra[key] = value


def _make_answer(choice, probability):
    return {"choice": choice, "probabilities": {choice: probability}}


class TestLLMBackend:
    @pytest.mark.asyncio
    async def test_llm_backend_never_calls_jev(self, make_judger):
        judger = make_judger({"judge_backend": "llm"})
        called = []

        async def boom(cfg, state, questions, idem=None):
            called.append(1)
            return {"status": "ready", "answers": {}}

        judger.jev_client.evaluate = boom

        event = FakeEvent()
        emotion = await judger.judge_emotion(event, text="今天真开心", labels=["开心"])
        assert emotion == "开心"
        assert called == []  # 一次 Jev 都没调
        assert len(judger._test_provider_calls) == 1  # LLM 调了一次

    @pytest.mark.asyncio
    async def test_llm_prompt_unchanged(self, make_judger):
        """LLM 路径的提示词必须和接入 Jev 之前逐字一致。"""
        judger = make_judger({"judge_backend": "llm"})
        await judger.judge_emotion(FakeEvent(), text="今天真开心", labels=["开心"])
        call = judger._test_provider_calls[0]
        assert call["system_prompt"] == (
            "你是一个情感分析专家。\n"
            "只能从以下情感标签中选择一个：['开心']\n"
            "请严格按照 JSON 格式输出，不要包含任何多余内容。\n"
            '输出示例：{"emotion": "开心"}'
        )
        assert call["prompt"] == "文本内容：今天真开心"

    @pytest.mark.asyncio
    async def test_llm_bad_json_returns_none(self, make_judger):
        judger = make_judger({"judge_backend": "llm"}, llm_text="不是 JSON")
        assert await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"]) is None

    @pytest.mark.asyncio
    async def test_labels_not_restricted(self, make_judger):
        """不限制标签时，提示词里就不该有候选表。"""
        judger = make_judger({"judge_backend": "llm"})
        await judger.judge_emotion(FakeEvent(), text="随便什么")
        assert "不限制情感标签" in judger._test_provider_calls[0]["system_prompt"]


class TestJevBackend:
    @pytest.mark.asyncio
    async def test_jev_backend_uses_jev(self, make_judger):
        judger = make_judger(
            {"judge_backend": "jev", "jev_judge": {"enabled": True}},
            jev_answer=_make_answer("开心", 0.9),
        )
        event = FakeEvent()
        emotion = await judger.judge_emotion(event, text="今天真开心", labels=["开心"])
        assert emotion == "开心"
        assert len(judger._test_provider_calls) == 0  # 没调 LLM
        assert event.get_extra("emotion") == "开心"  # 缓存写进去了

    @pytest.mark.asyncio
    async def test_jev_backend_disabled_does_not_call_llm(self, make_judger):
        """纯 Jev 模式：Jev 没启用就不回落 LLM（跟 hybrid 的区别）。"""
        judger = make_judger(
            {"judge_backend": "jev", "jev_judge": {"enabled": False}},
            jev_answer=_make_answer("开心", 0.9),
        )
        assert await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"]) is None
        assert len(judger._test_provider_calls) == 0

    @pytest.mark.asyncio
    async def test_jev_backend_low_confidence_no_fallback(self, make_judger):
        judger = make_judger(
            {"judge_backend": "jev", "jev_judge": {"enabled": True, "min_confidence": 0.6}},
            jev_answer=_make_answer("开心", 0.2),
        )
        assert await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"]) is None
        assert len(judger._test_provider_calls) == 0

    @pytest.mark.asyncio
    async def test_jev_backend_transport_error_no_fallback(self, make_judger):
        judger = make_judger(
            {"judge_backend": "jev", "jev_judge": {"enabled": True}}
        )

        async def failing(cfg, state, questions, idem=None):
            return {"status": "upstream_error"}

        judger.jev_client.evaluate = failing
        assert await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"]) is None
        assert len(judger._test_provider_calls) == 0

    @pytest.mark.asyncio
    async def test_jev_backend_without_labels_returns_none(self, make_judger):
        """没有候选标签 → Jev 问不了 → 纯 Jev 模式不回落 LLM。"""
        judger = make_judger(
            {"judge_backend": "jev", "jev_judge": {"enabled": True}},
            jev_answer=_make_answer("开心", 0.9),
        )
        assert await judger.judge_emotion(FakeEvent(), text="x", labels=None) is None
        assert len(judger._test_provider_calls) == 0


class TestHybridBackend:
    @pytest.mark.asyncio
    async def test_hybrid_uses_jev_when_confident(self, make_judger):
        judger = make_judger(
            {"judge_backend": "hybrid", "jev_judge": {"enabled": True}},
            jev_answer=_make_answer("开心", 0.9),
        )
        emotion = await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"])
        assert emotion == "开心"
        assert len(judger._test_provider_calls) == 0

    @pytest.mark.asyncio
    async def test_hybrid_falls_back_to_llm_when_unconfident(self, make_judger):
        judger = make_judger(
            {"judge_backend": "hybrid", "jev_judge": {"enabled": True, "min_confidence": 0.6}},
            jev_answer=_make_answer("开心", 0.2),
        )
        emotion = await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"])
        assert emotion == "开心"  # 来自 LLM
        assert len(judger._test_provider_calls) == 1

    @pytest.mark.asyncio
    async def test_hybrid_falls_back_when_jev_disabled(self, make_judger):
        judger = make_judger(
            {"judge_backend": "hybrid", "jev_judge": {"enabled": False}}
        )
        emotion = await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"])
        assert emotion == "开心"
        assert len(judger._test_provider_calls) == 1

    @pytest.mark.asyncio
    async def test_hybrid_falls_back_when_jev_raises(self, make_judger):
        judger = make_judger(
            {"judge_backend": "hybrid", "jev_judge": {"enabled": True}}
        )

        async def exploding(cfg, state, questions, idem=None):
            raise RuntimeError("boom")

        judger.jev_client.evaluate = exploding
        emotion = await judger.judge_emotion(FakeEvent(), text="x", labels=["开心"])
        assert emotion == "开心"
        assert len(judger._test_provider_calls) == 1


class TestEmotionCache:
    @pytest.mark.asyncio
    async def test_cached_emotion_is_reused(self, make_judger):
        judger = make_judger({"judge_backend": "llm"})
        event = FakeEvent()
        event.set_extra("emotion", "开心")
        assert await judger.judge_emotion(event, text="x", labels=["开心"]) == "开心"
        assert len(judger._test_provider_calls) == 0  # 压根没再问模型

    @pytest.mark.asyncio
    async def test_cached_emotion_not_in_labels_is_ignored(self, make_judger):
        judger = make_judger({"judge_backend": "llm"})
        event = FakeEvent()
        event.set_extra("emotion", "疑惑")
        emotion = await judger.judge_emotion(event, text="x", labels=["开心"])
        assert emotion == "开心"  # 重新判了
        assert len(judger._test_provider_calls) == 1


class TestBackendConstants:
    def test_three_backends(self):
        assert _emotion.JUDGE_BACKENDS == ("llm", "jev", "hybrid")

    def test_default_backend_is_llm(self, make_judger):
        """没配 judge_backend 的老配置，走 LLM（行为不变）。"""
        judger = make_judger({})
        assert judger.cfg.judge_backend is None
