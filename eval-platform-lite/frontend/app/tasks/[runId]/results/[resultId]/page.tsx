"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Bot, ChevronLeft, ClipboardCheck, Eye, FileSearch,
  Image as ImageIcon, Layers, MessageSquareWarning, RefreshCw, Save,
  Sparkles, Tags, WandSparkles,
} from "lucide-react";
import {
  annotate, createAiAnalysis, getDiagnosticContext, getFailureCodes, saveFailureCodes,
} from "@/lib/api";
import GraderResults from "@/components/GraderResults";
import TraceViewer from "@/components/TraceViewer";
import { StatusBadge } from "@/components/Badge";

const PLATFORM_LABELS: Record<string, string> = { taobao: "淘宝", douyin: "抖音", xiaohongshu: "小红书" };
const TABS = [
  ["compare", "产物对比", FileSearch],
  ["images", "图像诊断", ImageIcon],
  ["grounding", "文案 Grounding", Eye],
  ["trace", "Agent Trace", Layers],
  ["graders", "Grader 结果", ClipboardCheck],
  ["ai", "AI 分析", Bot],
  ["review", "人工审核", Tags],
] as const;

type TabKey = typeof TABS[number][0];

export default function ResultDetailPage() {
  const { runId, resultId } = useParams<{ runId: string; resultId: string }>();
  const [ctx, setCtx] = useState<any>(null);
  const [tab, setTab] = useState<TabKey>("compare");
  const [codes, setCodes] = useState<any[]>([]);
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [ann, setAnn] = useState({ q1: null as boolean | null, q2: null as boolean | null, q3: null as boolean | null, note: "" });
  const [busy, setBusy] = useState("");

  const load = async () => {
    const data = await getDiagnosticContext(runId, resultId);
    setCtx(data);
    setSelectedCodes((data.failure_codes || []).map((c: any) => c.code));
    if (data.annotation) {
      setAnn({
        q1: data.annotation.q1_publishable === 1 ? true : data.annotation.q1_publishable === 0 ? false : null,
        q2: data.annotation.q2_competitor_parity === 1 ? true : data.annotation.q2_competitor_parity === 0 ? false : null,
        q3: data.annotation.q3_would_click === 1 ? true : data.annotation.q3_would_click === 0 ? false : null,
        note: data.annotation.biggest_issue || "",
      });
    }
  };

  useEffect(() => {
    load();
    getFailureCodes().then(setCodes).catch(console.error);
  }, [runId, resultId]);

  const summary = useMemo(() => {
    const layer = ctx?.layer_summary || {};
    const trustedBlockers = Object.values(layer).reduce((n: number, x: any) => n + (x.trusted_blockers || 0), 0);
    const provisionalBlockers = Object.values(layer).reduce((n: number, x: any) => n + (x.provisional_blockers || 0), 0);
    const failed = (ctx?.scores || []).filter((s: any) => s.verdict === "fail");
    return { trustedBlockers, provisionalBlockers, failed };
  }, [ctx]);

  const runAiAnalysis = async () => {
    setBusy("ai");
    try {
      await createAiAnalysis(runId, resultId);
      await load();
      setTab("ai");
    } finally {
      setBusy("");
    }
  };

  const saveReview = async () => {
    setBusy("review");
    try {
      await annotate(runId, resultId, {
        q1_publishable: ann.q1,
        q2_competitor_parity: ann.q2,
        q3_would_click: ann.q3,
        biggest_issue: ann.note,
      });
      await saveFailureCodes(runId, resultId, { codes: selectedCodes, note: ann.note, source: "human" });
      await load();
    } finally {
      setBusy("");
    }
  };

  if (!ctx) return <div style={{ padding: 32, color: "var(--muted)" }}>加载诊断上下文…</div>;

  const result = ctx.result || {};
  const output = ctx.output || {};
  const source = ctx.source || {};
  const ai = ctx.ai_analysis?.analysis_json;

  return (
    <div style={{ padding: 28, maxWidth: 1480, margin: "0 auto" }}>
      <Link href={`/tasks/${runId}`} style={backLink}>
        <ChevronLeft size={14} /> 返回实验详情
      </Link>

      <div style={topbar}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <h1 style={{ fontSize: 19, margin: 0, fontWeight: 750 }}>
              {PLATFORM_LABELS[result.platform] || result.platform} · {result.category || "未分类"}
            </h1>
            <StatusBadge status={result.status} />
            <DecisionBadge trusted={summary.trustedBlockers} provisional={summary.provisionalBlockers} />
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>
            {result.run_name} · {result.agent_version} · {result.duration_ms ? `${(result.duration_ms / 1000).toFixed(1)}s` : "imported"} · {result.source_quality || "source"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} style={iconButton} title="刷新"><RefreshCw size={15} /></button>
          <button onClick={runAiAnalysis} disabled={busy === "ai"} style={primaryButton}>
            <WandSparkles size={15} /> {busy === "ai" ? "分析中" : "生成 AI 分析"}
          </button>
        </div>
      </div>

      <LayerCards summary={ctx.layer_summary || {}} />

      <div style={diagnosticGrid}>
        <SourcePanel source={source} result={result} />
        <OutputPanel output={output} />
        <DecisionPanel summary={summary} ai={ai} recommendedCodes={ctx.recommended_codes || []} />
      </div>

      <div style={tabs}>
        {TABS.map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} style={tabButton(tab === key)}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === "compare" && <CompareTab source={source} output={output} result={result} />}
      {tab === "images" && <ImagesTab source={source} output={output} scores={ctx.scores || []} />}
      {tab === "grounding" && <GroundingTab claims={ctx.claims || []} source={source} output={output} />}
      {tab === "trace" && <Panel><TraceViewer trace={ctx.trace} /></Panel>}
      {tab === "graders" && <Panel><GraderResults scores={ctx.scores || []} /></Panel>}
      {tab === "ai" && <AiTab ai={ai} onRun={runAiAnalysis} busy={busy === "ai"} />}
      {tab === "review" && (
        <ReviewTab
          ann={ann}
          setAnn={setAnn}
          codes={codes}
          selectedCodes={selectedCodes}
          setSelectedCodes={setSelectedCodes}
          recommendedCodes={ctx.recommended_codes || []}
          onSave={saveReview}
          saving={busy === "review"}
        />
      )}
    </div>
  );
}

