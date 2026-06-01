export type Severity = "fatal" | "blocker" | "warning" | "info";
export type Verdict = "pass" | "fail" | "skipped" | null;

const SEVERITY_COLOR: Record<Severity, string> = {
  fatal: "#ef444422",
  blocker: "#ef444422",
  warning: "#f9731622",
  info: "#6c6ef722",
};
const SEVERITY_TEXT: Record<Severity, string> = {
  fatal: "#ef4444",
  blocker: "#ef4444",
  warning: "#f97316",
  info: "#6c6ef7",
};
const VERDICT_COLOR: Record<string, string> = {
  pass: "#22c55e22",
  fail: "#ef444422",
  skipped: "#8892a422",
};
const VERDICT_TEXT: Record<string, string> = {
  pass: "#22c55e",
  fail: "#ef4444",
  skipped: "#8892a4",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const label: Record<Severity, string> = { fatal: "FATAL", blocker: "BLOCKER", warning: "WARNING", info: "INFO" };
  return (
    <span style={{
      background: SEVERITY_COLOR[severity],
      color: SEVERITY_TEXT[severity],
      padding: "1px 7px", borderRadius: 4, fontSize: 10, fontWeight: 700,
      border: `1px solid ${SEVERITY_TEXT[severity]}44`,
    }}>
      {label[severity]}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  if (verdict === null) return <span style={{ color: "var(--muted)", fontSize: 12 }}>—</span>;
  const label = verdict === "pass" ? "PASS" : verdict === "fail" ? "FAIL" : "SKIP";
  return (
    <span style={{
      background: VERDICT_COLOR[verdict],
      color: VERDICT_TEXT[verdict],
      padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
    }}>
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    running: ["#f9731622", "#f97316"],
    completed: ["#22c55e22", "#22c55e"],
    failed: ["#ef444422", "#ef4444"],
    pending: ["#6c6ef722", "#6c6ef7"],
  };
  const [bg, text] = map[status] || ["#ffffff22", "#ffffff"];
  return (
    <span style={{ background: bg, color: text, padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
      {status}
    </span>
  );
}
