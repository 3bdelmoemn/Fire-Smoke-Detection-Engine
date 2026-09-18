import { useState, useRef } from 'react';
import { Upload, Image, Film, Check, AlertTriangle, Loader } from 'lucide-react';
import { detectImage, detectVideo } from '../services/api';

export default function UploadPage() {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const imageExts = ['.jpg', '.jpeg', '.png', '.bmp', '.webp'];
  const videoExts = ['.mp4', '.avi', '.mov', '.mkv'];

  const handleFile = (f) => {
    setFile(f);
    setResult(null);
    setError('');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      let data;
      if (imageExts.includes(ext)) {
        data = await detectImage(file);
      } else if (videoExts.includes(ext)) {
        data = await detectVideo(file);
      } else {
        throw new Error('Unsupported file format');
      }
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isImage = file && imageExts.includes('.' + file.name.split('.').pop().toLowerCase());
  const isVideo = file && videoExts.includes('.' + file.name.split('.').pop().toLowerCase());

  return (
    <>
      <div className="page-header">
        <h2>Upload & Detect</h2>
        <p>Upload an image or video for fire and smoke detection analysis</p>
      </div>

      {/* Upload Zone */}
      <div
        className={`upload-zone ${dragOver ? 'dragover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <Upload size={48} />
        <h3>Drop your file here or click to browse</h3>
        <p>Supports JPG, PNG, BMP, WebP, MP4, AVI, MOV, MKV (max 50MB)</p>
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.bmp,.webp,.mp4,.avi,.mov,.mkv"
          style={{ display: 'none' }}
          onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
        />
      </div>

      {/* Selected file */}
      {file && (
        <div className="card" style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {isImage ? <Image size={20} /> : <Film size={20} />}
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{file.name}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB · {isImage ? 'Image' : 'Video'}
              </div>
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleUpload} disabled={loading}>
            {loading ? <Loader size={16} className="spinner" /> : <><Check size={16} /> Analyze</>}
          </button>
        </div>
      )}

      {error && (
        <div className="card" style={{ marginTop: 16, borderColor: 'var(--accent-fire)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-fire)' }}>
            <AlertTriangle size={16} />
            <span style={{ fontWeight: 600 }}>{error}</span>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 16 }}>Detection Results</h3>

          <div className="kpi-grid">
            <div className="kpi-card fire">
              <div className="kpi-label">Fire Detections</div>
              <div className="kpi-value">{result.total_fire}</div>
            </div>
            <div className="kpi-card smoke">
              <div className="kpi-label">Smoke Detections</div>
              <div className="kpi-value">{result.total_smoke}</div>
            </div>
            <div className="kpi-card info">
              <div className="kpi-label">Processing Time</div>
              <div className="kpi-value">{(result.processing_time_ms / 1000).toFixed(2)}<span style={{fontSize:'0.9rem',fontWeight:400}}>s</span></div>
            </div>
          </div>

          {/* Annotated result */}
          {result.annotated_image_url && (
            <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: 20 }}>
              <img
                src={`http://localhost:8000${result.annotated_image_url}`}
                alt="Annotated detection result"
                style={{ width: '100%', display: 'block' }}
              />
            </div>
          )}

          {result.annotated_video_url && (
            <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: 20 }}>
              <video
                src={`http://localhost:8000${result.annotated_video_url}`}
                controls
                style={{ width: '100%', display: 'block' }}
              />
            </div>
          )}

          {/* Detection table */}
          {result.detections && result.detections.length > 0 && (
            <div className="card">
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
                Detailed Detections ({result.detections.length})
              </h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Confidence</th>
                    <th>Bounding Box</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.detections_summary || result.detections).slice(0, 20).map((d, i) => (
                    <tr key={i}>
                      <td><span className={`type-badge ${d.class_name}`}>{d.class_name}</span></td>
                      <td style={{ fontWeight: 600 }}>{(d.confidence * 100).toFixed(1)}%</td>
                      <td style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                        ({d.bbox.x1.toFixed(0)}, {d.bbox.y1.toFixed(0)}, {d.bbox.x2.toFixed(0)}, {d.bbox.y2.toFixed(0)})
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}
