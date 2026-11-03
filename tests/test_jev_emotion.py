"""Jev 情感判定层（core/jev_emotion.py）的纯逻辑测试。

这一层不 import astrbot，所以测试不需要框架环境。
"""

import importlib
import json
import random
import sys
from pathlib import Path

import pytest

# 插件目录名可能不是 astrbot_plugin_emoji_like（测试时会被 clone 成别的名字），
# 这里按实际目录名解析包路径，避免硬编码。
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_ROOT.parent))
jev_emotion = importlib.import_module(f"{_ROOT.name}.core.jev_emotion")
prompts = importlib.import_module(f"{_ROOT.name}.prompts.jev_emotion")

LABELS = ["开心", "得意", "害羞", "难过", "生气", "无语"]


class TestQuestions:
    def test_criteria_keys_are_the_labels(self):
        """选项键就是情感标签，Jev 选回来就能直接贴表情。"""
        criteria = jev_emotion.build_questions(LABELS, "zh")[
            jev_emotion.QUESTION_NAME
        ]["criteria"]
        assert list(criteria) == LABELS

    def test_question_type_is_choice(self):
        question = jev_emotion.build_questions(LABELS, "zh")[jev_emotion.QUESTION_NAME]
        assert question["type"] == "choice"
        assert question["instructions"].strip()

    def test_instructions_within_documented_limit(self):
        """Jev 文档：instructions ≤ 1800 字符。"""
        for language in ("zh", "en"):
            question = jev_emotion.build_questions(LABELS, language)[
                jev_emotion.QUESTION_NAME
            ]
            assert len(question["instructions"]) <= 1800

    def test_criteria_within_documented_limit(self):
        """Jev 文档：criteria 序列化后 ≤ 2000 字符。"""
        for language in ("zh", "en"):
            question = jev_emotion.build_questions(LABELS, language)[
                jev_emotion.QUESTION_NAME
            ]
            payload = json.dumps(question["criteria"], ensure_ascii=False)
            assert len(payload) <= 2000

    def test_many_labels_still_fit(self):
        """标签很多时也要塞得进 Jev 的限制内。"""
        labels = [f"情绪{i}" for i in range(40)]
        question = jev_emotion.build_questions(labels, "zh")[jev_emotion.QUESTION_NAME]
        assert len(question["instructions"]) <= 1800
        assert len(json.dumps(question["criteria"], ensure_ascii=False)) <= 2000


class TestState:
    def test_state_is_structured(self):
        state = jev_emotion.build_state("今天真开心", has_image=True)
        assert state["文本"] == "今天真开心"
        assert state["含图片"] is True

    def test_english_keys(self):
        state = jev_emotion.build_state("happy", has_image=False, language="en")
        assert state["text"] == "happy"
        assert state["hasImage"] is False

    def test_long_text_truncated(self):
        state = jev_emotion.build_state("啊" * 5000, max_chars=100)
        assert len(state["文本"]) == 100

    def test_empty_text(self):
        state = jev_emotion.build_state("")
        assert state["文本"] == ""


class TestLanguage:
    def test_detect_chinese(self):
        assert jev_emotion.detect_language("你好") == "zh"

    def test_detect_english(self):
        assert jev_emotion.detect_language("hello") == "en"

    def test_resolve_auto_follows_content(self):
        assert jev_emotion.resolve_language("auto", "开心") == "zh"
        assert jev_emotion.resolve_language("auto", "happy") == "en"

    def test_resolve_explicit_wins(self):
        assert jev_emotion.resolve_language("en", "开心") == "en"


class TestEmotionConfidence:
    def test_probabilities_preferred(self):
        answer = {"choice": "开心", "probabilities": {"开心": 0.82}, "confidence": 0.4}
        assert jev_emotion.emotion_confidence(answer, LABELS) == ("开心", 0.82)

    def test_fallback_to_confidence_field(self):
        answer = {"choice": "开心", "confidence": 0.55}
        assert jev_emotion.emotion_confidence(answer, LABELS) == ("开心", 0.55)

    def test_missing_probability_is_protocol_error(self):
        answer = {"choice": "开心"}
        assert jev_emotion.emotion_confidence(answer, LABELS) == ("开心", None)

    def test_unknown_choice(self):
        answer = {"choice": "困惑", "probabilities": {"困惑": 0.9}}
        assert jev_emotion.emotion_confidence(answer, LABELS) == (None, None)

    def test_not_a_dict(self):
        assert jev_emotion.emotion_confidence("开心", LABELS) == (None, None)


