import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  ChartBar, FileMagnifyingGlass, Books, SignOut,
  ShieldWarning, User, Plus,
} from "@phosphor-icons/react";

const NAV = [
  { to: "/dashboard", label: "Overview", icon: ChartBar },
  { to: "/audits", label: "Audit Sessions", icon: FileMagnifyingGlass },
  { to: "/rules", label: "Rules Library", icon: Books },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  return (
    <div className="min-h-screen flex bg-surface-muted">
      <aside className="w-64 bg-white border-r border-surface-line flex flex-col sticky top-0 h-screen">
        <div className="px-6 py-6 border-b border-surface-line">
          <div className="flex items-center gap-2">
            <ShieldWarning size={24} weight="duotone" className="text-flag-primary" />
            <div>
              <div className="font-heading font-extrabold text-lg tracking-tight leading-none">REDFLAG</div>
              <div className="monokey mt-0.5">PWD Audit · v1.0</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-6 space-y-0.5">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                data-testid={`nav-${item.to.replace("/", "")}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-ink text-white"
                      : "text-ink-60 hover:bg-surface-muted hover:text-ink"
                  }`
                }
              >
                <Icon size={18} weight="regular" />
                {item.label}
              </NavLink>
            );
          })}
          <button
            data-testid="nav-new-audit"
            onClick={() => nav("/audits/new")}
            className="btn-primary w-full mt-6"
          >
            <Plus size={16} weight="bold" /> New audit
          </button>
        </nav>
        <div className="p-4 border-t border-surface-line">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <User size={16} className="text-ink-60" />
                <span className="text-sm font-medium truncate">{user?.name || user?.email}</span>
              </div>
              <div className="text-xs text-ink-60 truncate mt-0.5">{user?.email}</div>
            </div>
            <button
              data-testid="logout-btn"
              onClick={logout}
              title="Sign out"
              className="p-2 border border-surface-line hover:border-ink transition-colors"
            >
              <SignOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0 animate-fade-in">{children}</main>
    </div>
  );
}
