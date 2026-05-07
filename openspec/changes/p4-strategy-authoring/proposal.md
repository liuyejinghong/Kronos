## Why

Kronos 现在已经具备稳定的研究底座：数据、因子、验证、回测、实验和 `strategy init-r-breaker / validate / smoke-test / register`。但用户仍需要手工把策略想法翻译成 TOML，这会让“从想法到研究对象”的路径太长，也容易让产品只剩工程入口，没有真正的策略创建体验。

v0.4.3 的目标不是再加一个自由文本聊天框，而是把自然语言策略想法接到现有的策略配置与验证链路上，让用户能先得到策略概要，再得到可编辑草案，最后沿现有验证流程继续推进。

## What Changes

- 新增 AI 辅助策略起草流程，把自然语言策略想法转成结构化策略概要和 TOML 草案。
- 新增模板驱动的策略意图识别，首版只允许命中当前支持的策略模板，不支持的意图必须明确拒绝。
- 新增澄清问题和默认假设的展示方式，避免系统静默补全关键参数。
- 新增 `kronos strategy draft` 这类用户入口，并让 `kronos agent start` 可以把“我有一个策略想法”导向起草流程。
- 明确草案必须进入现有 `validate → smoke-test → register` 链路，不能绕过现有策略配置体系。

## Capabilities

### New Capabilities

- `strategy-authoring`: 自然语言策略起草——把用户描述的交易想法转成结构化概要和可验证的 TOML 草案。

### Modified Capabilities

- `agent-runtime`: Agent console 需要识别“我有一个想法”这类意图，并导向策略起草流程。
- `agent-observability`: 策略起草过程需要保留 prompt / model / artifact traceability。
- `agent-workbench`: 研究工作台需要能读到草案结果和后续验证结果，而不是只显示工程层面文本。
- `strategy-config`: 现有策略配置和校验流程必须继续作为草案落地的唯一出口。

## Impact

- **新增用户入口**：`kronos strategy draft`
- **新增体验路径**：Agent console 的“我有一个策略想法”分支
- **新增产物**：策略概要、策略草案、可追溯日志、验证接力
- **约束**：不新增策略引擎、不绕过 validate/smoke-test/register、不引入模拟盘或实盘
