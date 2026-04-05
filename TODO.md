# Kronos 全局 TODO

> 最后更新：2026-04-05
> 状态标记：⬜ 未开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 阻塞

---

## 总览

| Phase | 模块 | 任务组数 | 任务数 | 状态 |
|---|---|---|---|---|
| Global | global-code-standards | 3 | 13 | 🔄 |
| Global | global-module-contracts | 4 | 13 | 🔄 |
| Global | global-release-workflow | 4 | 13 | 🔄 |
| P1 | p1-data-layer | 9 | 55 | 🔄 |
| P1 | p1-factor-platform | 7 | 49 | ⬜ |
| P1 | p1-backtest-engine | 8 | 40 | ⬜ |
| P2 | p2-experiment-management | 6 | 22 | ⬜ |
| P2 | p2-factor-families | — | 待写 | ⬜ |
| P2 | p2-signal-diagnostics | — | 待写 | ⬜ |
| P2 | p2-walkforward | — | 待写 | ⬜ |
| P3 | p3-portfolio-construction | — | 待写 | ⬜ |
| P3 | p3-risk-engine | — | 待写 | ⬜ |
| P3 | p3-freqtrade-crosscheck | — | 待写 | ⬜ |
| P3 | p3-notification-system | — | 待写 | ⬜ |
| P4 | p4-factor-auto-generation | — | 待写 | ⬜ |
| P4 | p4-ml-factors | — | 待写 | ⬜ |
| P4 | p4-knowledge-base | — | 待写 | ⬜ |
| P5 | p5-execution-layer | — | 待写 | ⬜ |
| P5 | p5-monitoring | — | 待写 | ⬜ |
| P6 | p6-governance | — | 待写 | ⬜ |
| P6 | p6-live-launch | — | 待写 | ⬜ |

---

## 建议执行顺序

Global 三个模块和 P1 三个模块之间有依赖关系，推荐按以下顺序执行：

```
第一批（项目基础设施，可并行）：
  global-code-standards    → 工具链、测试基础设施
  global-release-workflow  → 版本管理、.gitignore、pre-commit
  global-module-contracts  → 共享类型、依赖方向检测

第二批（P1 核心，有依赖，按序执行）：
  p1-data-layer           → 数据层（依赖 global 基础设施）
  p1-factor-platform      → 因子中台（依赖 data-layer）
  p1-backtest-engine      → 回测引擎（依赖 factor-platform）

第三批（P2，P1 完成后启动）：
  p2-experiment-management → 实验管理
  p2-factor-families       → 补全因子家族（tasks 待写）
  p2-signal-diagnostics    → Signal 诊断（tasks 待写）
  p2-walkforward           → Walk-forward 验证（tasks 待写）
```

---

## Global: global-code-standards

> 来源：`openspec/changes/global-code-standards/tasks.md`

### G-CS-1. 工具链配置
- [x] G-CS-1.1 在 pyproject.toml 中配置 ruff（lint + format 规则）
- [x] G-CS-1.2 在 pyproject.toml 中配置 mypy strict
- [x] G-CS-1.3 在 pyproject.toml 中配置 pytest + coverage
- [x] G-CS-1.4 创建 `.pre-commit-config.yaml`：ruff check + ruff format + mypy

### G-CS-2. 测试基础设施
- [x] G-CS-2.1 创建 `tests/unit/`、`tests/integration/`、`tests/e2e/` 目录结构
- [x] G-CS-2.2 创建 `tests/conftest.py`：公共 fixtures（tmp_path、mock DuckDB、时间冻结）
- [x] G-CS-2.3 创建 `tests/fixtures/` 目录：预录制的 Binance API 响应
- [x] G-CS-2.4 配置 pytest markers：`e2e`（默认 skip）
- [ ] G-CS-2.5 创建 hypothesis profiles：默认 + CI 用的更高 max_examples

### G-CS-3. 验收
- [ ] G-CS-3.1 验证 pre-commit hooks 正常拦截不合规代码
- [ ] G-CS-3.2 验证 mypy strict 对空项目零错误
- [ ] G-CS-3.3 验证 pytest 能分层运行（unit / integration / e2e）

---

## Global: global-module-contracts

> 来源：`openspec/changes/global-module-contracts/tasks.md`

### G-MC-1. 共享类型定义
- [x] G-MC-1.1 实现 `kronos/common/types.py`：Factor Protocol、BacktestResult、TargetPortfolio、CoverageInfo、Constraints
- [x] G-MC-1.2 实现枚举类型：Level、FactorStatus、RuntimeMode
- [x] G-MC-1.3 实现 Notifier Protocol
- [x] G-MC-1.4 定义配置 section schema（Pydantic 模型对应 TOML 各 section）

