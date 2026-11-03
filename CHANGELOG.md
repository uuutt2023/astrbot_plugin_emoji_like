# 更新日志

## v2.1.0

上游仓库（Zhalslar/astrbot_plugin_emoji_like）已停止维护，本仓库为其续作分支。

### Added

- **接口协议可切换（SystemOne / OpenAI Decisions）**：新增配置项 `api_format`。
  `systemone`（默认）打 `POST {base_url}/v1/systemone`——官方 Jev / TypeSafe /
  StartLux 的 SystemOne 通道都走这个；`decisions` 打 `POST {base_url}/v1/decisions`
  ——OpenAI 新出的 Decisions 协议，部分中转站用的是这个端点。两者请求体结构不同
  （SystemOne 是 `state` + `questions` 映射，Decisions 是 `input` + `questions` 数组，
  是非题在 Decisions 里叫 `predicate`、候选项从 `criteria` 映射变成 `choices` 数组），
  插件在传输层自动双向翻译：**判定层一行都不用改**，内部始终是 SystemOne 的形状。
  老配置不填就是 systemone，行为不变。`core/jev_transport.py`、`_conf_schema.json`、
  `scripts/probe_jev.py`（新增 `--api-format`）、`tests/test_jev_api_formats.py`。

- **Jev 决策后端**：情感判断可以改用 [Jev](https://jevmodel.org/zh/docs/) 决策模型。
  情感分类本质是「从固定选项里选一个」，正好是决策模型擅长的类型化判断——
  不生成文字、只对输入 token 计费，比让 LLM 写一句 JSON 再解析更快也更便宜。
  - 配置项「情感判断的后端」新增三种取值：`llm`（默认，行为与原来完全一致）、
    `jev`（只用 Jev）、`hybrid`（Jev 先判，把握不足时回退 LLM）。
  - Jev 的候选选项直接取自「情感映射表」里配的情感标签：标签名就是选项名，
    选回来即可贴表情，不需要再做一层映射。
  - 新增「Jev 判断」配置分组：API Key、接口地址、模型名、超时、重试、
    置信度门控方式、采信阈值、发送文本长度上限、提示词语言。
  - 新增 `core/jev_transport.py`（传输层：本地预检、幂等键、错误码映射）
    与 `core/jev_emotion.py`（判定层：state 构造、选项映射、置信度门控）。
  - 新增 `prompts/` 目录：所有提示词集中放置（`llm_emotion.py` / `jev_emotion.py`），
    改文案不用翻业务代码。
  - 新增 `tests/`：50 条测试覆盖判定层纯逻辑与三种后端的分发/回落行为；
    新增 `scripts/eval_emotion.py`，可用真实 Jev API 离线评测判定准确率。

### Fixed

- **Jev 网关返回 500 时能看懂、能重试**：中转网关在「上游任务失败」时经常返回 500
  而不是 502，此前传输层把 500 当成不可重试的未知错误；现在 500 归入「上游故障」
  并参与重试。错误体解析同时支持 `{"error": "..."}` 字符串与顶层 `message`——
  此前只认 `{"error": {...}}` 对象，字符串形态的错误会被整条吞掉，日志里只剩
  「HTTP 500」，看不到上游真正说了什么。另附 `scripts/probe_jev.py`：网关连通性
  诊断脚本，按文档格式发两次最小请求并把结果翻译成结论。`core/jev_transport.py`、
  `scripts/probe_jev.py`。
- 插件卸载时关闭 Jev 客户端（`terminate()`），避免 aiohttp 会话泄漏。

### Changed

- LLM 后端的情感分析提示词原样搬到 `prompts/llm_emotion.py`，**文案逐字未改**，
  只是换了个地方放。

### 不变的东西

- 默认后端仍是 `llm`：不填任何新配置，行为与升级前完全一致。
- 情感映射表、贴表情概率、表情间隔、`/贴表情` 命令的用法都没动。
