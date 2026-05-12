# Kronos Project Status

> 更新时间：2026-05-11 | 当前版本：0.4.10 | 下一版本：0.4.11

## 一句话判断

v0.4.8 在只读观察计划之后，新增 Binance 模拟盘 / 测试网模拟盘最小闭环：用户可以配置 Binance testnet API Key / Secret，运行 `paper preflight`，再用 `paper start/status/stop` 验证测试网订单链路。自动化验证默认用 mock testnet 适配器，不会碰真实网络。

v0.4.6 把 fresh Docker 新用户体验继续压短，并修复 Dockerfile 禁用 `uv` 缓存导致的慢构建问题。v0.4.5 则把结果卡往前推成解释卡：`quickstart` 和 `report latest` 先给结果卡，`report replay` / `report regime` / `report observation` 再把关键交易、市场状态分段和只读观察边界接出来。

v0.4.4 把 Docker 首次体验语义收口成结果卡，`quickstart` 和 `report latest` 先给结果卡，说明用了什么数据、评估了什么、结论能不能信、下一步做什么；策略起草后的验证链路也先翻译成检查配置、空跑确认、进入候选池。

v0.4.2 已经把 v0.4.1 多画像 Docker 评测暴露的首次体验信任断点收口：Agent 不再输出错误事实，`report latest` 第一屏能说明数据、策略、结论和下一步，7 天 sample 数据不再被包装成 90 天复验，Docker 路径和日志噪音也已修正。

2026-05-08 的 fresh Docker 模拟用户测试确认：`report latest` 已经是稳定结果卡，`strategy draft`、`report regime` 和 `report observation` 也把解释链路补齐；`agent start` 能把无数据用户带到 sample 数据和策略草案，但首次入口对完全小白仍偏长。最新复测还确认：`quickstart` 的结果卡已经干净，`report replay` 的缺内容提示清楚，`agent start` 能在 fresh Docker 中接住数据与策略池。首次构建慢的直接根因已定位为 Dockerfile 禁用 `uv` 缓存；去掉 `--no-cache` 后，fresh build 的依赖准备从 15m49s 回到约 12s。

当前产品边界是**研究报告、Agent 复盘、策略草案、策略配置试算、只读观察计划和 Binance testnet 模拟盘最小闭环**。Kronos v0.4.8 只允许测试网模拟盘，不允许主网实盘，不触碰真实资金。

v0.4.9 已完成 **测试网证据与 Web 状态可见性**：保留真实 testnet E2E 的安全闸门，并让 Web 工作台只读展示 paper 状态、最近订单、成交 / 错误和报告入口。testnet 凭证已写入本机 ignored SecretStore；系统用真实 90.14 天数据生成 `promoted=1` 的观察候选，通过 preflight，并完成一笔 Binance testnet ETHUSDT BUY 0.01 订单，order id `8693595272`，状态 `FILLED`。验收记录见 `docs/TESTNET_E2E_ACCEPTANCE_20260509.md`；多画像模拟用户验收见 `docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md`。

v0.4.10 已完成 **Agent 记忆与交接控制台**：把当前开发侧持久化 Agent Harness 产品化，让 Web 工作台展示当前状态、最近决策、失败教训、下一步、一键交接包和记忆漂移检查。控制台首版只读优先，所有摘要带来源文件，检查结果不自动覆盖长期记忆。验收记录见 `docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md`。

## v0.4.8 交付方向

v0.4.8 不是继续做本地虚拟成交，而是进入 **Binance 模拟盘 / 测试网真实成交**：执行层只允许 Binance testnet endpoint，CLI 提供 credentials、preflight、start、status、stop，报告会记录 testnet order id 和测试网成交证据。

当前已立项的开发指引见 `docs/RELEASE_0.4.8_TESTNET_PAPER_TRADING.md` 和 `openspec/changes/p4-testnet-paper-trading/`。

## 当前能力