function DecisionBadge({ trusted, provisional }: { trusted: number; provisional: number }) {
  if (trusted > 0) return <span style={{ ...pill, color: "var(--red)", borderColor: "#ef444455" }}>Trusted Blocker {trusted}</span>;
  if (provisional > 0) return <span style={{ ...pill, color: "var(--orange)", borderColor: "#f9731655" }}>Needs Review {provisional}</span>;
  return <span style={{ ...pill, color: "var(--green)", borderColor: "#22c55e55" }}>No Hard Blocker</span>;
}

function LayerCards({ summary }: { summary: Record<string, any> }) {
  const layers = [
    ["run_validity", "Run Validity"],
    ["outcome_verification", "Outcome"],
    ["grounding", "Grounding"],
    ["conversion_quality", "Conversion"],
    ["listing_quality", "Listing Quality"],
    ["process_quality", "Process"],
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, minmax(0, 1fr))", gap: 10, marginBottom: 16 }}>
      {layers.map(([key, label]) => {
        const item = summary[key] || {};
        const rate = item.pass_rate;
        const color = item.trusted_blockers ? "var(--red)" : item.fail ? "var(--orange)" : "var(--green)";
        return (
          <div key={key} style={metricCard}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 760, color }}>{rate === null || rate === undefined ? "—" : `${rate}%`}</div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>{item.pass || 0}/{item.judged || 0} pass · {item.fail || 0} fail</div>
          </div>
        );
      })}
    </div>
  );
}

