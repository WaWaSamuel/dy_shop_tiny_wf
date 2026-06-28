# 历史角色：上架准备 Agent

## 定位

这是一个 **已被 skill 替代的历史 agent 定义**。

当前执行路径必须由 `listing-readiness-check` skill 承载；本 agent 不再作为 workflow 节点被调用。

本文件只保留历史边界：上架准备度检查是商品部和内容素材部之间的门槛检查，不是发布动作，也不是人工确认。

## 历史专业画像

- 原能力对应上架准备度检查专家，擅长判断商品、货源、素材、价格、库存、类目和风险说明是否齐全。
- 熟悉从候选、供应链、内容素材到上架前确认之间的门槛条件和缺失项表达。
- 擅长给出“可继续 / 需补充 / 建议暂停”的准备度结论，而不是替代真实发布动作。
- 当前该专业能力已经沉淀到 `listing-readiness-check` skill，本 agent 只保留迁移说明，不再作为执行角色。

## 历史职责

- 检查信息是否齐全
- 判断素材、价格、库存、类目、风险说明是否具备
- 给出“可继续 / 需补充 / 建议暂停”的结论

## 当前替代关系

- 替代 skill：`listing-readiness-check`
- 所属 workflow：`ecommerce_workflow`、`product_department_workflow`、`content_material_department_workflow`
- 上游消费者：商品候选结果、供应链结果、内容素材结果
- 下游消费者：`human-gate-approval`、`workflow-archive-report`

## 输入

- 当前商品结果
- 货源结果
- 素材结果
- 上架前检查项

## 输出

- 上架准备结论
- 缺失项
- 风险摘要
- 是否建议进入最终确认

## 边界

- 不直接执行发布
- 不把明显缺资料的对象硬说成可上架
- 不接管异常订单或归档职责
- 不发送 IM，不替代 `human-gate-approval`
- 不再声明默认下一跳，真实流转以 workflow yaml 和 `listing-readiness-check` 输出为准

## 保留原因

用于帮助维护者理解 `listing-readiness-check` 的来源、职责边界和迁移关系，避免未来把同一能力重新做回 agent。
