import { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom';
import {
  Flame, LayoutDashboard, Video, Upload, BarChart3,
  Bell, LogOut, Shield
} from 'lucide-react';

import LoginPage from './pages/Login';
import Dashboard from './pages/Dashboard';
import UploadPage from './pages/Upload';
import EvaluationPage from './pages/Evaluation';
import AlertsPage from './pages/Alerts';

import './index.css';

function Sidebar({ onLogout, user }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">
          <Flame size={20} color="white" />
        </div>
        <div>
          <h1>FireGuard AI</h1>
          <div className="brand-sub">Detection System</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} end>
          <LayoutDashboard size={20} />
          Dashboard
        </NavLink>
        <NavLink to="/upload" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Upload size={20} />
          Upload & Detect
        </NavLink>
        <NavLink to="/evaluation" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <BarChart3 size={20} />
          Model Evaluation
        </NavLink>
        <NavLink to="/alerts" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Bell size={20} />
          Alert History
        </NavLink>
      </nav>

      <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', marginBottom: 8 }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'var(--gradient-blue)', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            fontSize: '0.8rem', fontWeight: 700,
          }}>
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>{user?.username || 'User'}</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Operator</div>
          </div>
        </div>
        <button className="nav-link" onClick={onLogout} style={{ color: 'var(--accent-fire)' }}>
          <LogOut size={18} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}

function AppLayout({ onLogout, user }) {
  return (
    <div className="app-layout">
      <Sidebar onLogout={onLogout} user={user} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState(() => {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    return token ? { token, user: user ? JSON.parse(user) : null } : null;
  });

  const handleLogin = (data) => {
    setAuth({ token: data.access_token, user: { id: data.user_id, username: data.username } });
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setAuth(null);
  };

  return (
    <BrowserRouter>
      {auth ? (
        <AppLayout onLogout={handleLogout} user={auth.user} />
      ) : (
        <Routes>
          <Route path="*" element={<LoginPage onLogin={handleLogin} />} />
        </Routes>
      )}
    </BrowserRouter>
  );
}