| 模块 | 状态 | 当前用户能得到什么 |
|---|---|---|
| 快速开始 | 已完成 | `kronos quickstart` 一键生成数据、注册 R-breaker、输出研究报告 |
| 最新报告 | 已完成 | `kronos report latest` 直接打印最近一次产品报告摘要，自动研究报告优先展示数据来源、样本范围、评估对象、结论、可信度和下一步；关键交易重放可用 `kronos report replay` 查看，市场状态分段可用 `kronos report regime` 查看，只读观察边界可用 `kronos report observation` 查看，只读观察计划可用 `kronos report observation-plan` 生成 |
| 内置策略 | 已完成 | R-breaker 日内突破策略作为示例策略，quickstart 后可被 Agent 看到 |
| 策略起草 | 已完成 | `kronos strategy draft --prompt "..."` 将 R-breaker 相关想法转成概要、trace 和 TOML 草案；缺字段会澄清，不支持模板会拒绝 |
| 策略配置 | 已完成 | `kronos strategy init-r-breaker` 生成 TOML，`validate` 校验，`smoke-test` 本地试算 |
| 策略注册 | 已完成 | `kronos strategy register` 默认要求烟雾测试通过，再写入候选池 |
| 报告解释 | 已完成 | 技术指标保留，同时补充交易语言解释、模拟盘边界和只读观察计划 |
| 数据同步 | 已完成 | Binance USDM 公开 K 线 / Funding / OI，同步前说明来源、范围和无需 API Key |
| 测试网模拟盘 | 已完成首版 | `kronos paper credentials/preflight/start/status/stop` 可配置测试网凭证、做 preflight、用 mock testnet 验证订单链路并生成报告 |
| 测试网 Web 状态 | 已完成 | Web 展示 paper 状态、最近订单、成交 / 错误和报告入口；真实 testnet E2E 已通过，仍必须保留凭证、候选、观察计划和 preflight 闸门 |
| Agent 记忆控制台 | 已完成 | Web 已展示当前状态、决策、教训、交接包和记忆漂移检查；首版只读优先，不自动覆盖长期记忆 |
| 对话 Agent | 已完成 | `kronos agent start` 可做首次用户引导、策略起草、环境感知和中英文对话，并按当前数据样本动态说明结论边界 |
| Web 工作台 | 已完成 | FastAPI + Next.js，本地查看候选池、时间线、报告、设置和审批入口 |
| Docker | 已完成 | `docker compose up` 可跑通 quickstart 主路径；策略路径提示使用容器内 `/root/.kronos/...`，默认首屏隐藏工程调试日志 |

## 当前目标用户

Kronos 不应默认面向完全小白。当前主用户是两类人：

- 有经验的主观/半自动交易者：已经有交易想法，需要判断它是否值得继续观察。
- 会 Python/pandas 的交易研究者：能读懂指标和代码，但不想反复搭数据、验证和实验管理底座。

小白用户仍然重要，但主要用于检验 onboarding、Docker、错误提示和报告阅读是否足够清楚。完整画像见 `docs/USER_PERSONAS.md`。

## 当前不具备的能力

| 能力 | 当前状态 | 产品边界 |
|---|---|---|
| AI 自然语言创建策略 | 已交付首版 | 当前只支持 R-breaker 相关想法起草成 TOML；不能把任意自然语言自动变成新策略代码 |
| 历史重放 | 已完成起步 | 当前提供关键交易重放报告，不做逐笔/逐分钟交易回放 |
| 市场状态分段评估 | 已完成起步 | 当前可用 `kronos report regime` 查看市场状态切片，不把整体均值当作全部答案 |
| 只读观察计划 | 已完成 | 当前可以从研究报告生成观察计划，但不会启动实时模拟盘 |
| Binance 模拟盘真实成交 | 已完成首版 | 当前支持测试网凭证、preflight、mock testnet 订单链路、status/stop 和模拟盘报告；真实 testnet 下单需用户显式配置凭证 |
| 实盘执行 | v0.5.0+ 以后 | 必须等研究闭环、模拟盘和人工闸门稳定后再考虑 |

## v0.4.0 前置修复

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P0 | 测试流程可能触碰真实候选池 | 已修复：测试使用临时 `KRONOS_CANDIDATES_PATH` |
| P0 | 项目状态文档旧版本口径误导路线 | 已修复：本文重写为 v0.3.4 当前事实 |
| P0 | 主产品设计文档混淆当前能力和未来能力 | 已修复：拆分 current / target / deferred |
| P1 | `report latest` 需要稳定“最新”语义 | 已修复：优先结构化 run 时间，mtime 仅作 fallback |
| P1 | Web 模型配置 provider 边界需收紧 | 已修复：写入和状态读取统一只接受当前支持的 DeepSeek |

## v0.4.2 体验修复结论

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P0 | Agent 文案出现 `{n}` 未替换、7 天样本误写 90 天、1 个策略误写 12 个旧策略 | 已修复：数量、样本天数、synthetic 边界和研究下一步全部从当前 run context 生成 |
| P0 | `report latest` 只给内部流程摘要，不能形成交易用户第一屏判断 | 已修复：自动研究报告第一屏展示数据类型、样本天数、策略数量、验证结果和下一步 |
| P0 | 自动研究报告中 7 天样本与“90 天复验已完成”冲突 | 已修复：只有实际覆盖不少于 90 天才允许使用 90 天复验表达 |
| P1 | Docker 用户容易混用宿主机 `~/.kronos` 和容器 `/root/.kronos` 路径 | 已修复：Docker 命令速查和策略 init 输出容器内路径，误传宿主机路径时给出提示 |
| P1 | quickstart/Agent 使用 1m，TOML 默认 15m，用户难以确认自己验证的是哪套 R-breaker 策略 | 已修复：CLI 输出明确 quickstart 是 1m sample 试跑，TOML 是可编辑策略配置 |
| P1 | quickstart / agent start 首屏出现工程日志 | 已修复：dev 配置默认日志级别降为 `WARNING` |

