"""pytest 公共装置。

原插件没有测试框架。为了能测「情感判断后端分发」这段接线逻辑，这里用最小
AstrBot 桩件把 main.py 导入进来——桩件只提供插件真正用到的那几个名字，
不追求还原框架行为。

运行：``pytest tests/ -v``（需要 pytest + pytest-asyncio；插件运行时本身不依赖它们）
"""

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── 最小 AstrBot 桩件 ──────────────────────────────────────────────────
def _install_astrbot_stub():
    if "astrbot" in sys.modules:
        return

    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    event = types.ModuleType("astrbot.api.event")
    star = types.ModuleType("astrbot.api.star")
    core = types.ModuleType("astrbot.core")
    core_config = types.ModuleType("astrbot.core.config")
    astrbot_config = types.ModuleType("astrbot.core.config.astrbot_config")
    core_message = types.ModuleType("astrbot.core.message")
    components = types.ModuleType("astrbot.core.message.components")
    core_platform = types.ModuleType("astrbot.core.platform")
    astr_message_event = types.ModuleType("astrbot.core.platform.astr_message_event")
    core_sources = types.ModuleType("astrbot.core.platform.sources")
    aiocqhttp = types.ModuleType("astrbot.core.platform.sources.aiocqhttp")
    aiocqhttp_event = types.ModuleType(
        "astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event"
    )
    core_provider = types.ModuleType("astrbot.core.provider")
    provider_mod = types.ModuleType("astrbot.core.provider.provider")
    core_star = types.ModuleType("astrbot.core.star")
    star_context = types.ModuleType("astrbot.core.star.context")
    star_tools = types.ModuleType("astrbot.core.star.star_tools")
    core_utils = types.ModuleType("astrbot.core.utils")
    astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")

    class _Any:
        """万能占位：支持属性访问与调用（调用返回装饰器）。"""

        def __getattr__(self, name):
            return _Any()

        def __call__(self, *args, **kwargs):
            def deco(func):
                return func

            if len(args) == 1 and not kwargs and callable(args[0]):
                return args[0]
            return deco

    class _Filter:
        EventMessageType = _Any()

        def command(self, *args, **kwargs):
            def deco(func):
                func.__filter_cmd__ = True
                return func

            if len(args) == 1 and not kwargs and callable(args[0]):
                return args[0]
            return deco

        def event_message_type(self, *args, **kwargs):
            def deco(func):
                return func

            if len(args) == 1 and not kwargs and callable(args[0]):
                return args[0]
            return deco

        def __getattr__(self, name):
            return _Any()

    class AstrMessageEvent:
        def __init__(self, **kwargs):
            self._extra = {}
            self.unified_msg_origin = kwargs.get("unified_msg_origin", "test@Group")

        def get_extra(self, key):
            return self._extra.get(key)

        def set_extra(self, key, value):
            self._extra[key] = value

    class MessageEventResult:
        pass

    class Context:
        pass

    class Star:
        def __init__(self, context=None, *args, **kwargs):
            self.context = context

    class StarTools:
        @staticmethod
        def get_data_dir(name=None):
            path = Path("/tmp/emoji_like_test_data")
            path.mkdir(parents=True, exist_ok=True)
            return path

    class AstrBotConfig:
        """够用的配置替身：dict 行为 + 一个 save_config。"""

        def __init__(self, data=None):
            self._data = dict(data or {})

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def __contains__(self, key):
            return key in self._data

        def get(self, key, default=None):
            return self._data.get(key, default)

        def save_config(self):
            pass

    class Provider:
        pass

    class Face:
        pass

    class Image:
        pass

    class Reply:
        pass

    class AiocqhttpMessageEvent(AstrMessageEvent):
        pass

    def get_astrbot_plugin_path():
        return "/tmp/emoji_like_test_plugins"

    api.logger = _Any()
    event.filter = _Filter()
    event.AstrMessageEvent = AstrMessageEvent
    event.MessageEventResult = MessageEventResult
    star.Context = Context
    star.Star = Star
    astrbot_config.AstrBotConfig = AstrBotConfig
    components.Face = Face
    components.Image = Image
    components.Reply = Reply
    astr_message_event.AstrMessageEvent = AstrMessageEvent
    aiocqhttp_event.AiocqhttpMessageEvent = AiocqhttpMessageEvent
    provider_mod.Provider = Provider
    star_context.Context = Context
    star_tools.StarTools = StarTools
    astrbot_path.get_astrbot_plugin_path = get_astrbot_plugin_path

    astrbot.api = api
    astrbot.core = core
    api.event = event
    api.star = star
    core.config = core_config
    core_config.astrbot_config = astrbot_config
    core.message = core_message
    core_message.components = components
    core.platform = core_platform
    core_platform.astr_message_event = astr_message_event
    core_platform.sources = core_sources
    core_sources.aiocqhttp = aiocqhttp
    aiocqhttp.aiocqhttp_message_event = aiocqhttp_event
    core.provider = core_provider
    core_provider.provider = provider_mod
    core.star = core_star
    core_star.context = star_context
    core_star.star_tools = star_tools
    core.utils = core_utils
    core_utils.astrbot_path = astrbot_path

    for name, module in {
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
        "astrbot.core": core,
        "astrbot.core.config": core_config,
        "astrbot.core.config.astrbot_config": astrbot_config,
        "astrbot.core.message": core_message,
        "astrbot.core.message.components": components,
        "astrbot.core.platform": core_platform,
        "astrbot.core.platform.astr_message_event": astr_message_event,
        "astrbot.core.platform.sources": core_sources,
        "astrbot.core.platform.sources.aiocqhttp": aiocqhttp,
        "astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event": aiocqhttp_event,
        "astrbot.core.provider": core_provider,
        "astrbot.core.provider.provider": provider_mod,
        "astrbot.core.star": core_star,
        "astrbot.core.star.context": star_context,
        "astrbot.core.star.star_tools": star_tools,
        "astrbot.core.utils": core_utils,
        "astrbot.core.utils.astrbot_path": astrbot_path,
    }.items():
        sys.modules[name] = module


