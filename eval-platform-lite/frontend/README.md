# 评测中心前端

这是货郎评测中心公开版的 Next.js 前端源码，保留数据集、实验、诊断分析、值班报告和单 case 诊断页面。

## Getting Started

先启动 `eval-platform-lite/backend`，再运行前端：

```bash
npm run dev
```

默认通过 `next.config.ts` 将 `/api/*` 转发到本地 FastAPI 后端。

打开 `http://localhost:3000` 查看页面。

## 关键文件

- `app/page.tsx`: 首页和最新实验概览。
- `app/datasets/`: 数据集与 case 管理。
- `app/tasks/`: 实验列表、实验详情、结果详情。
- `app/analysis/`: failure coding、实验对比和问题热点。
- `app/reports/`: 值班报告列表和报告详情。
- `components/TraceViewer.tsx`: Agent trace 可视化。
- `components/GraderResults.tsx`: grader 分层结果展示。

## 公开版说明

这个目录保留真实页面结构和组件代码，但不包含私有数据库、运行日志、账号配置或原始抓取文件。
