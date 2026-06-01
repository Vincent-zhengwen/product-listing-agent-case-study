"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, PlayCircle, BarChart2, FileText, Activity } from "lucide-react";

const NAV = [
  { href: "/", label: "主页", icon: Activity },
  { href: "/datasets", label: "数据集", icon: Database },
  { href: "/tasks", label: "实验", icon: PlayCircle },
  { href: "/analysis", label: "诊断分析", icon: BarChart2 },
  { href: "/reports", label: "值班报告", icon: FileText },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside style={{ width: 200, background: "var(--surface)", borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
      <div style={{ padding: "20px 16px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>评测中心</div>
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>Diagnostic Harness</div>
      </div>
      <nav style={{ padding: "8px 0", flex: 1 }}>
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "9px 16px", fontSize: 13,
              color: active ? "var(--text)" : "var(--muted)",
              background: active ? "var(--surface2)" : "transparent",
              borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
              transition: "all 0.15s",
            }}>
              <Icon size={15} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
