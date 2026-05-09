# Changelog

All notable changes to Kronos will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- v0.4.8 将推进 Binance 模拟盘 / 测试网真实成交：允许测试网 API Key、测试网真实订单和测试网成交，但禁止主网和真实资金
- 新增 v0.4.8 版本需求和 OpenSpec 约束，先把产品边界写清楚再进入代码实现

## [0.4.7] — 2026-05-09

### Added

- **只读观察计划**：新增 `kronos report observation-plan`，可从最新研究报告或指定报告生成 `paper_observation_plan.md`
- **v0.4.7 版本需求 + OpenSpec**：新增 `docs/RELEASE_0.4.7_PAPER_OBSERVATION_PLAN.md` 和 `openspec/changes/p4-paper-observation-plan/`，把模拟盘前的观察计划边界写成正式约束
- 观察计划生成器会记录来源报告、观察对象、样本范围、准入判断、虚拟订单假设、延迟/滑点假设和人工闸门

### Changed

- README / README.en / PROJECT_STATUS / ROADMAP / TODO 同步到 v0.4.7：当前新增的是只读观察计划，不是实时模拟盘

### Fixed

- 修正项目状态和 TODO 标题滞后问题，版本口径从 v0.4.5 / v0.4.6 对齐到 v0.4.7

## [0.4.6] — 2026-05-08

### Added

- **Docker 模拟用户测试与修复方案**：新增 2026-05-08 fresh Docker 多画像测试记录和根因修复方案，按用户看到的问题、根因、产品逻辑、验收证据落档
- Dockerfile 回归测试，防止 `uv sync --no-cache` 重新引入导致 fresh build 依赖准备被放大

### Changed

- `quickstart` 首次输出继续压缩为更短的结果卡和阶段提示，减少 entrypoint 末尾重复收尾
- `agent start` 的 sample 数据语义更直接：先判断当前结果能不能信，再给最短下一步
- `report latest` 结果卡压缩数据来源、市场状态和只读边界表达，让新用户更快判断“这是试跑还是结论”
- `report replay` / `report observation` 缺内容时改为产品化下一步提示，不再只像工具报错
- 项目状态、路线图和 TODO 同步到 v0.4.6 fresh Docker 复测结论

### Fixed

- Docker fresh build 不再因 `uv sync --no-cache` 禁用依赖缓存而把首次依赖准备放大到 15 分钟级；修复后复测依赖准备约 12 秒

## [0.4.5] — 2026-05-07

### Added

- `kronos report replay`、`kronos report regime`、`kronos report observation` 三个只读下钻入口
- 关键交易重放、市场状态分段、只读观察边界和逐 symbol smoke-test 的 0.4.5 版本需求与 OpenSpec
- 多品种 smoke-test 逐 symbol 结果输出，不再只验证首个品种

### Changed

- `report latest` 的产品边界继续往下钻：重放、市场状态分段和只读观察入口从产品报告中显式可读
- 项目状态、路线图、TODO 和主设计文档同步到 v0.4.5 解释路径边界

### Fixed

- 用户不再需要从研究工作台或报告文件里猜测“市场状态分段”和“只读观察边界”在哪读
- 多品种策略不会只因第一个品种通过就误导成整体通过

## [0.4.4] — 2026-05-07

### Added

- **Docker 首次体验修复方案 + OpenSpec**：新增 `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260507.md` 和 `openspec/changes/p4-docker-first-use-result-card/`，把 v0.4.3 fresh clone 评测暴露的问题按用户看到的问题、根因、产品逻辑和验收标准落档
- `quickstart` 自动研究完成后直接打印与 `report latest` 一致的结果卡，让用户先看到数据来源、样本范围、评估对象、结论、可信度和下一步
- Agent 首屏新增助手定位文案，先说明“判断结果能不能信，再给下一步”，再进入菜单选择

### Changed

- `kronos report latest` 的第一屏改成固定结果卡结构，并把 sample 数据明确标为“流程试跑，不代表策略有效性”
- `strategy draft` 和 Agent 策略起草分支把 `validate / smoke-test / register` 翻译成交易者语言：检查配置、空跑确认、进入候选池
- Docker entrypoint 和 quickstart 下一步提示收敛为“先读最新报告”，再按需要起草策略、同步真实数据或进入 Agent
- README / README.en / PROJECT_STATUS / TODO / ROADMAP / 策略系统设计文档同步到 v0.4.4 当前边界