### G-MC-2. 依赖方向检测
- [ ] G-MC-2.1 编写 `scripts/check_imports.py`：扫描 kronos/ 下所有 import，检测违反依赖方向的引用
- [ ] G-MC-2.2 将 import 检查加入 pre-commit hooks

### G-MC-3. 接口集成测试
- [ ] G-MC-3.1 编写 Layer 1→2 接口测试：验证 data.load() 返回的 DataFrame 列名和类型符合契约
- [ ] G-MC-3.2 编写 Layer 2→3 接口测试：验证 factor_scores DataFrame 格式
- [ ] G-MC-3.3 编写共享类型测试：验证 Protocol 实现的类型检查

### G-MC-4. 验收
- [ ] G-MC-4.1 `mypy --strict` 验证所有 Protocol 定义
- [ ] G-MC-4.2 import 检查脚本零违规

---

## Global: global-release-workflow

> 来源：`openspec/changes/global-release-workflow/tasks.md`

### G-RW-1. 版本管理基础设施
- [x] G-RW-1.1 创建 `VERSION` 文件，初始值 `0.0.0`
- [x] G-RW-1.2 创建 `CHANGELOG.md`，初始模板（Unreleased section）
- [x] G-RW-1.3 创建 `.gitignore`：排除 data/、experiments/、logs/、__pycache__、.venv、*.parquet.tmp
- [x] G-RW-1.4 配置 pre-commit hooks：ruff check + ruff format + mypy

### G-RW-2. 数据版本管理
- [ ] G-RW-2.1 实现 `kronos/common/versioning.py`：data_snapshot_id 生成（日期 + git short hash）
- [ ] G-RW-2.2 实现 snapshot.json 写入：同步完成后自动记录
- [ ] G-RW-2.3 实现 config_hash 计算：SHA-256 前 12 位

### G-RW-3. 实验可复现性
- [ ] G-RW-3.1 定义实验日志 schema：run_id, git_commit, data_snapshot_id, config_hash, factors, universe, split_dates, results, artifact_paths
- [ ] G-RW-3.2 实现实验目录自动创建：`experiments/{run_id}/`
- [ ] G-RW-3.3 实现 config 快照保存：实验启动时复制当前配置到产物目录

### G-RW-4. 验收
- [ ] G-RW-4.1 验证 pre-commit hooks 正常工作
- [ ] G-RW-4.2 验证 data_snapshot_id 生成和记录
- [ ] G-RW-4.3 验证 CHANGELOG 格式规范

---

## Phase 1: p1-data-layer

> 来源：`openspec/changes/p1-data-layer/tasks.md`
> Oracle 评审：✅ 已通过并修正

### P1-DL-1. 项目骨架搭建
- [x] P1-DL-1.1 创建 `kronos/` Python package 目录结构
- [x] P1-DL-1.2 创建 `pyproject.toml`：Python 3.12+，依赖列表
- [x] P1-DL-1.3 配置开发工具链：mypy strict、ruff、pre-commit、pytest + hypothesis
- [x] P1-DL-1.4 创建 `configs/dev.toml` 和 `configs/backtest.toml` 基础配置文件
- [x] P1-DL-1.5 实现 `kronos/common/config.py`：Pydantic + TOML 配置加载
- [x] P1-DL-1.6 实现 `kronos/common/log.py`：structlog JSON 日志初始化
- [x] P1-DL-1.7 实现 `kronos/common/errors.py`：统一异常基类

### P1-DL-2. 数据 Schema + 时间模型
- [x] P1-DL-2.1 定义三时间戳基类：event_time, available_at, ingested_at
- [x] P1-DL-2.2 实现 candle.py：K 线 Pydantic 模型
- [x] P1-DL-2.3 实现 funding.py：Funding rate Pydantic 模型
- [x] P1-DL-2.4 实现 oi.py：OI Pydantic 模型
- [x] P1-DL-2.5 实现 OHLC 一致性验证器
- [x] P1-DL-2.6 定义去重键
- [x] P1-DL-2.7 编写 schema 单元测试

### P1-DL-3. 市场元数据
- [x] P1-DL-3.1 实现 exchange_info.py：Binance exchangeInfo 拉取
- [x] P1-DL-3.2 提取 symbol 列表、onboardDate、精度信息
- [x] P1-DL-3.3 存储到 exchange_info.parquet
- [x] P1-DL-3.4 实现 symbol 有效性验证函数
- [x] P1-DL-3.5 编写元数据单元测试