## v0.4.3 策略起草结论

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P0 | 用户有策略想法时仍要先懂 TOML 或 Python 入口 | 已修复：`strategy draft` 和 Agent console 都能把 R-breaker 想法起草成概要、trace 和 TOML |
| P0 | 自然语言入口容易伪装成“任何策略都能生成” | 已修复：只允许命中当前支持模板；均线、RSI、网格、套利等不支持模板会明确拒绝 |
| P1 | 缺少品种或周期时容易被系统静默补默认值 | 已修复：返回“需要澄清”，列出未确定项和下一步 |
| P1 | Docker 用户需要可复制的下一步命令 | 已修复：Docker 环境输出 `docker compose run --rm kronos uv run kronos strategy ...` 链路 |

## v0.4.4 首次体验语义收口

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P0 | Docker 首次运行后仍需要用户从多段输出里自行拼出结果边界和下一步 | 已修复：`quickstart` 和 `report latest` 共用结果卡，固定展示数据来源、样本范围、评估对象、结论、可信度、下一步 |
| P1 | 策略起草成功后直接暴露 `validate / smoke-test / register`，交易者理解成本偏高 | 已修复：对外先写检查配置、空跑确认、进入候选池，再保留可复制命令 |
| P1 | Agent 首屏仍偏菜单，不够像研究助手 | 已修复：首屏先说明会判断结果能不能信并给下一步，再进入选项 |
| P2 | Docker 首次构建输出容易被误读成异常 | 已修复：entrypoint 先说明首次运行会准备环境和生成 sample 流程试跑报告，完成后只强调先读最新报告 |
| P2 | Docker fresh build 依赖下载被反复放大 | 已修复：Dockerfile 去掉 `uv sync --no-cache`，fresh build 复测依赖准备约 12s |

## v0.4.7 只读观察计划

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P0 | 用户读完研究报告后仍不知道能否进入观察 | 已修复：`kronos report observation-plan` 从报告生成只读观察计划 |
| P0 | sample / 短样本容易被误解成可观察结论 | 已修复：观察计划按 sample、短样本、未通过、已通过分层给出准入判断 |
| P1 | 模拟盘前的虚拟订单、延迟、滑点和人工闸门没有落成产物 | 已修复：计划正文固定记录这些假设，并声明不会发送真实订单 |

## v0.4.8 Binance 测试网模拟盘

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P0 | 只读观察计划之后缺少下单链路验证 | 已修复：新增 `kronos paper start --mock-testnet` 验证 testnet 订单链路 |
| P0 | 模拟盘可能误连主网或泄漏密钥 | 已修复：执行层只允许 Binance testnet endpoint；SecretStore 状态和报告脱敏；凭证移除 argv secret，支持环境变量和隐藏输入 |
| P0 | 停止后可能误重启 | 已修复：`paper stop` 后再次启动必须显式 `--reset-stopped` |
| P1 | 用户缺少启动前安全检查 | 已修复：新增 `kronos paper preflight`，检查观察计划 metadata、来源报告 hash、凭证和 testnet 连接 |
| P1 | 用户缺少停止和复盘入口 | 已修复：新增 `paper status/stop`、订单 / 成交 / 错误 ledger 和 Markdown 报告 |

## v0.4.9 测试网证据与 Web 状态可见性

| 优先级 | 问题 | 规划处理 |
|---|---|---|
| P0 | 真实 testnet E2E 还没有成功证据 | `done`：已完成 `20260509T134805Z-paper`，记录 order id、trade id、成交价、手续费和报告 |
| P0 | 2026-05-09 初始验收被阻止，但原因需要成为版本约束 | `done`：凭证、候选、观察计划、preflight 闸门保留；初始阻塞和后续成功验收均已落档 |
| P1 | Web 还看不到测试网模拟盘状态 | `done`：新增 Web paper status/report API 和状态面板 |
| P1 | 用户需要看到最近订单、成交、错误和报告入口 | `done`：Web 展示最近订单、成交 / 错误和 Markdown 报告入口 |
| P1 | Web 展示可能被误解成实盘控制台 | `done`：Web 只读优先，标记 testnet，不提供 mainnet/live 切换或绕过 preflight 的启动按钮 |
| P1 | 需要按模拟用户流程复核成功、空状态、无凭证和负责人 review | `done`：2026-05-11 多画像验收通过；暴露的版本自证入口已补 `kronos --version` |
| P1 | Web 看板第一眼不够聚焦 v0.4.9 testnet 验收对象 | `done`：测试网模拟盘面板已提升到今日看板内容区最前面，桌面首屏可见，390px 移动首屏露出核心模块和边界文案 |

