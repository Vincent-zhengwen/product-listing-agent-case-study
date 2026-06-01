import { SeverityBadge, VerdictBadge } from "./Badge";

interface Score {
  grader_id: string;
  grader_type: string;
  severity: "fatal" | "blocker" | "warning" | "info";
  verdict: "pass" | "fail" | "skipped" | null;
  confidence: string;
  score?: number | null;
  reason?: string;
  reason_json?: any;
  label?: string;
  harness_layer?: string;
  target?: string;
  stage?: string;
  calibration?: string;
  failures?: any[];
}

const LAYERS = [
  ["run_validity", "Run Validity"],
  ["outcome_verification", "Outcome Verification"],
  ["grounding", "Grounding"],
  ["conversion_quality", "Conversion Quality"],
  ["listing_quality", "Listing Quality"],
  ["process_quality", "Process Quality"],
];

function getReason(score: Score) {
  if (score.reason_json?.critique) return score.reason_json.critique;
  if (score.reason) {
    try {
      const parsed = JSON.parse(score.reason);
      return parsed.critique || score.reason;
    } catch {
      return score.reason;
    }
  }
  return "";
}

function getFailures(score: Score) {
  if (Array.isArray(score.failures)) return score.failures;
  if (Array.isArray(score.reason_json?.failures)) return score.reason_json.failures;
  return [];
}

export default function GraderResults({ scores }: { scores: Score[] }) {
  if (!scores?.length) {
    return <div style={{ color: "var(--muted)", fontSize: 13 }}>暂无评分数据</div>;
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {LAYERS.map(([layer, label]) => {
        const items = scores.filter(s => (s.harness_layer || s.reason_json?.harness_layer || "outcome_verification") === layer);
        if (!items.length) return null;
        const failed = items.filter(s => s.verdict === "fail");
        const skipped = items.filter(s => s.verdict === "skipped");
        return (
          <section key={layer} style={{ border: "1px solid var(--border)", borderRadius: 6, overflow: "hidden" }}>
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 12px", background: "var(--surface2)", borderBottom: "1px solid var(--border)",
            }}>
              <div style={{ fontSize: 12, fontWeight: 700 }}>{label}</div>
              <div style={{ display: "flex", gap: 10, fontSize: 11, color: "var(--muted)" }}>
                <span>{items.length} graders</span>
                <span style={{ color: failed.length ? "var(--red)" : "var(--green)" }}>{failed.length} fail</span>
                {skipped.length ? <span>{skipped.length} skipped</span> : null}
              </div>
            </div>
            <div>
              {items.map(score => {
                const failures = getFailures(score);
                return (
                  <div key={score.grader_id} style={{
                    padding: "10px 12px", borderBottom: "1px solid var(--border)",
                    display: "grid", gridTemplateColumns: "210px 92px 1fr", gap: 12,
                  }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 650 }}>{score.label || score.reason_json?.label || score.grader_id}</div>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                        <SeverityBadge severity={score.severity || "info"} />
                        <span style={metaPill}>{score.grader_type}</span>
                        <span style={metaPill}>{score.calibration || score.reason_json?.calibration || "trusted"}</span>
                      </div>
                    </div>
                    <div><VerdictBadge verdict={score.verdict} /></div>
                    <div>
                      {typeof score.score === "number" && (
                        <div style={{ fontSize: 20, fontWeight: 750, color: score.score >= 75 ? "var(--green)" : score.score >= 60 ? "var(--orange)" : "var(--red)", marginBottom: 4 }}>
                          {Math.round(score.score)} <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 500 }}>/100</span>
                        </div>
                      )}
                      <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>{getReason(score)}</div>
                      <div style={{ display: "flex", gap: 8, marginTop: 7, flexWrap: "wrap", fontSize: 11, color: "var(--muted)" }}>
                        <span>stage: {score.stage || score.reason_json?.stage || "final_artifact"}</span>
                        <span>target: {score.target || score.reason_json?.target || "output"}</span>
                        {score.confidence ? <span>confidence: {score.confidence}</span> : null}
                      </div>
                      {failures.length > 0 && (
                        <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                          {failures.slice(0, 3).map((failure: any, idx: number) => (
                            <div key={idx} style={{
                              borderLeft: "2px solid var(--orange)", paddingLeft: 8,
                              fontSize: 12, color: "var(--text)", lineHeight: 1.45,
                            }}>
                              <div>{failure.evidence_quote || failure.issue_type || "failure"}</div>
                              {failure.suggested_fix && (
                                <div style={{ color: "var(--muted)", marginTop: 2 }}>fix: {failure.suggested_fix}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}

const metaPill: React.CSSProperties = {
  border: "1px solid var(--border)",
  color: "var(--muted)",
  borderRadius: 4,
  padding: "1px 6px",
  textTransform: "uppercase",
};