### P1-DL-4. 存储层（月分区 + 原子写入）
- [x] P1-DL-4.1 实现 parquet_store.py：月分区 Parquet 写入
- [x] P1-DL-4.2 实现分区读取
- [x] P1-DL-4.3 实现分区追加（去重 + 排序 + 原子重写）
- [x] P1-DL-4.4 实现临时文件清理
- [x] P1-DL-4.5 实现目录自动创建
- [x] P1-DL-4.6 编写存储层单元测试

### P1-DL-5. 查询层（DuckDB over Parquet）
- [x] P1-DL-5.1 实现 query.py：DuckDB 直接查询 Parquet
- [x] P1-DL-5.2 实现 kronos.data.load() API
- [x] P1-DL-5.3 实现时间框架重采样
- [x] P1-DL-5.4 实现 kronos.data.load_universe() API
- [x] P1-DL-5.5 实现 as_of 过滤
- [x] P1-DL-5.6 实现覆盖范围查询
- [x] P1-DL-5.7 编写查询层单元测试

### P1-DL-6. Binance USDM 数据采集
- [ ] P1-DL-6.1 实现 binance_usdm.py：Binance USDM adapter
- [ ] P1-DL-6.2 实现 1m K 线分页拉取
- [ ] P1-DL-6.3 实现 funding rate 分页拉取
- [ ] P1-DL-6.4 实现 OI 历史拉取
- [ ] P1-DL-6.5 实现重试 + 指数退避
- [ ] P1-DL-6.6 实现请求间隔控制
- [ ] P1-DL-6.7 实现 raw 层存储
- [ ] P1-DL-6.8 编写 adapter 单元测试

### P1-DL-7. 数据同步管线
- [ ] P1-DL-7.1 实现 sync.py：完整管线
- [ ] P1-DL-7.2 实现增量同步
- [ ] P1-DL-7.3 实现缺口检测
- [ ] P1-DL-7.4 编写同步管线集成测试

### P1-DL-8. CLI 命令
- [ ] P1-DL-8.1 实现 cli/main.py：Typer 应用骨架
- [ ] P1-DL-8.2 实现 `kronos data sync` 命令
- [ ] P1-DL-8.3 实现同步进度显示
- [ ] P1-DL-8.4 实现 `kronos data status` 命令
- [ ] P1-DL-8.5 实现错误处理
- [ ] P1-DL-8.6 编写 CLI 集成测试

### P1-DL-9. 验收验证
- [ ] P1-DL-9.1 端到端验证：拉取 BTCUSDT、ETHUSDT、SOLUSDT
- [ ] P1-DL-9.2 验证重采样
- [ ] P1-DL-9.3 验证 PIT 查询
- [ ] P1-DL-9.4 验证增量同步
- [ ] P1-DL-9.5 验证原子写入
- [ ] P1-DL-9.6 验证 schema 检查
- [ ] P1-DL-9.7 验证 OI 限制处理
- [ ] P1-DL-9.8 mypy --strict 零错误、ruff 零 warning、pytest 全部通过
- [ ] P1-DL-9.9 单元测试覆盖率 > 80%

---

## Phase 1: p1-factor-platform

> 来源：`openspec/changes/p1-factor-platform/tasks.md`
> Oracle 评审：⬜ 待审

### P1-FP-1. Factor Protocol + base classes
- [ ] P1-FP-1.1 创建 protocol.py、base.py、schemas.py
- [ ] P1-FP-1.2 定义 FactorMeta Pydantic 模型
- [ ] P1-FP-1.3 实现 BaseFactor 抽象基类
- [ ] P1-FP-1.4 实现统一家族枚举
- [ ] P1-FP-1.5 实现输入校验
- [ ] P1-FP-1.6 实现 warmup 辅助工具
- [ ] P1-FP-1.7 编写协议级文档字符串

### P1-FP-2. Factor Registry
- [ ] P1-FP-2.1 实现 FactorRegistry 类
- [ ] P1-FP-2.2 实现 register()
- [ ] P1-FP-2.3 实现 get()
- [ ] P1-FP-2.4 实现 list()
- [ ] P1-FP-2.5 实现 status()
- [ ] P1-FP-2.6 实现 compute_all()
- [ ] P1-FP-2.7 输出整理为标准长表
- [ ] P1-FP-2.8 实现物化路径解析
- [ ] P1-FP-2.9 实现缓存元数据
- [ ] P1-FP-2.10 实现缓存命中/失效判断

