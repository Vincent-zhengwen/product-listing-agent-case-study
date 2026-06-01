"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getReport } from "@/lib/api";

const GRADER_LABELS: Record<string, string> = {
  b2c_transform: "B2C文案转化", factual_accuracy: "内容准确性",
  platform_tone: "平台风格匹配", title_appeal: "标题吸引力",
  image_copy_coherence: "图文一致性", detail_image_narrative: "详情图叙事",
  copy_conversion_quality: "文案转化质量",
  category_fit_quality: "品类适配质量",
  main_image_quality: "主图商业质量",
  detail_page_quality: "详情页说服质量",
  title_length_check: "标题长度", title_no_banned_words: "无违禁词",
  attributes_required: "属性必填项", main_image_count: "主图数量",
  detail_image_exists: "详情图存在", steps_completed: "步骤完成",
};

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<any>(null);

  useEffect(() => { getReport(id).then(setReport).catch(console.error); }, [id]);

  if (!report) return <div style={{ padding: 32, color: "var(--muted)" }}>加载中…</div>;

  const data = report.report_json || {};
  const healthColor = (s: number) => s >= 80 ? "var(--green)" : s >= 60 ? "var(--yellow)" : "var(--red)";

  return (
    <div style={{ padding: 32 }}>
      <Link href="/reports" style={{ color: "var(--muted)", fontSize: 12, display: "flex", alignItems: "center", gap: 4, marginBottom: 16 }}>
        <ChevronLeft size={14} /> 返回报告列表
      </Link>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>值班报告 — {report.report_date}</h1>
          <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
            {data.run_name} · {data.total_cases} 个用例 · {data.platform}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 36, fontWeight: 700, color: healthColor(report.health_score) }}>
            {report.health_score}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>健康分/100</div>
        </div>
      </div>

      {/* summary metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "发布通过率", value: `${data.pass_rate}%`, color: data.pass_rate >= 80 ? "var(--green)" : "var(--orange)" },
          { label: "上架质量分", value: data.listing_quality_score ?? data.quality_score, color: (data.listing_quality_score ?? data.quality_score) >= 75 ? "var(--green)" : (data.listing_quality_score ?? data.quality_score) >= 60 ? "var(--orange)" : "var(--red)" },
          { label: "安全质量分", value: data.publish_quality_score ?? data.quality_score, color: "var(--text)" },
          { label: "FATAL 失败", value: data.fatal_failures_count, color: data.fatal_failures_count > 0 ? "var(--red)" : "var(--green)" },
          { label: "WARNING 失败", value: data.warning_failures_count, color: data.warning_failures_count > 0 ? "var(--orange)" : "var(--green)" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* AI analysis */}
      {data.ai_analysis && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>💡 AI 问题分析</div>
          <div style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.8 }}>{data.ai_analysis}</div>
        </div>
      )}

      {/* listing quality */}
      {(data.quality_dimension_scores || data.quality_issues?.length > 0 || data.case_quality?.length > 0) && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14 }}>上架质量诊断</div>
          {data.quality_dimension_scores && Object.keys(data.quality_dimension_scores).length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 16 }}>
              {Object.entries(data.quality_dimension_scores).map(([name, value]) => {
                const n = value as number;
                return (
                  <div key={name} style={{ background: "var(--surface2)", borderRadius: 6, padding: "10px 12px" }}>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>{name}</div>
                    <div style={{ fontSize: 18, fontWeight: 750, color: n >= 75 ? "var(--green)" : n >= 60 ? "var(--orange)" : "var(--red)" }}>{n}</div>
                  </div>
                );
              })}
            </div>
          )}
          {data.case_quality?.length > 0 && (
            <div style={{ display: "grid", gap: 8, marginBottom: 16 }}>
              {data.case_quality.map((c: any) => (
                <div key={c.run_result_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--surface2)", borderRadius: 6, padding: "8px 12px", fontSize: 12 }}>
                  <span>{c.category || "未分类"} · {c.run_result_id.slice(0, 8)}</span>
                  <span style={{ fontWeight: 750, color: c.listing_quality_score >= 75 ? "var(--green)" : c.listing_quality_score >= 60 ? "var(--orange)" : "var(--red)" }}>
                    {c.listing_quality_score} · {c.quality_verdict}
                  </span>
                  <Link href={`/tasks/${data.run_id}/results/${c.run_result_id}`} style={{ color: "var(--accent)" }}>查看 →</Link>
                </div>
              ))}
            </div>
          )}
          {data.quality_issues?.length > 0 && (
            <div style={{ display: "grid", gap: 8 }}>
              {data.quality_issues.slice(0, 12).map((issue: any, i: number) => (
                <div key={i} style={{ borderLeft: "2px solid var(--orange)", paddingLeft: 10, fontSize: 12, lineHeight: 1.55 }}>
                  <div style={{ color: "var(--text)", fontWeight: 650 }}>{issue.code} · {issue.category} · {issue.score}</div>
                  <div style={{ color: "var(--muted)" }}>{issue.reason}</div>
                  {issue.suggested_fix && <div style={{ color: "var(--muted)" }}>fix: {issue.suggested_fix}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* per-grader rates */}
      {data.grader_rates && Object.keys(data.grader_rates).length > 0 && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14 }}>各维度通过率</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {Object.entries(data.grader_rates).filter(([_, v]) => v !== null).map(([gid, rate]) => {
              const r = rate as number;
              return (
                <div key={gid} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", background: "var(--surface2)", borderRadius: 6 }}>
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>{GRADER_LABELS[gid] || gid}</span>
                  <span style={{
                    fontSize: 13, fontWeight: 700,
                    color: r >= 80 ? "var(--green)" : r >= 60 ? "var(--yellow)" : "var(--red)",
                  }}>
                    {r}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* fatal failures */}
      {data.fatal_failures?.length > 0 && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            🔴 FATAL 失败详情 ({data.fatal_failures_count} 例)
          </div>
          {data.fatal_failures.map((f: any, i: number) => (
            <div key={i} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
              <div style={{ fontSize: 11, color: "var(--red)", minWidth: 140 }}>
                [{GRADER_LABELS[f.grader_id] || f.grader_id}]
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)", flex: 1 }}>{f.reason}</div>
              <div style={{ fontSize: 11, color: "var(--border)", whiteSpace: "nowrap" }}>
                {f.platform} · {f.category}
              </div>
              <Link href={`/tasks/${data.run_id}/results/${f.run_result_id}`} style={{ fontSize: 11, color: "var(--accent)" }}>
                查看 →
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* warning failures */}
      {data.warning_failures?.length > 0 && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            🟡 WARNING 失败详情 ({data.warning_failures_count} 例)
          </div>
          {data.warning_failures.map((f: any, i: number) => (
            <div key={i} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
              <div style={{ fontSize: 11, color: "var(--orange)", minWidth: 140 }}>
                [{GRADER_LABELS[f.grader_id] || f.grader_id}]
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)", flex: 1 }}>{f.reason}</div>
              <div style={{ fontSize: 11, color: "var(--border)", whiteSpace: "nowrap" }}>
                {f.platform} · {f.category}
              </div>
              <Link href={`/tasks/${data.run_id}/results/${f.run_result_id}`} style={{ fontSize: 11, color: "var(--accent)" }}>
                查看 →
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
