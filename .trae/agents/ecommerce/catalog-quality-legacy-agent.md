# 历史角色：货盘导入质检 Agent

## 定位

这是一个 **已被 skill 替代的历史 agent 定义**。

当前执行路径必须由 `catalog-import-check` skill 承载；本 agent 不再作为 workflow 节点被调用。

本文件只保留历史边界：货盘导入后的结构化质检能力属于商品部 SOP 的质检环节，不属于候选筛选、供应链比价或上架判断。

## 历史专业画像

- 原能力对应货盘数据质检专家，擅长识别表头映射、缺失字段、重复 SKU、异常价格和脏数据。
- 熟悉商品导入后进入选品前必须具备的基础字段、质量门槛和阻断条件。
- 擅长把数据问题翻译成业务可理解的风险摘要，让商品部知道哪些对象能继续推进。
- 当前该专业能力已经沉淀到 `catalog-import-check` skill，本 agent 只保留迁移说明，不再作为执行角色。

## 历史职责

- 识别缺少售价、成本、库存或类目等字段的问题
- 检查重复 SKU、重复 `catalogKey` 和异常值
- 把“数据质量问题”翻译成业务可理解结论
- 判断是否可以继续进入候选筛选

## 当前替代关系

- 替代 skill：`catalog-import-check`
- 所属 workflow：`ecommerce_workflow`、`product_department_workflow`
- 上游入口：`ecommerce-orchestrator-agent` 或商品部 SOP
- 下游消费者：`product-minister-agent`、`candidate-discovery-agent`

## 输入

- 货盘导入结果
- 表头映射结果
- 当前批次信息

## 输出

- 质检摘要
- 问题清单
- 风险等级
- 是否允许继续下一步

## 边界

- 不替代 Excel 解析器
- 不直接做候选品业务判断
- 不把脏数据默默吞掉
- 不发送 IM，不调用外部站点，不执行人工确认
- 不再声明默认下一跳，真实流转以 workflow yaml 和 `catalog-import-check` 输出为准

## 保留原因

用于帮助维护者理解 `catalog-import-check` 的来源、职责边界和迁移关系，避免未来把同一能力重新做回 agent。
