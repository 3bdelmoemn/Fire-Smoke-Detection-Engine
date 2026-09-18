import { useState, useEffect, useRef, useCallback } from 'react';
import { Flame, Wind, Shield, Activity, AlertTriangle, Bell, TrendingUp } from 'lucide-react';
import { createWebSocket, startStream, stopStream, getStreamStatus, getAlerts } from '../services/api';

// ── Alarm Sound via Web Audio API ───────────────────────────────────────
// Generates a pulsing alarm tone for ~3 seconds, then stops.
// No external audio file needed.
const ALARM_DURATION_MS = 3000;

function playAlarmSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const startTime = ctx.currentTime;
    const endTime = startTime + ALARM_DURATION_MS / 1000;

    // Create a pulsing alarm with two alternating tones
    const frequencies = [880, 660]; // A5 and E5
    const pulseInterval = 0.25; // seconds per pulse

    for (let t = 0; t < ALARM_DURATION_MS / 1000; t += pulseInterval) {
      const freq = frequencies[Math.floor(t / pulseInterval) % 2];
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'square';
      osc.frequency.setValueAtTime(freq, startTime + t);

      // Envelope: quick attack, sustain, quick release
      gain.gain.setValueAtTime(0, startTime + t);
      gain.gain.linearRampToValueAtTime(0.15, startTime + t + 0.02);
      gain.gain.setValueAtTime(0.15, startTime + t + pulseInterval - 0.03);
      gain.gain.linearRampToValueAtTime(0, startTime + t + pulseInterval);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(startTime + t);
      osc.stop(startTime + t + pulseInterval);
    }

    // Close context after alarm finishes to free resources
    setTimeout(() => ctx.close().catch(() => {}), ALARM_DURATION_MS + 500);
    return true;
  } catch (err) {
    console.warn('Alarm playback failed:', err);
    return false;
  }
}

