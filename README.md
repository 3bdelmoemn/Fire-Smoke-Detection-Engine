# 🔥 FireGuard AI — Fire & Smoke Detection System

Production-grade, YOLO-based real-time fire and smoke detection system with a FastAPI backend, React dashboard, and WhatsApp alert integration.

## Architecture

```
Frontend (React + Vite)  ←→  REST + WebSocket  ←→  FastAPI Backend
                                                        │
                    ┌───────────────────────────────────────┐
                    │                                       │
              InferenceService                    AlertDecisionEngine
              (YOLO wrapper)                     (temporal validation)
                    │                                       │
              Camera / Upload                    NotificationService
                                                  (WhatsApp / Console)
                    │                                       │
                 Storage                              Database
              (screenshots)                       (SQLite / Postgres)
```

## Quick Start (Local Development)

### 1. Backend

```bash
cd backend

# Create environment file
cp .env.example .env
# Edit .env — set MODEL_PATH to your trained weights

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### 3. Open the App

- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health

### 4. First-Time Setup

1. Register a user at the Login page
2. Sign in with your credentials
3. Navigate to **Dashboard** → click **Start** to begin live detection
4. Use **Upload** to analyze individual images/videos
5. Check **Evaluation** to review model performance metrics

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-Time Detection** | WebSocket-powered live camera feed with YOLO inference |
| **Temporal Validation** | Sliding-window algorithm prevents false positives |
| **Alert System** | Cooldown-based alerts with WhatsApp notification |
| **Upload Analysis** | Drag-and-drop image/video detection |
| **Model Evaluation** | Gallery of training metrics (F1, PR, confusion matrix) |
| **JWT Authentication** | Secure user registration and login |
| **Production-Ready** | Docker deployment, structured logging, health checks |

## Project Structure

```
fire-smoke-detection/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Route handlers
│   │   ├── core/            # Config, security, logging
│   │   ├── db/              # SQLAlchemy engine & session
│   │   ├── ml/              # YOLO model loader
│   │   ├── models/          # ORM models
│   │   ├── repositories/    # DB access layer
│   │   ├── schemas/         # Pydantic models
│   │   ├── services/        # Business logic
│   │   └── utils/           # File validation, annotation
│   ├── tests/               # Unit, API, integration tests
│   └── storage/             # Uploads, detections, logs
├── frontend/
│   └── src/
│       ├── pages/           # Login, Dashboard, Upload, Evaluation, Alerts
│       └── services/        # API client, WebSocket
└── docker-compose.yml
```

## Configuration

All settings are in `backend/.env`. Key values:

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_PATH` | Path to YOLO weights (.pt) | `../YOLOv8.../best.pt` |
| `CONFIDENCE_THRESHOLD` | Min detection confidence | `0.60` |
| `MIN_DETECTION_DURATION_SEC` | Seconds before alert | `3` |
| `ALERT_COOLDOWN_SEC` | Seconds between alerts | `60` |
| `CAMERA_SOURCE` | Webcam index or video path | Video file |
| `DATABASE_URL` | SQLite or PostgreSQL URL | SQLite |

## Testing

```bash
cd backend
pytest tests/ -v
```

## Docker Deployment

```bash
docker-compose up --build
```

## Tech Stack

- **Model**: YOLOv8s (Ultralytics) + PyTorch
- **Backend**: FastAPI + Uvicorn + SQLAlchemy + Alembic
- **Frontend**: React + Vite + Recharts + Lucide Icons
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Notifications**: WhatsApp Cloud API (pluggable)
- **Deployment**: Docker + docker-compose + nginx
