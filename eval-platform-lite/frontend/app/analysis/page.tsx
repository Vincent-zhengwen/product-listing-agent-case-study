"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BarChart3, Code2, GitCompareArrows, RefreshCw, Workflow } from "lucide-react";
import { compareRunsV3, getCodingBoard, getFailureTaxonomy, getTaskRuns } from "@/lib/api";

const LAYERS = [
  ["run_validity", "Run Validity"],
  ["outcome_verification", "Outcome"],
  ["grounding", "Grounding"],
  ["conversion_quality", "Conversion"],
  ["process_quality", "Process"],
];
const LAYER_LABEL: Record<string, string> = Object.fromEntries(LAYERS);

export default function AnalysisPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [compare, setCompare] = useState<any[]>([]);
  const [board, setBoard] = useState<any[]>([]);
  const [taxonomy, setTaxonomy] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const allRuns = await getTaskRuns();
      const completed = allRuns.filter((t: any) => t.status === "completed");
      setRuns(completed);
      const defaultSelected = selected.length ? selected : completed.slice(0, 3).map((r: any) => r.id);
      setSelected(defaultSelected);
      if (defaultSelected.length) setCompare(await compareRunsV3(defaultSelected));
      setBoard(await getCodingBoard());
      setTaxonomy(await getFailureTaxonomy());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (selected.length) compareRunsV3(selected).then(setCompare).catch(console.error);
  }, [selected.join(",")]);

  const rootCodes = useMemo(() => {
    const count: Record<string, number> = {};
    board.forEach(row => (row.recommended_codes || []).forEach((code: string) => { count[code] = (count[code] || 0) + 1; }));
    return Object.entries(count).sort((a, b) => b[1] - a[1]).slice(0, 10);
  }, [board]);

  const toggle = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id].slice(-5));
  };

  return (
    <div style={{ padding: 32, maxWidth: 1440, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 750, margin: 0 }}>诊断分析</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>实验对比、Failure Coding、回归热点都从 case 诊断沉淀出来</p>
        </div>
        <button onClick={load} style={secondaryButton}><RefreshCw size={14} /> {loading ? "刷新中" : "刷新"}</button>
      </div>

      <section style={panel}>
          <div style={sectionTitle}><GitCompareArrows size={15} /> 实验对比</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          {runs.map(run => (
            <button key={run.id} onClick={() => toggle(run.id)} style={runButton(selected.includes(run.id))}>
              {run.name}<span style={{ opacity: 0.65, marginLeft: 6 }}>{run.agent_version}</span>
            </button>
          ))}
          {!runs.length && <span style={{ color: "var(--muted)", fontSize: 13 }}>暂无已完成实验</span>}
        </div>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>实验</th>
              {LAYERS.map(([, label]) => <th key={label} style={th}>{label}</th>)}
              <th style={th}>Top Failures</th>
            </tr>
          </thead>
          <tbody>
            {compare.map(run => (
              <tr key={run.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={td}>
                  <Link href={`/tasks/${run.id}`} style={{ color: "var(--accent)", fontWeight: 650 }}>{run.name}</Link>
                  <div style={{ color: "var(--muted)", fontSize: 11 }}>{run.agent_version}</div>
                </td>
                {LAYERS.map(([key]) => {
                  const item = run.layer_summary?.[key];
                  const rate = item?.pass_rate;
                  return <td key={key} style={{ ...td, color: rateColor(rate), fontWeight: 750 }}>{rate === null || rate === undefined ? "—" : `${rate}%`}</td>;
                })}
                <td style={td}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {(run.top_failed_graders || []).slice(0, 4).map((x: any) => <span key={x.grader_id} style={pill}>{x.grader_id} · {x.count}</span>)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 16, marginTop: 16 }}>
        <section style={panel}>
          <div style={sectionTitle}><BarChart3 size={15} /> Root Cause Hotspots</div>
          <div style={{ display: "grid", gap: 8 }}>
            {rootCodes.map(([code, count]) => (
              <div key={code} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
                <span>{code}</span>
                <b style={{ color: "var(--orange)" }}>{count}</b>
              </div>
            ))}
            {!rootCodes.length && <div style={{ color: "var(--muted)", fontSize: 13 }}>暂无失败热点</div>}
          </div>
        </section>

        <section style={panel}>
          <div style={sectionTitle}><Code2 size={15} /> Failure Coding Queue</div>
          <table style={{ ...table, tableLayout: "fixed" }}>
            <thead>
              <tr>
                {[
                  ["Case", "24%"],
                  ["Experiment", "22%"],
                  ["Layer", "15%"],
                  ["AI 推荐 Code", "23%"],
                  ["人工标注", "9%"],
                  ["操作", "7%"],
                ].map(([h, width]) => <th key={h} style={{ ...th, width }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {board.slice(0, 40).map(row => {
                const failedLayers = Object.entries(row.layer_summary || {})
                  .filter(([, v]: any) => (v.fail || 0) > 0)
                  .map(([k]) => LAYER_LABEL[k] || k);
                return (
                  <tr key={row.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ ...td, wordBreak: "break-word" }}>
                      <div>{row.category || "未分类"}</div>
                      <div style={{ color: "var(--muted)", fontSize: 11 }}>{row.source_url?.slice(0, 42)}…</div>
                    </td>
                    <td style={{ ...td, wordBreak: "break-word" }}>{row.run_name}<div style={{ color: "var(--muted)", fontSize: 11 }}>{row.agent_version}</div></td>
                    <td style={{ ...td, wordBreak: "break-word" }}>{failedLayers.slice(0, 3).join(" / ") || "—"}</td>
                    <td style={td}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                        {(row.recommended_codes || []).slice(0, 3).map((code: string) => <span key={code} style={pill}>{code}</span>)}
                      </div>
                    </td>
                    <td style={{ ...td, wordBreak: "break-word" }}>{row.failure_codes?.length ? row.failure_codes.map((c: any) => c.code).join(" / ") : row.biggest_issue || "未标注"}</td>
                    <td style={td}><Link href={`/tasks/${row.task_run_id}/results/${row.id}`} style={{ color: "var(--accent)", whiteSpace: "nowrap" }}>诊断 →</Link></td>
                  </tr>
                );
              })}
              {!board.length && <tr><td colSpan={6} style={{ ...td, color: "var(--muted)", textAlign: "center" }}>暂无失败 case</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <section style={{ ...panel, marginTop: 16 }}>
        <div style={sectionTitle}><Workflow size={15} /> Failure Taxonomy</div>
        <table style={table}>
          <thead>
            <tr>
              {["Code", "Category", "Stage", "Root Cause", "Cases", "Suggested Fix"].map(h => <th key={h} style={th}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {taxonomy.map(code => (
              <tr key={code.code} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={td}><span style={pill}>{code.label || code.code}</span></td>
                <td style={td}>{code.category || "—"}</td>
                <td style={td}>{code.stage || "—"}</td>
                <td style={td}>{code.root_cause || "—"}</td>
                <td style={{ ...td, fontWeight: 750, color: code.case_count ? "var(--orange)" : "var(--muted)" }}>{code.case_count || 0}</td>
                <td style={{ ...td, color: "var(--muted)" }}>{code.suggested_fix || code.description || "—"}</td>
              </tr>
            ))}
            {!taxonomy.length && <tr><td colSpan={6} style={{ ...td, color: "var(--muted)", textAlign: "center" }}>暂无 taxonomy</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}

const panel: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 7, padding: 18 };
const sectionTitle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 750, marginBottom: 14 };
const secondaryButton: React.CSSProperties = { display: "flex", alignItems: "center", gap: 7, background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text)", padding: "8px 12px", cursor: "pointer" };
const runButton = (active: boolean): React.CSSProperties => ({ padding: "6px 10px", borderRadius: 6, border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`, background: active ? "#0f766e33" : "var(--surface2)", color: active ? "var(--text)" : "var(--muted)", cursor: "pointer", fontSize: 12 });
const table: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: 12 };
const th: React.CSSProperties = { padding: "8px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 600, borderBottom: "1px solid var(--border)" };
const td: React.CSSProperties = { padding: "10px", verticalAlign: "top", lineHeight: 1.45 };
const pill: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 5, padding: "2px 6px", color: "var(--muted)", fontSize: 11 };
const rateColor = (rate: number | null | undefined) => rate === null || rate === undefined ? "var(--muted)" : rate >= 85 ? "var(--green)" : rate >= 65 ? "var(--orange)" : "var(--red)";
