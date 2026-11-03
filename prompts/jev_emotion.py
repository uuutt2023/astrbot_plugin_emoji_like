"""Jev 后端的情感分析提示词。

Jev 是**决策模型**：不生成文字，只从固定选项里选一个并给出概率分布。
所以这里的形态是 instructions（怎么判）+ criteria（有哪些选项）。

选项来自用户在「情感映射表」里配的标签——每个标签就是一个选项，
标签名直接当选项键，Jev 选回来就能直接拿去贴表情，不用再做一层映射。

约束（见 Jev 文档）：instructions ≤ 1800 字符，criteria 序列化后 ≤ 2000 字符。
"""

# 中文 instructions
INSTRUCTIONS_ZH = (
    "你是一个群聊表情反应插件的情感分析器。玩家发来一条消息，你要从给定的情感标签里"
    "挑一个最能概括这条消息主要情绪的标签。\n\n"
    "判定要求：\n"
    "1. 只从给定标签中选一个，不要输出标签以外的内容。\n"
    "2. 看的是「这条消息表达的情绪」，不是消息里谈论的那个人的情绪——"
    "例如「今天加班到十点」表达的是疲惫，不是开心。\n"
    "3. 语气、标点和用词都要算进去：「呵呵」多半是不悦或嘲讽，不是开心。\n"
    "4. 拿不准时选语义上最接近的那个标签；消息里读不出明显情绪时，"
    "选最中性或最接近日常的那个标签。\n"
    "5. 只根据给出的文本判断，不要臆测说话人的身份、经历或画面内容。"
)

# 英文 instructions
INSTRUCTIONS_EN = (
    "You are the emotion analyser of a chat reaction plugin. Given one message, "
    "pick the single emotion label that best captures its main emotional tone.\n\n"
    "How to decide:\n"
    "1. Choose exactly one of the given labels; never output anything else.\n"
    "2. Judge the emotion the message expresses, not the emotion of whoever it talks "
    "about - 'worked until ten tonight' expresses exhaustion, not happiness.\n"
    "3. Tone, punctuation and wording count: 'hehe' is more likely displeasure or "
    "sarcasm than happiness.\n"
    "4. When unsure, pick the semantically closest label; if the message carries no "
    "clear emotion, pick the most neutral one.\n"
    "5. Judge only from the given text; do not imagine the speaker's identity, "
    "background or what they can see."
)


def criteria_for(labels: list[str], language: str = "zh") -> dict[str, str]:
    """把用户的情感标签表变成 Jev 的 criteria。

    选项键就是标签本身，描述补一句「主要情绪是这个」——标签的具体含义
    模型自己就懂（开心、愤怒、无语……），不必逐条写说明。
    """
    if language == "en":
        return {
            label: f"The main emotion of the message is {label}." for label in labels
        }
    return {label: f"消息的主要情绪是「{label}」。" for label in labels}
