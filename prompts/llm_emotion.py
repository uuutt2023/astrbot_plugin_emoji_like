"""LLM 后端的情感分析提示词。

从 ``core/emotion.py`` 原样搬出——逐字未改，只是换了个地方放。
"""


def build_emotion_prompt(text: str, labels: list[str] | None) -> tuple[str, str]:
    """构造 (系统提示词, 用户提示词)。

    ``labels`` 为空表示不限制情感标签，由模型自己给一个。
    """
    if labels:
        label_hint = f"只能从以下情感标签中选择一个：{labels}\n"
    else:
        label_hint = (
            "不限制情感标签，请自行判断文本的主要情感。\n"
            "情感应为简短、常见、可概括的情感词\n"
        )

    system_prompt = (
        "你是一个情感分析专家。\n"
        f"{label_hint}"
        "请严格按照 JSON 格式输出，不要包含任何多余内容。\n"
        '输出示例：{"emotion": "开心"}'
    )

    prompt = f"文本内容：{text}"
    return system_prompt, prompt
