"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Clock } from "lucide-react";

interface Step {
  step_id: number | string;
  name: string;
  status: string;
  duration_ms?: number;
  model?: string;
  tokens?: number;
  input?: any;
  output?: any;
  error?: string | null;
}

interface Trace {
  steps: Step[];
  total_tokens?: number;
  total_model_calls?: number;
}

export default function TraceViewer({ trace }: { trace: Trace | null }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  if (!trace || !trace.steps?.length) {
    return <div style={{ color: "var(--muted)", fontSize: 13 }}>暂无 Trace 数据</div>;
  }

  const toggle = (id: string) => setOpen(prev => ({ ...prev, [id]: !prev[id] }));

  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 12, color: "var(--muted)" }}>
        <span>共 {trace.steps.length} 步</span>
        {trace.total_tokens ? <span>总 Token: {trace.total_tokens}</span> : null}
        {trace.total_model_calls ? <span>模型调用: {trace.total_model_calls} 次</span> : null}
      </div>
      {trace.steps.map((step, i) => {
        const key = String(i);
        const isOpen = !!open[key];
        const success = step.status === "success";
        return (
          <div key={key} style={{
            border: "1px solid var(--border)", borderRadius: 6,
            marginBottom: 6, overflow: "hidden",
          }}>
            <button
              onClick={() => toggle(key)}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: 10,
                padding: "9px 12px", background: "var(--surface2)",
                border: "none", cursor: "pointer", color: "var(--text)",
              }}
            >
              {success
                ? <CheckCircle size={14} color="var(--green)" />
                : <XCircle size={14} color="var(--red)" />}
              <span style={{ fontSize: 12, fontWeight: 600, flex: 1, textAlign: "left" }}>
                Step {step.step_id}: {step.name}
              </span>
              {step.duration_ms ? (
                <span style={{ fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 4 }}>
                  <Clock size={11} /> {(step.duration_ms / 1000).toFixed(2)}s
                </span>
              ) : null}
              {step.model && (
                <span style={{ fontSize: 11, color: "var(--accent)", marginLeft: 8 }}>
                  {step.model} {step.tokens ? `· ${step.tokens}tk` : ""}
                </span>
              )}
              {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </button>
            {isOpen && (
              <div style={{ padding: "10px 12px", background: "var(--surface)", borderTop: "1px solid var(--border)" }}>
                {step.error && (
                  <div style={{ color: "var(--red)", fontSize: 12, marginBottom: 8 }}>
                    ❌ 错误: {step.error}
                  </div>
                )}
                {step.output && (
                  <div>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>OUTPUT</div>
                    <pre style={{
                      fontSize: 11, color: "var(--text)", background: "var(--surface2)",
                      padding: 8, borderRadius: 4, overflow: "auto", maxHeight: 200,
                      whiteSpace: "pre-wrap", wordBreak: "break-all",
                    }}>
                      {JSON.stringify(step.output, null, 2)}
                    </pre>
                  </div>
                )}
                {step.input && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>INPUT</div>
                    <pre style={{
                      fontSize: 11, color: "var(--muted)", background: "var(--surface2)",
                      padding: 8, borderRadius: 4, overflow: "auto", maxHeight: 120,
                      whiteSpace: "pre-wrap", wordBreak: "break-all",
                    }}>
                      {JSON.stringify(step.input, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
