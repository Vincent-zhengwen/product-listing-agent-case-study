"use client";
import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Plus, Upload, Trash2, ChevronLeft, Download, Loader, PackageCheck, RefreshCw } from "lucide-react";
import { backfillSnapshots, buildCaseSnapshot, getDataset, getCases, createCase, deleteCase } from "@/lib/api";

const CATEGORIES = ["收纳", "家纺", "厨具", "装饰", "清洁", "其他"];
const DIFFICULTIES = ["easy", "medium", "hard"];
const QUALITIES = ["rich", "medium", "sparse"];

const EMPTY_FORM = {
  source_url: "", category: "", difficulty: "", source_quality: "",
  taobao_ref_url: "", douyin_ref_url: "", xiaohongshu_ref_url: "", notes: "",
};

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<any>(null);
  const [cases, setCases] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [filterCat, setFilterCat] = useState("");
  const [filterDiff, setFilterDiff] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [snapshotBusy, setSnapshotBusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadCases = () => {
    const params = new URLSearchParams();
    if (filterCat) params.set("category", filterCat);
    if (filterDiff) params.set("difficulty", filterDiff);
    getCases(id, params.toString()).then(setCases).catch(console.error);
  };

  useEffect(() => { getDataset(id).then(setDataset); }, [id]);
  useEffect(() => { loadCases(); }, [id, filterCat, filterDiff]);

  // Auto-analyze URL when it looks like a valid 1688 link
  const handleUrlBlur = async () => {
    const url = form.source_url.trim();
    if (!url || analyzed) return;
    if (!url.startsWith("http")) return;
    setAnalyzing(true);
    try {
      const res = await fetch("/api/datasets/analyze-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_url: url }),
      });
      const data = await res.json();
      setForm(f => ({
        ...f,
        category: data.category || "其他",
        difficulty: data.difficulty || "medium",
        source_quality: data.source_quality || "medium",
      }));
      setAnalyzed(true);
    } catch {
      // silently fall back — user can fill manually
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAdd = async () => {
    if (!form.source_url.trim()) return;
    await createCase(id, {
      ...form,
      category: form.category || "其他",
      difficulty: form.difficulty || "medium",
      source_quality: form.source_quality || "medium",
    });
    setForm(EMPTY_FORM);
    setAnalyzed(false);
    setShowAdd(false);
    loadCases();
  };

  const handleDelete = async (caseId: string) => {
    if (!confirm("删除此测试用例？")) return;
    await deleteCase(id, caseId);
    loadCases();
  };

  const handleCSV = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // reset input so same file can be re-selected
    e.target.value = "";
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/datasets/${id}/import-csv`, { method: "POST", body: fd });
    const data = await res.json();
    alert(`导入完成：${data.inserted} 条成功${data.errors?.length ? `，${data.errors.length} 条错误` : ""}`);
    loadCases();
  };

  const handleBackfillSnapshots = async () => {
    setSnapshotBusy("all");
    try {
      await backfillSnapshots(id);
      loadCases();
    } finally {
      setSnapshotBusy("");
    }
  };

  const handleCaseSnapshot = async (caseId: string) => {
    setSnapshotBusy(caseId);
    try {
      await buildCaseSnapshot(id, caseId);
      loadCases();
    } finally {
      setSnapshotBusy("");
    }
  };

  const downloadTemplate = () => {
    window.open("/api/datasets/csv-template", "_blank");
  };

  if (!dataset) return <div style={{ padding: 32, color: "var(--muted)" }}>加载中…</div>;

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 20 }}>
        <Link href="/datasets" style={{ color: "var(--muted)", fontSize: 12, display: "flex", alignItems: "center", gap: 4, marginBottom: 10 }}>
          <ChevronLeft size={14} /> 返回数据集列表
        </Link>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{dataset.name}</h1>
            <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
              {dataset.description} · {dataset.version} · {cases.length} 个用例
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={handleBackfillSnapshots} disabled={snapshotBusy === "all"} style={btnSecondary} title="为当前数据集生成 source snapshot package">
              <PackageCheck size={13} /> {snapshotBusy === "all" ? "生成中" : "补齐快照"}
            </button>
            <button onClick={downloadTemplate} style={btnSecondary} title="下载 CSV 模板">
              <Download size={13} /> 下载模板
            </button>
            <button onClick={() => fileRef.current?.click()} style={btnSecondary}>
              <Upload size={13} /> 导入 CSV
            </button>
            <input ref={fileRef} type="file" accept=".csv" style={{ display: "none" }} onChange={handleCSV} />
            <button onClick={() => { setShowAdd(true); setAnalyzed(false); setForm(EMPTY_FORM); }} style={btnPrimary}>
              <Plus size={13} /> 添加用例
            </button>
          </div>
        </div>
      </div>

      {/* filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <select value={filterCat} onChange={e => setFilterCat(e.target.value)} style={selectStyle}>
          <option value="">所有品类</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filterDiff} onChange={e => setFilterDiff(e.target.value)} style={selectStyle}>
          <option value="">所有难度</option>
          {DIFFICULTIES.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {showAdd && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>添加测试用例</div>

          {/* URL input — full width, with auto-analyze */}
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>1688 货源页 URL *</label>
            <div style={{ position: "relative" }}>
              <input
                value={form.source_url}
                onChange={e => { setForm({ ...form, source_url: e.target.value }); setAnalyzed(false); }}
                onBlur={handleUrlBlur}
                placeholder="粘贴后自动识别品类和货源质量…"
                style={{ ...inputStyle, paddingRight: analyzing ? 36 : 12 }}
              />
              {analyzing && (
                <span style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)" }}>
                  <Loader size={13} color="var(--accent)" style={{ animation: "spin 1s linear infinite" }} />
                </span>
              )}
            </div>
            {analyzed && (
              <div style={{ fontSize: 11, color: "var(--green)", marginTop: 4 }}>
                ✓ 已自动识别，可手动调整下方字段
              </div>
            )}
          </div>

          {/* auto-filled fields — shown compactly, user can override */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 12 }}>
            <div>
              <label style={labelStyle}>品类 {analyzing && <span style={{ color: "var(--accent)" }}>识别中…</span>}</label>
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} style={inputStyle}>
                <option value="">自动识别</option>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>难度</label>
              <select value={form.difficulty} onChange={e => setForm({ ...form, difficulty: e.target.value })} style={inputStyle}>
                <option value="">自动识别</option>
                {DIFFICULTIES.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>货源质量</label>
              <select value={form.source_quality} onChange={e => setForm({ ...form, source_quality: e.target.value })} style={inputStyle}>
                <option value="">自动识别</option>
                {QUALITIES.map(q => <option key={q} value={q}>{q}</option>)}
              </select>
            </div>
          </div>

          {/* reference URLs — collapsed by default */}
          <details style={{ marginBottom: 12 }}>
            <summary style={{ fontSize: 12, color: "var(--muted)", cursor: "pointer", userSelect: "none", marginBottom: 8 }}>
              参考竞品 URL（选填，用于竞品对比评分）
            </summary>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, paddingTop: 8 }}>
              <div>
                <label style={labelStyle}>淘宝参考</label>
                <input value={form.taobao_ref_url} onChange={e => setForm({ ...form, taobao_ref_url: e.target.value })}
                  placeholder="https://item.taobao.com/..." style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>抖音参考</label>
                <input value={form.douyin_ref_url} onChange={e => setForm({ ...form, douyin_ref_url: e.target.value })}
                  placeholder="https://v.douyin.com/..." style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>小红书参考</label>
                <input value={form.xiaohongshu_ref_url} onChange={e => setForm({ ...form, xiaohongshu_ref_url: e.target.value })}
                  placeholder="https://www.xiaohongshu.com/..." style={inputStyle} />
              </div>
            </div>
          </details>

          <div style={{ marginBottom: 14 }}>
            <label style={labelStyle}>备注（选填）</label>
            <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
              placeholder="如：货源页图片较少、有水印等" style={inputStyle} />
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={handleAdd} disabled={!form.source_url.trim()} style={{
              ...btnPrimary,
              opacity: form.source_url.trim() ? 1 : 0.5,
            }}>
              保存
            </button>
            <button onClick={() => setShowAdd(false)} style={btnSecondary}>取消</button>
          </div>
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["货源 URL", "品类", "难度", "货源质量", "Source Snapshot", "参考链接", "备注", "操作"].map(h => (
              <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 500, fontSize: 12 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map(c => (
            <tr key={c.id} style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "10px 10px", maxWidth: 200 }}>
                <a href={c.source_url} target="_blank" rel="noopener noreferrer"
                  style={{ color: "var(--accent)", fontSize: 11, wordBreak: "break-all" }}>
                  {c.source_url.replace(/^https?:\/\//, "").slice(0, 50)}…
                </a>
              </td>
              <td style={{ padding: "10px 10px" }}><span style={tagStyle}>{c.category || "—"}</span></td>
              <td style={{ padding: "10px 10px" }}>
                <span style={{ ...tagStyle,
                  background: c.difficulty === "hard" ? "#ef444418" : c.difficulty === "easy" ? "#22c55e18" : "#f9731618",
                  color: c.difficulty === "hard" ? "#ef4444" : c.difficulty === "easy" ? "#22c55e" : "#f97316" }}>
                  {c.difficulty || "—"}
                </span>
              </td>
              <td style={{ padding: "10px 10px", color: "var(--muted)", fontSize: 12 }}>{c.source_quality || "—"}</td>
              <td style={{ padding: "10px 10px" }}>
                <SnapshotBadge snapshot={c.snapshot} />
              </td>
              <td style={{ padding: "10px 10px", fontSize: 11 }}>
                {c.taobao_ref_url && <a href={c.taobao_ref_url} target="_blank" rel="noopener noreferrer" style={{ color: "#ff6600", marginRight: 6 }}>淘宝</a>}
                {c.douyin_ref_url && <a href={c.douyin_ref_url} target="_blank" rel="noopener noreferrer" style={{ color: "#00b5ff", marginRight: 6 }}>抖音</a>}
                {c.xiaohongshu_ref_url && <a href={c.xiaohongshu_ref_url} target="_blank" rel="noopener noreferrer" style={{ color: "#ff385c" }}>小红书</a>}
                {!c.taobao_ref_url && !c.douyin_ref_url && !c.xiaohongshu_ref_url && <span style={{ color: "var(--border)" }}>—</span>}
              </td>
              <td style={{ padding: "10px 10px", color: "var(--muted)", fontSize: 12 }}>{c.notes || "—"}</td>
              <td style={{ padding: "10px 10px" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <button onClick={() => handleCaseSnapshot(c.id)} disabled={snapshotBusy === c.id} title="生成 Source Snapshot" style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
                  <RefreshCw size={13} />
                </button>
                <button onClick={() => handleDelete(c.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
                  <Trash2 size={13} />
                </button>
                </div>
              </td>
            </tr>
          ))}
          {cases.length === 0 && (
            <tr><td colSpan={8} style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>暂无用例</td></tr>
          )}
        </tbody>
      </table>

      <style>{`@keyframes spin { from { transform: translateY(-50%) rotate(0deg); } to { transform: translateY(-50%) rotate(360deg); } }`}</style>
    </div>
  );
}

function SnapshotBadge({ snapshot }: { snapshot?: any }) {
  const score = snapshot?.quality_score;
  const status = snapshot?.status || "missing";
  const color = status === "ready" ? "var(--green)" : status === "partial" ? "var(--orange)" : "var(--red)";
  const label = status === "ready" ? "ready" : status === "partial" ? "partial" : "missing";
  const detail = snapshot ? `${snapshot.attributes_count || 0} attrs · ${snapshot.images_count || 0} imgs` : "未生成";
  return (
    <div style={{ display: "grid", gap: 3 }}>
      <span style={{ ...tagStyle, color, border: `1px solid ${color}`, background: "transparent", width: "fit-content" }}>
        {label}{score !== null && score !== undefined ? ` · ${score}` : ""}
      </span>
      <span style={{ color: "var(--muted)", fontSize: 10 }}>{detail}</span>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--surface2)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "8px 10px", color: "var(--text)", fontSize: 13, width: "100%",
};
const selectStyle: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "7px 12px", color: "var(--text)", fontSize: 12, cursor: "pointer",
};
const labelStyle: React.CSSProperties = { fontSize: 11, color: "var(--muted)", marginBottom: 4, display: "block" };
const tagStyle: React.CSSProperties = {
  background: "var(--surface2)", color: "var(--muted)", padding: "2px 8px", borderRadius: 4, fontSize: 11,
};
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