class TestGate:
    def test_threshold_accepts_high_confidence(self):
        assert jev_emotion.decide_gate(0.9, 0.6, "threshold") == (True, 0.0)

    def test_threshold_rejects_low_confidence(self):
        assert jev_emotion.decide_gate(0.3, 0.6, "threshold") == (False, 0.0)

    def test_missing_probability_never_accepted(self):
        assert jev_emotion.decide_gate(None, 0.6, "threshold")[0] is False

    def test_sample_mode_uses_rng(self):
        rng = random.Random(0)
        # 概率 0 一定不采信
        assert jev_emotion.decide_gate(0.0, 0.6, "sample", rng)[0] is False
        # 概率 1 一定采信
        assert jev_emotion.decide_gate(1.0, 0.6, "sample", rng)[0] is True


class TestPickEmotion:
    def test_accepted(self):
        answer = {"choice": "开心", "probabilities": {"开心": 0.9}}
        picked = jev_emotion.pick_emotion(answer, LABELS, 0.6, "threshold")
        assert picked["ok"] is True
        assert picked["emotion"] == "开心"
        assert picked["confidence"] == 0.9

    def test_rejected_by_gate(self):
        answer = {"choice": "开心", "probabilities": {"开心": 0.2}}
        picked = jev_emotion.pick_emotion(answer, LABELS, 0.6, "threshold")
        assert picked["ok"] is False
        assert picked["parsed"] is True
        assert picked["accepted"] is False

    def test_protocol_error_unknown_choice(self):
        picked = jev_emotion.pick_emotion(
            {"choice": "困惑", "probabilities": {"困惑": 0.9}}, LABELS
        )
        assert picked["ok"] is False
        assert picked["parsed"] is False

    def test_protocol_error_missing_probability(self):
        picked = jev_emotion.pick_emotion({"choice": "开心"}, LABELS)
        assert picked["ok"] is False
        assert picked["parsed"] is True
        assert "协议错误" in picked["reason"]


class FakeClient:
    """假的 Jev 客户端：按预设返回传输层的结果。"""

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def evaluate(self, cfg, state, questions, idem=None):
        self.calls.append({"cfg": cfg, "state": state, "questions": questions})
        return self.result


class TestJudgeViaJev:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        client = FakeClient(
            {
                "status": "ready",
                "answers": {
                    "emotion": {
                        "choice": "开心",
                        "probabilities": {"开心": 0.91, "生气": 0.09},
                    }
                },
                "seconds": 2.4,
            }
        )
        result = await jev_emotion.judge_via_jev(
            client, {"min_confidence": 0.6}, "今天真好", LABELS
        )
        assert result["ok"] is True
        assert result["emotion"] == "开心"
        assert result["confidence"] == 0.91
        assert result["prompt_version"] == jev_emotion.PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_no_labels_cannot_ask(self):
        """没有候选标签时 Jev 没法问（它要的是固定选项集）。"""
        client = FakeClient({"status": "ready", "answers": {}})
        result = await jev_emotion.judge_via_jev(client, {}, "今天真好", [])
        assert result["ok"] is False
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_transport_failure(self):
        client = FakeClient({"status": "unauthorized"})
        result = await jev_emotion.judge_via_jev(client, {}, "今天真好", LABELS)
        assert result["ok"] is False
        assert "API Key" in result["reason"]

    @pytest.mark.asyncio
    async def test_low_confidence_not_accepted(self):
        client = FakeClient(
            {
                "status": "ready",
                "answers": {"emotion": {"choice": "开心", "probabilities": {"开心": 0.2}}},
            }
        )
        result = await jev_emotion.judge_via_jev(
            client, {"min_confidence": 0.6}, "今天真好", LABELS
        )
        assert result["ok"] is False
        assert result["emotion"] == "开心"  # 解析出来了，但没通过门控

    @pytest.mark.asyncio
    async def test_state_and_questions_shape(self):
        client = FakeClient({"status": "ready", "answers": {}})
        await jev_emotion.judge_via_jev(client, {}, "今天真好", LABELS, has_image=True)
        call = client.calls[0]
        assert call["state"]["文本"] == "今天真好"
        assert call["state"]["含图片"] is True
        assert list(call["questions"][jev_emotion.QUESTION_NAME]["criteria"]) == LABELS


class TestPrompts:
    def test_criteria_description_mentions_label(self):
        criteria = prompts.criteria_for(LABELS, "zh")
        assert "开心" in criteria["开心"]

    def test_english_criteria(self):
        criteria = prompts.criteria_for(["happy"], "en")
        assert "happy" in criteria["happy"]
