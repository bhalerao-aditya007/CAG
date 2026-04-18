import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ShieldWarning, ArrowRight } from "@phosphor-icons/react";

export default function Register() {
  const { register, error } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const ok = await register(name, email, password);
    setLoading(false);
    if (ok) nav("/dashboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-8">
      <form onSubmit={onSubmit} className="w-full max-w-md" data-testid="register-form">
        <div className="flex items-center gap-2 mb-12">
          <ShieldWarning size={24} weight="duotone" className="text-flag-primary" />
          <div className="font-heading font-extrabold text-lg">REDFLAG</div>
        </div>
        <div className="monokey mb-3">Register</div>
        <h2 className="font-heading text-4xl font-extrabold tracking-tighter leading-none mb-10">
          Create an auditor account.
        </h2>
        <label className="monokey block mb-2">Full name</label>
        <input data-testid="register-name" required value={name} onChange={(e)=>setName(e.target.value)} className="input-sharp mb-5" />
        <label className="monokey block mb-2">Email</label>
        <input data-testid="register-email" type="email" required value={email} onChange={(e)=>setEmail(e.target.value)} className="input-sharp mb-5" />
        <label className="monokey block mb-2">Password (min 6)</label>
        <input data-testid="register-password" type="password" required minLength={6} value={password} onChange={(e)=>setPassword(e.target.value)} className="input-sharp mb-6" />
        {error && (
          <div data-testid="register-error" className="mb-5 text-sm text-flag-critical border border-flag-critical/30 bg-flag-critical/5 p-3">{error}</div>
        )}
        <button data-testid="register-submit" type="submit" disabled={loading} className="btn-primary w-full justify-center">
          {loading ? "Creating…" : (<>Create account <ArrowRight size={16} weight="bold" /></>)}
        </button>
        <div className="mt-8 text-sm text-ink-60">
          Already registered?{" "}
          <Link to="/login" className="text-ink underline underline-offset-4" data-testid="goto-login">Sign in</Link>
        </div>
      </form>
    </div>
  );
}