### Fixed

- Docker 新用户首次运行后不再需要从多段输出里自行拼接“这次跑了什么、能不能信、下一步做什么”
- 策略起草成功后的下一步不再只暴露内部命令标签，降低非工程用户理解 `validate / smoke-test / register` 的门槛

## [0.4.3] — 2026-05-07

### Added

- **自然语言策略起草**：新增 `kronos strategy draft --prompt "..."`，把 R-breaker 日内突破相关想法转成策略概要、trace 记录和可编辑 TOML 草案
- Agent console 新增“描述策略想法，先起草配置”分支；策略池为空时不再引导用户写 Python 注册代码，而是先走草案 → 校验 → 烟雾测试 → 注册链路
- 策略起草产物记录 prompt version、解析来源、模板命中、默认假设、澄清问题、输出路径和下一步命令
- **Docker 首次体验再评测**：新增 2026-05-07 的 GitHub 全新 clone Docker 体验记录，确认 `report latest`、`strategy draft` 和 `agent start` 的承接效果

### Changed

- README / README.en / Docker 命令速查加入 `strategy draft` 主路径，并继续明确当前版本不会启动模拟盘或真实下单
- 项目状态、路线图、TODO 和策略系统设计文档同步到 v0.4.3：首版只支持 R-breaker 模板，不支持任意策略代码生成

### Fixed

- 策略想法缺少品种或周期时返回“需要澄清”，不会静默补默认值伪装成完成
- 均线、RSI、网格、套利等当前未支持模板会被明确拒绝，不会生成看起来可用但系统无法验证的 TOML

## [0.4.2] — 2026-05-06

### Added

- **Docker 首次体验根因修复方案**：新增 `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260506.md`，把 v0.4.1 多画像评测暴露的问题逐项绑定到用户看到的问题、根因、产品修复和验收标准
- `report latest` 对自动研究报告优先读取 `auto_run_summary.json`，在第一屏展示数据类型、样本天数、策略数量、验证结果和下一步命令

### Fixed

- Agent 策略列表不再显示未替换的 `{n}`，研究结论不再把 7 天 sample 数据说成 90 天复验，也不再把单个 R-breaker 写成“12 个旧策略”
- 自动研究报告在样本少于 90 天时不再输出“90 天复验已完成”，sample 数据会明确标注为流程试跑而非策略有效性结论
- Docker 场景下的策略配置提示改为容器内 `/root/.kronos/...` 路径，并在宿主机路径误传时给出可复制的修正命令

### Changed

- `configs/dev.toml` 默认日志级别从 `DEBUG` 调整为 `WARNING`，避免 quickstart / agent 首屏泄露 `query.loaded`、`partition.written` 等工程日志
- README / README.en 命令速查拆分本地 uv 和 Docker 路径，明确 quickstart 的 1m sample 试跑与 TOML 默认 15m 策略配置不是同一层结论

## [0.4.1] — 2026-05-06

### Added

- **Docker 多画像体验评测**：新增 `docs/DOCKER_PERSONA_UX_EVALUATION_20260506.md`，按 L0/L1/L2/L3/L4/L6 用户画像记录 v0.4.0 Docker 首次使用反馈、信任断点和修复优先级

### Changed

- TODO 产品体验 backlog 增补 Docker 多画像评测暴露的 P0/P1 问题：Agent 事实错误、`report latest` 摘要不足、7 天样本与 90 天文案冲突、Docker 路径误导和 quickstart/TOML 粒度错配

## [0.4.0] — 2026-05-06

### Added

- **TOML 策略配置入口**：新增 `kronos strategy init-r-breaker`，生成 `~/.kronos/strategies/r_breaker.toml` 风格的可编辑策略配置
- **策略配置校验**：新增 `kronos strategy validate`，校验策略 ID、交易品种、时间周期和 R-breaker 参数边界
- **本地烟雾测试**：新增 `kronos strategy smoke-test`，用本地 K 线试算策略信号，输出是否能进入研究验证的产品结论
- **配置注册到候选池**：新增 `kronos strategy register`，默认要求烟雾测试通过后才把策略写入共享候选池，Agent/Web 可见

### Changed

