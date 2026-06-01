# 货郎评测中心 Lite

这是货郎 Listing Agent 评测中心的公开展示版。它保留真实工程结构和核心代码，用来说明如何把一个商品上架 Agent 做成可诊断、可回归、可追踪的 Eval Harness。

公开版做了脱敏和收敛：

- 保留：Next.js 前端、FastAPI 后端、数据集/实验/诊断/报告路由、Trace Viewer、Grader 结果、Failure Coding、值班报告生成逻辑。
- 移除：私有环境变量、真实 SQLite 数据库、运行日志、浏览器 profile、原始抓取页面、平台账号相关文件、历史构建产物。
- 替换：默认数据库名改为 `portfolio_eval_demo.sqlite`，fixture 目录用于放公开演示数据。

## 目录结构

```text
eval-platform-lite/
├── frontend/          # Next.js 评测中心前端
├── backend/           # FastAPI API、grader、report generator
└── fixtures/          # 公开版脱敏样例数据说明
```

## 能力重点

- 数据集管理：把真实上架 case 固化为可复测样本。
- 实验管理：每次 Agent、prompt、工具链变化都沉淀为一次可复现实验。
- 单 case 诊断：对照 source facts、Agent output、trace、grader evidence 和人工审核结论。
- Grader 分层：区分 run validity、outcome、grounding、conversion、listing quality、process。
- Failure Coding：把零散失败沉淀为可统计、可修复的 failure mode。
- 值班报告：把一轮实验汇总成健康分、问题模式和下一轮修复建议。

## 本地运行

后端：

```bash
cd eval-platform-lite/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

前端：

```bash
cd eval-platform-lite/frontend
npm install
npm run dev -- --port 3001
```

然后打开 `http://localhost:3001`。

## 公开说明

这个目录不是完整私有工作台备份，而是面向作品集的公开版代码包。真实业务数据、账号凭据、原始抓取文件和运行数据库不在仓库中发布。