### P1-FP-3. Factor validation pipeline
- [ ] P1-FP-3.1 创建 validation 模块结构
- [ ] P1-FP-3.2 定义 ValidationConfig + 默认阈值
- [ ] P1-FP-3.3 实现 validate_factor()
- [ ] P1-FP-3.4 实现 IC / Rank IC 计算
- [ ] P1-FP-3.5 实现 grouped returns
- [ ] P1-FP-3.6 实现 turnover 计算
- [ ] P1-FP-3.7 实现 decay 分析
- [ ] P1-FP-3.8 实现验证结论聚合（pass/review/fail）
- [ ] P1-FP-3.9 实现验证结果持久化

### P1-FP-4. Initial factor implementations
- [ ] P1-FP-4.1 创建 implementations 模块
- [ ] P1-FP-4.2 实现 ASISpreadFactor
- [ ] P1-FP-4.3 ASISpreadFactor warmup + 方向处理
- [ ] P1-FP-4.4 实现 CMOMomentumFactor
- [ ] P1-FP-4.5 CMOMomentumFactor lookback + NaN 行为
- [ ] P1-FP-4.6 实现 FundingRegimeFactor
- [ ] P1-FP-4.7 FundingRegimeFactor 稀疏处理 + 符号翻转
- [ ] P1-FP-4.8 创建 bootstrap.py 集中注册

### P1-FP-5. Alphalens integration
- [ ] P1-FP-5.1 实现 alphalens_adapter.py
- [ ] P1-FP-5.2 实现价格序列加载与对齐
- [ ] P1-FP-5.3 实现 warmup/缺失值过滤
- [ ] P1-FP-5.4 调用 Alphalens 计算
- [ ] P1-FP-5.5 导出图表到报告目录
- [ ] P1-FP-5.6 记录运行参数到报告元数据

### P1-FP-6. Unit tests
- [ ] P1-FP-6.1 test_protocol.py
- [ ] P1-FP-6.2 test_registry.py
- [ ] P1-FP-6.3 test_materialize.py
- [ ] P1-FP-6.4 test_validation_metrics.py
- [ ] P1-FP-6.5 test_asi_spread.py
- [ ] P1-FP-6.6 test_cmo_momentum.py
- [ ] P1-FP-6.7 test_funding_regime.py
- [ ] P1-FP-6.8 test_alphalens_adapter.py

### P1-FP-7. Acceptance verification
- [ ] P1-FP-7.1 单因子计算端到端验证
- [ ] P1-FP-7.2 多 symbol compute_all() 验证
- [ ] P1-FP-7.3 三因子注册/计算/物化/读取验证
- [ ] P1-FP-7.4 warmup NaN 验证
- [ ] P1-FP-7.5 缓存策略验证
- [ ] P1-FP-7.6 IC/Rank IC/grouped returns/turnover/decay 验证
- [ ] P1-FP-7.7 Alphalens tear sheet 验证
- [ ] P1-FP-7.8 pytest 全部通过
- [ ] P1-FP-7.9 ruff + mypy 零错误

---

## Phase 1: p1-backtest-engine

> 来源：`openspec/changes/p1-backtest-engine/tasks.md`
> Oracle 评审：⬜ 待审

### P1-BT-1. 模块骨架与配置契约
- [ ] P1-BT-1.1 创建 backtest 模块结构
- [ ] P1-BT-1.2 定义回测配置模型
- [ ] P1-BT-1.3 定义 BacktestResult/BacktestMetrics/CrossValidationResult schema
- [ ] P1-BT-1.4 新增 backtest.toml 配置段

### P1-BT-2. 输入契约与数据校验
- [ ] P1-BT-2.1 实现 validators.py：signals 校验
- [ ] P1-BT-2.2 data 字段校验
- [ ] P1-BT-2.3 PIT 校验
- [ ] P1-BT-2.4 lookahead 预检查
- [ ] P1-BT-2.5 编写输入契约单元测试

### P1-BT-3. 核心回测流水线
- [ ] P1-BT-3.1 实现 engine.py：Engine(config).run()
- [ ] P1-BT-3.2 实现 ranking.py：横截面排序
- [ ] P1-BT-3.3 实现 weights.py：权重归一化
- [ ] P1-BT-3.4 实现调仓频率处理
- [ ] P1-BT-3.5 实现延迟一 bar 生效
- [ ] P1-BT-3.6 实现持仓漂移逻辑
- [ ] P1-BT-3.7 编写核心流水线单元测试

### P1-BT-4. 收益、成本与交易台账
- [ ] P1-BT-4.1 实现 returns.py
- [ ] P1-BT-4.2 实现 costs.py
- [ ] P1-BT-4.3 实现 funding 扣减开关
- [ ] P1-BT-4.4 实现 trades.py：trade ledger
- [ ] P1-BT-4.5 编写收益与成本单元测试

