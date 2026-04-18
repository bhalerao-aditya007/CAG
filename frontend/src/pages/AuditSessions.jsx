import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { ArrowRight, ArrowUpRight, Trash } from "@phosphor-icons/react";

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString();
}

function safeNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

export default function AuditSessions() {
  const navigate = useNavigate();

  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);

    api
      .get("/audit/sessions")
      .then((res) => {
        const data = Array.isArray(res.data) ? res.data : [];
        setSessions(data);
      })
      .catch(() => {
        setError("Failed to load sessions.");
        setSessions([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let mounted = true;

    setLoading(true);
    setError(null);

    api
      .get("/audit/sessions")
      .then((res) => {
        if (!mounted) return;
        const data = Array.isArray(res.data) ? res.data : [];
        setSessions(data);
      })
      .catch(() => {
        if (!mounted) return;
        setError("Failed to load sessions.");
        setSessions([]);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const hasData = (sessions?.length ?? 0) > 0;

  const handleDelete = useCallback(async (id) => {
    if (!id) return;

    const ok = window.confirm("Delete this session? This action cannot be undone.");
    if (!ok) return;

    try {
      setDeletingId(id);
      await api.delete(`/audit/sessions/${id}`);

      // optimistic update
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      alert("Failed to delete session.");
    } finally {
      setDeletingId(null);
    }
  }, []);

  const rows = useMemo(() => {
    return sessions.map((s) => ({
      id: s.id,
      division: s.division_name || "—",
      period: s.audit_period || "—",
      transactions: safeNum(s.transaction_count),
      flags: safeNum(s.flag_count),
      critical: safeNum(s.critical_count),
      status: s.status || "unknown",
      created: formatDate(s.created_at),
    }));
  }, [sessions]);

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
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="monokey mb-1">Audits</div>
          <h1 className="sectiontitle text-2xl">Audit Sessions</h1>
        </div>
        <button
          onClick={() => navigate("/audits/new")}
          className="btn-primary flex items-center gap-2"
        >
          New Session <ArrowRight size={14} />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white border border-surface-line">
        {(hasData && (
          <table className="audit-table">
            <thead>
              <tr>
                <th>Division</th>
                <th>Period</th>
                <th>Transactions</th>
                <th>Flags</th>
                <th>Critical</th>
                <th>Status</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-surface-line">
                  <td>
                    <button
                      onClick={() => navigate(`/audits/${r.id}`)}
                      className="text-left w-full"
                    >
                      {r.division}
                    </button>
                  </td>
                  <td className="text-ink-60 text-sm">{r.period}</td>
                  <td className="monokey">{r.transactions}</td>
                  <td className="monokey">{r.flags}</td>
                  <td>
                    {r.critical > 0 ? (
                      <span className="badge badge-critical">{r.critical}</span>
                    ) : (
                      <span className="text-ink-30">—</span>
                    )}
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        r.status === "completed" ? "badge-medium" : "badge-low"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="text-ink-60 text-sm">{r.created}</td>
                  <td className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(`/audits/${r.id}`)}
                      className="p-1"
                      title="Open"
                    >
                      <ArrowUpRight size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(r.id)}
                      className="p-1 text-red-500"
                      disabled={deletingId === r.id}
                      title="Delete"
                    >
                      <Trash size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )) || (
          <div className="p-8 text-center text-ink-60 text-sm">
            No audit sessions found.
          </div>
        )}
      </div>
    </div>
  );
}
