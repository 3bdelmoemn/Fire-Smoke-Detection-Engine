import { useState, useEffect } from 'react';
import { getEvaluationAssets, getEvalAssetUrl } from '../services/api';
import { BarChart3, Loader } from 'lucide-react';

export default function EvaluationPage() {
  const [assets, setAssets] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState('all');
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);

  useEffect(() => {
    getEvaluationAssets()
      .then(data => {
        setAssets(data.assets || []);
        setCategories(data.categories || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = activeCategory === 'all'
    ? assets
    : assets.filter(a => a.category === activeCategory);

  if (loading) {
    return (
      <div className="loading-center">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h2>Model Evaluation</h2>
        <p>Training metrics, validation results, and performance curves for the YOLOv8s fire detection model</p>
      </div>

      {/* Category tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button
          className={`btn ${activeCategory === 'all' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveCategory('all')}
          style={{ padding: '8px 16px', fontSize: '0.8rem' }}
        >
          All ({assets.length})
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            className={`btn ${activeCategory === cat ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setActiveCategory(cat)}
            style={{ padding: '8px 16px', fontSize: '0.8rem' }}
          >
            {cat.charAt(0).toUpperCase() + cat.slice(1)} ({assets.filter(a => a.category === cat).length})
          </button>
        ))}
      </div>

      {/* Gallery */}
      <div className="eval-gallery">
        {filtered.map((asset, i) => (
          <div
            key={i}
            className="eval-card"
            onClick={() => setSelectedImage(asset)}
            style={{ cursor: 'pointer' }}
          >
            <img
              src={getEvalAssetUrl(asset.category, asset.filename)}
              alt={asset.description}
              loading="lazy"
            />
            <div className="eval-card-info">
              <h4>{asset.filename}</h4>
              <p>{asset.description}</p>
            </div>
          </div>
        ))}
      </div>

      {assets.length === 0 && (
        <div className="empty-state">
          <BarChart3 size={48} />
          <h3>No Evaluation Assets Found</h3>
          <p>Check that the EVAL_DIR path in .env points to your YOLO training runs directory</p>
        </div>
      )}

      {/* Full-screen image modal */}
      {selectedImage && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.9)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            cursor: 'pointer',
            padding: 40,
          }}
          onClick={() => setSelectedImage(null)}
        >
          <div style={{ maxWidth: '90vw', maxHeight: '90vh' }}>
            <img
              src={getEvalAssetUrl(selectedImage.category, selectedImage.filename)}
              alt={selectedImage.description}
              style={{ maxWidth: '100%', maxHeight: '85vh', borderRadius: 12 }}
            />
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{selectedImage.filename}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{selectedImage.description}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
