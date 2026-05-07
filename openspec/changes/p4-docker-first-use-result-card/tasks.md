## 1. 结果卡

- [x] 1.1 `report latest` 第一屏输出数据来源、样本范围、评估对象、结论、可信度和下一步
- [x] 1.2 `quickstart` 自动研究完成后复用同一结果卡
- [x] 1.3 sample 场景明确标注流程试跑，不代表策略有效性

## 2. 策略下一步文案

- [x] 2.1 `strategy draft` 成功后先解释检查配置、空跑确认、进入候选池
- [x] 2.2 `strategy init-r-breaker` 输出同样的交易语言下一步
- [x] 2.3 Agent 策略起草分支复用同样的下一步文案

## 3. Docker 首次入口

- [x] 3.1 Docker entrypoint 解释首次运行的环境准备和 sample 报告边界
- [x] 3.2 quickstart 的 Docker 下一步先指向 `report latest`

## 4. 文档与验证

- [x] 4.1 同步 README / README.en / CHANGELOG / TODO / PROJECT_STATUS / ROADMAP / 产品设计文档
- [x] 4.2 运行 targeted tests、ruff、mypy、非 e2e 测试和 Docker 首次路径验证
