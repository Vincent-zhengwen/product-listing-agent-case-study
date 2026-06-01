"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, RefreshCw, FileText, GitBranchPlus } from "lucide-react";
import { createRegressionDataset, getTaskRun, getRunResults, generateReport } from "@/lib/api";
import { StatusBadge } from "@/components/Badge";

const PLATFORM_LABELS: Record<string, string> = { taobao: "淘宝", douyin: "抖音", xiaohongshu: "小红书" };

export default function TaskRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<any>(null);
  const [results, setResults] = useState<any[]>([]);
  const [generating, setGenerating] = useState(false);
  const [creatingRegression, setCreatingRegression] = useState(false);
  const [filterStatus, setFilterStatus] = useState("");

  const load = () => {
    getTaskRun(runId).then(setRun);
    getRunResults(runId).then(setResults);
  };

  useEffect(() => {
    load();
    const t = setInterval(() => {
      getTaskRun(runId).then(r => {
        setRun(r);
        if (r.status !== "running") clearInterval(t);
        else getRunResults(runId).then(setResults);
      });
    }, 3000);
    return () => clearInterval(t);
  }, [runId]);

  const handleGenerateReport = async () => {
    setGenerating(true);
    try {
      await generateReport(runId);
      alert("报告生成成功！");
    } catch (e) {
      alert("生成失败：" + (e as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCreateRegression = async () => {
    setCreatingRegression(true);
    try {
      const res = await createRegressionDataset(runId, { scope: "failed" });
      alert(`回归数据集已生成：${res.case_count} 个 case`);
      window.location.href = `/datasets/${res.dataset_id}`;
    } catch (e) {
      alert("生成失败：" + (e as Error).message);
    } finally {
      setCreatingRegression(false);
    }
  };

  if (!run) return <div style={{ padding: 32, color: "var(--muted)" }}>加载中…</div>;

  const progress = run.progress_total > 0 ? Math.round(run.progress_completed / run.progress_total * 100) : 0;
  const filtered = filterStatus ? results.filter(r => r.status === filterStatus) : results;

  // compute summary
  const allScores = results.flatMap((r: any) => r.scores || []);
  const blockerScores = allScores.filter((s: any) => s.severity === "blocker" && (s.verdict === "pass" || s.verdict === "fail"));
  const blockerPass = blockerScores.filter((s: any) => s.verdict === "pass").length;
  const blockerTotal = blockerScores.length;
  const passRate = blockerTotal > 0 ? Math.round(blockerPass / blockerTotal * 100) : null;

  return (
    <div style={{ padding: 32 }}>
      <Link href="/tasks" style={{ color: "var(--muted)", fontSize: 12, display: "flex", alignItems: "center", gap: 4, marginBottom: 16 }}>
        <ChevronLeft size={14} /> 返回 Experiments
      </Link>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{run.name}</h1>
          <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
            Agent 版本: {run.agent_version} · 平台: {run.platform} · 触发: {run.trigger}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} style={btnSecondary}><RefreshCw size={13} /></button>
          {run.status === "completed" && (
            <>
              <button onClick={handleCreateRegression} disabled={creatingRegression} style={btnSecondary}>
                <GitBranchPlus size={13} /> {creatingRegression ? "生成中…" : "失败转回归集"}
              </button>
              <button onClick={handleGenerateReport} disabled={generating} style={btnPrimary}>
                <FileText size={13} /> {generating ? "生成中…" : "生成值班报告"}
              </button>
            </>
          )}
        </div>
      </div>

      {/* summary bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "状态", value: <StatusBadge status={run.status} /> },
          { label: "进度", value: `${run.progress_completed}/${run.progress_total}` },
          { label: "失败", value: run.progress_failed },
          { label: "Blocker 通过率", value: passRate !== null ? `${passRate}%` : "—" },
          { label: "创建时间", value: run.created_at?.slice(0, 16) },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* progress bar */}
      <div style={{ marginBottom: 20, background: "var(--surface)", borderRadius: 6, padding: "12px 14px", border: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
          <span style={{ color: "var(--muted)" }}>总体进度</span>
          <span>{progress}%</span>
        </div>
        <div style={{ height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ width: `${progress}%`, height: "100%", background: "var(--accent)", transition: "width 0.5s" }} />
        </div>
      </div>

      {/* filter */}
      <div style={{ marginBottom: 12, display: "flex", gap: 8, fontSize: 12 }}>
        {["", "success", "partial", "failed", "pending"].map(s => (
          <button key={s} onClick={() => setFilterStatus(s)} style={{
            padding: "4px 12px", borderRadius: 4, border: "1px solid var(--border)", cursor: "pointer",
            background: filterStatus === s ? "var(--accent)" : "var(--surface)",
            color: filterStatus === s ? "white" : "var(--muted)",
          }}>
            {s || "全部"} ({s ? results.filter(r => r.status === s).length : results.length})
          </button>
        ))}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["Case", "平台", "状态", "Outcome", "Grounding", "Listing", "Process", "耗时", "操作"].map(h => (
              <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.map(r => {
            const layer = r.layer_summary || {};
            return (
              <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "10px 10px" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>{r.category || "—"}</div>
                  <div style={{ fontSize: 10, color: "var(--border)", wordBreak: "break-all", maxWidth: 140 }}>
                    {r.source_url?.slice(0, 40)}…
                  </div>
                </td>
                <td style={{ padding: "10px 10px" }}>{PLATFORM_LABELS[r.platform] || r.platform}</td>
                <td style={{ padding: "10px 10px" }}><StatusBadge status={r.status} /></td>
                <td style={layerCell(layer.outcome_verification)}>{formatLayer(layer.outcome_verification)}</td>
                <td style={layerCell(layer.grounding)}>{formatLayer(layer.grounding)}</td>
                <td style={layerCell(layer.listing_quality)}>{formatLayer(layer.listing_quality)}</td>
                <td style={layerCell(layer.process_quality)}>{formatLayer(layer.process_quality)}</td>
                <td style={{ padding: "10px 10px", color: "var(--muted)" }}>
                  {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : "—"}
                </td>
                <td style={{ padding: "10px 10px" }}>
                  <Link href={`/tasks/${runId}/results/${r.id}`} style={{ color: "var(--accent)" }}>详情 →</Link>
                </td>
              </tr>
            );
          })}
          {filtered.length === 0 && (
            <tr><td colSpan={9} style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>暂无结果</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const btnPrimary: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 6,
  background: "var(--accent)", color: "white", border: "none",
  borderRadius: 6, padding: "8px 14px", fontSize: 13, cursor: "pointer",
};
const formatLayer = (layer: any) => {
  if (!layer || layer.pass_rate === null || layer.pass_rate === undefined) return "—";
  return `${layer.pass_rate}%`;
};
const layerCell = (layer: any): React.CSSProperties => {
  const rate = layer?.pass_rate;
  return {
    padding: "10px 10px",
    color: rate === null || rate === undefined ? "var(--muted)" : rate >= 85 ? "var(--green)" : rate >= 65 ? "var(--orange)" : "var(--red)",
    fontWeight: 700,
  };
};
const btnSecondary: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 6,
  background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "8px 14px", fontSize: 13, cursor: "pointer",
};