function SourcePanel({ source, result }: { source: any; result: any }) {
  const completeness = source.completeness || {};
  return (
    <Panel>
      <PanelTitle icon={<FileSearch size={15} />} title="输入依据" />
      <div style={{ fontSize: 13, fontWeight: 650, lineHeight: 1.45, marginBottom: 10 }}>{source.title || "源页快照缺失"}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        <span style={pill}>Snapshot {completeness.status || source._snapshot_meta?.status || "live"}</span>
        <span style={pill}>{completeness.score ?? source._snapshot_meta?.quality_score ?? "—"} / 100</span>
        <span style={pill}>{completeness.attributes_count ?? Object.keys(source.attributes || {}).length} attrs</span>
        <span style={pill}>{completeness.images_count ?? (source.images || []).length} imgs</span>
      </div>
      <div style={kvGrid}>
        <span>平台</span><b>{source.platform || "—"}</b>
        <span>供应商</span><b>{source.supplier || "—"}</b>
        <span>价格</span><b>{source.price ?? "—"}</b>
        <span>利润率</span><b>{source.business?.profit_margin || "—"}</b>
      </div>
      <a href={result.source_url} target="_blank" rel="noreferrer" style={sourceLink}>{result.source_url}</a>
      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        {result.taobao_ref_url && <a style={miniLink} href={result.taobao_ref_url} target="_blank" rel="noreferrer">淘宝参考</a>}
        {result.douyin_ref_url && <a style={miniLink} href={result.douyin_ref_url} target="_blank" rel="noreferrer">抖音参考</a>}
        {result.xiaohongshu_ref_url && <a style={miniLink} href={result.xiaohongshu_ref_url} target="_blank" rel="noreferrer">小红书参考</a>}
      </div>
    </Panel>
  );
}

function OutputPanel({ output }: { output: any }) {
  return (
    <Panel>
      <PanelTitle icon={<Sparkles size={15} />} title="Agent 输出" />
      <div style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.45, marginBottom: 10 }}>{output.title || "无标题"}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 12 }}>
        <MiniMetric label="主图" value={`${output.main_images?.length || 0}`} />
        <MiniMetric label="详情图" value={output.detail_image ? "有" : "无"} />
        <MiniMetric label="属性" value={`${Object.keys(output.attributes || {}).length}`} />
      </div>
      <div style={{ display: "grid", gap: 5 }}>
        {(output.selling_points || []).slice(0, 4).map((sp: string, i: number) => (
          <div key={i} style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.4 }}>{i + 1}. {sp}</div>
        ))}
      </div>
    </Panel>
  );
}

function DecisionPanel({ summary, ai, recommendedCodes }: { summary: any; ai: any; recommendedCodes: string[] }) {
  return (
    <Panel>
      <PanelTitle icon={<MessageSquareWarning size={15} />} title="诊断摘要" />
      <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
        <MiniMetric label="Trusted Blocker" value={String(summary.trustedBlockers)} tone={summary.trustedBlockers ? "red" : "green"} />
        <MiniMetric label="Provisional" value={String(summary.provisionalBlockers)} tone={summary.provisionalBlockers ? "orange" : "green"} />
        <MiniMetric label="Failed Graders" value={String(summary.failed.length)} tone={summary.failed.length ? "orange" : "green"} />
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--muted)" }}>
        {ai?.summary || "还没有 AI root cause 分析。可以先看 trusted blocker，再生成 AI 分析。"}
      </div>
      {recommendedCodes.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {recommendedCodes.map(code => <span key={code} style={pill}>{code}</span>)}
        </div>
      )}
    </Panel>
  );
}

function CompareTab({ source, output, result }: { source: any; output: any; result: any }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "360px 1fr 360px", gap: 14 }}>
      <Panel>
        <PanelTitle icon={<FileSearch size={15} />} title="Source Snapshot" />
        <ImageStrip images={source.images || []} />
        <AttributeTable data={source.attributes || source.raw_data || {}} />
      </Panel>
      <Panel>
        <PanelTitle icon={<Sparkles size={15} />} title="Agent Listing" />
        <h2 style={{ fontSize: 18, margin: "0 0 12px" }}>{output.title}</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <AttributeTable data={output.attributes || {}} />
          <div style={{ fontSize: 13, lineHeight: 1.65, whiteSpace: "pre-wrap" }}>{output.body_copy}</div>
        </div>
      </Panel>
      <Panel>
        <PanelTitle icon={<Eye size={15} />} title="Reference & Review" />
        <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
          这里保留平台参考商品和人工审核入口。当前 case 的核心展示是 source facts、Agent output、grader failure 能在一个页面里完成对照。
        </div>
        <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
          <a style={miniLink} href={result.source_url} target="_blank" rel="noreferrer">打开货源页</a>
          {result.taobao_ref_url && <a style={miniLink} href={result.taobao_ref_url} target="_blank" rel="noreferrer">打开淘宝参考</a>}
        </div>
      </Panel>
    </div>
  );
}