## v0.4.10 Agent 记忆与交接控制台（已完成）

| 优先级 | 问题 | 规划处理 |
|---|---|---|
| P1 | 新 agent / 新会话容易混淆旧 Agent MVP 结论和当前产品边界 | `done`：Web 展示当前状态、版本边界、最高优先级和来源文件 |
| P1 | v0.4.9 验收暴露首屏验收对象不够直观 | `done`：v0.4.10 首屏展示当前版本、当前验收对象、最新成功运行 / 验收记录、来源文档和建议下一步 |
| P1 | 决策、失败教训、拒绝方案分散在多份文档中 | `done`：Web 汇总最近决策、经验教训和被拒绝方案，并保留来源引用 |
| P1 | 接手提示词依赖人工临场整理 | `done`：生成一键交接包，包含项目路径、必读文件、当前待办、禁止事项和建议第一步 |
| P1 | 记忆文件和项目状态文档可能漂移 | `done`：增加记忆漂移检查，识别版本冲突、缺索引、必备段落缺失和疑似 secret |
| P1 | 长期记忆可能被模型自动污染 | `done`：首版只读优先，只给建议，不自动覆盖 `MEMORY.md` 或 `DECISIONS.md` |

## 当前推荐顺序

1. 对 v0.4.10 Agent 记忆控制台做产品 review，确认首屏、交接包和漂移检查是否符合用户预期。
2. 规划 v0.4.11：把 Agent 失败记忆约束接入候选生成和研究决策，避免重复提出已失败方向。
3. 主网实盘执行仍不推进；testnet 成交只证明链路，不证明策略可实盘。

## 版本事实源

- 版本号：`VERSION`、`pyproject.toml`、README badge、`CHANGELOG.md`
- 当前待办：`TODO.md`
- 产品边界：`README.md` / `README.en.md`
- 用户画像：`docs/USER_PERSONAS.md`
- Docker 多画像体验评测：`docs/DOCKER_PERSONA_UX_EVALUATION_20260506.md`
- Docker 多画像体验评测（2026-05-07）：`docs/DOCKER_PERSONA_UX_EVALUATION_20260507.md`
- Docker 体验根因修复方案：`docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260506.md`
- Docker 体验语义收口方案：`docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260507.md`
- v0.4.4 OpenSpec：`openspec/changes/p4-docker-first-use-result-card/`
- v0.4.5 版本需求：`docs/RELEASE_0.4.5_RESEARCH_INTERPRETABILITY.md`
- v0.4.5 OpenSpec：`openspec/changes/p4-research-interpretation-path/`
- v0.4.7 版本需求：`docs/RELEASE_0.4.7_PAPER_OBSERVATION_PLAN.md`
- v0.4.7 OpenSpec：`openspec/changes/p4-paper-observation-plan/`
- v0.4.8 版本需求：`docs/RELEASE_0.4.8_TESTNET_PAPER_TRADING.md`
- v0.4.8 OpenSpec：`openspec/changes/p4-testnet-paper-trading/`
- v0.4.9 版本需求：`docs/RELEASE_0.4.9_TESTNET_WEB_STATUS.md`
- v0.4.9 OpenSpec：`openspec/changes/p4-testnet-web-status/`
- v0.4.9 testnet E2E 阻塞记录：`docs/TESTNET_E2E_ATTEMPT_20260509.md`
- v0.4.9 testnet E2E 通过记录：`docs/TESTNET_E2E_ACCEPTANCE_20260509.md`
- v0.4.9 多画像模拟用户验收：`docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md`
- v0.4.9 Web paper API：`kronos/web/routes/paper.py`
- v0.4.9 Web paper 面板：`web/components/paper-status-panel.tsx`
- v0.4.10 版本需求：`docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md`
- v0.4.10 OpenSpec：`openspec/changes/p4-agent-memory-control/`
- v0.4.10 多画像模拟用户验收：`docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md`
- 策略系统设计：`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`
- 审查与修复方案：`docs/reviews/`
- v0.4.3 版本需求：`docs/RELEASE_0.4.3_STRATEGY_AUTHORING.md`
- v0.4.3 OpenSpec：`openspec/changes/p4-strategy-authoring/`
