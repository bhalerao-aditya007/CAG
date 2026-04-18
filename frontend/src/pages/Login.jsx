import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ShieldWarning, ArrowRight } from "@phosphor-icons/react";

export default function Login() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const ok = await login(email, password);
    setLoading(false);
    if (ok) nav("/dashboard");
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left: hero */}
      <div
        className="hidden lg:flex relative overflow-hidden"
        style={{
          backgroundImage:
            "url(https://images.unsplash.com/photo-1764412089634-ecbfc7e2760c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBjb3Jwb3JhdGUlMjBhcmNoaXRlY3R1cmUlMjBnbGFzcyUyMGdlb21ldHJpY3xlbnwwfHx8fDE3NzY0OTA5NDZ8MA&ixlib=rb-4.1.0&q=85)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-white/80 backdrop-blur-sm" />
        <div className="relative z-10 p-16 flex flex-col justify-between w-full">
          <div className="flex items-center gap-2">
            <ShieldWarning size={28} weight="duotone" className="text-flag-primary" />
            <div className="font-heading font-extrabold text-xl tracking-tight">REDFLAG</div>
          </div>
          <div className="max-w-md">
            <div className="monokey mb-4">PWD · Automated audit</div>
            <h1 className="font-heading text-5xl font-extrabold tracking-tighter leading-none">
              Forensic red-flag detection for Public Works auditors.
            </h1>
            <p className="text-ink-60 mt-6 leading-relaxed">
              Upload Excel, PDF or Word files from BEAMS, AMS and Agreement Registers. 17 deterministic
              rules run instantly. Download a signed PDF findings report.
            </p>
            <div className="monokey mt-10 text-ink-30">17 Rules · 4 file formats · 0 guesswork</div>
          </div>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-8 lg:p-16 bg-white">
        <form onSubmit={onSubmit} className="w-full max-w-md" data-testid="login-form">
          <div className="monokey mb-3">Sign in</div>
          <h2 className="font-heading text-4xl font-extrabold tracking-tighter leading-none mb-2">
            Access your audit desk.
          </h2>
          <p className="text-ink-60 mb-10 text-sm">
            Default admin: <span className="font-mono">auditor@pwd.gov.in</span> /{" "}
            <span className="font-mono">Audit@2026</span>
          </p>

          <label className="monokey block mb-2">Email</label>
          <input
            data-testid="login-email"
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input-sharp mb-5"
            placeholder="auditor@pwd.gov.in"
          />
          <label className="monokey block mb-2">Password</label>
          <input
            data-testid="login-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input-sharp mb-6"
            placeholder="••••••••"
          />
          {error && (
            <div
              data-testid="login-error"
              className="mb-5 text-sm text-flag-critical border border-flag-critical/30 bg-flag-critical/5 p-3"
            >
              {error}
            </div>
          )}
          <button
            data-testid="login-submit"
            type="submit"
            disabled={loading}
            className="btn-primary w-full justify-center"
          >
            {loading ? "Signing in…" : (<>Sign in <ArrowRight size={16} weight="bold" /></>)}
          </button>
          <div className="mt-8 text-sm text-ink-60">
            New auditor?{" "}
            <Link to="/register" className="text-ink underline underline-offset-4" data-testid="goto-register">
              Create an account
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