function ImagesTab({ source, output, scores }: { source: any; output: any; scores: any[] }) {
  const imageFailures = scores.filter(s => s.verdict === "fail" && (s.target === "artifact" || s.grader_id?.startsWith("image_")));
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <Panel>
        <PanelTitle icon={<ImageIcon size={15} />} title="主图诊断" />
        <ImageGrid images={output.main_images || []} />
      </Panel>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Panel>
          <PanelTitle icon={<FileSearch size={15} />} title="源图" />
          <ImageGrid images={source.images || []} compact />
        </Panel>
        <Panel>
          <PanelTitle icon={<ImageIcon size={15} />} title="详情图" />
          <ImageGrid images={output.detail_images?.length ? output.detail_images : [output.detail_image].filter(Boolean)} compact />
        </Panel>
      </div>
      <Panel>
        <PanelTitle icon={<MessageSquareWarning size={15} />} title="图片相关失败" />
        {imageFailures.length ? imageFailures.map(f => (
          <div key={f.grader_id} style={failureRow}>
            <b>{f.label || f.grader_id}</b>
            <span>{f.critique}</span>
          </div>
        )) : <div style={{ color: "var(--muted)", fontSize: 13 }}>没有图片类失败。</div>}
      </Panel>
    </div>
  );
}

function GroundingTab({ claims, source, output }: { claims: any[]; source: any; output: any }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 14 }}>
      <Panel>
        <PanelTitle icon={<Eye size={15} />} title="Claim → Source Evidence" />
        <table style={table}>
          <thead>
            <tr>
              {["字段", "Claim", "状态", "命中的源页词"].map(h => <th key={h} style={th}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {claims.map((claim, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={td}>{claim.field}</td>
                <td style={td}>{claim.text}</td>
                <td style={td}><ClaimBadge status={claim.status} /></td>
                <td style={td}>{claim.supported_terms?.join(" / ") || "—"}</td>
              </tr>
            ))}
            {!claims.length && <tr><td colSpan={4} style={{ ...td, color: "var(--muted)" }}>暂无可抽取 claim。</td></tr>}
          </tbody>
        </table>
      </Panel>
      <Panel>
        <PanelTitle icon={<FileSearch size={15} />} title="Source Facts" />
        <AttributeTable data={source.attributes || source.raw_data || {}} />
        <div style={{ borderTop: "1px solid var(--border)", marginTop: 12, paddingTop: 12, fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
          正文长度：{output.body_copy?.length || 0} 字。具体数字、材质、颜色、功能词会优先进入 claim 检查。
        </div>
      </Panel>
    </div>
  );
}

function AiTab({ ai, onRun, busy }: { ai: any; onRun: () => void; busy: boolean }) {
  return (
    <Panel>
      <PanelTitle icon={<Bot size={15} />} title="AI Root Cause Analysis" />
      {!ai ? (
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>还没有生成分析。第一版使用结构化 grader evidence 做可解释归因，不依赖外部 API key。</div>
          <button onClick={onRun} disabled={busy} style={primaryButton}><WandSparkles size={15} /> {busy ? "分析中" : "生成分析"}</button>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{ai.summary}</div>
          <div style={aiGrid}>
            <MiniMetric label="Root Cause" value={ai.root_cause} />
            <MiniMetric label="Same Case Rerun" value={ai.rerun_scope?.same_case ? "yes" : "no"} />
          </div>
          <div>
            <div style={sectionLabel}>Suggested Fix</div>
            <div style={{ fontSize: 13, lineHeight: 1.6 }}>{ai.suggested_fix}</div>
          </div>
          <div>
            <div style={sectionLabel}>Rerun Scope</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(ai.rerun_scope?.focus_stages || []).map((s: string) => <span key={s} style={pill}>{s}</span>)}
              {(ai.rerun_scope?.recommended_failure_codes || []).map((s: string) => <span key={s} style={pill}>{s}</span>)}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function ReviewTab(props: {
  ann: any;
  setAnn: (fn: any) => void;
  codes: any[];
  selectedCodes: string[];
  setSelectedCodes: (codes: string[]) => void;
  recommendedCodes: string[];
  onSave: () => void;
  saving: boolean;
}) {
  const { ann, setAnn, codes, selectedCodes, setSelectedCodes, recommendedCodes, onSave, saving } = props;
  const toggleCode = (code: string) => {
    setSelectedCodes(selectedCodes.includes(code) ? selectedCodes.filter(c => c !== code) : [...selectedCodes, code]);
  };
  return (
    <Panel>
      <PanelTitle icon={<Tags size={15} />} title="人工审核与 Failure Coding" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div>
          {[
            ["q1", "这份 listing 今天可以直接发布？"],
            ["q2", "与参考竞品相比质量相当或更好？"],
            ["q3", "如果你是买家，看到标题和主图会点进来？"],
          ].map(([key, label]) => (
            <div key={key} style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, marginBottom: 8 }}>{label}</div>
              <div style={{ display: "flex", gap: 8 }}>
                {[true, false, null].map(v => (
                  <button key={String(v)} onClick={() => setAnn((a: any) => ({ ...a, [key]: v }))} style={choiceButton(ann[key] === v, v)}>
                    {v === true ? "是" : v === false ? "否" : "跳过"}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <label style={sectionLabel}>最大的问题</label>
          <textarea value={ann.note} onChange={e => setAnn((a: any) => ({ ...a, note: e.target.value }))}
            placeholder="例如：源页快照缺少 attributes，导致事实一致性无法自动判断。"
            style={textarea} />
        </div>
        <div>
          <div style={sectionLabel}>Failure Codes</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {codes.map(code => {
              const selected = selectedCodes.includes(code.code);
              const recommended = recommendedCodes.includes(code.code);
              return (
                <button key={code.code} onClick={() => toggleCode(code.code)} style={codeButton(selected, recommended)}>
                  {code.label}
                </button>
              );
            })}
          </div>
          <button onClick={onSave} disabled={saving} style={{ ...primaryButton, marginTop: 18 }}>
            <Save size={15} /> {saving ? "保存中" : "保存审核"}
          </button>
        </div>
      </div>
    </Panel>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <section style={panel}>{children}</section>;
}

function PanelTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 12, fontWeight: 750, color: "var(--text)" }}>{icon}{title}</div>;
}

function MiniMetric({ label, value, tone }: { label: string; value: string; tone?: "red" | "green" | "orange" }) {
  const color = tone === "red" ? "var(--red)" : tone === "orange" ? "var(--orange)" : tone === "green" ? "var(--green)" : "var(--text)";
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "8px 10px", minWidth: 0 }}>
      <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 700, color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
    </div>
  );
}

function AttributeTable({ data }: { data: Record<string, any> }) {
  const entries = Object.entries(data || {}).slice(0, 14);
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k} style={{ borderBottom: "1px solid var(--border)" }}>
            <td style={{ padding: "6px 7px", color: "var(--muted)", width: 104, verticalAlign: "top" }}>{k}</td>
            <td style={{ padding: "6px 7px", lineHeight: 1.45 }}>{typeof v === "object" ? JSON.stringify(v).slice(0, 120) : String(v).slice(0, 160)}</td>
          </tr>
        ))}
        {!entries.length && <tr><td style={{ padding: 8, color: "var(--muted)" }}>暂无结构化属性</td></tr>}
      </tbody>
    </table>
  );
}

