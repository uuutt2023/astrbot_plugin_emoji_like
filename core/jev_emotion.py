"""Jev 情感判定层。

纯逻辑，**不 import astrbot**，可以脱离 AstrBot 单独单测。

做的事：把「这条消息是什么情绪」变成一次 Jev 决策请求——
选项就是用户在「情感映射表」里配的情感标签，选回来的标签直接就能贴表情。

Jev 是决策模型：只从固定选项里选一个并给出概率分布，不生成文字，
所以比让 LLM 写一句话再解析要快也便宜（只对输入 token 计费，输出免费）。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from ..prompts import jev_emotion as prompts

# 提示词版本：改 instructions / criteria / state 形状时必须升版本
PROMPT_VERSION = "v1-2026-11-emoji"

# Jev 请求里的问题名
QUESTION_NAME = "emotion"

# 默认采信阈值（跟 soupai 一个口径）
DEFAULT_MIN_CONFIDENCE = 0.6

# 发送给 Jev 的文本长度上限
DEFAULT_MAX_STATE_CHARS = 800

# 置信度门控方式
GATE_MODE_THRESHOLD = "threshold"
GATE_MODE_SAMPLE = "sample"
GATE_MODES = (GATE_MODE_THRESHOLD, GATE_MODE_SAMPLE)

# 提示词语言
LANG_AUTO = "auto"
LANG_ZH = "zh"
LANG_EN = "en"
LANGUAGES = (LANG_AUTO, LANG_ZH, LANG_EN)

# state 的字段名（中文模式）
STATE_KEYS_ZH = {"text": "文本", "has_image": "含图片"}
STATE_KEYS_EN = {"text": "text", "has_image": "hasImage"}


def detect_language(*texts: Any) -> str:
    """看文本里有没有中文字符，判断提示词该用中文还是英文。"""
    for text in texts:
        if not isinstance(text, str) or not text:
            continue
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                return LANG_ZH
    return LANG_EN


def resolve_language(preferred: Any, *texts: Any) -> str:
    """定下提示词语言：auto 按内容判断，其余按配置来。"""
    if preferred in (LANG_ZH, LANG_EN):
        return preferred
    return detect_language(*texts)


def build_questions(labels: List[str], language: str = LANG_ZH) -> Dict[str, Dict[str, Any]]:
    """构造 Jev 的 choice 问题：选项就是情感标签。"""
    instructions = (
        prompts.INSTRUCTIONS_EN if language == LANG_EN else prompts.INSTRUCTIONS_ZH
    )
    criteria = prompts.criteria_for(list(labels), language)
    return {
        QUESTION_NAME: {
            "type": "choice",
            "instructions": instructions,
            "criteria": criteria,
        }
    }


def build_state(
    text: str,
    has_image: bool = False,
    max_chars: int = DEFAULT_MAX_STATE_CHARS,
    language: str = LANG_ZH,
) -> Dict[str, Any]:
    """构造发给 Jev 的 state。

    用结构化对象而不是裸字符串：Jev 文档支持 ``string / object / array``，
    命名字段比一大段裸文本更稳，模型也知道哪块是正文。
    """
    keys = STATE_KEYS_EN if language == LANG_EN else STATE_KEYS_ZH
    body = (text or "").strip()
    limit = max(0, int(max_chars or 0))
    if limit and len(body) > limit:
        # 超长就截断尾部（聊天消息的结论通常在末尾，但表情反应更看开头也行）
        body = body[:limit]
    return {
        keys["text"]: body,
        keys["has_image"]: bool(has_image),
    }


def emotion_confidence(
    answer: Any, labels: List[str]
) -> Tuple[Optional[str], Optional[float]]:
    """从 Jev 的 choice 答案里取出 (情感标签, 置信度)。

    置信度优先取「被选中那一档的概率」；没有分布时退回 ``confidence`` 字段。
    两者都缺失就返回 (标签, None)——缺概率是协议错误，调用方不能拿它去贴表情。
    """
    if not isinstance(answer, dict):
        return None, None
    choice = answer.get("choice")
    if not isinstance(choice, str):
        return None, None
    if choice not in labels:
        return None, None
    confidence: Optional[float] = None
    probabilities = answer.get("probabilities")
    if isinstance(probabilities, dict):
        top = probabilities.get(choice)
        if type(top) in (int, float):
            confidence = float(top)
    if confidence is None:
        raw = answer.get("confidence")
        if type(raw) in (int, float):
            confidence = float(raw)
    return choice, confidence


def decide_gate(
    probability: Optional[float],
    threshold: float = DEFAULT_MIN_CONFIDENCE,
    mode: str = GATE_MODE_THRESHOLD,
    rng: Optional[random.Random] = None,
) -> Tuple[bool, float]:
    """把「Jev 对自己这一档有多确定」变成「采不采信它」。

    - ``threshold``：概率 ≥ 阈值才采信。行为可复现、成本可预期。
    - ``sample``：以概率 p 采信，否则回退 LLM。LLM 调用频率随 Jev 的
      不确定性线性上升——Jev 越没把握，越可能多花一次 LLM 的钱。
    """
    if probability is None:
        return False, 0.0
    if mode != GATE_MODE_SAMPLE:
        return probability >= float(threshold), 0.0
    draw = (rng or random).random()
    return draw <= probability, draw


def pick_emotion(
    answer: Any,
    labels: List[str],
    threshold: float = DEFAULT_MIN_CONFIDENCE,
    mode: str = GATE_MODE_THRESHOLD,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """把 Jev 的 choice 答案翻成最终情感标签。

    Returns:
        dict: ``{"ok", "parsed", "emotion", "confidence", "accepted", "draw", "reason"}``
        ``parsed`` 表示答案结构合法；``accepted`` 表示门控通过；
        ``ok`` 是两者同时成立——只有 ok 为真时 ``emotion`` 才能拿去贴表情。
    """
    emotion, confidence = emotion_confidence(answer, labels)
    if emotion is None:
        return {
            "ok": False,
            "parsed": False,
            "emotion": "",
            "confidence": 0.0,
            "accepted": False,
            "draw": 0.0,
            "reason": "Jev 返回的选项不在候选内（协议错误）",
        }
    if confidence is None:
        # 缺概率是协议错误，不能默认成 0——那等于拿一个来路不明的判定去贴表情
        return {
            "ok": False,
            "parsed": True,
            "emotion": emotion,
            "confidence": 0.0,
            "accepted": False,
            "draw": 0.0,
            "reason": "Jev 未返回该选项的概率（协议错误）",
        }
    accepted, draw = decide_gate(confidence, threshold, mode, rng)
    return {
        "ok": bool(accepted),
        "parsed": True,
        "emotion": emotion,
        "confidence": confidence,
        "accepted": bool(accepted),
        "draw": draw,
        "reason": "" if accepted else "置信度不足",
    }


def status_reason(status: str) -> str:
    """把传输层的状态翻译成人话（给日志看）。"""
    return {
        "unconfigured": "未配置 Jev API Key",
        "unauthorized": "API Key 无效或已被禁用",
        "insufficient_credits": "Jev 账户余额不足",
        "invalid_request": "请求体未通过 Jev 校验",
        "rate_limited": "触发 Jev 限流",
        "upstream_error": "Jev 上游故障",
        "overloaded": "Jev 服务过载",
        "conflict": "幂等键冲突",
        "error": "网络或响应异常",
        "closed": "Jev 客户端已关闭",
        "busy": "并发过高，本轮已跳过",
        "backoff": "处于退避窗口，本轮跳过",
    }.get(status, status or "未知状态")


async def judge_via_jev(
    client,
    cfg: Dict[str, Any],
    text: str,
    labels: List[str],
    has_image: bool = False,
) -> Dict[str, Any]:
    """用 Jev 判断消息情感。

    返回 ``{"ok", "emotion", "confidence", "reason", ...}``；
    ``ok`` 为假时 ``emotion`` 是空串，调用方按自己的后端策略处理。
    """
    if not labels:
        # Jev 要的是固定选项集，没有候选标签就没法问
        return {"ok": False, "emotion": "", "confidence": 0.0, "reason": "没有可选的情感标签"}

    language = resolve_language(cfg.get("prompt_language"), *labels, text)
    questions = build_questions(list(labels), language)
    state = build_state(
        text,
        has_image=has_image,
        max_chars=cfg.get("max_state_chars") or DEFAULT_MAX_STATE_CHARS,
        language=language,
    )

    result = await client.evaluate(cfg, state, questions)
    status = result.get("status")
    if status != "ready":
        return {
            "ok": False,
            "emotion": "",
            "confidence": 0.0,
            "reason": status_reason(status),
            "status": status,
        }

    answers = result.get("answers") or {}
    answer = answers.get(QUESTION_NAME)
    picked = pick_emotion(
        answer,
        list(labels),
        threshold=cfg.get("min_confidence", DEFAULT_MIN_CONFIDENCE),
        mode=cfg.get("gate_mode") or GATE_MODE_THRESHOLD,
    )
    picked.update(
        {
            "prompt_version": PROMPT_VERSION,
            "language": language,
            "seconds": result.get("seconds"),
            "cache_hit": bool(result.get("cache_hit")),
        }
    )
    return picked
