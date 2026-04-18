import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { ArrowLeft, FloppyDisk, UploadSimple } from "@phosphor-icons/react";

function safeStr(v) {
  return typeof v === "string" ? v : "";
}

function safeNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

export default function NewAudit() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    division_name: "",
    audit_period: "",
  });

  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const onChange = useCallback((e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }, []);

  const onFileChange = useCallback((e) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
  }, []);

  const isValid = useMemo(() => {
    return safeStr(form.division_name).trim().length > 0 && file;
  }, [form, file]);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (!isValid || submitting) return;

    setSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      const fd = new FormData();
      fd.append("division_name", safeStr(form.division_name).trim());
      fd.append("audit_period", safeStr(form.audit_period));
      if (file) fd.append("file", file);

      const res = await api.post("/audit/sessions", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const id = res?.data?.id;
      setSuccess(true);

      // slight delay for UX feedback
      setTimeout(() => {
        if (id) navigate(`/audits/${id}`);
        else navigate("/audits");
      }, 600);
    } catch (err) {
      setError("Failed to create audit session.");
    } finally {
      setSubmitting(false);
    }
  }, [form, file, isValid, submitting, navigate]);

  useEffect(() => {
    return () => {
      // cleanup file reference
      setFile(null);
    };
  }, []);

  return (
    <div className="p-8 max-w-2xl">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="monokey mb-1">Audits</div>
          <h1 className="sectiontitle text-2xl">New Audit Session</h1>
        </div>
        <button
          onClick={() => navigate("/audits")}
          className="text-sm flex items-center gap-2"
        >
          <ArrowLeft size={14} /> Back
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm mb-1">Division Name *</label>
          <input
            name="division_name"
            value={form.division_name}
            onChange={onChange}
            className="w-full border border-surface-line px-3 py-2"
            placeholder="e.g. Finance"
            required
          />
        </div>

        <div>
          <label className="block text-sm mb-1">Audit Period</label>
          <input
            name="audit_period"
            value={form.audit_period}
            onChange={onChange}
            className="w-full border border-surface-line px-3 py-2"
            placeholder="e.g. Jan 2026"
          />
        </div>

        <div>
          <label className="block text-sm mb-1">Upload File *</label>
          <label className="flex items-center gap-3 border border-dashed border-surface-line p-4 cursor-pointer">
            <UploadSimple size={18} />
            <span className="text-sm">
              {file ? file.name : "Click to upload CSV / Excel"}
            </span>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={onFileChange}
              className="hidden"
              required
            />
          </label>
        </div>

        {error && <div className="text-red-500 text-sm">{error}</div>}
        {success && <div className="text-green-600 text-sm">Session created successfully.</div>}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!isValid || submitting}
            className="btn-primary flex items-center gap-2"
          >
            <FloppyDisk size={14} />
            {submitting ? "Creating..." : "Create Session"}
          </button>
        </div>
      </form>
    </div>
  );
}
