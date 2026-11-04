# 更新日志

## v2.1.0

上游仓库（Zhalslar/astrbot_plugin_emoji_like）已停止维护，本仓库为其续作分支。

### Added
- **自报家门**：请求网关时带上 `X-Jev-Gateway-Client` 头（插件名），
  网关据此在拓扑图里显示这个插件的调用次数、错误数与走的协议。
- **请求协议改成固定下拉**：协议只有 SystemOne / OpenAI Decisions / Custom 三项，
  网关里同一种协议可以登记多个入口，按优先级分层后由负载均衡策略挑选，插件这边
  不用再关心有几条上游。
- **Docker 适配**：容器内的 `127.0.0.1` 指向容器自己。网关地址支持写成
  `http://<令牌>@<网关容器名>:8770`，令牌自动作为 `X-Jev-Gateway-Token` 头发给网关；
  连不上时错误提示会直接说清怎么查（网关是否启用、端口是否一致、跨容器要绑
  `0.0.0.0` 并用容器名）。
- **Jev 接入收拢到网关**：判定请求的传输层搬到了
  [astrbot_plugin_jev_gateway](https://github.com/uuutt2023/astrbot_plugin_jev_gateway)——
  协议翻译（SystemOne ⇄ OpenAI Decisions）、重试、30 秒去重缓存、余额追踪都由网关负责。
  本插件的 Jev 设置只剩「网关代理地址」与「请求协议」两项，Key、地址、模型、超时
  都在网关那边配。传输层从 760 多行瘦到 200 行以内。
- **支持 Jev 决策网关**：新增「网关代理地址」与「请求协议」两项配置。填了代理
  地址后，请求会转给 `astrbot_plugin_jev_gateway` 由它按协议名中转到上游，插件
  自己就不用再填 Key 和地址了——换网关只改网关一处。代理地址留空时行为与以前
  完全一样（直连）。
  `core/jev_transport.py`（`resolve_proxy`）、`_conf_schema.json`。
- **支持 JevTypeSafeAI 第三方代理**：新增「端点路径」配置项，填 `/api/v1/decide`
  即可对接 `https://jevtypesafeai.com`——它的协议与 SystemOne 完全一致，只是路径带
  `/api` 前缀。另外补上 403（账户未激活）与 413（请求体过大）的状态映射，
  并读取第三方代理放在 `usage.credits_remaining_usd` 里的余额。
  `core/jev_transport.py`、`_conf_schema.json`、`scripts/probe_jev.py`（新增
  `--endpoint-path`）。
- **配置页文案精简**：Jev 配置组的每个选项改成一句话说明，不再重复解释同一件事
  （路径只由「接口协议」说、默认值不再在提示里重复、后端下拉去掉了与标签重复的副标题）。
  AngelHeart 的「Jev 决策」组描述从 1414 字压到 316 字，「回复节奏」「唤醒互动」两组
  同步收短，并去掉所有提示里冗余的「默认值：X」。`_conf_schema.json`。

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
