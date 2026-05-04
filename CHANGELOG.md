# Changelog

All notable changes to Kronos will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
