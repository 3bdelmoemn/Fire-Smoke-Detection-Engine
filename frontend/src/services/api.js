const API_BASE = 'http://localhost:8000/api/v1';

function getHeaders() {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function getAuthHeaders() {
  const token = localStorage.getItem('token');
  return { 'Authorization': `Bearer ${token}` };
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Login failed');
  }
  return res.json();
}

export async function register(username, countryCode, mobilePhone, password) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      country_code: countryCode,
      mobile_phone: mobilePhone,
      password,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    // Pydantic validation errors come as an array in err.detail
    if (Array.isArray(err.detail)) {
      const msgs = err.detail.map(e => e.msg || e.message || JSON.stringify(e));
      throw new Error(msgs.join('; '));
    }
    throw new Error(err.detail || 'Registration failed');
  }
  return res.json();
}

export async function getCountryCodes() {
  const res = await fetch(`${API_BASE}/auth/country-codes`);
  if (!res.ok) return [];
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health/detailed`, { headers: getHeaders() });
  return res.json();
}

export async function getKPIs() {
  const res = await fetch(`${API_BASE}/health/kpis`, { headers: getHeaders() });
  return res.json();
}

export async function getDetections(page = 1, perPage = 20) {
  const res = await fetch(`${API_BASE}/alerts?page=${page}&per_page=${perPage}`, {
    headers: getHeaders(),
  });
  if (!res.ok) return { items: [], total: 0 };
  return res.json();
}

export async function getAlerts(page = 1, perPage = 20) {
  const res = await fetch(`${API_BASE}/alerts?page=${page}&per_page=${perPage}`, {
    headers: getHeaders(),
  });
  if (!res.ok) return { items: [], total: 0 };
  return res.json();
}

export async function detectImage(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/detect/image`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Detection failed');
  }
  return res.json();
}

export async function detectVideo(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/detect/video`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Detection failed');
  }
  return res.json();
}

export async function startStream() {
  const res = await fetch(`${API_BASE}/stream/start`, {
    method: 'POST',
    headers: getHeaders(),
  });
  return res.json();
}

export async function stopStream() {
  const res = await fetch(`${API_BASE}/stream/stop`, {
    method: 'POST',
    headers: getHeaders(),
  });
  return res.json();
}

export async function getStreamStatus() {
  const res = await fetch(`${API_BASE}/stream/status`, { headers: getHeaders() });
  return res.json();
}

export async function getEvaluationAssets() {
  const res = await fetch(`${API_BASE}/evaluation/assets`, { headers: getHeaders() });
  return res.json();
}

export function getEvalAssetUrl(category, filename) {
  return `${API_BASE}/evaluation/assets/${category}/${filename}`;
}

export function createWebSocket() {
  return new WebSocket('ws://localhost:8000/api/v1/stream/ws');
}
