# Binance Connector Migration Note

更新时间：2026-04-25

## 当前结论

Kronos 数据层当前不依赖 `binance-futures-connector` 的运行时代码。实际行情采集路径是：

Binance USDM public REST API -> `httpx` -> Kronos schema -> raw / curated storage

因此，本轮处理 deprecated connector 风险的正确动作不是立刻引入新的 SDK，而是先移除未使用且已废弃的旧依赖，固定当前 REST adapter 边界，并把未来 modular SDK 的接入点限制在明确的 spike 任务里。

## 已完成

- 从 `pyproject.toml` 移除 `binance-futures-connector`。
- 移除 mypy 配置里已经不需要的 `binance.*` 忽略项。
- 保留当前 `httpx` REST adapter，因为它已经覆盖 K 线、funding、OI 和 exchangeInfo 的公开端点。
- 将 OpenSpec 和项目管理文档改为“Binance-first adapter”，不再把 deprecated SDK 当作既定依赖。

## 当前 adapter 边界

| 数据 | 当前入口 | 当前实现方式 | 是否需要 API key |
|---|---|---|---|
| K 线 | `fetch_klines` | Binance USDM public REST + `httpx` | 否 |
| Funding rate | `fetch_funding_rates` | Binance USDM public REST + `httpx` | 否 |
| Open interest | `fetch_open_interest` | Binance futures data REST + `httpx` | 否 |
| Exchange info | `fetch_exchange_info` | Binance USDM public REST + `httpx` | 否 |

## 后续 modular SDK spike 条件

只有出现以下情况，才启动 Binance modular SDK spike：

1. 数据层需要不适合直接 REST 维护的新端点。
2. 执行层开始设计，需要签名请求、订单、账户、仓位、testnet 和错误码语义。
3. 当前 `httpx` REST adapter 维护成本超过 SDK adapter。

## spike 验收标准

未来 spike 不应直接替换主链路。先完成以下验证：

1. 用 modular SDK 拉取和当前 REST adapter 等价的 K 线、funding、OI、exchangeInfo 样本。
2. 输出字段能无损转换为现有 Kronos schema。
3. 错误处理、限流、重试和超时语义可控。
4. 能在测试里注入 fake client，不让单元测试访问真实网络。
5. 不把 SDK 对象泄漏到数据层以外。

## 暂不做

- 暂不引入 `binance-connector-python` 或 modular SDK 运行时依赖。
- 暂不做 ccxt 多交易所抽象。
- 暂不重写当前已可测试的 REST adapter。
- 暂不把执行层 SDK 设计提前塞进数据层。
