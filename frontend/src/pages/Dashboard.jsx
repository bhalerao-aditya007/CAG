import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import {
  ShieldWarning,
  Warning,
  ArrowRight,
  FileMagnifyingGlass,
  CheckCircle,
  ArrowUpRight,
} from "@phosphor-icons/react";

const SEVERITY_CONFIG = [
  { key: "critical", label: "Critical", class: "badge-critical", bar: "bg-flag-critical" },
  { key: "high", label: "High", class: "badge-high", bar: "bg-flag-high" },
  { key: "medium", label: "Medium", class: "badge-medium", bar: "bg-flag-medium" },
  { key: "low", label: "Low", class: "badge-low", bar: "bg-flag-low" },
];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let mounted = true;

    api
      .get("/stats/overview")
      .then((res) => {
        if (!mounted) return;
        setStats(res.data || {});
      })
      .catch(() => {
        if (!mounted) return;
        setError("Failed to load dashboard data.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const topRules = useMemo(() => {
    if (!stats?.by_rule) return [];

    return Object.entries(stats.by_rule)
      .map(([k, v]) => [k, Number(v) || 0])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }, [stats]);

  if (loading) {
    return (
      <div className="p-10">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 bg-surface-line" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 bg-surface-line" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return <div className="p-10 text-red-500">{error}</div>;
  }

  if (!stats) return null;

  const totalFlags = Number(stats.total_flags) || 0;

  const safe = (val) => (Number.isFinite(Number(val)) ? Number(val) : 0);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8 flex items-end justify-between">
        <div>
          <div className="monokey mb-1">Overview</div>
          <h1 className="sectiontitle text-3xl">Audit Intelligence Dashboard</h1>
        </div>
        <button
          onClick={() => navigate("/audits/new")}
          className="btn-primary flex items-center gap-2"
        >
          <FileMagnifyingGlass size={16} weight="bold" />
          New Audit Session
        </button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          {
            label: "Total Sessions",
            value: safe(stats.total_sessions),
            icon: FileMagnifyingGlass,
            color: "text-flag-primary",
          },
          {
            label: "Transactions Parsed",
            value: safe(stats.total_transactions).toLocaleString(),
            icon: CheckCircle,
            color: "text-flag-medium",
          },
          {
            label: "Total Red Flags",
            value: safe(stats.total_flags),
            icon: Warning,
            color: "text-flag-high",
          },
          {
            label: "Critical Flags",
            value: safe(stats.critical_count),
            icon: ShieldWarning,
            color: "text-flag-critical",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white border border-surface-line p-6">
            <div className="flex items-start justify-between mb-4">
              <span className="monokey">{label}</span>
              <Icon size={20} weight="duotone" className={color} />
            </div>
            <div className={`font-heading text-4xl font-extrabold ${color}`}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Severity + Top Rules */}
      <div className="grid lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white border border-surface-line p-6">
          <div className="monokey mb-5">Severity Breakdown</div>
          <div className="space-y-3">
            {SEVERITY_CONFIG.map(({ key, label, class: cls, bar }) => {
              const count = safe(stats[`${key}_count`]);
              const pct = totalFlags ? Math.round((count / totalFlags) * 100) : 0;

              return (
                <div key={key}>
                  <div className="flex justify-between mb-1.5">
                    <span className={`badge ${cls}`}>{label}</span>
                    <span className="monokey">
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div className="h-1.5 bg-surface-line w-full">
                    <div className={`h-full ${bar}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white border border-surface-line p-6">
          <div className="monokey mb-5">Top Flagged Rules</div>
          {topRules.length === 0 ? (
            <p className="text-ink-60 text-sm">No flags detected yet.</p>
          ) : (
            <div className="space-y-2">
              {topRules.map(([code, count]) => (
                <div
                  key={code}
                  className="flex items-center justify-between py-1.5 border-b border-surface-line last:border-0"
                >
                  <span className="font-mono text-xs text-ink-60 uppercase">
                    {code}
                  </span>
                  <span className="font-heading font-bold text-lg">
                    {count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Sessions */}
      <div className="bg-white border border-surface-line">
        <div className="px-6 py-4 border-b border-surface-line flex justify-between">
          <div className="monokey">Recent Audit Sessions</div>
          <button
            onClick={() => navigate("/audits")}
            className="text-xs text-ink-60 hover:text-ink flex items-center gap-1"
          >
            View all <ArrowRight size={12} />
          </button>
        </div>

        {(stats.recent_sessions?.length ?? 0) === 0 ? (
          <div className="p-8 text-center text-ink-60 text-sm">
            No audit sessions yet.
          </div>
        ) : (
          <table className="audit-table">
            <thead>
              <tr>
                <th>Division</th>
                <th>Period</th>
                <th>Transactions</th>
                <th>Flags</th>
                <th>Critical</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {stats.recent_sessions.map((s) => (
                <tr key={s.id} className="hover:bg-surface-line">
                  <td>
                    <button
                      onClick={() => navigate(`/audits/${s.id}`)}
                      className="text-left w-full"
                    >
                      {s.division_name}
                    </button>
                  </td>
                  <td className="text-ink-60 text-sm">
                    {s.audit_period || "—"}
                  </td>
                  <td className="monokey">{safe(s.transaction_count)}</td>
                  <td className="monokey">{safe(s.flag_count)}</td>
                  <td>
                    {safe(s.critical_count) > 0 ? (
                      <span className="badge badge-critical">
                        {safe(s.critical_count)}
                      </span>
                    ) : (
                      <span className="text-ink-30">—</span>
                    )}
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        s.status === "completed"
                          ? "badge-medium"
                          : "badge-low"
                      }`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td>
                    <ArrowUpRight size={14} className="text-ink-30" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
