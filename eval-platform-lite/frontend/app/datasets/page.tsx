"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, Trash2, ExternalLink } from "lucide-react";
import { getDatasets, createDataset, deleteDataset } from "@/lib/api";
import { StatusBadge } from "@/components/Badge";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", version: "v1.0" });

  const load = () => getDatasets().then(setDatasets).catch(console.error);
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    await createDataset(form);
    setForm({ name: "", description: "", version: "v1.0" });
    setShowCreate(false);
    load();
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定要删除数据集「${name}」吗？`)) return;
    await deleteDataset(id);
    load();
  };

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>数据集</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>管理测试用例集，支持手动录入和 CSV 批量导入</p>
        </div>
        <button onClick={() => setShowCreate(true)} style={{
          display: "flex", alignItems: "center", gap: 6,
          background: "var(--accent)", color: "white",
          border: "none", borderRadius: 6, padding: "8px 16px",
          fontSize: 13, cursor: "pointer",
        }}>
          <Plus size={14} /> 创建数据集
        </button>
      </div>

      {showCreate && (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 8, padding: 20, marginBottom: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>新建数据集</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr 100px", gap: 12, marginBottom: 14 }}>
            <input placeholder="数据集名称 *" value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              style={inputStyle} />
            <input placeholder="描述（可选）" value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              style={inputStyle} />
            <input placeholder="版本" value={form.version}
              onChange={e => setForm({ ...form, version: e.target.value })}
              style={inputStyle} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={handleCreate} style={btnPrimary}>创建</button>
            <button onClick={() => setShowCreate(false)} style={btnSecondary}>取消</button>
          </div>
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["数据集名称", "版本", "用例数", "状态", "创建时间", "操作"].map(h => (
              <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 500, fontSize: 12 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {datasets.map(ds => (
            <tr key={ds.id} style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "12px 12px" }}>
                <Link href={`/datasets/${ds.id}`} style={{ fontWeight: 600, color: "var(--accent)" }}>
                  {ds.name}
                </Link>
                {ds.description && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{ds.description}</div>}
              </td>
              <td style={{ padding: "12px 12px", color: "var(--muted)" }}>{ds.version}</td>
              <td style={{ padding: "12px 12px", fontWeight: 600 }}>{ds.case_count ?? 0}</td>
              <td style={{ padding: "12px 12px" }}><StatusBadge status={ds.status} /></td>
              <td style={{ padding: "12px 12px", color: "var(--muted)", fontSize: 12 }}>{ds.created_at?.slice(0, 10)}</td>
              <td style={{ padding: "12px 12px" }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <Link href={`/datasets/${ds.id}`} style={{ color: "var(--accent)", fontSize: 12 }}>
                    <ExternalLink size={14} />
                  </Link>
                  <button onClick={() => handleDelete(ds.id, ds.name)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {datasets.length === 0 && (
            <tr><td colSpan={6} style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>暂无数据集</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--surface2)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "8px 12px", color: "var(--text)",
  fontSize: 13, width: "100%",
};
const btnPrimary: React.CSSProperties = {
  background: "var(--accent)", color: "white", border: "none",
  borderRadius: 6, padding: "8px 16px", fontSize: 13, cursor: "pointer",
};
const btnSecondary: React.CSSProperties = {
  background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)",
  borderRadius: 6, padding: "8px 16px", fontSize: 13, cursor: "pointer",
};
