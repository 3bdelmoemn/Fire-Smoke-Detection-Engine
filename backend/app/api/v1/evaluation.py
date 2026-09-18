"""
Evaluation router — serves existing YOLO evaluation images.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_app_settings
from app.core.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])

# Known evaluation asset descriptions
ASSET_DESCRIPTIONS = {
    "hf-pretrained-results.png": "Training Results — loss and mAP curves over training epochs",
    "custom-results.png": "Training Results — loss and mAP curves over training epochs",
    "F1_curve.png": "F1-Confidence Curve — shows the F1 score at different confidence thresholds",
    "PR_curve.png": "Precision-Recall Curve — the trade-off between precision and recall",
    "P_curve.png": "Precision-Confidence Curve — precision at different confidence thresholds",
    "R_curve.png": "Recall-Confidence Curve — recall at different confidence thresholds",
    "confusion_matrix.png": "Confusion Matrix — classification accuracy per class",
    "val_batch0_pred.jpg": "Validation Predictions (Batch 0) — sample model predictions",
    "val_batch0_labels.jpg": "Validation Labels (Batch 0) — ground truth labels",
    "val_batch1_pred.jpg": "Validation Predictions (Batch 1) — sample model predictions",
    "val_batch1_labels.jpg": "Validation Labels (Batch 1) — ground truth labels",
    "val_batch2_pred.jpg": "Validation Predictions (Batch 2) — sample model predictions",
    "val_batch2_labels.jpg": "Validation Labels (Batch 2) — ground truth labels",
    "train_batch0.jpg": "Training Batch 0 — sample training images with augmentation",
    "train_batch1.jpg": "Training Batch 1 — sample training images with augmentation",
    "train_batch2.jpg": "Training Batch 2 — sample training images with augmentation",
}


def _discover_assets(eval_dir: Path) -> List[dict]:
    """Walk the eval directory and find all image assets."""
    assets = []
    image_exts = {".png", ".jpg", ".jpeg"}

    for subdir in ["train", "val"]:
        dir_path = eval_dir / subdir
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.iterdir()):
            if f.suffix.lower() in image_exts:
                assets.append({
                    "filename": f.name,
                    "category": subdir,
                    "description": ASSET_DESCRIPTIONS.get(f.name, f.stem.replace("_", " ").title()),
                    "path": str(f.resolve()),
                    "url": f"/api/v1/evaluation/assets/{subdir}/{f.name}",
                })
    return assets


@router.get("/assets")
async def list_evaluation_assets(settings: Settings = Depends(get_app_settings)):
    """List all available evaluation images (confusion matrix, PR curve, etc.)."""
    eval_dir = settings.eval_path
    if not eval_dir.exists():
        return {"assets": [], "message": "Evaluation directory not found"}

    assets = _discover_assets(eval_dir)
    return {
        "assets": assets,
        "total": len(assets),
        "categories": list(set(a["category"] for a in assets)),
    }


@router.get("/assets/{category}/{filename}")
async def get_evaluation_asset(
    category: str,
    filename: str,
    settings: Settings = Depends(get_app_settings),
):
    """Serve a specific evaluation image file."""
    filepath = settings.eval_path / category / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Asset not found")

    media_type = "image/png" if filepath.suffix == ".png" else "image/jpeg"
    return FileResponse(str(filepath), media_type=media_type)