function ImageStrip({ images }: { images: any[] }) {
  return <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, marginBottom: 12 }}>{images.slice(0, 4).map((img, i) => <ImageTile key={i} img={img} compact />)}</div>;
}

function ImageGrid({ images, compact = false }: { images: any[]; compact?: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: compact ? "repeat(3, minmax(0, 1fr))" : "repeat(5, minmax(0, 1fr))", gap: 10 }}>
      {(images || []).map((img, i) => <ImageTile key={i} img={img} index={i + 1} compact={compact} />)}
      {!images?.length && <div style={{ color: "var(--muted)", fontSize: 13 }}>暂无图片</div>}
    </div>
  );
}

function ImageTile({ img, index, compact }: { img: any; index?: number; compact?: boolean }) {
  const normalized = typeof img === "string" ? { url: img, label: "source_image" } : (img || {});
  const src = normalized.artifact_url || normalized.url || normalized.image_url;
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 6, overflow: "hidden", background: "var(--surface2)" }}>
      <div style={{ aspectRatio: "1 / 1", display: "flex", alignItems: "center", justifyContent: "center", background: "#111" }}>
        {src ? <img src={src} alt={normalized.label || `image-${index || ""}`} style={{ width: "100%", height: "100%", objectFit: "contain" }} /> : <span style={{ color: "var(--muted)", fontSize: 12 }}>no image</span>}
      </div>
      <div style={{ padding: compact ? "5px 6px" : "7px 8px", fontSize: 11, color: "var(--muted)", minHeight: compact ? 26 : 40 }}>
        <div>{index ? `${index}. ` : ""}{normalized.label || normalized.role || normalized.purpose || "image"}</div>
        {normalized.width && normalized.height ? <div>{normalized.width}×{normalized.height}</div> : null}
      </div>
    </div>
  );
}

