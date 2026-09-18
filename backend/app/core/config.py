"""
Centralized application settings.

All configuration flows through this single class. Values are read from
environment variables (or a `.env` file) and validated at startup by
pydantic-settings.  Nothing else in the codebase should read os.environ
directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Model ────────────────────────────────────────────────────────────
    MODEL_PATH: str = "./app/ml/weights/best.pt"
    CONFIDENCE_THRESHOLD: float = 0.60
    IOU_THRESHOLD: float = 0.45
    DEVICE: str = "cpu"

    # ── Temporal Validation ──────────────────────────────────────────────
    MIN_DETECTION_DURATION_SEC: int = 3
    MIN_CONSECUTIVE_FRAMES: int = 30
    DETECTION_RATIO_THRESHOLD: float = 0.8
    ALERT_COOLDOWN_SEC: int = 15

    # ── Auth ─────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_TO_A_RANDOM_SECRET_KEY"
    JWT_EXPIRE_MINUTES: int = 60

    # ── WhatsApp Notification ────────────────────────────────────────────
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_API_BASE: str = "https://www.wasenderapi.com/api"


    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/app.db"

    # ── Storage ──────────────────────────────────────────────────────────
    STORAGE_DIR: str = "./storage"
    EVAL_DIR: str = "./app/ml/eval/runs/detect"

    # ── Camera ───────────────────────────────────────────────────────────
    CAMERA_SOURCE: str = "0"
    CAMERA_FPS: int = 10
    FRAME_SKIP: int = 2

    # ── App ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    # ── Derived helpers ──────────────────────────────────────────────────
    @property
    def storage_path(self) -> Path:
        return Path(self.STORAGE_DIR)

    @property
    def uploads_path(self) -> Path:
        return self.storage_path / "uploads"

    @property
    def detections_path(self) -> Path:
        return self.storage_path / "detections"

    @property
    def eval_path(self) -> Path:
        return Path(self.EVAL_DIR)

    def ensure_directories(self) -> None:
        """Create required storage directories if they don't exist."""
        for d in [
            self.storage_path,
            self.uploads_path,
            self.detections_path,
            self.storage_path / "logs",
        ]:
            d.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Factory function; can be overridden in tests via dependency injection."""
    return Settings()
