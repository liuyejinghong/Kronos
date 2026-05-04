# Kronos 全量代码审查报告

> 审查时间：2026-05-04
> 审查范围：kronos/ + cli/ + tests/，全部 90+ Python 文件
> 审查人：Claude Code (deepseek-v4-pro)

## 总览

| 严重度 | 数量 | 说明 |
|--------|------|------|
| CRITICAL | 8 | 安全漏洞、数据完整性问题、核心不变量被破坏 |
| MAJOR | 20 | Bug、死代码、未连接的管道、不一致 |
| MINOR | 47 | 样式、测试缺口、冗余、性能 |

---

## CRITICAL

### C1. Web API 路径穿越漏洞（3 处）

**文件**: `kronos/web/routes/agent.py:63-81`, `events.py:54-62`, `approvals.py:54`

`run_id` 参数直接拼接到文件系统路径，无校验。攻击者可传入 `../../etc` 跨越目录边界。agent.py 的 `read_text()` 可读取任意文件，approvals.py 的 `write_event()` 可写入任意目录。

**修复**: 添加 `_validate_run_id()` 校验，拒绝包含 `..`、`/`、`\` 的值，或 `resolve()` 后检查是否在预期根目录内。

### C2. SQL 注入向量

**文件**: `kronos/data/storage/query.py:49-51, 113-140`

`symbol` 和 `dataset` 参数通过 f-string 拼入 DuckDB SQL：`f"SELECT * FROM read_parquet('{glob}')"`。恶意 `symbol` 值可注入任意 SQL。

**修复**: 校验 symbol/dataset 不含引号、分号、路径字符，或使用参数化查询。

### C3. Pydantic Schema 从未用于生产数据校验

**文件**: `kronos/data/schemas/candle.py`, `funding.py`, `oi.py`

`CandleRecord`/`FundingRecord`/`OIRecord` 仅在测试中使用。生产管线（loader → sync → parquet）直接写入原始 API 响应，不经过 OHLC 一致性、PIT 时序、负值校验。畸形 API 响应会静默写入脏数据。

**修复**: 在 loader 的 row-building 循环中或 sync 的 `write_records_partitioned` 前施加 schema 校验。

### C4. 回测引擎忽略 `execution_delay_bars` 配置

**文件**: `kronos/research/backtest/engine.py:152-167`

`BacktestConfig.execution_delay_bars` 在 `validate_lookahead` 中校验但 `_schedule_targets` 从不读取。设置 `execution_delay_bars=2` 会被静默忽略，总是执行 1-bar delay。

**修复**: 将 config 传入 `_schedule_targets`，按 `config.execution_delay_bars` 跳过时间戳。

### C5. 回测引擎自生成 run_id，破坏调用方线程

**文件**: `kronos/research/backtest/engine.py:195-198`

`Engine.run()` 内部生成 `run_id`（基于 signal min/max timestamp + config hash），不接受调用方传入。实验账本中回测 artifact 的 run_id 与上游研究循环的 run_id 不一致，无法通过 run_id 跨模块关联。

**修复**: `Engine.run()` 增加可选 `run_id` 参数，仅在未提供时 fallback 到 `_run_id()`。

### C6. 知识库 watchlist evidence 用 batch_id 代替 run_id

**文件**: `kronos/research/knowledge_base/store.py:200`

`add_watchlist_evidence_entry` 使用 `metadata.get("batch_id")` 作为 `run_id`，而非 `metadata.get("run_id")`（其他所有 `add_*_entry` 的行为）。按 run_id 查询知识库会遗漏 watchlist evidence。

**修复**: 统一使用 `run_id`。

### C7. Secret 脱敏函数三处重复定义

**文件**: `kronos/agent/events.py:75-91`, `tools.py:331-347`, `reports.py:173-189`

`_redact_secret_like_values` 和 `_is_secret_like_key` 三处逐字相同。修改脱敏逻辑时必须同步三处，遗漏一处会导致 secret 泄露。

**修复**: 在 `events.py` 中公开这两个函数，`tools.py` 和 `reports.py` 改为导入。

### C8. 审批中心 API 始终返回空

**文件**: `kronos/web/routes/approvals.py:25-28`

`list_approvals()` 无条件返回 `ApprovalListResponse(items=[])`。审批流程完全不可用。

**修复**: 实现从 Agent 事件时间线扫描 pending approval 的逻辑，或先标记为 stub。

---

## MAJOR

### Bug

**M1. `fetch_open_interest` UnboundLocalError 路径**
`kronos/data/loaders/binance_usdm.py:345-358` — 当首页 OI 数据请求失败触发 except 分支时，`data` 未定义，`if not data:` 抛出 `UnboundLocalError`。

**M2. `_request_with_retry` 在首次请求前 sleep**
`kronos/data/loaders/binance_usdm.py:52` — `time.sleep(request_interval_ms / 1000)` 在每次调用时都执行，包括首次尝试。应仅在重试间 sleep。

**M3. `load()` 静默掩盖 Parquet 损坏**
`kronos/data/storage/query.py:142-146` — `duckdb.IOException` 被统一视为"无数据"。损坏的 parquet 文件、权限错误、磁盘故障都会被静默返回空 DataFrame。

**M4. 风控引擎 leverage 缩放后跳过 `max_single_weight` 再检查**
`kronos/risk/engine.py:130-139` — `_apply_hard_limits` 在杠杆缩放后提前 return，跳过了后续的 `max_single_weight` 约束检查。

**M5. `_classify_decision_failure` 用脆弱字符串匹配**
`kronos/research/workbench.py:807-825` — 通过匹配英文原因字符串文本来分类失败原因。若 `promotion.py` 的原因文案变更，分类会静默失效。

**M6. Freqtrade bridge `inner` merge 在无重叠时静默返回 `inf`**
`kronos/research/backtest/freqtrade_bridge.py:96-113` — 两条权益曲线时间戳零重叠时，返回 `float("inf")` 指标而非抛出明确的数据错误。

### 预建契约（非 Bug — 开发节奏有意为之）

以下模块在 `docs/AGENT_MVP_EXECUTION_PLAN.md` 的 B2-B3 批次中明确标记为 "skeleton 完成"——契约定义+测试完备，但集成批次尚未排到。**这不是死代码或 bug**，不应视为缺陷。

| 模块 | 行数 | 批次 | 说明 |
|------|------|------|------|
| `agent/state_machine.py` | ~175 | B2.T5, B2.T7 | CandidateLifecycleMachine + FailureConvergenceGuard |
| `agent/idle.py` | ~100 | B2.T6 | AgentIdleScanner（标注 "skeleton 完成"） |
| `agent/queue.py` | ~80 | B2.T2 | AgentResearchQueue |
| `agent/analyzer.py` | ~120 | B4.T3 | SelectiveKnowledgeWriter |
| `agent/prompts.py` | ~70 | B3.T1, B3.T3 | PromptVersionStore |
| `factor/materialize.py` | ~130 | P1-FP | 因子物化 ETL 库 |
| `agent/tools.py` 部分定义 | — | B4 | research_workbench/watchlist_evidence tool 定义（handler 待排） |
| `agent/llm.py` LLM event bridge | — | B3 | build/write_llm_invocation_event（集成待排） |

**注意**：这些模块应该在后续开发计划中排入集成批次，而不是放在这里当 bug 修。

### 实际 Bug（非计划内）

**M7. `compute_ic_series()` 定义但无人调用**
`kronos/factor/validation/metrics.py:100-131` — 导出但零生产/测试引用。这不在执行计划中，是真正的遗漏。

**M8. portfolio/risk/notify 三方工作流入口无调用方**
`construct_with_risk_review`、`emit_risk_notification`、`should_rebalance` — 仅在测试中调用。执行计划中 P3 标注为"基础能力已有，等候选通过验证后启动"，但连接代码应补一个集成 smoke test。

**M9. 4 个 AgentErrorCategory 值从未使用**
`kronos/agent/types.py:80-91` — `INPUT_DATA`、`REPORTING`、`WEB_API`、`TIMELINE_RECOVERY` 定义但从未在生产代码中实例化。合理的预定义，但应在对应错误路径中实际使用。

### 设计不一致

**M15. `_apply_volatility_target` 从未使用 target_volatility 的值**
`kronos/portfolio/allocator.py:87-108` — 只要 `target_volatility` 不为 None，行为完全相同（risk parity），配置的数值被忽略。

**M16. `experiment_root` 在两处定义，行为不一致**
`kronos/research/experiments/artifacts.py`（创建目录）vs `ledger.py`（不创建目录）。

**M17. 回测 `git_commit` 和 `data_snapshot_id` 硬编码 `"unknown"`**
`kronos/research/backtest/engine.py:112-114` — 即使调用方传入了真实值，也被引擎覆盖。

**M18. walk-forward `_stability_summary` 返回 NaN（非 JSON 安全）**
`kronos/research/walkforward/core.py:186-194` — 窗口过少时返回 `float("nan")`，部分 JSON 序列化路径会崩溃。

**M19. `execution_delay_bars` 和 `SUPPORTED_TIMEFRAMES` 在两处重复定义**
`kronos/research/backtest/engine.py:142` — `freq_map` 是 `config.py` 中 `SUPPORTED_TIMEFRAMES` 的拷贝，值在不同单位。

**M20. `fetch_exchange_info()` 无重试逻辑**
`kronos/data/loaders/exchange_info.py:38-51` — 其他 API 调用使用 `_request_with_retry(max_retries=5)`，唯独 exchangeInfo 无重试。

---

## MINOR

完整 47 项按模块分组：

### 数据层
| # | 描述 | 文件 |
|---|------|------|
| m1 | Dedup key 常量为可变 list，应为 tuple | `schemas/*.py` |
| m2 | `load_liquidations()` 指向不存在的数据集 | `data/__init__.py` |
| m3 | `validate_symbol` 每次调用重新读 Parquet | `exchange_info.py` |
| m4 | `coverage()` 在循环中创建/销毁 DuckDB 连接 | `query.py` |
| m5 | `write_partition` 捕获裸 `Exception` | `parquet_store.py` |
| m6 | `_save_raw` 函数体内 import Path | `sync.py` |
| m7 | 分区按 `event_time` 分月而非 PIT anchor `available_at` | `parquet_store.py` |

### 因子层
| # | 描述 | 文件 |
|---|------|------|
| m8 | `compute_all()` 无操作 try/except | `registry.py:218-219` |
| m9 | `compute_turnover()` 死代码循环和表达式 | `metrics.py:244,248-254` |
| m10 | `_assert_protocol()` 定义但从未调用 | `base.py:150-151` |
| m11 | 未使用的重导出（noqa: F401） | `base.py:16-20` |
| m12 | `materialize.py` 冗余 `pass` 语句 | `materialize.py:28` |
| m13 | `compute_params_hash` 值→字符串转换可能冲突 | `registry.py:434-437` |
| m14 | IC 最小观测数硬编码 10 | `metrics.py:85` |
| m15 | Walkforward 门禁未实现，靠调用方传入 bool | `pipeline.py` + `registry.py` |

### 研究层
| # | 描述 | 文件 |
|---|------|------|
| m16 | `_json_safe` 在 6 个文件中重复定义 | `agent_planner.py` 等 |
| m17 | `validate_pit_contract` 冗余检查 | `backtest/validators.py:53-63` |
| m18 | `CrossValidationResult.status` 用 string 而非 bool | `backtest/types.py` |
| m19 | `rebuild_ledger_index` 不处理重复 run_id | `experiments/ledger.py` |
| m20 | walk-forward 产物路径 `run_id` 重复嵌套 | `walkforward/reporting.py` |
| m21 | `compare_runs` TOCTOU 竞态 | `experiments/query.py` |
| m22 | 知识库 FTS5 MATCH 不过滤特殊字符 | `knowledge_base/store.py` |

### Portoflio / Risk / Notify
| # | 描述 | 文件 |
|---|------|------|
| m23 | `TelegramNotifier` 无网络异常处理 | `notify/notifier.py` |
| m24 | `emit_risk_notification` fallback body 死代码 | `risk/engine.py:113` |
| m25 | RiskConfig 硬编码默认值依赖领域假设 | `risk/engine.py:16-27` |
| m26 | `mix_scores` 硬编码 1/N 策略权重 | `portfolio/mixing.py:23` |
| m27 | `construct()` 元数据手动逐字段复制 | `portfolio/allocator.py:38-44` |

### Agent
| # | 描述 | 文件 |
|---|------|------|
| m28 | Supervisor `publish_run_snapshot` 不校验事件 run_id 一致性 | `supervisor.py` |
| m29 | LLM 重试无退避延迟 | `llm.py:205-228` |
| m30 | `WAITING_CONFIGURATION` 映射到 `WAITING_APPROVAL` 语义不匹配 | `llm.py:380-385` |
| m31 | `AgentOutput` validator 用裸 ValueError | `types.py:292` |
| m32 | `_is_secret_like_key` substring 匹配过于激进 | `events.py:13-20` |
| m33 | 事件时间线双重存储无一致性契约 | `planner.py` + `supervisor.py` |

### Web / CLI
| # | 描述 | 文件 |
|---|------|------|
| m34 | 缺少 CORS 中间件 | `web/app.py` |
| m35 | `run_today` 缺少 `try/except DataError` | `cli/main.py:577-610` |
| m36 | SSE 端点非真流式，全部加载到内存 | `web/routes/events.py:33-51` |
| m37 | `list_events` 和 `/stream` 功能重复 | `web/routes/events.py` |
| m38 | AgentRunBriefResponse.status 用 str 而非 enum | `web/schemas.py:102` |
| m39 | `agent_conclude` 用 `""` 而非 `...` 做默认值 | `cli/main.py:784-788` |
| m40 | `data_sync` 捕获裸 Exception | `cli/main.py:99` |
| m41 | `import_material` JSONL 并发写竞态 | `web/routes/materials.py:37-39` |
| m42 | provider 路径解析逻辑重复 | `web/routes/agent.py:63-82` |
| m43 | provider 名称规范化不一致 | `web/routes/settings.py` |
| m44 | `sample_config_path` fixture 用错键名 | `tests/conftest.py` |
| m45 | 缺少 404/validation error 路径测试 | `tests/integration/web/` |
| m46 | Schema 测试覆盖不足（仅 2 个测试） | `tests/integration/web/test_schemas.py` |
| m47 | CLI 测试 `.output` vs `.stdout` 不一致 | `tests/integration/test_cli.py` |

---

## 测试质量评估

| 维度 | 评估 |
|------|------|
| 覆盖率 | 91.11%，良好 |
| Happy path 覆盖 | 强 — 核心流程和基本异常路径都有测试 |
| 边界条件覆盖 | 弱 — 空 DataFrame、NaN 传播、单标的、极端数值测试缺失 |
| 错误路径覆盖 | 弱 — 404、validation error、损坏文件、并发写测试缺失 |
| 分页测试 | 仅 OI 有，klines/funding 缺失 |
| 集成测试真实性 | 中 — mock 为主，真实 E2E 受限于 SOCKS 代理 |

---

## 预建契约统计（非死代码）

以下模块按 `docs/AGENT_MVP_EXECUTION_PLAN.md` 在 B2-B4 批次中预先构建，契约+测试完备，等待后续批次集成。**不应视为缺陷**。

| 模块 | 行数 | 构建批次 | 状态 |
|------|------|----------|------|
| `agent/state_machine.py` | ~175 | B2.T5, B2.T7 | 骨架完成，待集成 |
| `agent/idle.py` | ~100 | B2.T6 | skeleton 完成 |
| `agent/queue.py` | ~80 | B2.T2 | 骨架完成 |
| `agent/analyzer.py` | ~120 | B4.T3 | 骨架完成 |
| `agent/prompts.py` | ~70 | B3.T1, B3.T3 | 骨架完成 |
| `factor/materialize.py` | ~130 | P1-FP | ETL 库完成 |
| **合计** | **~675** | 预建完毕，集成批次待排 |

---

## 整体评价

代码质量**中上**——架构清晰、协议一致、覆盖率 91%、类型检查严格。

约 675 行的预建契约（状态机、空闲扫描器、研究队列等）按 `docs/AGENT_MVP_EXECUTION_PLAN.md` 提前构建+测试完毕，等待后续批次集成。这是**骨架先行策略**，不是缺陷。

真正需要修的集中在：**安全**（路径穿越、SQL 注入）、**数据完整性**（schema 未用于生产校验）、**核心不变量**（run_id 断裂、execution_delay_bars 被忽略）、**Secret 安全**（脱敏逻辑三处重复定义）。

---

## 建议修复优先级

### 本周（安全 + 数据完整性）
1. C1 — Web 路径穿越（3 处）
2. C2 — SQL 注入
3. C3 — 生产数据无 schema 校验
4. C7 — Secret 脱敏三处重复

### 本月（核心不变量 + Bug）
5. C4 + M1 — 回测 `execution_delay_bars` 被忽略
6. C5 + M17 — run_id 线程断裂
7. C6 — 知识库 batch_id/run_id 混用
8. M3 — Parquet 损坏静默掩盖
9. 预建契约集成 — 将 B2-B4 骨架模块纳入后续开发计划，安排集成批次
10. C8 — 审批中心 stub

### 持续
11. 测试边界条件补齐
12. 重复代码提取（`_json_safe`、路径解析、配置重复）
13. MINOR 项目逐步清理
