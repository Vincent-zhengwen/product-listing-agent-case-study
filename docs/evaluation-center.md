# 货郎评测中心

货郎评测中心是 Listing Agent 的诊断式 Eval Harness。它不是只看一个总分的后台，而是把真实上架 case、Agent 运行过程、生成结果、grader evidence 和人工审核组织成一个可回归的质量闭环。

## 为什么需要它

商品上架 Agent 的失败不是单一问题。它可能是 source facts 缺失、标题事实漂移、主图重复、详情页说服力不足、B2B 供货话术泄漏，也可能是工具调用或持久化失败。

所以评测中心要回答四个问题：

1. 这次评测是否可信：source snapshot、trace、图片 artifact 是否完整。
2. 这条 listing 是否可发布：标题、属性、主图、详情图是否达到发布门槛。
3. 这条 listing 是否值得发布：文案是否像面向消费者的商品页，图片是否有点击和转化价值。
4. 失败发生在哪里：source_fetch、copy、image_plan、render、qa、persistence 等哪个阶段出了问题。

## 核心模块

- 数据集：沉淀高质量、低质量、争议 case，形成稳定回归集。
- 实验：每次 Agent、prompt 或工具改动都新建实验，避免覆盖历史结果。
- 结果诊断：把 source facts、Agent output、trace、grader 和人工审核放在同一页。
- 诊断分析：统计 failure code、root cause hotspot 和版本对比。
- 值班报告：把一次实验总结成健康分、质量分、FATAL/WARNING 问题和下一轮建议。

## Grader 设计

评测分为六层：

- Run Validity：本次运行是否可信。
- Outcome：最终结果是否达到基本发布门槛。
- Grounding：文案和图片是否忠于 source facts。
- Conversion：是否使用 C 端买家能理解的表达。
- Listing Quality：标题、卖点、主图、详情页是否像一条能卖货的 listing。
- Process：Agent 执行过程是否健康。

这套设计的重点不是一次性打分，而是帮助产品和工程团队知道“下一轮应该修哪里”。

## 展示入口

- 静态可点击 Demo：`eval-center/index.html`
- 公开版代码：`eval-platform-lite/`
