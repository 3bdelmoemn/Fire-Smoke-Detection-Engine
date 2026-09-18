"""
Singleton YOLO model loader.

Loads the weights file exactly once and caches the model in memory.
FastAPI's lifespan event calls ``load_model()`` at startup and stores
the result on ``app.state``.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_model(model_path: str, device: str = "cpu"):
    """
    Load a YOLO model from *model_path* onto *device*.

    Returns the ``ultralytics.YOLO`` model instance.  The ``@lru_cache``
    decorator guarantees this is called at most once per process.
    """
    from ultralytics import YOLO

    resolved = Path(model_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Model weights not found: {resolved}")

    logger.info("Loading YOLO model from %s onto %s …", resolved, device)
    model = YOLO(str(resolved))
    logger.info("Model loaded successfully — classes: %s", model.names)
    return model
