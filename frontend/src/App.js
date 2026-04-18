import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import AuditSessions from "./pages/AuditSessions";
import NewAudit from "./pages/NewAudit";
import AuditDetail from "./pages/AuditDetail";
import RulesLibrary from "./pages/RulesLibrary";
import Layout from "./components/Layout";

function PrivateRoute({ children }) {
  const { user } = useAuth();
  if (user === null) return <div className="min-h-screen flex items-center justify-center"><div className="monokey">Loading...</div></div>;
  if (user === false) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function PublicRoute({ children }) {
  const { user } = useAuth();
  if (user === null) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
          <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/audits" element={<PrivateRoute><AuditSessions /></PrivateRoute>} />
          <Route path="/audits/new" element={<PrivateRoute><NewAudit /></PrivateRoute>} />
          <Route path="/audits/:id" element={<PrivateRoute><AuditDetail /></PrivateRoute>} />
          <Route path="/rules" element={<PrivateRoute><RulesLibrary /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
