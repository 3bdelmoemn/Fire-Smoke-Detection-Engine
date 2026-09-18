"""
Logging configuration.

- **Development**: human-readable coloured console output.
- **Production**: structured JSON lines, rotating file handler.

Call ``setup_logging()`` once during app startup (in ``main.py``).
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(*, log_level: str = "INFO", log_dir: str = "./storage/logs") -> None:
    """Configure the root logger for the application."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any default handlers
    root.handlers.clear()

    # ── Console handler (human-readable) ─────────────────────────────
    console_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Force UTF-8 on Windows to prevent UnicodeEncodeError with special chars
    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass  # not available on all Python/OS combos
    console_handler = logging.StreamHandler(stream)
    console_handler.setFormatter(console_fmt)
    console_handler.setLevel(level)
    root.addHandler(console_handler)

    # ── Rotating file handler (JSON lines for production) ────────────
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    file_fmt = logging.Formatter(
        fmt='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "ultralytics"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialised  level=%s  file=%s", log_level, log_path / "app.log"
    )
