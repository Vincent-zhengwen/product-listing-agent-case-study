"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  BarChart2,
  Database,
  FileText,
  Image as ImageIcon,
  PlayCircle,
  Target,
} from "lucide-react";

type HomeStats = {
  datasets: any[];
  tasks: any[];
  reports: any[];
  latestReport: any | null;
  latestReportDetail: any | null;
  completedTasks: any[];
};

const isImageIssue = (issue: any) => {
  const text = [
    issue?.code,
    issue?.field,
    issue?.reason,
    issue?.impact,
    issue?.suggested_fix,
  ].filter(Boolean).join(" ").toLowerCase();
  return /image|main|detail|visual|photo|picture|图片|主图|详情图|详情页|构图|素材|首图/.test(text);
};

const formatValue = (value: any, fallback = "—") => {
  if (value === null || value === undefined || value === "") return fallback;
  return value;
};

const healthColor = (score: number | null) =>
  score === null ? "var(--muted)" : score >= 80 ? "var(--green)" : score >= 60 ? "var(--orange)" : "var(--red)";

export default function Home() {
  const [stats, setStats] = useState<HomeStats | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      fetch("/api/datasets").then(r => r.json()).catch(() => []),
      fetch("/api/tasks").then(r => r.json()).catch(() => []),
      fetch("/api/reports").then(r => r.json()).catch(() => []),
    ]).then(async ([datasets, tasks, reports]) => {
      const latestReport = reports[0] || null;
      const latestReportDetail = latestReport?.id
        ? await fetch(`/api/reports/${latestReport.id}`).then(r => r.json()).catch(() => null)
        : null;
      if (cancelled) return;
      setStats({
        datasets,
        tasks,
        reports,
        latestReport,
        latestReportDetail,
        completedTasks: tasks.filter((t: any) => t.status === "completed"),
      });
    });

    return () => { cancelled = true; };
  }, []);

  const derived = useMemo(() => {
    const latestReport = stats?.latestReport || null;
    const reportJson = stats?.latestReportDetail?.report_json || {};
    const qualityIssues = Array.isArray(reportJson.quality_issues) ? reportJson.quality_issues : [];
    const imageIssueCount = qualityIssues.filter(isImageIssue).length;
    const activeDatasets = (stats?.datasets || []).filter((d: any) => d.status !== "archived");
    const activeCaseCount = activeDatasets.reduce((sum: number, d: any) => sum + (Number(d.case_count) || 0), 0);
    const latestCompletedTask = stats?.completedTasks?.[0] || null;
    const latestQualityScore = reportJson.listing_quality_score ?? reportJson.quality_score ?? latestReport?.quality_score ?? null;
    const latestHealthScore = latestReport?.health_score ?? null;
    const fatalCount = latestReport?.fatal_failures ?? reportJson.fatal_failures_count ?? 0;
    const warningCount = latestReport?.warning_failures ?? reportJson.warning_failures_count ?? 0;
    const totalCases = activeCaseCount || latestReport?.total_cases || 0;

    return {
      latestReport,
      reportJson,
      imageIssueCount,
      activeCaseCount,
      latestCompletedTask,
      latestQualityScore,
      latestHealthScore,
      fatalCount,
      warningCount,
      totalCases,
      qualityIssues,
    };
  }, [stats]);

  const primaryAction = (() => {
    if (!stats) return null;
    if (!stats.datasets.length) {
      return {
        title: "先建立真实上架 case 数据集",
        description: "评测中心的价值来自真实样本。先把需要长期回归的“我的上架”结果放进数据集。",
        href: "/datasets",
        label: "去创建数据集",
        tone: "var(--accent)",
      };
    }
    if (!stats.tasks.length) {
      return {
        title: "启动第一轮实验",
        description: "数据集已有样本，但还没有可复现实验。先跑一轮基线，后续 Agent 改动才有对照。",
        href: "/tasks",
        label: "新建实验",
        tone: "var(--accent)",
      };
    }
    if (derived.imageIssueCount > 0) {
      return {
        title: "优先复查图片链路",
        description: "最新一轮实验仍发现图片相关问题，建议先看诊断分析里的图片质量、素材重复和详情页证明力。",
        href: "/analysis",
        label: "查看诊断",
        tone: "var(--red)",
      };
    }
    if (derived.fatalCount > 0) {
      return {
        title: "优先确认 FATAL 失败",
        description: "最新报告仍有阻断发布的问题。先确认是否属于事实一致性、数据缺失或 Agent 步骤失败。",
        href: "/analysis",
        label: "查看失败 case",
        tone: "var(--red)",
      };
    }
    return {
      title: "复盘最新实验结论",
      description: "最新一轮实验没有明显阻断项，可以进入值班报告查看问题模式和下一轮优化方向。",
      href: derived.latestReport ? `/reports/${derived.latestReport.id}` : "/reports",
      label: "查看报告",
      tone: "var(--green)",
    };
  })();

  const actions = [
    primaryAction,
    {
      title: "沉淀回归数据集",
      description: "把高质量 case、低质量 case 和争议 case 固定下来，让每次 Agent 改动都能复测同一批样本。",
      href: "/datasets",
      label: "管理数据集",
      tone: "var(--orange)",
    },
    {
      title: "生成本轮值班报告",
      description: "将实验结果汇总成健康分、问题模式和改进建议，方便对齐下一轮修什么。",
      href: derived.latestReport ? `/reports/${derived.latestReport.id}` : "/reports",
      label: "查看值班报告",
      tone: "var(--muted)",
    },
  ].filter(Boolean) as { title: string; description: string; href: string; label: string; tone: string }[];

  const metricCards = [
    {
      icon: Target,
      label: "最新质量分",
      value: formatValue(derived.latestQualityScore),
      unit: derived.latestQualityScore === null ? "" : "/100",
      hint: derived.latestReport ? `来自最新一轮已完成实验：${derived.latestReport.report_date}` : "完成一次实验并生成报告后展示",
      color: healthColor(derived.latestQualityScore === null ? null : Number(derived.latestQualityScore)),
    },
    {
      icon: ImageIcon,
      label: "图片质量问题",
      value: derived.latestReport ? derived.imageIssueCount : "—",
      unit: derived.latestReport ? "个" : "",
      hint: "统计主图、详情图、素材重复和视觉证明力相关问题",
      color: derived.imageIssueCount > 0 ? "var(--red)" : "var(--green)",
    },
    {
      icon: AlertTriangle,
      label: "事实一致性风险",
      value: derived.latestReport ? derived.fatalCount : "—",
      unit: derived.latestReport ? "个 FATAL" : "",
      hint: `${derived.warningCount || 0} 个 WARNING 作为辅助风险信号`,
      color: derived.fatalCount > 0 ? "var(--red)" : "var(--green)",
    },
    {
      icon: Database,
      label: "当前覆盖",
      value: stats ? derived.totalCases : "—",
      unit: stats ? "个 case" : "",
      hint: stats ? `${stats.datasets.length} 个数据集，${stats.tasks.length} 次实验` : "读取评测资产中",
      color: "var(--text)",
    },
  ];

  const modules = [
    {
      href: "/datasets",
      icon: Database,
      label: "数据集",
      description: "管理测试用例集，支持手动录入和 CSV 批量导入。",
      foot: `${stats?.datasets?.length ?? "—"} 个数据集`,
    },
    {
      href: "/tasks",
      icon: PlayCircle,
      label: "实验",
      description: "每次 Agent、prompt 或工具改动都沉淀成可复现实验。",
      foot: `${stats?.tasks?.length ?? "—"} 次实验`,
    },
    {
      href: "/analysis",
      icon: BarChart2,
      label: "诊断分析",
      description: "实验对比、Failure Coding、回归热点都从 case 诊断沉淀出来。",
      foot: derived.imageIssueCount ? `${derived.imageIssueCount} 个图片问题` : "查看问题模式",
    },
    {
      href: "/reports",
      icon: FileText,
      label: "值班报告",
      description: "每日自动评测汇总，AI 分析问题模式，每天 02:00 自动生成。",
      foot: derived.latestReport ? `最新 ${derived.latestReport.report_date}` : "暂无报告",
    },
  ];

  return (
    <div style={{ padding: 32, maxWidth: 1440, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 20, marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>评测中心</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
            面向多模态 Listing Agent 迭代的诊断式 Eval Harness
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/analysis" style={btnSecondary}>查看诊断</Link>
          <Link href="/tasks" style={btnPrimary}>新建实验</Link>
        </div>
      </div>

      <section style={{ marginBottom: 20 }}>
        <div style={sectionHeader}>
          <span>最新一轮实验概览</span>
          <span style={{ color: "var(--muted)", fontSize: 12, fontWeight: 500 }}>
            {derived.latestCompletedTask?.name || derived.latestReport?.report_date || "等待实验数据"}
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 14 }}>
          {metricCards.map(({ icon: Icon, label, value, unit, hint, color }) => (
            <div key={label} style={metricCard}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 12 }}>
                <Icon size={15} color="var(--accent)" />
                {label}
              </div>
              <div style={{ fontSize: 28, fontWeight: 750, color, marginTop: 10 }}>
                {value}<span style={{ color: "var(--muted)", fontSize: 12, marginLeft: 3, fontWeight: 500 }}>{unit}</span>
              </div>
              <div style={{ color: "var(--muted)", fontSize: 11, lineHeight: 1.5, marginTop: 8 }}>{hint}</div>
            </div>
          ))}
        </div>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16, marginBottom: 20 }}>
        <section style={panel}>
          <div style={panelTitle}>
            <span>当前建议动作</span>
            <span style={panelSub}>按当前评测状态生成</span>
          </div>
          <div>
            {actions.map((action, index) => (
              <Link key={action.title} href={action.href} style={{
                display: "grid",
                gridTemplateColumns: "24px minmax(0, 1fr) auto",
                gap: 12,
                alignItems: "start",
                padding: index === 0 ? "2px 0 14px" : "14px 0",
                borderTop: index === 0 ? "none" : "1px solid var(--border)",
              }}>
                <span style={{
                  width: 24, height: 24, borderRadius: 6,
                  display: "grid", placeItems: "center",
                  background: "var(--surface2)", border: "1px solid var(--border)",
                  color: action.tone, fontSize: 12, fontWeight: 750,
                }}>
                  {index + 1}
                </span>
                <span>
                  <span style={{ display: "block", fontSize: 13, fontWeight: 700 }}>{action.title}</span>
                  <span style={{ display: "block", color: "var(--muted)", fontSize: 12, lineHeight: 1.6, marginTop: 4 }}>{action.description}</span>
                </span>
                <span style={{ color: "var(--accent)", fontSize: 12, display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
                  {action.label}<ArrowRight size={13} />
                </span>
              </Link>
            ))}
          </div>
        </section>

        <section style={panel}>
          <div style={panelTitle}>
            <span>最新实验</span>
            <span style={panelSub}>{derived.latestReport?.total_cases ?? derived.latestCompletedTask?.progress_total ?? 0} 个用例</span>
          </div>
          {derived.latestReport ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
                {[
                  { label: "健康分", value: derived.latestHealthScore, color: healthColor(Number(derived.latestHealthScore ?? 0)) },
                  { label: "通过率", value: `${derived.latestReport.pass_rate}%`, color: derived.latestReport.pass_rate >= 80 ? "var(--green)" : "var(--orange)" },
                  { label: "质量分", value: derived.latestReport.quality_score, color: "var(--text)" },
                  { label: "失败", value: `${derived.fatalCount}/${derived.warningCount}`, color: derived.fatalCount > 0 ? "var(--red)" : "var(--orange)" },
                ].map(item => (
                  <div key={item.label}>
                    <div style={{ color: "var(--muted)", fontSize: 10 }}>{item.label}</div>
                    <div style={{ color: item.color, fontSize: 18, fontWeight: 750, marginTop: 4 }}>{item.value}</div>
                  </div>
                ))}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.7, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
                {derived.latestReport.ai_analysis || "暂无 AI 分析。"}
              </div>
              <Link href={`/reports/${derived.latestReport.id}`} style={{ color: "var(--accent)", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4, marginTop: 12 }}>
                查看完整报告 <ArrowRight size={13} />
              </Link>
            </>
          ) : (
            <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.7 }}>
              暂无已生成报告。完成一次实验后，可在实验详情里生成值班报告。
            </div>
          )}
        </section>
      </div>

      <section>
        <div style={sectionHeader}>
          <span>评测闭环</span>
          <span style={{ color: "var(--muted)", fontSize: 12, fontWeight: 500 }}>真实 case → 可复现实验 → 诊断问题模式 → 汇总报告</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
          {modules.map(({ href, icon: Icon, label, description, foot }) => (
            <Link key={href} href={href} style={moduleCard}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <Icon size={15} color="var(--accent)" />
                <span style={{ fontSize: 14, fontWeight: 750 }}>{label}</span>
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, minHeight: 38 }}>{description}</div>
              <div style={{ color: "var(--accent)", fontSize: 12, marginTop: 14, fontWeight: 650 }}>{foot}</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

const sectionHeader: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 16,
  fontSize: 14,
  fontWeight: 750,
  marginBottom: 12,
};

const metricCard: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "17px 18px",
  minHeight: 118,
};

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 18,
};

const panelTitle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 12,
  fontSize: 14,
  fontWeight: 750,
  marginBottom: 14,
};

const panelSub: React.CSSProperties = { color: "var(--muted)", fontSize: 12, fontWeight: 500 };

const moduleCard: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
  minHeight: 132,
  display: "block",
};

const btnPrimary: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--accent)",
  color: "white",
  borderRadius: 6,
  padding: "8px 14px",
  fontSize: 13,
  fontWeight: 650,
  whiteSpace: "nowrap",
};

const btnSecondary: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--surface2)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  padding: "8px 14px",
  fontSize: 13,
  fontWeight: 650,
  whiteSpace: "nowrap",
};
