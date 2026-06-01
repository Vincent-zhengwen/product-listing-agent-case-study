"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { getReports } from "@/lib/api";

export default function ReportsPage() {
  const [reports, setReports] = useState<any[]>([]);

  useEffect(() => { getReports().then(setReports).catch(console.error); }, []);

  const healthColor = (score: number) =>
    score >= 80 ? "var(--green)" : score >= 60 ? "var(--yellow)" : "var(--red)";

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>值班报告</h1>
        <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
          每日自动评测汇总，AI 分析问题模式，每天 02:00 自动生成
        </p>
      </div>

      {reports.length === 0 && (
        <div style={{ padding: 48, textAlign: "center", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📊</div>
          <div style={{ color: "var(--muted)", fontSize: 14 }}>暂无值班报告</div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
            完成一次评测任务后，点击"生成值班报告"或等待每日自动生成
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {reports.map(r => (
          <Link key={r.id} href={`/reports/${r.id}`} style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 8, padding: 20, display: "block", textDecoration: "none",
            transition: "border-color 0.15s",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>值班报告 — {r.report_date}</div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  {r.total_cases} 个用例
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: healthColor(r.health_score) }}>
                  {r.health_score}
                </div>
                <div style={{ fontSize: 10, color: "var(--muted)" }}>健康分/100</div>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
              {[
                { label: "通过率", value: `${r.pass_rate}%`, color: r.pass_rate >= 80 ? "var(--green)" : "var(--orange)" },
                { label: "质量分", value: r.quality_score, color: "var(--text)" },
                { label: "FATAL 失败", value: r.fatal_failures, color: r.fatal_failures > 0 ? "var(--red)" : "var(--green)" },
                { label: "WARNING 失败", value: r.warning_failures, color: r.warning_failures > 0 ? "var(--orange)" : "var(--green)" },
              ].map(({ label, value, color }) => (
                <div key={label}>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>{label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
                </div>
              ))}
            </div>

            {r.ai_analysis && (
              <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.6, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                💡 {r.ai_analysis.slice(0, 200)}{r.ai_analysis.length > 200 ? "…" : ""}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
