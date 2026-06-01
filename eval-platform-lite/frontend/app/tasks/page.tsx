"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { FlaskConical, Plus, RefreshCw } from "lucide-react";
import { getTaskRuns, createTaskRun, getDatasets } from "@/lib/api";
import { StatusBadge } from "@/components/Badge";

const PLATFORMS = ["all", "taobao", "douyin", "xiaohongshu"];
const PLATFORM_LABELS: Record<string, string> = {
  all: "全平台", taobao: "淘宝", douyin: "抖音", xiaohongshu: "小红书",
};

export default function TasksPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "", dataset_id: "", platform: "all", agent_version: "latest", runs_per_case: 1,
  });

  const load = () => getTaskRuns().then(setRuns).catch(console.error);
  useEffect(() => {
    load();
    getDatasets().then(setDatasets).catch(console.error);
    const t = setInterval(load, 5000); // auto-refresh for running tasks
    return () => clearInterval(t);
  }, []);

  const handleCreate = async () => {
    if (!form.name || !form.dataset_id) return;
    await createTaskRun(form);
    setShowCreate(false);
    setForm({ name: "", dataset_id: "", platform: "all", agent_version: "latest", runs_per_case: 1 });
    load();
  };

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>实验</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>每次 Agent、prompt 或工具改动都沉淀成可复现实验</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} style={btnSecondary}><RefreshCw size={13} /></button>
          <button onClick={() => setShowCreate(true)} style={btnPrimary}><Plus size={13} /> 新建实验</button>
        </div>
      </div>

      {showCreate && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>新建评测实验</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 14 }}>
            <div style={{ gridColumn: "1/-1" }}>
              <label style={labelStyle}>实验名称 *</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="如：v2 图片链路修复后真实回归" style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>数据集 *</label>
              <select value={form.dataset_id} onChange={e => setForm({ ...form, dataset_id: e.target.value })} style={inputStyle}>
                <option value="">选择数据集</option>
                {datasets.map(d => <option key={d.id} value={d.id}>{d.name} ({d.case_count ?? 0}条)</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>平台</label>
              <select value={form.platform} onChange={e => setForm({ ...form, platform: e.target.value })} style={inputStyle}>
                {PLATFORMS.map(p => <option key={p} value={p}>{PLATFORM_LABELS[p]}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>每 case 运行次数（pass@k）</label>
              <input type="number" min={1} max={5} value={form.runs_per_case}
                onChange={e => setForm({ ...form, runs_per_case: +e.target.value })} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Agent 版本标记</label>
              <input value={form.agent_version} onChange={e => setForm({ ...form, agent_version: e.target.value })}
                placeholder="如：v5.5" style={inputStyle} />
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleCreate} style={btnPrimary}>启动实验</button>
            <button onClick={() => setShowCreate(false)} style={btnSecondary}>取消</button>
          </div>
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["实验", "平台", "触发方式", "状态", "进度", "Outcome", "Grounding", "Process", "操作"].map(h => (
              <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 500, fontSize: 12 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map(run => {
            const progress = run.progress_total > 0
              ? Math.round(run.progress_completed / run.progress_total * 100) : 0;
            const layer = run.layer_summary || {};
            const outcome = layer.outcome_verification?.pass_rate ?? null;
            const grounding = layer.grounding?.pass_rate ?? null;
            const process = layer.process_quality?.pass_rate ?? null;
            return (
              <tr key={run.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "12px 10px" }}>
                  <Link href={`/tasks/${run.id}`} style={{ fontWeight: 650, color: "var(--accent)", display: "flex", alignItems: "center", gap: 7 }}>
                    <FlaskConical size={14} />
                    {run.name}
                  </Link>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{run.agent_version}</div>
                </td>
                <td style={{ padding: "12px 10px", color: "var(--muted)" }}>{PLATFORM_LABELS[run.platform] || run.platform}</td>
                <td style={{ padding: "12px 10px", color: "var(--muted)", fontSize: 12 }}>{run.trigger}</td>
                <td style={{ padding: "12px 10px" }}><StatusBadge status={run.status} /></td>
                <td style={{ padding: "12px 10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 80, height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{ width: `${progress}%`, height: "100%", background: "var(--accent)", transition: "width 0.3s" }} />
                    </div>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>
                      {run.progress_completed}/{run.progress_total}
                    </span>
                  </div>
                </td>
                <td style={rateCell(outcome)}>{outcome === null ? "—" : `${outcome}%`}</td>
                <td style={rateCell(grounding)}>{grounding === null ? "—" : `${grounding}%`}</td>
                <td style={rateCell(process)}>{process === null ? "—" : `${process}%`}</td>
                <td style={{ padding: "12px 10px" }}>
                  <Link href={`/tasks/${run.id}`} style={{ color: "var(--accent)", fontSize: 12 }}>查看 →</Link>
                </td>
              </tr>
            );
          })}
          {runs.length === 0 && (
            <tr><td colSpan={9} style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>暂无实验</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--surface2)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "8px 10px", color: "var(--text)", fontSize: 13, width: "100%",
};
const labelStyle: React.CSSProperties = { fontSize: 11, color: "var(--muted)", marginBottom: 4, display: "block" };
const btnPrimary: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 6,
  background: "var(--accent)", color: "white", border: "none",
  borderRadius: 6, padding: "8px 14px", fontSize: 13, cursor: "pointer",
};
const btnSecondary: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 6,
  background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "8px 14px", fontSize: 13, cursor: "pointer",
};
const rateCell = (rate: number | null): React.CSSProperties => ({
  padding: "12px 10px",
  fontWeight: 700,
  color: rate === null ? "var(--muted)" : rate >= 85 ? "var(--green)" : rate >= 65 ? "var(--orange)" : "var(--red)",
});
