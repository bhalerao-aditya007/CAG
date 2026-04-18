import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { MagnifyingGlass, ArrowClockwise } from "@phosphor-icons/react";

function safeStr(v) {
  return typeof v === "string" ? v : "";
}

function safeNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

const SEVERITIES = ["all", "critical", "high", "medium", "low"];

export default function RulesLibrary() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);

    api
      .get("/rules")
      .then((res) => {
        const data = Array.isArray(res.data) ? res.data : [];
        setRules(data);
      })
      .catch(() => {
        setError("Failed to load rules.");
        setRules([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    return rules.filter((r) => {
      const matchesQuery =
        safeStr(r.code).toLowerCase().includes(query.toLowerCase()) ||
        safeStr(r.description).toLowerCase().includes(query.toLowerCase());

      const matchesSeverity =
        severity === "all" || safeStr(r.severity) === severity;

      return matchesQuery && matchesSeverity;
    });
  }, [rules, query, severity]);

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 bg-surface-line" />
          <div className="h-64 bg-surface-line" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="mb-4 text-red-500">{error}</div>
        <button onClick={load} className="btn-primary">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <div className="monokey mb-1">Rules</div>
        <h1 className="sectiontitle text-2xl">Rules Library</h1>
      </div>

      {/* Controls */}
      <div className="flex flex-col lg:flex-row gap-3 items-start lg:items-center justify-between">
        <div className="flex items-center gap-2 border border-surface-line px-3 py-2 w-full lg:w-80">
          <MagnifyingGlass size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search rules..."
            className="w-full outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="border border-surface-line px-2 py-1"
          >
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          <button onClick={load} className="p-2">
            <ArrowClockwise size={16} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-surface-line">
        {filtered.length === 0 ? (
          <div className="p-8 text-center text-ink-60 text-sm">
            No rules found.
          </div>
        ) : (
          <table className="audit-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Description</th>
                <th>Severity</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.code} className="hover:bg-surface-line">
                  <td className="font-mono text-xs uppercase">
                    {safeStr(r.code) || "—"}
                  </td>
                  <td>{safeStr(r.description) || "—"}</td>
                  <td>
                    <span className={`badge badge-${safeStr(r.severity) || "low"}`}>
                      {safeStr(r.severity) || "low"}
                    </span>
                  </td>
                  <td className="monokey">{safeNum(r.score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