function ClaimBadge({ status }: { status: string }) {
  const map: Record<string, [string, string, string]> = {
    supported: ["var(--green)", "有源页依据", "#22c55e55"],
    needs_review: ["var(--orange)", "待人工判断", "#f9731655"],
    no_source: ["var(--red)", "无 source", "#ef444455"],
  };
  const [color, label, borderColor] = map[status] || ["var(--muted)", status, "var(--border)"];
  return <span style={{ ...pill, color, borderColor }}>{label}</span>;
}

const backLink: React.CSSProperties = { color: "var(--muted)", fontSize: 12, display: "flex", alignItems: "center", gap: 4, marginBottom: 16 };
const topbar: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, gap: 20 };
const diagnosticGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1.25fr 0.9fr", gap: 14, marginBottom: 16 };
const panel: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 7, padding: 16 };
const metricCard: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 7, padding: "12px 13px" };
const tabs: React.CSSProperties = { display: "flex", gap: 2, marginBottom: 14, borderBottom: "1px solid var(--border)", overflowX: "auto" };
const tabButton = (active: boolean): React.CSSProperties => ({
  display: "flex", alignItems: "center", gap: 7, padding: "10px 13px", border: "none", cursor: "pointer",
  background: "transparent", color: active ? "var(--text)" : "var(--muted)", borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent", fontSize: 13, whiteSpace: "nowrap",
});
const primaryButton: React.CSSProperties = { display: "flex", alignItems: "center", gap: 7, background: "var(--accent)", color: "white", border: "none", borderRadius: 6, padding: "8px 12px", fontSize: 13, cursor: "pointer" };
const iconButton: React.CSSProperties = { display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, width: 34, height: 34, cursor: "pointer" };
const pill: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 5, padding: "2px 7px", color: "var(--muted)", fontSize: 11 };
const kvGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "70px 1fr", gap: "6px 8px", fontSize: 12, color: "var(--muted)", marginBottom: 10 };
const sourceLink: React.CSSProperties = { display: "block", fontSize: 12, color: "var(--accent)", wordBreak: "break-all", lineHeight: 1.45 };
const miniLink: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 5, padding: "5px 8px", color: "var(--accent)", fontSize: 12 };
const table: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: 12 };
const th: React.CSSProperties = { padding: "8px 9px", textAlign: "left", color: "var(--muted)", borderBottom: "1px solid var(--border)", fontWeight: 600 };
const td: React.CSSProperties = { padding: "8px 9px", verticalAlign: "top", lineHeight: 1.45 };
const sectionLabel: React.CSSProperties = { display: "block", fontSize: 11, color: "var(--muted)", marginBottom: 7, fontWeight: 650, textTransform: "uppercase" };
const aiGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 180px", gap: 10 };
const failureRow: React.CSSProperties = { display: "grid", gridTemplateColumns: "220px 1fr", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12, color: "var(--muted)" };
const textarea: React.CSSProperties = { width: "100%", minHeight: 96, resize: "vertical", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text)", padding: 10, fontSize: 13, lineHeight: 1.5 };
const choiceButton = (selected: boolean, value: boolean | null): React.CSSProperties => ({
  padding: "7px 14px", borderRadius: 6, border: "1px solid var(--border)", cursor: "pointer", fontSize: 13,
  background: selected ? (value === true ? "#22c55e22" : value === false ? "#ef444422" : "var(--surface2)") : "var(--surface2)",
  color: selected ? (value === true ? "var(--green)" : value === false ? "var(--red)" : "var(--muted)") : "var(--muted)",
});
const codeButton = (selected: boolean, recommended: boolean): React.CSSProperties => ({
  padding: "6px 10px", borderRadius: 6, border: `1px solid ${selected ? "var(--accent)" : recommended ? "var(--orange)" : "var(--border)"}`,
  background: selected ? "#0f766e33" : "var(--surface2)", color: selected ? "var(--text)" : recommended ? "var(--orange)" : "var(--muted)",
  cursor: "pointer", fontSize: 12,
});