_install_astrbot_stub()

# 插件以包方式导入：把仓库根目录的父目录放进 sys.path，
# 让 `astrbot_plugin_emoji_like.main` 成为一个可导入的包。
_PARENT = str(ROOT.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

PLUGIN_PKG = ROOT.name


@pytest.fixture(scope="session")
def plugin_module():
    """导入 main.py（此时 astrbot 已被桩件顶替）。"""
    import importlib

    return importlib.import_module(f"{PLUGIN_PKG}.main")


@pytest.fixture
def make_judger(plugin_module):
    """造一个带假 provider 的判定器。"""

    def _make(config=None, llm_text='{"emotion": "开心"}', jev_answer=None):
        from astrbot.core.config.astrbot_config import AstrBotConfig
        from astrbot.core.provider.provider import Provider

        calls = []

        class FakeResponse:
            def __init__(self, text):
                self.completion_text = text

        class FakeProvider(Provider):
            async def text_chat(self, prompt=None, system_prompt=None, image_urls=None,
                                **kwargs):
                calls.append({"prompt": prompt, "system_prompt": system_prompt})
                return FakeResponse(llm_text)

        class FakeContext:
            def get_using_provider(self, umo=None):
                return FakeProvider()

            def get_provider_by_id(self, provider_id):
                return FakeProvider()

        cfg_data = {
            "emoji_follow_prob": 0.3,
            "emoji_like_prob": 0.03,
            "judge_provider_id": "",
            "emoji_interval": 0.4,
            "emotions_mapping_list": ["开心：1 2 3", "愤怒：4 5"],
        }
        cfg_data.update(config or {})

        judger = plugin_module.EmotionJudger(
            plugin_module.PluginConfig(AstrBotConfig(cfg_data), FakeContext())
        )
        judger._test_provider_calls = calls

        if jev_answer is not None:
            async def fake_evaluate(cfg, state, questions, idem=None):
                judger._test_jev_calls = getattr(judger, "_test_jev_calls", [])
                judger._test_jev_calls.append(
                    {"cfg": cfg, "state": state, "questions": questions}
                )
                return {"status": "ready", "answers": {"emotion": jev_answer}}

            judger.jev_client.evaluate = fake_evaluate

        return judger

    return _make
