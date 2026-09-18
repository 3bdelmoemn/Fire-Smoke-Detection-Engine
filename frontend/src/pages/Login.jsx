import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register, getCountryCodes } from '../services/api';
import { Flame, Shield, Phone, User, Lock, Eye, EyeOff, Check, X, ChevronDown } from 'lucide-react';

// ── Password requirement checker ────────────────────────────────────────
const PASSWORD_RULES = [
  { id: 'length', label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { id: 'upper', label: 'Contains an uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'Contains a lowercase letter', test: (p) => /[a-z]/.test(p) },
  { id: 'number', label: 'Contains a number', test: (p) => /\d/.test(p) },
  { id: 'special', label: 'Contains a special character', test: (p) => /[!@#$%^&*()_+\-=[\]{}|;':",./<>?`~\\]/.test(p) },
];

export default function LoginPage({ onLogin }) {
  const [tab, setTab] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [countryCode, setCountryCode] = useState('+20');
  const [countryCodes, setCountryCodes] = useState([]);
  const [showPassword, setShowPassword] = useState(false);
  const [showCodeDropdown, setShowCodeDropdown] = useState(false);
  const [codeSearch, setCodeSearch] = useState('');
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Load country codes from backend
  useEffect(() => {
    getCountryCodes()
      .then((codes) => {
        if (codes && codes.length > 0) setCountryCodes(codes);
        else {
          // Fallback if API is unreachable
          setCountryCodes([
            { code: '+20', name: 'Egypt', iso: 'EG' },
            { code: '+1', name: 'United States', iso: 'US' },
            { code: '+44', name: 'United Kingdom', iso: 'GB' },
            { code: '+966', name: 'Saudi Arabia', iso: 'SA' },
            { code: '+971', name: 'UAE', iso: 'AE' },
          ]);
        }
      })
      .catch(() => {
        setCountryCodes([
          { code: '+20', name: 'Egypt', iso: 'EG' },
          { code: '+1', name: 'United States', iso: 'US' },
          { code: '+44', name: 'United Kingdom', iso: 'GB' },
        ]);
      });
  }, []);

  // Password validation results
  const pwdResults = useMemo(
    () => PASSWORD_RULES.map((rule) => ({ ...rule, met: rule.test(password) })),
    [password]
  );
  const allPwdMet = useMemo(() => pwdResults.every((r) => r.met), [pwdResults]);

  // Filtered country codes for search
  const filteredCodes = useMemo(() => {
    if (!codeSearch) return countryCodes;
    const q = codeSearch.toLowerCase();
    return countryCodes.filter(
      (c) => c.name.toLowerCase().includes(q) || c.code.includes(q) || c.iso.toLowerCase().includes(q)
    );
  }, [countryCodes, codeSearch]);

  const selectedCountry = useMemo(
    () => countryCodes.find((c) => c.code === countryCode) || { code: countryCode, name: '', iso: '' },
    [countryCodes, countryCode]
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!showCodeDropdown) return;
    const handler = (e) => {
      if (!e.target.closest('.country-code-selector')) setShowCodeDropdown(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showCodeDropdown]);

  const canSubmitRegister = username.length >= 3 && phone.length >= 4 && allPwdMet;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setLoading(true);

    try {
      if (tab === 'register') {
        if (!canSubmitRegister) {
          setError('Please fill all fields correctly and meet all password requirements.');
          setLoading(false);
          return;
        }
        await register(username, countryCode, phone, password);
        setSuccessMsg('Account created successfully! You can now sign in.');
        setTab('login');
        setLoading(false);
        return;
      }
      const data = await login(username, password);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify({ id: data.user_id, username: data.username }));
      onLogin(data);
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand">
          <div className="brand-icon-lg">
            <Flame size={32} color="white" />
          </div>
          <h2>Fire & Smoke Detection</h2>
          <p className="sub">AI-Powered Real-Time Monitoring System</p>
        </div>

        <div className="login-tabs">
          <button
            className={`login-tab ${tab === 'login' ? 'active' : ''}`}
            onClick={() => { setTab('login'); setError(''); setSuccessMsg(''); }}
          >
            Sign In
          </button>
          <button
            className={`login-tab ${tab === 'register' ? 'active' : ''}`}
            onClick={() => { setTab('register'); setError(''); setSuccessMsg(''); }}
          >
            Register
          </button>
        </div>

        {error && <div className="error-msg">{error}</div>}
        {successMsg && <div className="success-msg">{successMsg}</div>}

        <form onSubmit={handleSubmit}>
          {/* Username */}
          <div className="form-group">
            <label className="form-label">
              <User size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
              Username
            </label>
            <input
              id="auth-username"
              className="form-input"
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          </div>

          {/* WhatsApp Phone — registration only */}
          {tab === 'register' && (
            <div className="form-group">
              <label className="form-label">
                <Phone size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                WhatsApp Number
              </label>
              <div className="phone-input-group">
                {/* Country code selector */}
                <div className="country-code-selector">
                  <button
                    type="button"
                    className="country-code-btn"
                    onClick={() => setShowCodeDropdown((v) => !v)}
                  >
                    <span className="cc-code">{selectedCountry.code}</span>
                    <ChevronDown size={14} />
                  </button>
                  {showCodeDropdown && (
                    <div className="country-code-dropdown">
                      <input
                        type="text"
                        className="cc-search"
                        placeholder="Search country..."
                        value={codeSearch}
                        onChange={(e) => setCodeSearch(e.target.value)}
                        autoFocus
                      />
                      <div className="cc-list">
                        {filteredCodes.map((c) => (
                          <button
                            key={c.iso}
                            type="button"
                            className={`cc-option ${c.code === countryCode ? 'selected' : ''}`}
                            onClick={() => {
                              setCountryCode(c.code);
                              setShowCodeDropdown(false);
                              setCodeSearch('');
                            }}
                          >
                            <span className="cc-name">{c.name}</span>
                            <span className="cc-code-label">{c.code}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                {/* Phone number input */}
                <input
                  id="auth-phone"
                  className="form-input phone-number-input"
                  type="tel"
                  placeholder="1012345678"
                  value={phone}
                  onChange={(e) => {
                    // Allow only digits and leading zeros
                    const v = e.target.value.replace(/[^\d]/g, '');
                    setPhone(v);
                  }}
                  required
                  autoComplete="tel"
                />
              </div>
              <p className="form-hint">
                Enter your local number without the country code
              </p>
            </div>
          )}

          {/* Password */}
          <div className="form-group">
            <label className="form-label">
              <Lock size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
              Password
            </label>
            <div className="password-input-wrap">
              <input
                id="auth-password"
                className="form-input"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={tab === 'register' ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Password requirements — registration only, shown when typing */}
            {tab === 'register' && password.length > 0 && (
              <div className="pwd-requirements">
                <p className="pwd-req-title">Password requirements:</p>
                {pwdResults.map((r) => (
                  <div key={r.id} className={`pwd-req-item ${r.met ? 'met' : 'unmet'}`}>
                    {r.met ? <Check size={13} /> : <X size={13} />}
                    <span>{r.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <button
            id="auth-submit"
            className="btn btn-primary"
            type="submit"
            disabled={loading || (tab === 'register' && !canSubmitRegister)}
            style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
          >
            {loading ? <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} /> : (
              <>
                <Shield size={16} />
                {tab === 'login' ? 'Sign In' : 'Create Account'}
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
