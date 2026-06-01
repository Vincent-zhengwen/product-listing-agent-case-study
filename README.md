# 货郎商品上架 Agent 作品集

这是一个面向电商上架场景的 AI Agent 作品集。它从 B2B 货源链接中提取真实商品事实, 过滤批发供货语境, 生成可用于 C 端商品发布的标题、属性、主图、详情页和详情长图。

当前展示案例是一款棉麻彩色桌布。原始货源页同时包含商品图片、规格、材质、批发代理、跨境供货和工厂信息; Agent 将其中可发布的商品事实转译为消费者能理解的商品页资产。

## 在线展示

作品集首页:

https://vincent-zhengwen.github.io/product-listing-agent-case-study/

核心页面:

- 最终上架资产 Demo: https://vincent-zhengwen.github.io/product-listing-agent-case-study/demo/
- Agent 四阶段演进: https://vincent-zhengwen.github.io/product-listing-agent-case-study/evolution/
- 评测中心静态 Demo: https://vincent-zhengwen.github.io/product-listing-agent-case-study/eval-center/

本地直接打开:

- `demo/index.html`
- `evolution/index.html`
- `eval-center/index.html`

这些页面是 GitHub Pages 友好的纯静态 HTML, 不依赖后端服务。

## 案例来源

- 货源链接: https://www.yiwugo.com/product/detail/982191293.html
- 商品: 跨境棉麻加厚彩色桌布花朵异域东南亚台布
- 生成结果: 5 张 800x800 主图, 8 屏详情图, 1 张详情长图

## 核心亮点

- 货源理解: 从商品页抽取材质、品类、颜色、尺寸、风格等可发布事实。
- 语境转换: 将供货、代理、跨境等 B2B 信息转译为买家能理解的商品表达。
- 类目化规划: 按桌布购买决策组织铺桌首图、尺寸规格、面料纹理、边缘垂坠和浅底确认。
- 交付完整度: 一次输出标题、属性、5 张主图、8 屏详情图和详情长图。
- 工程约束: 通过事实校验、图片角色约束和交付检查, 降低长链路生成的不稳定性。
- 评测闭环: 用数据集、实验、trace、grader、failure coding 和值班报告支撑 Agent 持续迭代。

## 仓库结构

```text
.
├── demo/                         # 静态展示页和生成图片资产
├── evolution/                    # Agent 架构演进展示
├── eval-center/                  # 评测中心静态可点击 Demo
├── eval-platform-lite/           # 脱敏后的评测中心真实代码结构
├── docs/
│   ├── agent-capabilities.md     # Agent 核心能力说明
│   ├── engineering-architecture.md # 工程架构与演进说明
│   ├── evaluation-and-lessons.md # 评估标准与迭代经验
│   ├── evaluation-center.md      # 评测中心设计说明
│   └── io-contract.md            # 输入输出结构说明
└── examples/
    └── tablecloth/               # 棉麻桌布案例输入输出摘要
```

## 工程说明

- [Agent 核心能力](docs/agent-capabilities.md)
- [工程架构与演进](docs/engineering-architecture.md)
- [评估与迭代经验](docs/evaluation-and-lessons.md)
- [评测中心设计](docs/evaluation-center.md)
- [输入输出结构](docs/io-contract.md)
- [桌布案例输入输出](examples/tablecloth/README.md)
- [评测中心 Lite 代码说明](eval-platform-lite/README.md)

## 仓库内容

仓库保留展示所需的生成结果、静态 demo、公开版评测中心代码、案例输入输出摘要和工程说明文档。账号凭据、真实运行数据库、原始抓取页面、浏览器 profile、运行日志和非必要商家信息不作为公开内容发布。
