import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { ArrowLeft, ArrowUpRight, Spinner } from "@phosphor-icons/react";

function safeNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function formatDate(v) {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export default function AuditDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!id) return;

    if (!silent) setLoading(true);
    else setRefreshing(true);

    setError(null);

    try {
      const res = await api.get(`/audit/sessions/${id}`);
      setData(res.data || {});
    } catch {
      setError("Failed to load audit session.");
      setData(null);
    } finally {
      if (!silent) setLoading(false);
      setRefreshing(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const flags = useMemo(() => data?.flags || [], [data]);

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 bg-surface-line" />
          <div className="h-40 bg-surface-line" />
          <div className="h-64 bg-surface-line" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="mb-4 text-red-500">{error}</div>
        <button onClick={() => load()} className="btn-primary">
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="monokey mb-1">Audit Detail</div>
          <h1 className="sectiontitle text-2xl">
            {data.division_name || "—"}
          </h1>
          <div className="text-sm text-ink-60">
            {data.audit_period || "—"} • Created {formatDate(data.created_at)}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => load(true)}
            className="text-sm flex items-center gap-2"
          >
            {refreshing && <Spinner size={14} className="animate-spin" />} Refresh
          </button>
          <button
            onClick={() => navigate("/audits")}
            className="text-sm flex items-center gap-2"
          >
            <ArrowLeft size={14} /> Back
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Transactions" value={safeNum(data.transaction_count)} />
        <Card label="Flags" value={safeNum(data.flag_count)} />
        <Card label="Critical" value={safeNum(data.critical_count)} />
        <Card label="Status" value={data.status || "—"} />
      </div>

      {/* Flags Table */}
      <div className="bg-white border border-surface-line">
        <div className="px-6 py-4 border-b border-surface-line flex justify-between">
          <div className="monokey">Detected Flags</div>
          <div className="text-xs text-ink-60">
            {flags.length} items
          </div>
        </div>

        {flags.length === 0 ? (
          <div className="p-8 text-center text-ink-60 text-sm">
            No flags detected.
          </div>
        ) : (
          <table className="audit-table">
            <thead>
              <tr>
                <th>Rule</th>
                <th>Description</th>
                <th>Severity</th>
                <th>Amount</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {flags.map((f, i) => (
                <tr key={i} className="hover:bg-surface-line">
                  <td className="font-mono text-xs uppercase">
                    {f.rule_code || "—"}
                  </td>
                  <td>{f.description || "—"}</td>
                  <td>
                    <span className={`badge badge-${f.severity || "low"}`}>
                      {f.severity || "low"}
                    </span>
                  </td>
                  <td className="monokey">
                    {safeNum(f.amount)}
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

function Card({ label, value }) {
  return (
    <div className="bg-white border border-surface-line p-4">
      <div className="text-xs text-ink-60 mb-1">{label}</div>
      <div className="font-heading text-xl font-bold">{value}</div>
    </div>
  );
}