export default function Dashboard() {
  const [status, setStatus] = useState('clear');
  const [streaming, setStreaming] = useState(false);
  const [frame, setFrame] = useState(null);
  const [detections, setDetections] = useState([]);
  const [stats, setStats] = useState({ frameNumber: 0, latency: 0 });
  const [alerts, setAlerts] = useState([]);
  const [kpis, setKpis] = useState({ totalFire: 0, totalSmoke: 0, totalAlerts: 0, avgConf: 0 });
  const [recentAlerts, setRecentAlerts] = useState([]);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  // Track alert UIDs we've already handled (alarm + display)
  // Using a ref so it persists across renders without triggering re-renders
  const handledAlertUids = useRef(new Set());

  // Debounce alert list refresh to avoid excessive API calls
  const alertRefreshTimer = useRef(null);
  const scheduleAlertRefresh = useCallback(() => {
    if (alertRefreshTimer.current) return; // already scheduled
    alertRefreshTimer.current = setTimeout(() => {
      getAlerts(1, 5).then(r => setRecentAlerts(r.items || [])).catch(() => {});
      alertRefreshTimer.current = null;
    }, 2000); // wait 2s to batch multiple rapid alerts
  }, []);

  // Load recent alerts on mount
  useEffect(() => {
    getAlerts(1, 5).then(data => setRecentAlerts(data.items || [])).catch(() => {});
    getStreamStatus().then(data => setStreaming(data.streaming)).catch(() => {});
  }, []);

  // WebSocket connection
  useEffect(() => {
    function connect() {
      const ws = createWebSocket();
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'detection') {
          setFrame(`data:image/jpeg;base64,${data.frame}`);
          setDetections(data.detections || []);
          setStats({ frameNumber: data.frame_number, latency: data.latency_ms });

          if (data.status?.includes('FIRE')) setStatus('fire');
          else if (data.status?.includes('SMOKE')) setStatus('smoke');
          else setStatus('clear');

          // Update live KPIs
          setKpis(prev => ({
            ...prev,
            totalFire: prev.totalFire + (data.detections?.filter(d => d.class_name === 'fire').length || 0),
            totalSmoke: prev.totalSmoke + (data.detections?.filter(d => d.class_name === 'smoke').length || 0),
          }));
        }

        if (data.type === 'alert') {
          const uid = data.alert_uid;

          // Deduplication: only handle each alert once
          if (uid && handledAlertUids.current.has(uid)) return;
          if (uid) handledAlertUids.current.add(uid);

          // Play alarm sound for 3 seconds (non-blocking)
          playAlarmSound();

          // Add to live alerts list
          setAlerts(prev => [data, ...prev.slice(0, 9)]);
          setKpis(prev => ({ ...prev, totalAlerts: prev.totalAlerts + 1 }));

          // Schedule a debounced refresh of DB alerts
          scheduleAlertRefresh();
        }

        if (data.type === 'status') {
          if (data.message === 'Stream started') setStreaming(true);
          if (data.message === 'Stream stopped') {
            setStreaming(false);
            setFrame(null);
            setDetections([]);
            setStatus('clear');
          }
        }
      };

      ws.onclose = () => {
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectRef.current);
      clearTimeout(alertRefreshTimer.current);
    };
  }, [scheduleAlertRefresh]);

  const handleToggleStream = async () => {
    try {
      if (streaming) {
        await stopStream();
        setStreaming(false);
      } else {
        await startStream();
        setStreaming(true);
      }
    } catch (err) {
      console.error('Stream toggle error:', err);
    }
  };

  const statusConfig = {
    fire: { label: 'FIRE DETECTED', className: 'fire', icon: <Flame size={16} /> },
    smoke: { label: 'SMOKE DETECTED', className: 'smoke', icon: <Wind size={16} /> },
    clear: { label: 'ALL CLEAR', className: 'clear', icon: <Shield size={16} /> },
  };

  const s = statusConfig[status];

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Real-time fire and smoke monitoring overview</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card fire">
          <div className="kpi-label">Fire Detections</div>
          <div className="kpi-value">{kpis.totalFire}</div>
          <div className="kpi-sub">Session total</div>
        </div>
        <div className="kpi-card smoke">
          <div className="kpi-label">Smoke Detections</div>
          <div className="kpi-value">{kpis.totalSmoke}</div>
          <div className="kpi-sub">Session total</div>
        </div>
        <div className="kpi-card safe">
          <div className="kpi-label">Alerts Triggered</div>
          <div className="kpi-value">{kpis.totalAlerts}</div>
          <div className="kpi-sub">Confirmed threats</div>
        </div>
        <div className="kpi-card info">
          <div className="kpi-label">Inference Latency</div>
          <div className="kpi-value">{stats.latency.toFixed(0)}<span style={{fontSize:'1rem',fontWeight:400}}>ms</span></div>
          <div className="kpi-sub">Frame #{stats.frameNumber}</div>
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid-2">
        {/* Live Feed */}
        <div>
          <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: 20 }}>
            <div style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Activity size={18} />
                <span style={{ fontWeight: 600 }}>Live Feed</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className={`status-badge ${s.className}`}>
                  <span className="status-dot" />
                  {s.icon} {s.label}
                </span>
                <button
                  id="stream-toggle"
                  className={`btn ${streaming ? 'btn-danger' : 'btn-primary'}`}
                  onClick={handleToggleStream}
                  style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                >
                  {streaming ? 'Stop' : 'Start'}
                </button>
              </div>
            </div>
            <div className="live-feed-container">
              {frame ? (
                <img src={frame} alt="Live detection feed" />
              ) : (
                <div className="empty-state">
                  <Activity size={48} />
                  <h3>No Feed Active</h3>
                  <p>Click "Start" to begin real-time detection</p>
                </div>
              )}
              {streaming && (
                <>
                  <div className="live-feed-overlay">
                    <div className="live-indicator">
                      <span className="dot" />
                      LIVE
                    </div>
                  </div>
                  <div className="feed-stats">
                    <div className="feed-stat">{stats.latency.toFixed(0)}ms</div>
                    <div className="feed-stat">Frame #{stats.frameNumber}</div>
                    <div className="feed-stat">{detections.length} detections</div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Current Detections */}
          {detections.length > 0 && (
            <div className="card">
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
                Current Frame Detections
              </h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Confidence</th>
                    <th>Position</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.map((d, i) => (
                    <tr key={i}>
                      <td><span className={`type-badge ${d.class_name}`}>{d.class_name}</span></td>
                      <td style={{ fontWeight: 600, color: d.confidence > 0.8 ? 'var(--accent-fire)' : 'var(--text-primary)' }}>
                        {(d.confidence * 100).toFixed(1)}%
                      </td>
                      <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                        ({d.bbox.x1.toFixed(0)}, {d.bbox.y1.toFixed(0)})
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right sidebar — Recent Alerts */}
        <div>
          <div className="card">
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Bell size={16} />
              Recent Alerts
            </h3>
            {alerts.length === 0 && recentAlerts.length === 0 ? (
              <div className="empty-state">
                <Shield size={32} />
                <h3>No Alerts</h3>
                <p>System is running normally</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {alerts.map((a, i) => (
                  <div key={a.alert_uid || `live-${i}`} className="card" style={{
                    padding: 12,
                    borderLeft: `3px solid ${a.class_name === 'fire' ? 'var(--accent-fire)' : 'var(--accent-smoke)'}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`type-badge ${a.class_name}`}>
                        {a.class_name === 'fire' ? <Flame size={12} /> : <Wind size={12} />}
                        {a.class_name}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {(a.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                      Duration: {a.duration_seconds?.toFixed(1)}s
                    </p>
                  </div>
                ))}
                {recentAlerts.map((a) => (
                  <div key={`db-${a.id}`} className="card" style={{ padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`status-pill ${a.notification_status}`}>
                        {a.notification_status}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {new Date(a.triggered_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Alert Toasts */}
      {alerts.length > 0 && alerts[0].timestamp > Date.now() / 1000 - 10 && (
        <div className="alert-toast">
          <h4>
            <AlertTriangle size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            {alerts[0].class_name.toUpperCase()} ALERT
          </h4>
          <p>
            Confidence: {(alerts[0].confidence * 100).toFixed(0)}% |
            Duration: {alerts[0].duration_seconds?.toFixed(1)}s
          </p>
        </div>
      )}
    </>
  );
}
