# 商品上架 Agent 架构演进案例

这个仓库展示一个面向电商上架场景的 AI Agent 项目: 输入 B2B 货源链接, 输出可发布的商品标题、属性、主图、详情图和详情长图。

项目围绕“如何把一条货源链接稳定变成商品上架资产”展开。主展示页用四个真实案例呈现架构演进: 从固定 Workflow, 到单 Agent + 多工具, 再到多专职 Agent 工作流, 最后进入 Claude Agent SDK 执行闭环。

## 在线展示

主展示页:

https://vincent-zhengwen.github.io/product-listing-agent-case-study/

本地打开:

- `evolution/index.html`

## 你可以看到什么

- 四阶段架构演进: 每一阶段对应一种 Agent 组织方式。
- 真实生成产物: 每个阶段都展示对应的主图和详情图。
- 上架交付链路: 货源理解、事实约束、图片规划、产物检查。
- 公开工程切片: runner、数据契约、事实校验、交付检查和 playbook 示例。

## 代表案例

最终阶段使用一款棉麻彩色桌布作为交付案例。原始货源页包含商品图片、材质、规格、批发代理、跨境供货和工厂信息; Agent 需要保留可发布的商品事实, 并过滤不适合出现在 C 端买家页里的供货语境。

生成结果包括:

- 5 张 800x800 主图
- 8 屏详情图
- 1 张详情长图
- 标题和商品属性摘要

## 仓库结构

```text
.
├── evolution/                    # 主展示页: 四阶段架构演进和真实产物
├── examples/
│   └── tablecloth/               # 桌布案例输入、输出和资产清单
├── playbooks/                    # 脱敏版上架 Agent playbook
├── src/                          # 公开工程切片
│   ├── contracts.py
│   ├── runner_example.py
│   └── tools/
└── docs/
    ├── agent-capabilities.md
    ├── engineering-architecture.md
    ├── agent-sdk-design.md
    ├── evaluation-and-lessons.md
    └── io-contract.md
```

## 工程说明

- [Agent 核心能力](docs/agent-capabilities.md)
- [工程架构与演进](docs/engineering-architecture.md)
- [Agent SDK 设计](docs/agent-sdk-design.md)
- [输入输出结构](docs/io-contract.md)
- [桌布案例输入输出](examples/tablecloth/README.md)
- [公开版 Playbook](playbooks/listing_agent_playbook.md)

## 公开边界

仓库只保留展示所需的生成结果、案例输入输出摘要、公开工程切片和工程说明文档。完整抓取实现、账号凭据、数据库、原始页面快照和非必要商家信息不公开。

质量评估体系已作为独立项目展示, 本仓库只保留与商品上架 Agent 交付相关的质量边界说明。
