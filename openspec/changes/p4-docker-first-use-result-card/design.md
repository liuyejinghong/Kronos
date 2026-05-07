## Design

### Result Card

结果卡是自动研究报告的第一屏结构，供 `quickstart` 和 `report latest` 共用。

字段顺序固定：

1. 本次结果
2. 数据来源
3. 样本范围
4. 评估对象
5. 结论
6. 可信度
7. 下一步

sample 数据必须写成“sample 流程试跑”，不能写成真实复验或有效性证明。

### Strategy Gate Translation

内部链路仍然是 `validate → smoke-test → register`。用户可见文案先翻译成：

1. 检查配置是否完整
2. 用本地数据空跑确认信号能算出来
3. 空跑通过后进入候选池，让 Agent 和报告能看到它

命令必须保留，方便 L2/L3 用户直接复制执行。

### Docker First Run

Docker entrypoint 必须先解释首次运行会准备 Python 研究环境和生成 sample 流程试跑报告。完成后只给一个主动作：读取最新报告。策略起草和 Agent 入口只能作为读完结论后的后续动作。

### Non-goals

- 不引入 verbose 模式。
- 不重构 Agent runtime。
- 不改变策略验证、候选池或报告生成的业务逻辑。