- 候选注册支持按 `candidate_id` 更新，重复注册同一个 TOML 策略不会制造重复候选
- README、quickstart 下一步提示、Agent 参数调整文案同步到 v0.4.0 策略配置主路径
- 项目状态和策略系统设计文档更新为 v0.4.0 当前能力边界：已支持 TOML 配置/校验/烟雾测试，AI 创建、历史重放和实时模拟盘仍未交付
- 新增并接入 `docs/USER_PERSONAS.md`，明确 Kronos 核心用户不是完全小白，而是有交易经验或研究能力、需要把策略想法变成证据的人

## [0.3.4] — 2026-05-06

### Fixed

- **候选池测试隔离**：测试默认使用临时 `KRONOS_CANDIDATES_PATH`，不再读写用户真实 `~/.kronos/candidates.json`
- **最新报告语义**：`kronos report latest` 优先使用 run summary / run_id 时间判断最新报告，文件 mtime 仅作 fallback
- **LLM provider 边界**：Web 设置写入和状态读取统一只接受当前支持的 DeepSeek provider
- **Agent 工具输入校验**：确定性工具执行前校验必需字段，缺字段时返回可解释错误且不调用 handler

### Changed

- 重写 `docs/PROJECT_STATUS.md` 为 v0.3.4 当前事实源
- 收敛 `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` 的当前能力边界，明确 AI 创建、历史重放和实时模拟盘属于后续 v0.4.x
- README badge、TODO 和产品控制文档统一到 v0.3.4

## [0.3.3] — 2026-05-06

### Added

- **最新报告入口**：新增 `kronos report latest`，直接打印最新产品报告摘要和路径，不需要用户手动 `ls reports/research/experiments`
- **交易语言解读**：研究工作台报告在候选结果中追加预测方向、多空分层、稳定频率、样本外稳定性和模拟盘判断
- **数据同步说明**：`kronos data sync` 执行前明确数据来源、同步范围、公开行情和无需 API Key 的边界

### Changed

- quickstart 下一步提示改为优先使用 `kronos report latest`，并明确当前版本只到研究报告，不会启动模拟盘或真实下单

## [0.3.2] — 2026-05-05

### Fixed

- **候选注册持久化**：quickstart 注册的 R-breaker 写入 `~/.kronos/candidates.json`，agent start 启动时自动加载。不再出现"quickstart 评估完 R-breaker，Agent 却说还没有定义任何策略"的 P0 断裂

## [0.3.1] — 2026-05-05

### Fixed

- benchmark 对比不再对 synthetic 数据展示虚假数字（随机游走收益无参考价值）
- quickstart 在 Docker 环境下自动切换输出指引（不再建议 `npm run dev`）
- `docker compose run` 不再重复下载 dev 依赖（`ENV UV_NO_SYNC=1`）
- 版本号统一：VERSION (0.3.1)、pyproject.toml (0.3.1)、README badge (0.3)
- README 添加 Docker 部署说明

## [0.3.0] — 2026-05-05

### Added

- **可信度评估报告**：quickstart 输出包含市场基准对比（vs 持有 BTC）、评估数量、通过数量、原因解释
- **参数调整引导**：Agent 控制台研究完成后展示可调参数列表、TOML 路径、常见调整建议
- **Docker 完整支持**：Dockerfile + docker-compose.yml + .dockerignore + entrypoint、6 项根因问题修复
- **惰性加载 matplotlib**：`diagnostics/reporting.py` 中改为函数内 import，避免生产环境非必要导入

### Fixed

- matplotlib 模块级 import 导致 `--no-dev` 下崩溃
- Web 全新 clone 空状态：无历史 run 时不再显示不存在的默认批次号
- Docker 构建 8 分钟超时（移除 500+ 个多余的 Debian 系统包）
- Dockerfile COPY 顺序修正（kronos/ 在 uv sync 之前）
- pyproject.toml 显式声明 scipy、numpy、matplotlib 生产依赖

## [0.2.0] — 2026-05-05

### Added

- **对话式 Agent**（`kronos agent start`）：上下文感知、主动引导、分阶段交互（首次用户/回访用户不同路径）
- **策略翻译层**：内部因子概念自动翻译为交易者可理解的策略描述
- **Agent 环境感知**：自动检测数据/模型/历史状态，主动提议修复缺失
- **i18n 完整翻译**：80+ 对话字符串中英双语，`--lang zh/en` 全局切换
- **策略列表优化**：按活跃/已验证分组，"趋势回踩" 替代 "trend_pullback_entry"

### Changed

