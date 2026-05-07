## Why

v0.4.3 已经让 Docker 首次用户能从 quickstart 继续到 `report latest`、`strategy draft` 和 Agent，但 fresh clone 评测显示第一屏仍偏长，用户还需要自己拼出这次跑了什么、用了什么数据、结论能不能信、下一步做什么。

v0.4.4 的目标不是扩展策略能力，而是把首次体验的解释链路收口成稳定结果卡，并把策略起草后的内部闸门翻译成交易者能理解的下一步。

## What Changes

- `quickstart` 自动研究完成后展示与 `report latest` 一致的结果卡。
- `report latest` 第一屏固定展示数据来源、样本范围、评估对象、结论、可信度和下一步。
- `strategy draft`、Agent 策略起草分支和 `strategy init-r-breaker` 对外先讲“检查配置、空跑确认、进入候选池”，再给可复制命令。
- Docker entrypoint 明确首次运行会准备环境和生成 sample 流程试跑报告，完成后只强调先读最新报告。

## Capabilities

### Modified Capabilities

- `quickstart-onboarding`: 首次体验必须先回答结果边界和下一步。
- `report-latest`: 最新报告摘要必须以结果卡作为第一屏。
- `strategy-authoring`: 起草后的验证链路必须保留，但对外文案先使用交易语言。
- `docker-onboarding`: Docker 默认入口必须解释首次运行噪音，并把主下一步收敛到读取最新报告。

## Impact

- **用户可见变化**：Docker 首次运行后更像产品结果页，而不是工程日志和命令列表。
- **不变约束**：不新增模拟盘、实盘、历史重放、新策略模板或任意代码生成。
- **验收重点**：sample 场景必须始终说明“流程试跑，不代表策略有效性”。