### P1-BT-5. 指标与 tearsheet
- [ ] P1-BT-5.1 实现 metrics.py：Sharpe/Sortino/Calmar/DD 等
- [ ] P1-BT-5.2 实现持仓统计
- [ ] P1-BT-5.3 实现尾部风险指标
- [ ] P1-BT-5.4 实现 reporting.py：tearsheet 生成
- [ ] P1-BT-5.5 编写 metrics 单元测试

### P1-BT-6. Freqtrade 交叉验证桥接
- [ ] P1-BT-6.1 实现 freqtrade_bridge.py
- [ ] P1-BT-6.2 实现信号导出器
- [ ] P1-BT-6.3 实现 Freqtrade 最小配置生成器
- [ ] P1-BT-6.4 实现 lookahead analysis 调用封装
- [ ] P1-BT-6.5 实现结果读取与比较
- [ ] P1-BT-6.6 实现阈值判定逻辑
- [ ] P1-BT-6.7 编写 bridge 单元测试

### P1-BT-7. 集成验证
- [ ] P1-BT-7.1 PIT-safe 数据 → Engine.run() 集成测试
- [ ] P1-BT-7.2 factor compute_all() → signals → 回测集成测试
- [ ] P1-BT-7.3 lookahead bias 防线验证
- [ ] P1-BT-7.4 三种模式权重约束验证
- [ ] P1-BT-7.5 Freqtrade bridge mock 验证

### P1-BT-8. 验收与文档同步
- [ ] P1-BT-8.1 对照 specs 检查所有 SHALL/MUST
- [ ] P1-BT-8.2 补充模块级 docstring
- [ ] P1-BT-8.3 运行全部测试通过
- [ ] P1-BT-8.4 记录已知限制

---

## Phase 2: p2-experiment-management

> 来源：`openspec/changes/p2-experiment-management/tasks.md`
> Oracle 评审：⬜ 待审

### P2-EM-1. Run ledger schema 与 run_id
- [ ] P2-EM-1.1 定义标准 run ledger schema
- [ ] P2-EM-1.2 实现 run_id 生成逻辑
- [ ] P2-EM-1.3 实现账本写入前校验

### P2-EM-2. JSONL 账本与 DuckDB 查询层
- [ ] P2-EM-2.1 实现 append-only JSONL ledger writer
- [ ] P2-EM-2.2 实现 DuckDB 索引/视图构建
- [ ] P2-EM-2.3 编写 JSONL → DuckDB 重建验证

### P2-EM-3. Artifact 目录约定与路径登记
- [ ] P2-EM-3.1 实现标准 artifact 根目录约定
- [ ] P2-EM-3.2 规定最小产出文件
- [ ] P2-EM-3.3 统一写出 equity.parquet 与 trades.parquet
- [ ] P2-EM-3.4 实现 artifact_paths 登记逻辑

### P2-EM-4. run_id 跨模块透传
- [ ] P2-EM-4.1 backtest engine 透传 run_id
- [ ] P2-EM-4.2 factor validation 透传 run_id
- [ ] P2-EM-4.3 signal diagnostics / walk-forward 复用 run_id

### P2-EM-5. 跨实验比较查询
- [ ] P2-EM-5.1 实现 DuckDB 查询接口
- [ ] P2-EM-5.2 实现跨实验对照输出
- [ ] P2-EM-5.3 编写比较场景验证

### P2-EM-6. 验收与规格对照
- [ ] P2-EM-6.1 对照 specs 确认所有 SHALL/MUST
- [ ] P2-EM-6.2 编写验证场景覆盖
- [ ] P2-EM-6.3 记录已知非目标

---

## Phase 2-6: 待详化模块

以下模块有 proposal + design + 概要 specs，但 tasks 尚未写（按 v1.0 文档策略，Phase 启动前再详化）：

| 模块 | Phase | 启动前提 |
|---|---|---|
| p2-factor-families | P2 | P1 完成 |
| p2-signal-diagnostics | P2 | P1 完成 |
| p2-walkforward | P2 | P1 完成 |
| p3-portfolio-construction | P3 | P2 完成 |
| p3-risk-engine | P3 | P2 完成 |
| p3-freqtrade-crosscheck | P3 | P2 完成 |
| p3-notification-system | P3 | P2 完成 |
| p4-factor-auto-generation | P4 | P3 完成 |
| p4-ml-factors | P4 | P3 完成 |
| p4-knowledge-base | P4 | P3 完成 |
| p5-execution-layer | P5 | P4 完成 |
| p5-monitoring | P5 | P4 完成 |
| p6-governance | P6 | P5 完成 |
| p6-live-launch | P6 | P5 完成 |
