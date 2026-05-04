# Kronos Agent MVP 交付验收说明

更新时间：2026-04-30

2026-05-01 产品复盘补充：本文件记录的是 Agent MVP 功能链路交付口径。基于普通量化交易员视角的浏览器实操复盘见 `docs/AGENT_MVP_PRODUCT_UX_REVIEW.md`；复盘结论是当前 Web 还不像可用产品。Product UX Repair Batch 第一批已完成，修正了主任务流、报告阅读、候选池信息架构和模型状态信任冲突。

## 一句话结论

Kronos Agent MVP 的功能链路已到可复查点，Web 产品体验已完成第一批可用性修复，但还没有到完整 Agent 产品验收点。

当前交付的不是自动交易系统，也不是定时日报系统，而是一个本地加密货币策略研究 Agent：它能读取上一轮研究结果，选择下一步研究方向，调用确定性工具，读取证据，输出可审计结论，并在 Web 工作台展示本轮状态。

## 验收入口

Web 工作台：

```text
http://127.0.0.1:3000
```

本地 API：

```text
http://127.0.0.1:8000
```

默认展示的交付批次：

```text
20260430-agent-mvp-delivery-v1
```

优先看这三个位置：

- Web 首页：当前状态、结论来源和下一步动作。
- Web 报告页：直接阅读本轮报告正文，技术路径折叠展示。
- Web 候选池：候选排序、当前判断、证据缺口和下一步动作。

## 这版已经能做什么

- 展示当前候选池和候选详情。
- 展示 Agent 当前研究批次、目标、结论、证据数量、风险和下一步动作。
- 展示 Agent 事件时间线。
- 在 Web 内阅读本轮 Agent 报告，不再要求用户复制本地文件路径。
- 明确展示“模型未配置时，本轮结论不是 DeepSeek 实时生成”。
- 读取真实本地研究摘要和专项证据，生成一轮 Agent 研究结论。
- 把 Agent run summary、report、event timeline 和 Web runtime 串到同一批次。
- 在设置页保存 DeepSeek API Key，并只展示脱敏状态。
- 在设置页检查 DeepSeek 是否已配置。
- 允许从 Web 导入用户研究材料。
- 保留审批中心入口，后续承接 prompt 生效、模拟盘准入和实盘申请。

## 本轮 Agent 结论

交付批次：`20260430-agent-mvp-delivery-v1`

结论：

- `trend_pullback_entry` 可以进入候选改造。
- 不进入组合。
- 不进入实盘。
- `multi_timeframe_confirmation` 仅保留观察。
- 下一轮应转向 crypto-native 机制改造，而不是每天重复跑同一批旧候选。

## 不属于当前 MVP

- 自动下单。
- 真钱实盘。
- 每天无脑定时重复跑。
- 多 Agent 长链路无限自我递归。
- 自动把候选送入组合或风控。
- 完整收益、回撤、K 线和评分走势图表。
- 完整后台 daemon 和远程访问权限体系。

## 验收清单

功能复查时只需要确认这些问题；真正的产品可用验收应以 `docs/AGENT_MVP_PRODUCT_UX_REVIEW.md` 中的下一版标准为准：

- 打开 Web 后，是否能看懂当前状态和下一步动作。
- 是否能看懂为什么研究它。
- 是否能在 Web 内直接阅读报告正文。
- 是否能进入候选池并看懂候选排序、当前判断和证据缺口。
- 是否明确没有进入组合或实盘。
- 设置页是否能看出 DeepSeek 当前是否已配置。
- Agent 时间线是否能说明本轮做了哪些步骤。
- 报告是否能让非工程人员理解本轮结论。

## 已验证

- Agent 交付批次运行完成，状态 `completed`。
- 交付批次事件时间线 6 条，研究目录和 Web runtime 一致。
- Web summary API 返回 200。
- DeepSeek 配置状态 API 返回 200。
- 桌面和 390px 窄屏浏览器都能看到交付批次、结论和 DeepSeek 状态，且无整页横向溢出。
- 后端 targeted tests：45 passed。
- 后端 lint：passed。
- 后端 mypy：passed。
- 前端 typecheck：passed。
- 前端 lint：passed。
- 前端 build：passed。
- `git diff --check`：passed。

## 下一阶段建议

验收通过后，下一阶段不应先做交易执行。

更合理的顺序是：

1. 强化候选评分维度。
2. 让失败记忆更强地约束下一轮假设。
3. 围绕 `trend_pullback_entry` 做 crypto-native 改造 proposal。
4. 补真实实验图表。
5. 再讨论 paper / testnet 运行。
