"""插件用到的全部提示词。

放在 ``prompts/`` 而不是业务代码里：改词不动逻辑，审阅时也能一眼看清
模型被要求做什么。

- ``llm_emotion``  LLM 后端的情感分析提示词（输出 JSON）
- ``jev_emotion``  Jev 后端的 instructions + criteria（从固定选项里选一个）
"""

from . import jev_emotion, llm_emotion

__all__ = ["jev_emotion", "llm_emotion"]
