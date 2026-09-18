import { useState, useEffect } from 'react';
import { getAlerts } from '../services/api';
import { Bell, AlertTriangle, Check, X, Loader } from 'lucide-react';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const perPage = 15;

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const data = await getAlerts(page, perPage);
      setAlerts(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAlerts(); }, [page, statusFilter]);

  const totalPages = Math.ceil(total / perPage);

  return (
    <>
      <div className="page-header">
        <h2>Alert History</h2>
        <p>All triggered alerts with notification delivery status</p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {['', 'sent', 'pending', 'failed'].map(s => (
          <button
            key={s}
            className={`btn ${statusFilter === s ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            style={{ padding: '8px 16px', fontSize: '0.8rem' }}
          >
            {s === '' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="loading-center"><div className="spinner" /></div>
        ) : alerts.length === 0 ? (
          <div className="empty-state">
            <Bell size={48} />
            <h3>No Alerts Yet</h3>
            <p>Alerts will appear here when fire or smoke is detected and confirmed</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Triggered At</th>
                <th>Event ID</th>
                <th>Status</th>
                <th>WhatsApp ID</th>
                <th>Screenshot</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600 }}>#{a.id}</td>
                  <td>{new Date(a.triggered_at).toLocaleString()}</td>
                  <td>#{a.detection_event_id}</td>
                  <td>
                    <span className={`status-pill ${a.notification_status}`}>
                      {a.notification_status === 'sent' && <Check size={12} />}
                      {a.notification_status === 'failed' && <X size={12} />}
                      {a.notification_status === 'pending' && <Loader size={12} />}
                      {a.notification_status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                    {a.whatsapp_message_id || '—'}
                  </td>
                  <td>
                    {a.screenshot_path ? (
                      <a href={`http://localhost:8000${a.screenshot_path}`} target="_blank" rel="noopener noreferrer"
                        style={{ fontSize: '0.8rem' }}>
                        View
                      </a>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 }}>
          <button className="btn btn-ghost" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
            Previous
          </button>
          <span style={{ display: 'flex', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Page {page} of {totalPages}
          </span>
          <button className="btn btn-ghost" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            Next
          </button>
        </div>
      )}
    </>
  );
}
