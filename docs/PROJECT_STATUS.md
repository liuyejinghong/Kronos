# Kronos Project Status

> 更新时间：2026-05-06 | 当前版本：0.4.0 | 下一版本：0.4.1

## 一句话判断

v0.4.0 已经把策略入口从“内置样例”推进到“可配置产品路径”：全新用户可以运行 `uv run kronos quickstart` 产出研究报告，也可以用 `uv run kronos strategy init-r-breaker` 生成 TOML 策略配置，经过 `validate` / `smoke-test` 后用 `register` 写入候选池，供 Agent/Web 读取。

当前产品边界仍是**研究报告、Agent 复盘和策略配置试算**。Kronos 不会启动实时模拟盘、不会接入真实交易、不会自动下单。

## 当前能力

| 模块 | 状态 | 当前用户能得到什么 |
|---|---|---|
| 快速开始 | 已完成 | `kronos quickstart` 一键生成数据、注册 R-breaker、输出研究报告 |
| 最新报告 | 已完成 | `kronos report latest` 直接打印最近一次产品报告摘要 |
| 内置策略 | 已完成 | R-breaker 日内突破作为示例策略，quickstart 后可被 Agent 看到 |
| 策略配置 | 已完成 | `kronos strategy init-r-breaker` 生成 TOML，`validate` 校验，`smoke-test` 本地试算 |
| 策略注册 | 已完成 | `kronos strategy register` 默认要求烟雾测试通过，再写入候选池 |
| 报告解释 | 已完成 | 技术指标保留，同时补充交易语言解释和模拟盘边界 |
| 数据同步 | 已完成 | Binance USDM 公开 K 线 / Funding / OI，同步前说明来源、范围和无需 API Key |
| 对话 Agent | 已完成 | `kronos agent start` 可做首次用户引导、环境感知和中英文对话 |
| Web 工作台 | 已完成 | FastAPI + Next.js，本地查看候选池、时间线、报告、设置和审批入口 |
| Docker | 已完成 | `docker compose up` 可跑通 quickstart 主路径 |

## 当前不具备的能力

| 能力 | 当前状态 | 产品边界 |
|---|---|---|
| AI 自然语言创建策略 | v0.4.1 目标 | 当前只能生成 R-breaker TOML 模板，不能把任意自然语言自动变成策略 |
| 历史重放 | v0.4.x 目标 | 当前有报告、指标和烟雾测试摘要，不做逐笔/逐分钟交易回放 |
| 市场状态分段评估 | v0.4.x 目标 | 当前可信度报告已有基础解释，但没有牛/熊/震荡的独立晋升门禁 |
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

## 当前推荐顺序

1. 用真实数据跑一遍 `kronos strategy init-r-breaker` → `smoke-test` → `register`，确认交易者能独立完成配置主路径。
2. 进入 v0.4.1：AI 自然语言策略创建，但输出必须先落到 TOML 并经过同一条 smoke-test/register 闸门。
3. 再做历史重放和市场状态分段评估，让用户能理解“为什么这段表现好/差”。
4. 在没有稳定模拟盘证据前，不推进真实交易执行。

## 版本事实源

- 版本号：`VERSION`、`pyproject.toml`、README badge、`CHANGELOG.md`
- 当前待办：`TODO.md`
- 产品边界：`README.md` / `README.en.md`
- 策略系统设计：`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`
- 审查与修复方案：`docs/reviews/`
