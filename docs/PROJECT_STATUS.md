# Kronos Project Status

> 更新时间：2026-05-06 | 当前版本：0.3.4 | 下一版本：0.4.0

## 一句话判断

v0.3.4 已经完成首次研究闭环和审查问题根因修复：全新用户可以运行 `uv run kronos quickstart`，生成 sample 数据，注册 R-breaker，跑出研究报告，并用 `uv run kronos report latest` 直接查看最新结论；开发验证流程不再默认读写真实候选池。

当前产品边界仍是**研究报告和 Agent 复盘**。Kronos 不会启动实时模拟盘、不会接入真实交易、不会自动下单。

## 当前能力

| 模块 | 状态 | 当前用户能得到什么 |
|---|---|---|
| 快速开始 | 已完成 | `kronos quickstart` 一键生成数据、注册 R-breaker、输出研究报告 |
| 最新报告 | 已完成 | `kronos report latest` 直接打印最近一次产品报告摘要 |
| 内置策略 | 已完成 | R-breaker 日内突破作为示例策略，quickstart 后可被 Agent 看到 |
| 报告解释 | 已完成 | 技术指标保留，同时补充交易语言解释和模拟盘边界 |
| 数据同步 | 已完成 | Binance USDM 公开 K 线 / Funding / OI，同步前说明来源、范围和无需 API Key |
| 对话 Agent | 已完成 | `kronos agent start` 可做首次用户引导、环境感知和中英文对话 |
| Web 工作台 | 已完成 | FastAPI + Next.js，本地查看候选池、时间线、报告、设置和审批入口 |
| Docker | 已完成 | `docker compose up` 可跑通 quickstart 主路径 |

## 当前不具备的能力

| 能力 | 当前状态 | 产品边界 |
|---|---|---|
| AI 自然语言创建策略 | v0.4.0 目标 | 当前只能使用内置 R-breaker 和手动注册候选 |
| TOML 策略配置文件 | v0.4.0 目标 | 当前没有稳定的 `~/.kronos/strategies/*.toml` 产品入口 |
| 历史重放 | v0.4.0 目标 | 当前有报告和关键指标，不做逐笔/逐分钟交易回放 |
| 实时模拟盘 | v0.4.0 目标 | 当前不会连接实时虚拟订单引擎 |
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

1. 完成并验证 `docs/reviews/KRONOS_REVIEW_FIX_PLAN_20260506.md` 中的修复。
2. 用 `uv run pytest -m "not e2e"` 重新确认本地验证不会触碰真实候选池。
3. 再进入 v0.4.0 主线：AI / TOML 策略创建、历史重放、实时模拟盘。
4. 在没有稳定模拟盘证据前，不推进真实交易执行。

## 版本事实源

- 版本号：`VERSION`、`pyproject.toml`、README badge、`CHANGELOG.md`
- 当前待办：`TODO.md`
- 产品边界：`README.md` / `README.en.md`
- 策略系统设计：`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`
- 审查与修复方案：`docs/reviews/`