- README 中英分离（`README.md` + `README.en.md`，顶部互相索引）
- README clone URL 改为 HTTPS（新用户无需配 SSH key）
- 前置条件补全（Python 3.12+、uv、git）
- 文档目录精简：30 个内部开发文档从公开仓库移除，仅保留 ROADMAP 和 PROJECT_STATUS

### Fixed

- 候选状态从英文 enum 值修正为中文标签（"已验证" 替代 "retired"）
- Web 工作台首页新增候选生命周期分布图表
- "开始下一轮研究"按钮根据 DeepSeek 配置动态启用/禁用
- 审批中心空状态补充说明文案

## [0.1.0] — 2026-05-04

### Added

- **Agent MVP 完整闭环**：Supervisor、角色注册、Prompt 版本化、DeepSeek LLM 适配器、确定性工具执行、事件时间线、`kronos agent run-once`
- **DeepSeek V4-Pro / V4-Flash 双模型支持**：研究员/反方/投委会用 V4-Pro，风控/执行分析用 V4-Flash
- **Web 研究工作台**：FastAPI 后端 + Next.js 16 前端，候选池、Agent 时间线、报告阅读器、设置面板、审批中心
- **Onboarding 系统**：`kronos quickstart` 一键启动、`README.md` 中英双语、`--lang zh/en` 全局语言切换、sample 数据自动生成、配置自动发现
- **17 个种子因子**：5 个家族（趋势动量、波动率路径、成交量流动性、均值回归、衍生品），含 PIT-safe 计算
- **完整回测引擎**：信号调度、成本模型、Freqtrade 交叉验证 bridge
- **因子验证管线**：IC/ICIR 指标、Alphalens 适配、双门禁晋升（validation + walkforward）
- **滚动窗口验证**：嵌套 train/validation/test 拆分、轻量参数搜索、lookahead 审计
- **信号诊断**：IC 时序、分组收益、换手率、衰减、相关性矩阵
- **实验管理**：run_id 贯穿、JSONL 账本、DuckDB 查询层、知识库（SQLite + FTS）
- **组合构建 + 风控 + 通知**：规则化 allocator、风控引擎、Telegram 通知
- **Binance USDM 数据管线**：K 线/Funding/OI 拉取、Parquet 分区存储、PIT-safe 查询、覆盖率/gap 检测
- **数据层**：Pydantic Schema、PyArrow 存储、DuckDB 查询、增量同步
- **CLI**：`kronos data`/`research`/`run`/`agent`/`quickstart` 五组子命令
- **综合文档**：CLAUDE.md、ROADMAP.md、PROJECT_STATUS.md、代码审查报告、产品验收报告

### Security

- **路径穿越修复**：Web API 的 run_id 参数添加文件系统安全校验
- **SQL 注入修复**：数据查询层的 symbol/dataset 参数添加标识符校验
- **Secret 脱敏统一**：三处重复定义合并到 `events.py`，tools.py 和 reports.py 改为导入

### Fixed

- 回测引擎 `execution_delay_bars` 配置被静默忽略（现正确传参给 `_schedule_targets`）
- 回测引擎自生成 run_id 导致跨模块链路断裂（现接受调用方传入 run_id）
- 知识库 `add_watchlist_evidence_entry` 使用 batch_id 代替 run_id（现已统一）
- `fetch_open_interest` 异常路径 UnboundLocalError
- `_request_with_retry` 首次请求前不必要的 sleep
- Parquet 损坏被静默掩盖为空 DataFrame
- 风控引擎杠杆缩放后跳过 `max_single_weight` 约束再检查
- DeepSeek V4-Pro `reasoning_content` 字段解析
- 候选生命周期状态全部卡在"迁移审查"（现根据研究证据差异化：8 淘汰 + 3 观察 + 1 候选改造）
- "开始下一轮研究"按钮永远 disabled（现根据 DeepSeek 配置状态动态切换）
- 审批中心空状态文案优化
- 新增候选生命周期分布图表

### Changed

- 配置加载增加 6 级自动发现 fallback 链
- `RuntimeConfig` 增加 `lang` 字段
- Agent 角色默认模型从硬编码改为 DeepSeek-V4-Pro/V4-Flash 分角色分配
- LLM 设置 API 返回 `available_models` 列表
- `_extract_content` 兼容 reasoning 模型的 `reasoning_content` 字段
- README 中英双语
- CLI 所有命令支持 `--lang zh/en`

## [0.0.0] — 2026-04-05

### Added
- Project skeleton and toolchain configuration
