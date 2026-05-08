# Kronos Project Status

> 更新时间：2026-05-07 | 当前版本：0.4.5 | 下一版本：0.4.6

## 一句话判断

v0.4.5 没有扩展实盘能力，而是把结果卡往前推成解释卡：`quickstart` 和 `report latest` 先给结果卡，`report replay` / `report regime` / `report observation` 再把关键交易、市场状态分段和只读观察边界接出来；策略起草后的验证链路也继续翻译成检查配置、空跑确认、进入候选池。

v0.4.4 把 Docker 首次体验语义收口成结果卡，`quickstart` 和 `report latest` 先给结果卡，说明用了什么数据、评估了什么、结论能不能信、下一步做什么；策略起草后的验证链路也先翻译成检查配置、空跑确认、进入候选池。

v0.4.2 已经把 v0.4.1 多画像 Docker 评测暴露的首次体验信任断点收口：Agent 不再输出错误事实，`report latest` 第一屏能说明数据、策略、结论和下一步，7 天 sample 数据不再被包装成 90 天复验，Docker 路径和日志噪音也已修正。

2026-05-07 的新一轮 Docker 全新 clone 评测确认：`report latest` 和 `strategy draft` 已经把交易者主线接起来，`agent start` 也能把“我有一个策略想法”导向同一条草案链路；v0.4.5 在此基础上把解释路径和只读观察入口补齐。

当前产品边界仍是**研究报告、Agent 复盘、策略草案和策略配置试算**。Kronos 不会启动实时模拟盘、不会接入真实交易、不会自动下单。

## v0.4.5 立项方向

v0.4.5 不再扩展新的研究入口，而是把 v0.4.4 的结果卡往前推一层：用户能从最新报告跳到关键交易重放，按市场状态看差异，并在只读观察前先看清虚拟订单、延迟、滑点和人工闸门。

当前已立项的开发指引见 `docs/RELEASE_0.4.5_RESEARCH_INTERPRETABILITY.md` 和 `openspec/changes/p4-research-interpretation-path/`。

## 当前能力

| 模块 | 状态 | 当前用户能得到什么 |
|---|---|---|
| 快速开始 | 已完成 | `kronos quickstart` 一键生成数据、注册 R-breaker、输出研究报告 |
| 最新报告 | 已完成 | `kronos report latest` 直接打印最近一次产品报告摘要，自动研究报告优先展示数据来源、样本范围、评估对象、结论、可信度和下一步；关键交易重放可用 `kronos report replay` 查看，市场状态分段可用 `kronos report regime` 查看，只读观察边界可用 `kronos report observation` 查看 |
| 内置策略 | 已完成 | R-breaker 日内突破作为示例策略，quickstart 后可被 Agent 看到 |
| 策略起草 | 已完成 | `kronos strategy draft --prompt "..."` 将 R-breaker 相关想法转成概要、trace 和 TOML 草案；缺字段会澄清，不支持模板会拒绝 |
| 策略配置 | 已完成 | `kronos strategy init-r-breaker` 生成 TOML，`validate` 校验，`smoke-test` 本地试算 |
| 策略注册 | 已完成 | `kronos strategy register` 默认要求烟雾测试通过，再写入候选池 |
| 报告解释 | 已完成 | 技术指标保留，同时补充交易语言解释和模拟盘边界 |
| 数据同步 | 已完成 | Binance USDM 公开 K 线 / Funding / OI，同步前说明来源、范围和无需 API Key |
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
| 实时模拟盘 | v0.4.x 目标 | 当前不会连接实时虚拟订单引擎 |
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
| P1 | quickstart/Agent 使用 1m，TOML 默认 15m，用户难以确认自己验证的是哪套 R-breaker | 已修复：CLI 输出明确 quickstart 是 1m sample 试跑，TOML 是可编辑策略配置 |
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

## 当前推荐顺序

1. 继续推进 v0.4.6：关键交易解释继续深化，补足更细的失败窗口和样本外分析。
2. 保持市场状态分段和只读观察边界的入口稳定，继续打磨文案和门禁。
3. 模拟盘前先定义只读 API Key、虚拟订单、延迟/滑点、人工闸门和报告入口。
4. 在没有稳定模拟盘证据前，不推进真实交易执行。

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
- 策略系统设计：`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`
- 审查与修复方案：`docs/reviews/`
- v0.4.3 版本需求：`docs/RELEASE_0.4.3_STRATEGY_AUTHORING.md`
- v0.4.3 OpenSpec：`openspec/changes/p4-strategy-authoring/`
