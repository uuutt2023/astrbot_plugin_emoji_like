import json
import re
from astrbot.api import logger
from astrbot.core.platform.astr_message_event import AstrMessageEvent

from ..prompts import llm_emotion as llm_prompts
from . import jev_emotion
from .config import PluginConfig
from .jev_transport import JevClient

# 后端标识
JUDGE_BACKEND_LLM = "llm"
JUDGE_BACKEND_JEV = "jev"
JUDGE_BACKEND_HYBRID = "hybrid"
JUDGE_BACKENDS = (JUDGE_BACKEND_LLM, JUDGE_BACKEND_JEV, JUDGE_BACKEND_HYBRID)


class EmotionJudger:
    def __init__(self, config: PluginConfig):
        self.cfg = config
        self.jev_client = JevClient()

    async def judge_emotion(
        self,
        event: AstrMessageEvent,
        *,
        text: str = "",
        image_urls: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> str | None:
        """
        判断消息情感并返回情感标签。

        按 ``judge_backend`` 分发：

        - ``llm``：走原来的 LLM 判断，行为与接入 Jev 之前完全一致；
        - ``jev``：走 Jev 决策模型（只计输入 token，不生成文字）；
        - ``hybrid``：Jev 先判，把握不足时再回退 LLM。

        对外行为约定：
        - 本方法 **不会抛出异常**，失败时返回 None
        - 若 event.extra 中已存在 emotion，则直接复用（避免重复调用）
        - 成功解析后会将 emotion 写入 event.extra，供后续流程复用

        :param event: AstrBot 消息事件
        :param text: 需要进行情感分析的文本
        :param image_urls: 可选的图片 URL（用于多模态模型）
        :param labels:
            - 指定可选的情感标签列表（如 ["开心", "愤怒", "悲伤"]）
            - 为空或 None 表示 **不限制情感标签**
        :return:
            - 成功时返回情感标签字符串
            - 失败时返回 None
        """
        if cached:= event.get_extra("emotion"):
            if (labels and cached in labels) or (not labels):
                logger.debug(f"复用情感标签: {cached}")
                return cached
        try:
            backend = self.cfg.judge_backend or JUDGE_BACKEND_LLM
            if backend in (JUDGE_BACKEND_JEV, JUDGE_BACKEND_HYBRID):
                emotion = await self._judge_via_jev(text, image_urls, labels)
                if emotion is not None:
                    logger.debug(f"情感分析结果(Jev): {emotion}")
                    event.set_extra("emotion", emotion)
                    return emotion
                if backend == JUDGE_BACKEND_JEV:
                    # 纯 Jev 模式不回落 LLM：拿不到判定就不贴，
                    # 由调用方随机贴一个表情（get_emoji_ids(None) 会走随机）。
                    return None

            provider = self.cfg.get_judge_provider(event.unified_msg_origin)
            system_prompt, prompt = self._build_prompt(text, labels)

            resp = await provider.text_chat(
                system_prompt=system_prompt,
                prompt=prompt,
                image_urls=image_urls,
            )

            emotion = self._parse_llm_response(resp.completion_text)
            logger.debug(f"情感分析结果: {emotion}")

            event.set_extra("emotion", emotion)
            return emotion

        except Exception as e:
            logger.exception(f"情感分析失败: {e}")
            return None

    async def _judge_via_jev(
        self,
        text: str,
        image_urls: list[str] | None,
        labels: list[str] | None,
    ) -> str | None:
        """用 Jev 判断情感；不可用时返回 None（调用方按后端策略处理）。"""
        cfg = self.cfg.jev_config
        if not cfg.get("enabled"):
            logger.info("Jev 情感判断未启用")
            return None
        try:
            result = await jev_emotion.judge_via_jev(
                self.jev_client,
                cfg,
                text,
                list(labels or []),
                has_image=bool(image_urls),
            )
        except Exception as e:
            logger.error(f"Jev 情感判断异常: {e}")
            return None

        if not result.get("ok"):
            logger.warning(
                f"Jev 未给出可用判定（{result.get('reason', '未知')}）"
            )
            return None
        logger.info(
            f"Jev 情感判定: {result.get('emotion')} "
            f"置信度 {result.get('confidence', 0.0):.3f} "
            f"提示词 {result.get('prompt_version', '')} "
            f"语言 {result.get('language', '')}"
        )
        return str(result.get("emotion") or "")

    async def close(self):
        """关闭 Jev 客户端（插件卸载时调用）。"""
        try:
            await self.jev_client.close()
        except Exception as e:
            logger.warning(f"关闭 Jev 客户端失败: {e}")

    # =========================
    # 内部方法
    # =========================

    def _build_prompt(
        self,
        text: str,
        labels: list[str] | None,
    ) -> tuple[str, str]:
        """构造情感分析提示词（文案在 prompts/llm_emotion.py）。"""
        return llm_prompts.build_emotion_prompt(text, labels)

    def _parse_llm_response(self, text: str) -> str:
        # 清理 markdown 代码块标记（支持单行和多行，兼容 \r\n 换行）
        text = text.strip()
        # 匹配 ```json ... ``` 或 ``` ... ```，支持单行和多行
        match = re.match(r"^```(?:\w*)\r?\n?(.*?)\r?\n?```$", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 返回非 JSON: {text}") from e

        emotion = data.get("emotion")
        if not emotion or not isinstance(emotion, str):
            raise ValueError(f"LLM JSON 缺少或非法 emotion 字段: {data}")

        return emotion
